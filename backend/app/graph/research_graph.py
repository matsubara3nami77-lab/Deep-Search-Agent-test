from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.services.clarification_service import detect_clarification
from app.services.gemini_service import generate_report
from app.services.intent_service import classify_intent
from app.services.plan_service import generate_plan
from app.tools.save_report_tool import save_report
from app.tools.search_tool import search_web


class ResearchState(TypedDict, total=False):
    query: str
    mode: str  # "todo" | "plan"
    intent: str  # "research" | "chat" | "mode_switch"
    chat_answer: str
    mode_target: str
    refined_query: str
    search_results: list[dict]
    report: str
    report_path: str
    save_approved: bool
    plan: list[str]
    edit_instruction: Optional[str]
    needs_clarification: bool
    clarification: dict
    current_step: int


# ---------------------------------------------------------------------------
# Intent (research vs. conversational/meta) — runs before any research work
# ---------------------------------------------------------------------------

async def intent_node(state: ResearchState) -> dict:
    result = await classify_intent(state["query"])
    kind = result.get("kind")
    if kind == "mode_switch":
        return {
            "intent": "mode_switch",
            "mode_target": result.get("target", "todo"),
            "chat_answer": result.get("answer", ""),
        }
    if kind == "chat":
        return {"intent": "chat", "chat_answer": result.get("answer", "")}
    return {"intent": "research"}


# ---------------------------------------------------------------------------
# Clarification (independent of plan mode)
# ---------------------------------------------------------------------------

async def clarify_check_node(state: ResearchState) -> dict:
    result = await detect_clarification(state["query"])
    if result.get("needs"):
        return {
            "needs_clarification": True,
            "clarification": {
                "question": result["question"],
                "options": result["options"],
            },
        }
    return {"needs_clarification": False}


async def clarification_node(state: ResearchState) -> dict:
    """Pause and ask the user to disambiguate. Resume value is the chosen answer."""
    answer = interrupt(
        {
            "kind": "clarification",
            "question": state["clarification"]["question"],
            "options": state["clarification"]["options"],
        }
    )
    refined = f'{state["query"]} (focus: {answer})'
    return {"refined_query": refined, "needs_clarification": False}


# ---------------------------------------------------------------------------
# Plan mode (regeneration-based editing)
# ---------------------------------------------------------------------------

async def plan_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    plan = await generate_plan(
        query,
        edit_instruction=state.get("edit_instruction"),
        previous_plan=state.get("plan"),
    )
    return {"plan": plan, "edit_instruction": None}


async def plan_review_node(state: ResearchState) -> dict:
    """
    Pause to show the plan. Resume value is either:
      {"action": "start"}                        -> begin execution
      {"action": "edit", "instruction": "..."}   -> regenerate plan
    """
    decision = interrupt({"kind": "plan_review", "plan": state["plan"]})
    if isinstance(decision, dict) and decision.get("action") == "edit":
        return {"edit_instruction": decision.get("instruction") or ""}
    return {"edit_instruction": None}


# ---------------------------------------------------------------------------
# Execution pipeline (shared by both modes)
# ---------------------------------------------------------------------------

async def search_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    results = await search_web(query)
    return {"search_results": results, "current_step": 2}


async def generate_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    report = await generate_report(query, state["search_results"])
    return {"report": report, "current_step": 4}


async def approval_node(state: ResearchState) -> dict:
    """Level 2 HITL: pause before saving. Resume value is a bool."""
    approved = interrupt({"kind": "approval"})
    return {"save_approved": bool(approved)}


async def save_node(state: ResearchState) -> dict:
    if state.get("save_approved"):
        path = await save_report(state["report"])
        return {"report_path": path, "current_step": 5}
    return {"report_path": "", "current_step": 5}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

def _route_after_intent(state: ResearchState) -> str:
    if state.get("intent") in ("chat", "mode_switch"):
        return END
    return "clarify_check"


def _route_after_clarify_check(state: ResearchState) -> str:
    if state.get("needs_clarification"):
        return "clarification"
    return "plan" if state.get("mode") == "plan" else "search"


def _route_after_clarification(state: ResearchState) -> str:
    return "plan" if state.get("mode") == "plan" else "search"


def _route_after_plan_review(state: ResearchState) -> str:
    # If the user asked to edit, loop back and regenerate the plan.
    return "plan" if state.get("edit_instruction") else "search"


def _route_after_approval(state: ResearchState) -> str:
    return "save" if state.get("save_approved") else END


def create_research_graph():
    """Build and compile the Level 3 research graph (todo/plan + clarification + HITL)."""
    checkpointer = MemorySaver()
    workflow: StateGraph = StateGraph(ResearchState)

    workflow.add_node("intent", intent_node)
    workflow.add_node("clarify_check", clarify_check_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("plan_review", plan_review_node)
    workflow.add_node("search", search_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("approval", approval_node)
    workflow.add_node("save", save_node)

    workflow.add_edge(START, "intent")
    workflow.add_conditional_edges("intent", _route_after_intent, ["clarify_check", END])
    workflow.add_conditional_edges(
        "clarify_check", _route_after_clarify_check, ["clarification", "plan", "search"]
    )
    workflow.add_conditional_edges(
        "clarification", _route_after_clarification, ["plan", "search"]
    )
    workflow.add_edge("plan", "plan_review")
    workflow.add_conditional_edges(
        "plan_review", _route_after_plan_review, ["plan", "search"]
    )
    workflow.add_edge("search", "generate")
    workflow.add_edge("generate", "approval")
    workflow.add_conditional_edges("approval", _route_after_approval, ["save", END])
    workflow.add_edge("save", END)

    return workflow.compile(checkpointer=checkpointer)
