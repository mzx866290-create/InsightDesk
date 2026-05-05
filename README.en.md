# InsightDesk

Language / 语言: [中文](./README.md) | [English](./README.en.md)

InsightDesk is an AI workbench for enterprise knowledge Q&A, document analysis,
research, workflow execution, and deliverable generation.

It combines chat, knowledge-base retrieval, attachment analysis, web research,
session memory, async tasks, report generation, and PPT delivery in one project.

## Positioning

InsightDesk is not just a chat page or a RAG demo. It is a workflow-oriented AI
application foundation for teams that need to:

- turn internal files into searchable, citable, traceable knowledge assets;
- continue analysis and delivery inside the same session;
- convert conversation results into reports, decks, and `PPTX` files;
- use local models, cloud models, or both depending on privacy and cost needs.

## Core Capabilities

- Workspaces, sessions, multi-panel chat, answer comparison, `continue`,
  `retry`, and `fork`.
- Knowledge-base ingestion and retrieval for `PDF`, `DOC`, `DOCX`, `TXT`,
  Markdown, CSV, and Excel.
- Retrieval testing with `semantic`, `keyword`, and `hybrid` modes.
- Attachment upload, attachment Q&A, and attachment-to-knowledge-base tasks.
- Session memory with manual pinning and staged summaries.
- Async task center for ingestion, analysis, report, and workflow tasks.
- Report, deck, `PPTX`, and PDF-oriented delivery paths.
- `function_calling`, `langgraph`, and `auto` agent modes.
- Workflow visualization, retrieval observability, security status, audit
  records, MCP connectors, and deployment readiness evidence.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI, Uvicorn |
| Agent | LangChain, LangGraph |
| Model access | Ollama, OpenAI-compatible APIs, OpenRouter |
| Retrieval | FAISS, sentence-transformers, CrossEncoder |
| Storage | SQLite by default, PostgreSQL/Qdrant upgrade path |
| Document processing | pypdf, docx2txt, mammoth, unstructured, pandas |
| Delivery export | python-pptx |
| Deployment | Windows scripts, Docker, docker compose |

## Quick Start

1. Copy `.env.example` to `.env`.
2. Configure at least one model provider:
   - local mode: configure `OLLAMA_BASE_URL` and an Ollama model;
   - cloud mode: configure `OPENAI_API_KEY`, OpenRouter, or another
     OpenAI-compatible provider.
3. Start the project:

```bash
start.bat
```

4. Open the frontend:

```text
http://localhost:5173
```

Manual startup:

```bash
venv312\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Docker startup:

```bash
copy .env.example .env
docker compose up --build -d api
```

Optional profiles:

- ARQ tasks: `docker compose --profile tasks up --build -d api redis worker`
- Qdrant storage: `docker compose --profile storage up --build -d api qdrant`
- Local SearXNG: `docker compose --profile search up -d searxng`

## Configuration

Common settings live in [`.env.example`](./.env.example):

- model access: `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, OpenRouter settings;
- web search: `TAVILY_API_KEY`, optional `SEARXNG_URL`;
- remote access protection: `APP_AUTH_TOKENS_JSON`, `ADMIN_API_TOKEN`;
- sharing and security: `SHARE_LINK_SECRET`, audit, and security settings.

## Documentation

- [QUICKSTART.md](./QUICKSTART.md): fastest local startup path.
- [docs/README.md](./docs/README.md): Chinese documentation map.
- [docs/README.en.md](./docs/README.en.md): English documentation map.
- [docs/DELIVERY_STATUS.md](./docs/DELIVERY_STATUS.md): current delivery
  status, validation commands, and remaining external approval.
- [docs/USER_MANUAL.md](./docs/USER_MANUAL.md): Chinese user manual.
- [docs/USER_MANUAL.en.md](./docs/USER_MANUAL.en.md): English user manual.
- [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md): setup options and
  first-run path.
- [docs/AGENT_AND_WORKFLOW.md](./docs/AGENT_AND_WORKFLOW.md): agent modes,
  LangGraph, and workflow visualization.
- [docs/RESEARCH_LOGIC_V2.md](./docs/RESEARCH_LOGIC_V2.md): research pipeline
  and evidence model.
- [docs/DECK_DELIVERY_PLAN.md](./docs/DECK_DELIVERY_PLAN.md): report and PPT
  delivery design.
- [docs/VALIDATION.md](./docs/VALIDATION.md): smoke, regression, and release
  validation.

## Current Boundary

The project has a complete product foundation for team-internal or lightweight
deployment use. It is not yet a turnkey enterprise multi-tenant SaaS.

Current defaults:

- `SQLite + local files + local FAISS`;
- token auth, RBAC-lite, and security audit foundations;
- single API process by default, with optional ARQ worker, Redis, and Qdrant via
  Compose profiles.

For the current delivery source of truth, see
[docs/DELIVERY_STATUS.md](./docs/DELIVERY_STATUS.md).
