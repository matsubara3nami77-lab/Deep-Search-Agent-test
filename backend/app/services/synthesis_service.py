import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    retry_if_exception_message,
    stop_after_attempt,
    wait_exponential,
)

from app.services.gemini_service import _normalise_llm_content


def _format_findings(findings: list[dict]) -> str:
    blocks: list[str] = []
    for f in findings:
        title = f.get("title", "Untitled task")
        summary = f.get("summary", "")
        sources = f.get("sources", [])
        src_lines = "\n".join(
            f"  - {s.get('title', 'Untitled')} ({s.get('url', '')})" for s in sources
        )
        block = f"### Task: {title}\n{summary}"
        if src_lines:
            block += f"\nSources:\n{src_lines}"
        blocks.append(block)
    return "\n\n".join(blocks) if blocks else "No findings were produced."


@retry(
    retry=retry_if_exception_message(match=".*RESOURCE_EXHAUSTED.*|.*UNAVAILABLE.*|.*429.*|.*503.*"),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def synthesize(query: str, findings: list[dict]) -> str:
    """
    Merge the independent worker findings into a single coherent synthesis.

    Resolves overlaps, removes duplication, and arranges the material into a logical
    structure that the report generator can turn into a final document. Returns an
    intermediate structured synthesis (not the final user-facing report).
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.5,
        max_retries=2,
    )

    # Stable ordering by task id keeps the synthesis deterministic across runs.
    ordered = sorted(findings, key=lambda f: (f.get("task_id") is None, f.get("task_id", 0)))

    prompt = f"""You are a research Synthesis agent. Several independent research workers each
investigated one sub-task of a larger topic. Merge their findings into a single coherent,
non-redundant synthesis.

Overall research topic: {query}

Worker findings:
{_format_findings(ordered)}

Instructions:
- Integrate the findings into one logically structured synthesis.
- Resolve and merge overlapping points; remove duplication.
- Preserve concrete facts and their sources.
- Organise the material into clear thematic sections with short headings.
- This is an intermediate synthesis for a report writer, not the final report — focus on
  completeness and structure, not polish.

Return the synthesis as structured markdown."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return _normalise_llm_content(response.content)
