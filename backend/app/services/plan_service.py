import json
import os
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.gemini_service import _normalise_llm_content

DEFAULT_PLAN = [
    "Define the research scope and key questions",
    "Search the web for relevant sources",
    "Analyze and synthesize the findings",
    "Generate the research report",
]


def _parse_json_array(text: str) -> list[str] | None:
    """Extract a JSON array of strings from an LLM response."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    steps = [str(item).strip() for item in data if str(item).strip()]
    return steps or None


async def generate_plan(
    query: str,
    edit_instruction: str | None = None,
    previous_plan: list[str] | None = None,
) -> list[str]:
    """
    Generate (or regenerate) a structured research plan.

    When `edit_instruction` and `previous_plan` are provided, the plan is fully
    regenerated according to the natural-language instruction (regeneration-based
    editing — no manual step edits).
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.4,
        max_retries=2,
    )

    prompt = f"""You are a research planner. Create a concise, step-by-step RESEARCH plan
for the topic below. The plan MUST have EXACTLY 4 steps that follow this pipeline:
1) define scope, 2) search sources, 3) analyze findings, 4) generate report.
Do NOT include a "save report" step — saving is handled separately after the report
is produced. Tailor each step's wording to the specific topic.

Research Topic: {query}
"""

    if edit_instruction and previous_plan:
        prompt += f"""
The user reviewed the previous plan and asked for changes.

Previous plan:
{chr(10).join(f"{i}. {step}" for i, step in enumerate(previous_plan, 1))}

Revision instruction: {edit_instruction}

Regenerate the FULL plan (still exactly 4 steps, no save step) incorporating this instruction.
"""

    prompt += """
Return ONLY a JSON array of exactly 4 short strings (one per step). No extra text."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = _normalise_llm_content(response.content)
        steps = _parse_json_array(text)
        if steps:
            return steps[:4] if len(steps) > 4 else steps
    except Exception:
        pass

    return list(DEFAULT_PLAN)
