import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from app.graph.research_graph import create_research_graph  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Deep Research Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str


def sse(data: dict) -> str:
    """Format a dict as a Server-Sent Events data line."""
    return f"data: {json.dumps(data)}\n\n"


@app.post("/api/research")
async def research(request: ResearchRequest):
    """
    Stream research progress via SSE, then emit the final report.

    Events emitted:
      {"type": "status",  "message": "..."}
      {"type": "report",  "content": "...markdown..."}
      {"type": "error",   "message": "..."}
    """

    async def generate():
        yield sse({"type": "status", "message": "Searching the web..."})

        graph = create_research_graph()
        final_state: dict = {}

        try:
            async for chunk in graph.astream({"query": request.query}):
                for node_name, node_output in chunk.items():
                    final_state.update(node_output)

                    if node_name == "search":
                        count = len(final_state.get("search_results", []))
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
                                "message": "Report generated. Saving to disk...",
                            }
                        )
                    elif node_name == "save":
                        path = final_state.get("report_path", "")
                        report = final_state.get("report", "")
                        yield sse(
                            {
                                "type": "status",
                                "message": f"Report saved to {path}",
                            }
                        )
                        yield sse({"type": "report", "content": report})

        except Exception as exc:
            yield sse({"type": "error", "message": f"Research failed: {exc}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
