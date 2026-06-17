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
from app.tools.search_tool import search_web


@retry(
    retry=retry_if_exception_message(match=".*RESOURCE_EXHAUSTED.*|.*UNAVAILABLE.*|.*429.*|.*503.*"),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _extract(task: dict, sources: list[dict]) -> str:
    """Use Gemini to extract structured findings for a single task from its sources."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.3,
        max_retries=2,
    )

    context_parts: list[str] = []
    for i, src in enumerate(sources, 1):
        title = src.get("title", "Untitled")
        url = src.get("url", "")
        content = src.get("content", "")
        context_parts.append(f"[{i}] {title}\nURL: {url}\n{content}")
    context = "\n\n".join(context_parts) if context_parts else "No search results were found."

    prompt = f"""You are a focused research worker. You are responsible for EXACTLY ONE
research task. Extract and summarize only the information relevant to your task from the
web search results below. Be factual and concise; do not speculate beyond the sources.

Your task: {task['title']}

Web search results:
{context}

Write a tight, information-dense summary (3-6 short paragraphs or a bulleted list) of the
key findings for THIS task only. Do not add a preamble or restate the task."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return _normalise_llm_content(response.content)


async def run_task(task: dict) -> dict:
    """
    Execute a single research task: web search + LLM extraction.

    Stateless: it only sees its own task. Errors are caught and returned as a finding
    with an error note so a single failing worker never aborts the synthesis stage.

    Returns a finding shaped like:
        {"task_id": int, "title": str, "summary": str, "sources": [{title, url}], "ok": bool}
    """
    task_id = task.get("id")
    title = task.get("title", "")
    search_query = task.get("query") or title

    try:
        results = await search_web(search_query)
        sources = [
            {"title": r.get("title", "Untitled"), "url": r.get("url", "")}
            for r in results
        ]
        summary = await _extract(task, results)
        return {
            "task_id": task_id,
            "title": title,
            "summary": summary,
            "sources": sources,
            "ok": True,
        }
    except Exception as exc:  # graceful degradation
        return {
            "task_id": task_id,
            "title": title,
            "summary": f"This task could not be completed due to an error: {exc}",
            "sources": [],
            "ok": False,
        }
