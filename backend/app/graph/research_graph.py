import operator
from typing import Annotated, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from app.services.clarification_service import detect_clarification
from app.services.gemini_service import generate_report
from app.services.intent_service import classify_intent
from app.services.supervisor_service import decompose
from app.services.synthesis_service import synthesize
from app.services.worker_service import run_task
from app.tools.save_report_tool import save_report


class ResearchState(TypedDict, total=False):
    query: str
    mode: str  # "todo" | "plan"
    intent: str  # "research" | "chat" | "mode_switch"
    chat_answer: str
    mode_target: str
    refined_query: str
    # --- Level 4 multi-agent fields ---
    tasks: list[dict]  # Supervisor decomposition: [{"id", "title", "query"}]
    findings: Annotated[list[dict], operator.add]  # fan-in accumulator (parallel workers)
    synthesis: str  # integrated synthesis from the Synthesis agent
    # --- Report + persistence ---
    report: str
    report_path: str
    save_approved: bool
    # --- Plan-mode review (reuses task titles) ---
    plan: list[str]
    edit_instruction: Optional[str]
    # --- Clarification ---
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
# Supervisor — dynamic task decomposition (no hardcoded roles)
# ---------------------------------------------------------------------------

async def supervisor_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    tasks = await decompose(
        query,
        edit_instruction=state.get("edit_instruction"),
        previous_tasks=state.get("tasks"),
    )
    return {
        "tasks": tasks,
        "plan": [t["title"] for t in tasks],
        "edit_instruction": None,
        "current_step": 1,
    }


async def task_review_node(state: ResearchState) -> dict:
    """
    Plan-mode pause: show the decomposed tasks for review. Resume value is either:
      {"action": "start"}                        -> begin parallel execution
      {"action": "edit", "instruction": "..."}   -> re-run the Supervisor
    """
    decision = interrupt({"kind": "plan_review", "plan": state["plan"]})
    if isinstance(decision, dict) and decision.get("action") == "edit":
        return {"edit_instruction": decision.get("instruction") or ""}
    return {"edit_instruction": None}


# ---------------------------------------------------------------------------
# Research Worker — stateless, identical units executed in parallel via Send
# ---------------------------------------------------------------------------

async def worker_node(state: ResearchState) -> dict:
    task = state["task"]  # injected per-Send payload
    finding = await run_task(task)
    return {"findings": [finding]}


# ---------------------------------------------------------------------------
# Synthesis — merge all worker findings into a coherent whole (fan-in)
# ---------------------------------------------------------------------------

async def synthesis_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    synthesis = await synthesize(query, state.get("findings", []))
    return {"synthesis": synthesis, "current_step": 2}


# ---------------------------------------------------------------------------
# Report — turn the synthesis into a user-facing markdown document
# ---------------------------------------------------------------------------

async def report_node(state: ResearchState) -> dict:
    query = state.get("refined_query") or state["query"]
    report = await generate_report(query, state.get("synthesis", ""))
    return {"report": report, "current_step": 4}


# ---------------------------------------------------------------------------
# HITL approval + save (Level 2, unchanged)
# ---------------------------------------------------------------------------

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

def _fan_out(state: ResearchState) -> list[Send]:
    """Fan out: one parallel worker per decomposed task."""
    return [Send("worker", {"task": task}) for task in state.get("tasks", [])]


def _route_after_intent(state: ResearchState) -> str:
    if state.get("intent") in ("chat", "mode_switch"):
        return END
    return "clarify_check"


def _route_after_clarify_check(state: ResearchState) -> str:
    if state.get("needs_clarification"):
        return "clarification"
    return "supervisor"


def _route_after_supervisor(state: ResearchState):
    # Plan mode pauses for review; todo mode fans out immediately.
    if state.get("mode") == "plan":
        return "task_review"
    return _fan_out(state)


def _route_after_task_review(state: ResearchState):
    # If the user asked to edit, loop back and re-decompose.
    if state.get("edit_instruction"):
        return "supervisor"
    return _fan_out(state)


def _route_after_approval(state: ResearchState) -> str:
    return "save" if state.get("save_approved") else END


def create_research_graph():
    """Build and compile the Level 4 multi-agent research graph."""
    checkpointer = MemorySaver()
    workflow: StateGraph = StateGraph(ResearchState)

    workflow.add_node("intent", intent_node)
    workflow.add_node("clarify_check", clarify_check_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("task_review", task_review_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("report", report_node)
    workflow.add_node("approval", approval_node)
    workflow.add_node("save", save_node)

    workflow.add_edge(START, "intent")
    workflow.add_conditional_edges("intent", _route_after_intent, ["clarify_check", END])
    workflow.add_conditional_edges(
        "clarify_check", _route_after_clarify_check, ["clarification", "supervisor"]
    )
    workflow.add_edge("clarification", "supervisor")
    workflow.add_conditional_edges(
        "supervisor", _route_after_supervisor, ["task_review", "worker"]
    )
    workflow.add_conditional_edges(
        "task_review", _route_after_task_review, ["supervisor", "worker"]
    )
    # Fan-in: synthesis runs once after all parallel workers in the superstep finish.
    workflow.add_edge("worker", "synthesis")
    workflow.add_edge("synthesis", "report")
    workflow.add_edge("report", "approval")
    workflow.add_conditional_edges("approval", _route_after_approval, ["save", END])
    workflow.add_edge("save", END)

    return workflow.compile(checkpointer=checkpointer)
