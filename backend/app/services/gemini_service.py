import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    retry_if_exception_message,
    stop_after_attempt,
    wait_exponential,
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    return "RESOURCE_EXHAUSTED" in msg or "UNAVAILABLE" in msg or "503" in msg or "429" in msg


def _normalise_llm_content(content: object) -> str:
    """
    Normalise provider-specific structured content into plain text.

    Gemini/LangChain can return a plain string, a list of chunks like
    {"type": "text", "text": "..."}, or nested dict/list payloads. We only
    ever expose plain markdown text to callers.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if isinstance(content.get("content"), str):
            return content["content"]
        parts = [_normalise_llm_content(v) for v in content.values()]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(content, list):
        parts = [_normalise_llm_content(item) for item in content]
        return "\n".join(part for part in parts if part).strip()
    return str(content)


@retry(
    retry=retry_if_exception_message(match=".*RESOURCE_EXHAUSTED.*|.*UNAVAILABLE.*|.*429.*|.*503.*"),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def generate_report(query: str, synthesis: str) -> str:
    """Generate a structured research report from an integrated synthesis.

    In the Level 4 multi-agent architecture the report is produced from the
    Synthesis agent's integrated output rather than from raw search results.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.7,
        max_retries=2,
    )

    context = synthesis.strip() if synthesis and synthesis.strip() else "No synthesis was produced."

    prompt = f"""You are an expert research analyst. Create a comprehensive, well-structured research report based on the following integrated research synthesis.

Research Topic: {query}

Research Synthesis:
{context}

Write a professional research report in Markdown format. Structure it with:
- A descriptive title as an H1 heading
- ## Executive Summary (2–3 paragraphs summarising the key points)
- ## Key Findings (bullet points with the most important discoveries)
- ## Detailed Analysis (multiple H3 subsections diving deep into the topic)
- ## Conclusion
- ## References (numbered list with titles and URLs)

Be thorough, cite sources where relevant, and provide genuine analytical value."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return _normalise_llm_content(response.content)
