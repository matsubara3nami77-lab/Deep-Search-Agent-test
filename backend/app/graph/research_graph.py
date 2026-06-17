from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.services.gemini_service import generate_report
from app.tools.save_report_tool import save_report
from app.tools.search_tool import search_web


class ResearchState(TypedDict):
    query: str
    search_results: list[dict]
    report: str
    report_path: str
    save_approved: bool


async def search_node(state: ResearchState) -> dict:
    results = await search_web(state["query"])
    return {"search_results": results}


async def generate_node(state: ResearchState) -> dict:
    report = await generate_report(state["query"], state["search_results"])
    return {"report": report}


async def approval_node(state: ResearchState) -> dict:
    """Pause execution here and ask the human whether to save the report."""
    approved: bool = interrupt(
        {
            "pending_action": "save_report",
            "message": "Report generated. Do you want to save it to disk?",
        }
    )
    return {"save_approved": approved}


async def save_node(state: ResearchState) -> dict:
    if state.get("save_approved"):
        path = await save_report(state["report"])
        return {"report_path": path}
    return {"report_path": ""}


def _route_after_approval(state: ResearchState) -> str:
    return "save" if state.get("save_approved") else END


def create_research_graph():
    """Build and compile the research LangGraph with HITL interrupt before save."""
    checkpointer = MemorySaver()
    workflow: StateGraph = StateGraph(ResearchState)

    workflow.add_node("search", search_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("approval", approval_node)
    workflow.add_node("save", save_node)

    workflow.add_edge(START, "search")
    workflow.add_edge("search", "generate")
    workflow.add_edge("generate", "approval")
    workflow.add_conditional_edges("approval", _route_after_approval, ["save", END])
    workflow.add_edge("save", END)

    return workflow.compile(checkpointer=checkpointer)
