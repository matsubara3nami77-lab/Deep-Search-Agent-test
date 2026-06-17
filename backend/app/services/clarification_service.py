import json
import os
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.gemini_service import _normalise_llm_content


def _parse_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


async def detect_clarification(query: str) -> dict:
    """
    Decide whether a research query is too ambiguous to execute reliably.

    Returns:
        {"needs": False}
        or
        {"needs": True, "question": "...", "options": ["...", "...", "..."]}

    This is intentionally conservative: on any failure it returns {"needs": False}
    so it never blocks execution.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.2,
        max_retries=1,
    )

    prompt = f"""You are triaging a research request. Decide if the query is ambiguous,
underspecified, or too broad to research reliably WITHOUT a follow-up question.

Query: "{query}"

If the query is clear and specific enough, respond with:
{{"needs_clarification": false}}

If it is genuinely ambiguous, respond with:
{{"needs_clarification": true,
  "question": "A short clarifying question",
  "options": ["Distinct interpretation A", "Distinct interpretation B", "Distinct interpretation C"]}}

Rules:
- Only ask for clarification when truly necessary.
- Provide 2-4 concise, mutually distinct options.
- Return ONLY the JSON object, no extra text."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = _normalise_llm_content(response.content)
        data = _parse_json_object(text)
        if not data or not data.get("needs_clarification"):
            return {"needs": False}

        question = str(data.get("question", "")).strip()
        options = [str(o).strip() for o in data.get("options", []) if str(o).strip()]
        if not question or len(options) < 2:
            return {"needs": False}

        return {"needs": True, "question": question, "options": options[:4]}
    except Exception:
        return {"needs": False}
