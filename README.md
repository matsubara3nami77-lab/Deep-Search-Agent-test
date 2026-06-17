# Deep Research Agent — Level 3

An AI-powered deep research web application. Enter a topic and the agent searches the web with Tavily, generates a comprehensive report with Gemini 3.1 Flash Lite, and streams everything live to the UI — with human-in-the-loop checkpoints, a plan-first mode, and automatic query clarification built in.

## Feature Levels

This project was built incrementally across three levels:

| Level | Feature added |
| ----- | ------------- |
| **Level 1** | Core pipeline: search → generate → save, SSE streaming to frontend |
| **Level 2** | Human-in-the-loop (HITL) approval before saving the report to disk |
| **Level 3** | Plan mode, query clarification, intent classification, mode management |

---

## Architecture

### Level 1 — Core Pipeline

```
User Query
  → LangGraph: intent node     (classify: research / chat / mode_switch)
  → LangGraph: search node     (Tavily web search)
  → LangGraph: generate node   (Gemini 3.1 Flash Lite)
  → SSE stream → Next.js frontend
```

### Level 2 — Human-in-the-Loop (HITL)

```
  ... generate node produces report ...
  → LangGraph: approval node   (interrupt — waits for user decision)
      ↓ approved               ↓ rejected
  → save node                 → END (report shown, not saved)
    (writes data/reports/report_<timestamp>.md)
```

**Why HITL is placed before the file save step:**

LLM outputs may contain hallucinations or low-quality synthesis, and automatic persistence would pollute the data/reports/ directory with unverified artifacts. The approval step ensures only user-validated outputs are stored.

Additionally, it reduces unnecessary I/O and storage overhead by preventing transient or incomplete results from being written to disk during iterative research runs.

### Level 3 — Plan Mode, Clarification, Mode Management

```
User Query
  → intent node        (research / chat / mode_switch)
       ↓ research
  → clarify_check node (is the query ambiguous?)
       ↓ needs clarification          ↓ clear
  → clarification node (interrupt)   → [plan or search]
       ↓ user answers
  → [plan or search]

  Plan mode path:
  → plan node          (LLM generates 4-step plan)
  → plan_review node   (interrupt — user can start, edit, or regenerate)
       ↓ start         ↓ edit instruction
  → search node        → plan node (regenerate)

  Both modes continue:
  → generate node → approval node (HITL) → save node → END
```

---

## Tech Stack

| Layer     | Technology                                        |
| --------- | ------------------------------------------------- |
| Frontend  | Next.js 16 (App Router), TypeScript, Tailwind CSS |
| Backend   | Python, FastAPI, LangGraph                        |
| LLM       | Gemini 3.1 Flash Lite (via LangChain)             |
| Search    | Tavily                                            |

---

## Project Structure

```
deepresearch-agent-test/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI app, SSE endpoints, session store
│   │   ├── graph/
│   │   │   └── research_graph.py         # LangGraph StateGraph (all nodes + routers)
│   │   ├── tools/
│   │   │   ├── search_tool.py            # Tavily web search
│   │   │   └── save_report_tool.py       # Save markdown report to disk
│   │   └── services/
│   │       ├── gemini_service.py         # Gemini report generation
│   │       ├── intent_service.py         # Classify: research / chat / mode_switch
│   │       ├── clarification_service.py  # Detect ambiguous queries, generate options
│   │       └── plan_service.py           # Generate / regenerate 4-step research plan
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                      # Root state, session orchestration
│   │   └── globals.css
│   ├── components/
│   │   ├── ChatPanel.tsx                 # Chat messages, status bar, input
│   │   ├── ReportPanel.tsx               # Markdown report viewer + download
│   │   ├── PlanViewer.tsx                # Plan steps, start / regenerate controls
│   │   ├── ClarificationCard.tsx         # Clarification question + option buttons
│   │   └── ModeToggle.tsx                # TODO / PLAN mode toggle
│   ├── lib/
│   │   └── api.ts                        # SSE streaming client, continueResearch
│   └── .env.local.example
├── data/
│   └── reports/                          # Approved .md reports saved here
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- A [Gemini API key](https://aistudio.google.com/app/apikey)
- A [Tavily API key](https://app.tavily.com)

---

## Setup

### 1. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Edit .env and add your API keys
```

