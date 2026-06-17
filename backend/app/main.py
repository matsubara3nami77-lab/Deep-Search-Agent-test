import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from langgraph.types import Command  # noqa: E402

from app.graph.research_graph import create_research_graph  # noqa: E402

# ---------------------------------------------------------------------------
# Single compiled graph instance (shared MemorySaver checkpointer lives here)
# ---------------------------------------------------------------------------
_graph = create_research_graph()

# ---------------------------------------------------------------------------
# In-memory session store: execution_id -> {"thread_id": str}
# An entry exists while a research session is paused at an interrupt.
# ---------------------------------------------------------------------------
_sessions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Deep Research Agent API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    query: str
    mode: str = "todo"  # "todo" | "plan"


class ContinueRequest(BaseModel):
    execution_id: str
    resume: Any  # bool | str | dict — interpreted by the paused interrupt node


# ---------------------------------------------------------------------------
# Plain-text / SSE contract helpers
# ---------------------------------------------------------------------------

def _as_text(value: object) -> str:
    """Coerce any value to a plain string for SSE/UI contracts."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return str(value)


def _as_text_list(value: object) -> list[str]:
    """Coerce a value into a list of plain strings."""
    if isinstance(value, list):
        return [_as_text(item) for item in value]
    return []


def sse(data: dict) -> str:
    payload = dict(data)
    for key in ("type", "message", "content", "execution_id", "target"):
        if key in payload:
            payload[key] = _as_text(payload[key])
    if "options" in payload:
        payload["options"] = _as_text_list(payload["options"])
    if "plan" in payload:
        payload["plan"] = _as_text_list(payload["plan"])
    return f"data: {json.dumps(payload)}\n\n"


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)

    if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower():
        return (
            "The AI model has reached its rate limit. "
            "Please wait a minute and try again, or check your API quota at https://ai.dev/rate-limit."
        )
    if "INVALID_ARGUMENT" in msg or "400" in msg:
        return "The request was invalid. Please try rephrasing your query."
    if "PERMISSION_DENIED" in msg or "403" in msg or "API key" in msg.lower():
        return "API key error: please check your GEMINI_API_KEY is set correctly."
    if "UNAVAILABLE" in msg or "503" in msg:
        return "The AI service is temporarily unavailable. Please try again in a moment."
    if "tavily" in msg.lower() or "TAVILY" in msg:
        return "Web search failed. Please check your TAVILY_API_KEY and try again."
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "The request timed out. Please try again."

    return "Something went wrong while processing your request. Please try again."


# ---------------------------------------------------------------------------
# Shared graph streaming — used by both /api/research and /api/research/continue
# ---------------------------------------------------------------------------

async def _stream_graph(execution_id: str, graph_input: Any, mode: str):
    """
    Drive the graph, translating LangGraph chunks into SSE events.

    Stops (returns) at the first interrupt, leaving the session registered so it
    can be resumed via /api/research/continue. On full completion it emits the
    final report/status and a `done` event, then removes the session.
    """
    config = {"configurable": {"thread_id": _sessions[execution_id]["thread_id"]}}
    current_state: dict = {}

    try:
        async for chunk in _graph.astream(graph_input, config=config):
            # --- Interrupt: pause for human input ---
            if "__interrupt__" in chunk:
                payload = chunk["__interrupt__"][0].value or {}
                kind = payload.get("kind")

                if kind == "clarification":
                    yield sse(
                        {
                            "type": "clarification_required",
                            "execution_id": execution_id,
                            "message": payload.get("question", ""),
                            "options": payload.get("options", []),
                        }
                    )
                elif kind == "plan_review":
                    yield sse(
                        {
                            "type": "plan_review",
                            "execution_id": execution_id,
                            "plan": payload.get("plan", []),
                        }
                    )
                elif kind == "approval":
                    yield sse({"type": "report", "content": _as_text(current_state.get("report", ""))})
                    if mode == "plan":
                        total = len(current_state.get("plan", [])) or 4
                        yield sse({"type": "plan_progress", "completed": total, "total": total})
                    yield sse(
                        {
                            "type": "approval_required",
                            "execution_id": execution_id,
                            "message": "Report generated. Do you want to save it to disk?",
                        }
                    )
                return

            # --- Normal node outputs: emit status / progress ---
            for node_name, node_output in chunk.items():
                if node_name.startswith("__") or not isinstance(node_output, dict):
                    continue
                current_state.update(node_output)

                if node_name == "intent" and current_state.get("intent") == "mode_switch":
                    yield sse(
                        {
                            "type": "mode_switch",
                            "target": current_state.get("mode_target", "todo"),
                            "message": current_state.get("chat_answer", ""),
                        }
                    )
                elif node_name == "intent" and current_state.get("intent") == "chat":
                    yield sse({"type": "chat", "content": current_state.get("chat_answer", "")})
                elif node_name == "plan":
                    yield sse({"type": "status", "message": "Plan ready for your review."})
                elif node_name == "search":
                    count = len(current_state.get("search_results", []))
                    yield sse(
                        {
                            "type": "status",
                            "message": f"Found {count} sources. Generating report with Gemini...",
                        }
                    )
                    if mode == "plan":
                        total = len(current_state.get("plan", [])) or 4
                        yield sse({"type": "plan_progress", "completed": 2, "total": total})
                elif node_name == "generate":
                    yield sse({"type": "status", "message": "Report generated."})
                    if mode == "plan":
                        total = len(current_state.get("plan", [])) or 4
                        yield sse({"type": "plan_progress", "completed": total, "total": total})

        # --- Graph finished (no further interrupt) ---
        report_path = current_state.get("report_path", "")
        if report_path:
            yield sse({"type": "status", "message": f"Report saved to {report_path}"})
        elif current_state.get("save_approved") is False:
            yield sse({"type": "status", "message": "Save skipped."})

        yield sse({"type": "done"})
        _sessions.pop(execution_id, None)

    except Exception as exc:
        _sessions.pop(execution_id, None)
        yield sse({"type": "error", "message": _friendly_error(exc)})


def _stream_response(generator) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/research — start a new research session
# ---------------------------------------------------------------------------

@app.post("/api/research")
async def research(request: ResearchRequest):
    execution_id = str(uuid.uuid4())
    _sessions[execution_id] = {"thread_id": execution_id}

    mode = request.mode if request.mode in ("todo", "plan") else "todo"
    graph_input = {"query": request.query, "mode": mode, "current_step": 0}

    return _stream_response(_stream_graph(execution_id, graph_input, mode))


# ---------------------------------------------------------------------------
# POST /api/research/continue — resume a paused session
# Used for: clarification answer, plan start, plan regeneration, save approval
# ---------------------------------------------------------------------------

@app.post("/api/research/continue")
async def continue_research(request: ContinueRequest):
    session = _sessions.get(request.execution_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Execution not found or already resolved.")

    # Recover the mode from the checkpointed state so progress events stay correct.
    config = {"configurable": {"thread_id": session["thread_id"]}}
    mode = "todo"
    try:
        snapshot = _graph.get_state(config)
        mode = (snapshot.values.get("mode") if snapshot and snapshot.values else "todo") or "todo"
    except Exception:
        mode = "todo"

    return _stream_response(
        _stream_graph(request.execution_id, Command(resume=request.resume), mode)
    )


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}
