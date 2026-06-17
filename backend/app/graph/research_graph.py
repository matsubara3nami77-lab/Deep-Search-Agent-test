from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.gemini_service import generate_report
from app.tools.save_report_tool import save_report
from app.tools.search_tool import search_web


class ResearchState(TypedDict):
    query: str
    search_results: list[dict]
    report: str
    report_path: str


async def search_node(state: ResearchState) -> dict:
    results = await search_web(state["query"])
    return {"search_results": results}


async def generate_node(state: ResearchState) -> dict:
    report = await generate_report(state["query"], state["search_results"])
    return {"report": report}


async def save_node(state: ResearchState) -> dict:
    path = await save_report(state["report"])
    return {"report_path": path}


def create_research_graph():
    """Build and compile the sequential research LangGraph."""
    workflow: StateGraph = StateGraph(ResearchState)

    workflow.add_node("search", search_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("save", save_node)

    workflow.add_edge(START, "search")
    workflow.add_edge("search", "generate")
    workflow.add_edge("generate", "save")
    workflow.add_edge("save", END)

    return workflow.compile()
