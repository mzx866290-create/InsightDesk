# Contributing

## Scope

InsightDesk is a full-stack AI workbench. Keep contributions small, testable, and aligned with the current architecture:

- Backend: FastAPI/Python in `backend/`
- Frontend: React + TypeScript + Vite in `frontend/`
- E2E tests: Playwright in `frontend/tests/e2e/`
- Operational docs: `docs/`

The current project target is a personal/open-source self-hosted workbench.
Please treat desktop packaging, full SaaS tenant isolation, managed alert
delivery, enterprise SIEM retention, and IdP hardening as future enhancements
unless an issue or maintainer explicitly scopes them for the current change.

## Before You Start

1. Create or update your local `.env` from `.env.example`.
2. Do not commit secrets, local databases, model files, vector stores, logs, or generated runtime evidence.
3. Check the current worktree before editing:

```powershell
git status --short
```

If unrelated files are already modified, leave them alone.

## Development Setup

```powershell
py -3.12 -m venv venv312
venv312\Scripts\python.exe -m pip install -r requirements.txt

cd frontend
npm ci
npx playwright install chromium
```

Run locally:

```powershell
start.bat
```

Or start services manually:

```powershell
venv312\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000

cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Validation Checklist

Use targeted checks while developing:

```powershell
cd frontend
npm run test:unit
npm run build
npx playwright test tests/e2e/settings.spec.ts
```

Before handoff for frontend behavior changes:

```powershell
cd frontend
npm run test:unit
npm run build
npx playwright test
```

Backend checks:

```powershell
venv312\Scripts\python.exe -m pytest -q tests
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick
```

CI runs backend checks, frontend unit tests, frontend build, and Playwright E2E on pull requests.

## Frontend Guidelines

- Use TypeScript strictly and keep React components functional with hooks.
- Prefer existing UI and state patterns over new abstractions.
- Use stable `data-testid` selectors for E2E-facing controls.
- Add mock API support in `frontend/tests/e2e/support/mockApi.ts` for browser flows.
- Import tests from `frontend/tests/e2e/support/testHarness.ts` so permissions and mocks are installed consistently.
- Keep settings panels operational and compact. Avoid adding explanatory in-app text when a control or status is enough.

## Backend Guidelines

- Keep API changes explicit and typed.
- Preserve existing auth, audit, and redaction behavior.
- Add focused tests for route contracts, storage behavior, and security-sensitive branches.
- Do not make production defaults depend on local-only paths or machine-specific model files.

## Pull Request Expectations

Include:

- What changed and why.
- Before/After behavior for user-visible or architectural changes.
- Commands run and their results.
- Any residual risk or environment assumptions.

Do not include:

- Secrets or real customer data.
- Generated `frontend/dist`, Playwright traces, logs, local databases, model files, or vector stores.
