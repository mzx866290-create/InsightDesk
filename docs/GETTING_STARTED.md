# Getting Started

## Scope Notes

InsightDesk is a self-hosted Web workbench by default. You do not need a desktop
installer, full SaaS tenant setup, or production Alertmanager routing to try the
project locally. Start with one model provider, one browser session, and the
default `memory` task backend.

## Recommended Path

If your goal is to run the project quickly:

1. Copy `.env.example` to `.env`
2. Choose one model mode:
   - `OpenRouter` for fastest setup
   - `Ollama` for local/private deployment
3. Start the backend and frontend
4. Upload `test_doc.md`
5. Verify chat, retrieval, and report export

## Verified Runtime Versions

Use the same versions that the launcher validates:

- Python `3.12.x`
- Node.js `18+`
- Recommended Node.js: `20 LTS`

The Windows launcher creates and uses `venv312`. Avoid using Python `3.14+` for this repo.

## Setup Options

### Option A: Cloud Model Mode

Use this when you want the fastest first-time experience.

Recommended environment values:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=qwen/qwen-2.5-72b-instruct
TAVILY_API_KEY=your_tavily_api_key
```

### Option B: Local Model Mode

Use this when you want private deployment or lower inference cost.

Recommended environment values:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3.5-2B:latest
OLLAMA_BASE_URL=http://localhost:11434
TAVILY_API_KEY=your_tavily_api_key
```

Check local model service:

```bash
ollama list
```

## Install

```bash
py -3.12 -m venv venv312
venv312\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
```

## Run

### Backend

```bash
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

### Windows One-Click

```bash
start.bat
```

### Connectivity Check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_frontend_backend_connectivity.ps1
```

This check starts temporary backend/frontend processes, verifies the backend API,
the Vite homepage, and the Vite `/api` proxy, then stops the temporary
processes.

## LangGraph Mode

Use LangGraph when:

- you run smaller local models
- you want predictable tool routing
- you need workflow visualization in the UI

Use `agent_mode=auto` for the default behavior:

- local models prefer `langgraph`
- cloud models prefer `function_calling`

## First Validation

After startup, validate these steps:

1. Open the UI
2. Create a session
3. Ask a plain text question
4. Upload `test_doc.md`
5. Ask a retrieval question against the uploaded content
6. Generate a report or deck

## Troubleshooting

### Agent initialization fails

- verify `.env`
- verify model endpoint is reachable
- verify API key is present for cloud mode

### Retrieval returns nothing

- verify document upload completed
- verify vector store exists
- verify the selected prompt/workspace is not pointing to the wrong knowledge base

### Web search fails

- verify `TAVILY_API_KEY`
- verify outbound network access

### First run is slow

- embedding and reranker models may still be downloading
- frontend may still be building dependencies
