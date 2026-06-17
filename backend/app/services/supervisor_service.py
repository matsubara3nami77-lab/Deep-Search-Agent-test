import json
import os
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.gemini_service import _normalise_llm_content

MIN_TASKS = 3
MAX_TASKS = 6


def _fallback_tasks(query: str) -> list[dict]:
    """A safe, generic decomposition used when the LLM call fails or is unparseable."""
    return [
        {"id": 1, "title": f"Background and core concepts of {query}", "query": f"{query} overview background"},
        {"id": 2, "title": f"Current state and key developments of {query}", "query": f"{query} latest developments"},
        {"id": 3, "title": f"Challenges, debates, and future outlook of {query}", "query": f"{query} challenges future outlook"},
    ]


def _parse_json_array(text: str) -> list | None:
    """Extract a JSON array from an LLM response (tolerant of code fences)."""
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
    return data if isinstance(data, list) else None


def _normalise_tasks(raw: list, query: str) -> list[dict]:
    """Coerce raw LLM items into well-formed task dicts with stable ids."""
    tasks: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("task") or "").strip()
            search = str(item.get("query") or item.get("search") or title).strip()
        else:
            title = str(item).strip()
            search = title
        if not title:
            continue
        tasks.append({"id": len(tasks) + 1, "title": title, "query": search or title})
        if len(tasks) >= MAX_TASKS:
            break
    return tasks


async def decompose(
    query: str,
    edit_instruction: str | None = None,
    previous_tasks: list[dict] | None = None,
) -> list[dict]:
    """
    Decompose an arbitrary research query into independent, parallelizable tasks.

    The decomposition is fully dynamic: there are NO fixed categories or domain
    roles. Each task is a self-contained research angle that a stateless worker can
    execute on its own.

    When `edit_instruction` and `previous_tasks` are supplied, the task list is
    regenerated according to the natural-language instruction (used by Plan Mode).

    On any failure it returns a generic 3-task fallback so execution is never blocked.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.4,
        max_retries=2,
    )

    prompt = f"""You are a research Supervisor. Decompose the user's research topic into
between {MIN_TASKS} and {MAX_TASKS} INDEPENDENT sub-tasks that can be researched in
parallel by identical, stateless research workers.

Research Topic: {query}

Hard rules:
- Tasks MUST be derived dynamically from THIS specific topic.
- Do NOT use generic fixed buckets or domain roles (e.g. "market", "technology",
  "open-source", "competitors"). Tailor every task to the actual topic.
- Tasks MUST be mutually distinct and non-overlapping so workers do not duplicate work.
- Each task must be self-contained (a worker sees only its own task, not the others).
- For each task provide a short human-readable "title" and an effective web-search
  "query" string.
"""

    if edit_instruction and previous_tasks:
        prev = "\n".join(f"{t['id']}. {t['title']}" for t in previous_tasks)
        prompt += f"""
The user reviewed the previous decomposition and requested changes.

Previous tasks:
{prev}

Revision instruction: {edit_instruction}

Regenerate the FULL task list incorporating this instruction (still {MIN_TASKS}-{MAX_TASKS}
distinct, non-overlapping tasks).
"""

    prompt += f"""
Return ONLY a JSON array of objects, each shaped exactly like:
{{"title": "short task title", "query": "web search query"}}
Return between {MIN_TASKS} and {MAX_TASKS} objects. No extra text."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = _normalise_llm_content(response.content)
        raw = _parse_json_array(text)
        if raw:
            tasks = _normalise_tasks(raw, query)
            if len(tasks) >= 1:
                return tasks
    except Exception:
        pass

    return _fallback_tasks(query)
