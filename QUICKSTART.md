# Quick Start

## Fastest Path

1. Copy `.env.example` to `.env`
2. Configure either `OpenRouter` or `Ollama`
3. Use Python `3.12.x`
4. Run `start.bat`
5. Open `http://localhost:5173`

The Windows launcher creates and uses `venv312` automatically.

If you access the app remotely and have enabled protected routes, open Settings and save a configured API token before using knowledge-base or prompt-management features. The backend accepts `Authorization: Bearer <token>`, `X-API-Token`, and the legacy `X-Admin-Token` header.

## Full Guide

See the consolidated setup guide:

- [docs/GETTING_STARTED.md](/f:/项目/AI智能体/docs/GETTING_STARTED.md)

## Recommended Reading Order

1. [README.md](/f:/项目/AI智能体/README.md)
2. [docs/GETTING_STARTED.md](/f:/项目/AI智能体/docs/GETTING_STARTED.md)
3. [docs/AGENT_AND_WORKFLOW.md](/f:/项目/AI智能体/docs/AGENT_AND_WORKFLOW.md)
