# Quick Start

## Scope

InsightDesk is currently shipped as a self-hosted Web app. Use the browser UI
and Windows startup scripts for the recommended local experience. Desktop
installers, full SaaS tenant isolation, and managed external alert delivery are
future enhancements, not required for local use.

## Fastest Path

1. Copy `.env.example` to `.env`
2. Configure either `OpenRouter` or `Ollama`
3. Use Python `3.12.x`
4. Run `start.bat`
5. Open `http://localhost:5173`

The Windows launcher creates and uses `venv312` automatically.

If you access the app remotely and have enabled protected routes, open Settings and save a configured API token before using knowledge-base or prompt-management features. The backend accepts `Authorization: Bearer <token>`, `X-API-Token`, and the legacy `X-Admin-Token` header.

## Connectivity Check

After dependencies are installed, you can verify the backend, frontend, and Vite
API proxy with one command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_frontend_backend_connectivity.ps1
```

Expected result: the backend API, frontend homepage, and Vite `/api` proxy all
return `200`, and the script cleans up its temporary processes.

## Full Guide

See the consolidated setup guide:

- [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md)

## Recommended Reading Order

1. [README.md](./README.md)
2. [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md)
3. [docs/AGENT_AND_WORKFLOW.md](./docs/AGENT_AND_WORKFLOW.md)
