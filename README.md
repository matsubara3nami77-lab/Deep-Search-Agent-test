# Deep Research Agent — Level 1

An AI-powered deep research web application. Enter a topic, and the agent searches the web with Tavily, generates a comprehensive report with Gemini 2.5 Flash Lite, saves it to disk, and streams everything live to the UI.

## Architecture

```
User Query
  → LangGraph: search node  (Tavily web search)
  → LangGraph: generate node (Gemini 2.5 Flash Lite)
  → LangGraph: save node     (writes data/reports/report_<timestamp>.md)
  → SSE stream → Next.js frontend
```

## Tech Stack

| Layer     | Technology                              |
| --------- | --------------------------------------- |
| Frontend  | Next.js 15 (App Router), TypeScript, Tailwind CSS |
| Backend   | Python, FastAPI, LangGraph              |
| LLM       | Gemini 2.5 Flash Lite (via LangChain)   |
| Search    | Tavily                                  |

## Project Structure

```
deepresearch-agent-test/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + SSE endpoint
│   │   ├── graph/
│   │   │   └── research_graph.py    # LangGraph StateGraph
│   │   ├── tools/
│   │   │   ├── search_tool.py       # Tavily web search
│   │   │   └── save_report_tool.py  # Save markdown to disk
│   │   └── services/
│   │       └── gemini_service.py    # Gemini report generation
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                 # Two-column layout + state
│   │   └── globals.css
│   ├── components/
│   │   ├── ChatPanel.tsx            # Chat + status feed
│   │   └── ReportPanel.tsx          # Markdown report viewer
│   ├── lib/
│   │   └── api.ts                   # SSE streaming client
│   └── .env.local.example
├── data/
│   └── reports/                     # Generated .md reports saved here
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- A [Gemini API key](https://aistudio.google.com/app/apikey)
- A [Tavily API key](https://app.tavily.com)

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
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (optional — defaults to http://localhost:8000)
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux

# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API

### `POST /api/research`

Streams Server-Sent Events (SSE) for real-time progress, then emits the final report.

**Request body:**
```json
{ "query": "AI coding agents in 2026" }
```

**Event stream:**
```
data: {"type": "status",  "message": "Searching the web..."}
data: {"type": "status",  "message": "Found 5 sources. Generating report with Gemini..."}
data: {"type": "status",  "message": "Report generated. Saving to disk..."}
data: {"type": "status",  "message": "Report saved to data/reports/report_20260617_120000.md"}
data: {"type": "report",  "content": "# Report Title\n\n## Executive Summary\n..."}
```

### `GET /health`

Returns `{"status": "ok"}`.

## Generated Reports

Reports are saved as Markdown files in `data/reports/`:
```
data/reports/report_20260617_120000.md
```

You can also download any report directly from the UI using the Download button in the report panel.
