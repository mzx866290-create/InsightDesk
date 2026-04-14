# Getting Started

## Recommended Path

If your goal is to run the project quickly:

1. Copy `.env.example` to `.env`
2. Choose one model mode:
   - `OpenRouter` for fastest setup
   - `Ollama` for local/private deployment
3. Start the backend and frontend
4. Upload `test_doc.md`
5. Verify chat, retrieval, and report export

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
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
```

## Run

### Backend

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

### Windows One-Click

```bash
start.bat
```

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