`.env` file:
```
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

Start the backend (from the `backend/` directory):
```bash
uvicorn app.main:app --reload --port 8080
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (optional — defaults to http://localhost:8080)
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux

# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Modes

### TODO Mode (default)

Research runs immediately after the query is submitted. The pipeline goes straight to web search and report generation, pausing only at the HITL approval step before saving.

### PLAN Mode

A 4-step research plan is generated and shown for review before any search is performed. The user can:

- **Start** — execute the plan as-is
- **Regenerate** — provide a natural-language instruction (e.g. "focus more on recent developments") and the LLM rewrites the full plan

Switch modes using the toggle in the top-right of the chat panel, or with slash commands:

| Command | Effect |
| ------- | ------ |
| `/plan` | Switch to PLAN mode |
| `/todo` | Switch to TODO mode |
| `/plan <query>` | Switch to PLAN mode and immediately start research |
| `/todo <query>` | Switch to TODO mode and immediately start research |

The active mode is persisted in `sessionStorage` and survives page refreshes.

---

## Clarification Flow

Before starting any search, the agent checks whether the query is too ambiguous to research reliably. If it is, the graph pauses and presents the user with:

- A clarifying question (e.g. "Which aspect of Python are you asking about?")
- 2–4 mutually distinct options to choose from

The selected answer is appended to the original query as a focus hint (e.g. `"Python (focus: performance optimisation)"`) and the pipeline continues. If the query is clear, this step is skipped entirely.

---

## Human-in-the-Loop (HITL) Approval

After the report is generated and displayed in the right panel, the pipeline **pauses** and asks the user to approve or reject saving it to disk.

**Why this checkpoint exists:**

- LLM outputs may contain hallucinations or unverified claims even when the pipeline succeeds technically
- Automatically saving every report would accumulate low-quality or incorrect research artifacts
- Placing approval here keeps `data/reports/` as a curated set of outputs the user has explicitly reviewed and accepted

If the user approves, the report is saved to `data/reports/report_<timestamp>.md`. If rejected, the report remains visible in the UI for the session but is not written to disk.

---

## API

### `POST /api/research`

Starts a new research session. Returns a Server-Sent Events (SSE) stream.

**Request body:**
```json
{ "query": "AI coding agents in 2026", "mode": "todo" }
```

`mode` is `"todo"` (default) or `"plan"`.

**SSE event types:**

| Event type | Fields | Description |
| --- | --- | --- |
| `status` | `message` | Progress update (searching, generating, saving…) |
| `chat` | `content` | Conversational reply (greetings, capability questions) |
| `mode_switch` | `target`, `message` | LLM detected a mode-change request |
| `report` | `content` | Full markdown report (emitted before approval prompt) |
| `plan_review` | `execution_id`, `plan` | Graph paused — plan ready for user review |
| `plan_progress` | `completed`, `total` | How many plan steps have been executed |
| `clarification_required` | `execution_id`, `message`, `options` | Graph paused — query needs disambiguation |
| `approval_required` | `execution_id`, `message` | Graph paused — waiting for save approval (HITL) |
| `error` | `message` | User-friendly error description |
| `done` | — | Session complete |

**Example stream (TODO mode, no clarification):**
```
data: {"type": "status",           "message": "Searching the web..."}
data: {"type": "status",           "message": "Found 5 sources. Generating report with Gemini..."}
data: {"type": "status",           "message": "Report generated."}
data: {"type": "report",           "content": "# Report Title\n\n## Executive Summary\n..."}
data: {"type": "approval_required","execution_id": "abc-123", "message": "Report generated. Do you want to save it to disk?"}
```

The stream **pauses** here. Resume it with `POST /api/research/continue`.

---

### `POST /api/research/continue`

Resumes a paused session. The `resume` value is interpreted by whichever interrupt node is currently waiting.

**Request body:**
```json
{ "execution_id": "abc-123", "resume": <value> }
```

| Paused at | `resume` value |
| --- | --- |
| `clarification_required` | `"<chosen option string>"` |
| `plan_review` — start | `{ "action": "start" }` |
| `plan_review` — regenerate | `{ "action": "edit", "instruction": "<natural language instruction>" }` |
| `approval_required` | `true` (save) or `false` (skip) |

Returns a new SSE stream that continues from where execution left off.

---

### `GET /health`

Returns `{"status": "ok"}`.

---

## Generated Reports

Approved reports are saved as Markdown files in `data/reports/`:
```
data/reports/report_20260617_120000.md
```

You can also download any report directly from the UI using the Download button in the report panel (no approval required for download — it saves to your browser's downloads, not the server).
