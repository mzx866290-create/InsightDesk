# InsightDesk

Language / 语言: [中文](./README.md) | [English](./README.en.md)

InsightDesk is an AI workbench for enterprise knowledge Q&A, document analysis,
web research, and delivery generation. It combines chat, knowledge-base
retrieval, attachment analysis, session memory, async tasks, reports, and PPT
delivery in one project.

## Core Capabilities

- Workspaces, sessions, multi-panel chat, and multi-model comparison.
- Knowledge-base ingestion and retrieval for PDF, Word, Markdown, CSV, Excel,
  and other document formats.
- Attachment Q&A, attachment-to-knowledge-base tasks, session memory, and staged
  summaries.
- Web Research, citation panels, research archives, and cross-archive conflict
  review.
- Writing agent, quality review agent, human approval gates, and task center.
- Report, deck, PPTX/PDF delivery, and evidence-based export gates.
- MCP connectors, integrations, identity/resource access, security audit, and
  trace operations.
- Local Ollama, cloud models, OpenAI-compatible APIs, and OpenRouter.

## Quick Start

```bash
copy .env.example .env
start.bat
```

Open the frontend:

```text
http://localhost:5173
```

Manual startup:

```bash
venv312\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000

cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

If Windows reserves port `8000`, choose another backend port and set
`BACKEND_PORT` accordingly.

## Common Configuration

- Local models: `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- Cloud models: `OPENAI_API_KEY`, OpenRouter, or OpenAI-compatible settings
- Web search: `TAVILY_API_KEY`, optional `SEARXNG_URL`
- Remote access: `APP_AUTH_TOKENS_JSON`, `ADMIN_API_TOKEN`
- Sharing and security: `SHARE_LINK_SECRET`, audit and security settings

## Documentation

- [Chinese user manual](./docs/USER_MANUAL.md)
- [English user manual](./docs/USER_MANUAL.en.md)
- [Chinese documentation map](./docs/README.md)
- [English documentation map](./docs/README.en.md)
- [Current delivery status](./docs/DELIVERY_STATUS.md)
- [Quick start](./QUICKSTART.md)
- [Deployment operations](./docs/DEPLOYMENT_OPERATIONS.md)
- [Validation](./docs/VALIDATION.md)

## Current Status

The previously tracked 11 remaining sections are code/product closed. The only
remaining non-code decision is whether operators accept the archived ARQ
evidence and approve switching the default task backend from `memory` to `arq`.

For the delivery source of truth, see
[docs/DELIVERY_STATUS.md](./docs/DELIVERY_STATUS.md).

