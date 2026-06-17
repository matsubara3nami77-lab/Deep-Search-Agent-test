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
# In-memory execution store
# Maps execution_id -> {"thread_id": str, "report": str}
# Entries are created when the graph pauses for approval and removed on resume.
# ---------------------------------------------------------------------------
_pending_executions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Deep Research Agent API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    query: str


class ApproveRequest(BaseModel):
    execution_id: str
    approved: bool


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Error sanitiser – converts raw exception messages into user-friendly text
# ---------------------------------------------------------------------------

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

    # Generic fallback — hide internal details
    return "Something went wrong while processing your request. Please try again."


# ---------------------------------------------------------------------------
# POST /api/research  – run until approval interrupt
# ---------------------------------------------------------------------------

@app.post("/api/research")
async def research(request: ResearchRequest):
    """
    Stream research progress via SSE.

    Events:
      {"type": "status",            "message": "..."}
      {"type": "report",            "content": "...markdown..."}
      {"type": "approval_required", "execution_id": "...", "message": "..."}
      {"type": "error",             "message": "..."}
    """

    execution_id = str(uuid.uuid4())
    thread_id = execution_id          # use same id as LangGraph thread key
    config = {"configurable": {"thread_id": thread_id}}

    async def generate():
        yield sse({"type": "status", "message": "Searching the web..."})

        current_state: dict = {}

        try:
            async for chunk in _graph.astream(
                {"query": request.query},
                config=config,
            ):
                # LangGraph emits {"__interrupt__": [...]} when paused
                if "__interrupt__" in chunk:
                    report = current_state.get("report", "")
                    _pending_executions[execution_id] = {
                        "thread_id": thread_id,
                        "report": report,
                    }
                    yield sse(
                        {
                            "type": "report",
                            "content": report,
                        }
                    )
                    yield sse(
                        {
                            "type": "approval_required",
                            "execution_id": execution_id,
                            "message": "Report generated. Do you want to save it to disk?",
                        }
                    )
                    return

                for node_name, node_output in chunk.items():
                    current_state.update(node_output)

                    if node_name == "search":
                        count = len(current_state.get("search_results", []))
                        yield sse(
                            {
                                "type": "status",
                                "message": f"Found {count} sources. Generating report with Gemini...",
                            }
                        )
                    elif node_name == "generate":
                        yield sse(
                            {
                                "type": "status",
                                "message": "Report generated. Awaiting your approval to save...",
                            }
                        )

        except Exception as exc:
            yield sse({"type": "error", "message": _friendly_error(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/research/approve  – resume graph with user decision
# ---------------------------------------------------------------------------

@app.post("/api/research/approve")
async def approve_research(request: ApproveRequest):
    """
    Resume a paused research execution.

    Request:  {"execution_id": "...", "approved": true|false}
    Response: {"status": "saved"|"skipped", "report_path": "..."}
    """
    execution = _pending_executions.pop(request.execution_id, None)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found or already resolved.")

    thread_id: str = execution["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Resume the graph by sending the human's decision as the interrupt resume value.
    # Command(resume=value) is LangGraph's API for continuing a paused graph;
    # passing a plain dict would restart from the beginning instead of resuming.
    final_state: dict = {}
    try:
        async for chunk in _graph.astream(
            Command(resume=request.approved),
            config=config,
        ):
            # Skip __interrupt__ and other non-node chunks
            for node_name, node_output in chunk.items():
                if node_name.startswith("__"):
                    continue
                if isinstance(node_output, dict):
                    final_state.update(node_output)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_friendly_error(exc)) from exc

    if request.approved:
        report_path = final_state.get("report_path", "")
        return {"status": "saved", "report_path": report_path}
    else:
        return {"status": "skipped", "report_path": ""}


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}
