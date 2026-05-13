# Claude Code Guide

This file is the short operating guide for Claude Code or any AI coding agent working in this repository.

## Project Shape

- Backend: FastAPI/Python under `backend/`.
- Frontend: React + TypeScript + Vite under `frontend/`.
- E2E: Playwright tests under `frontend/tests/e2e/`.
- Runtime and generated data live under `runtime/`, `logs/`, local databases, and vector stores. Do not commit those artifacts.

## First Rules

- Do not commit or expose `.env`, API keys, local model paths, databases, vector stores, logs, screenshots, or runtime evidence unless a maintainer explicitly asks for a sanitized artifact.
- Treat the worktree as shared. Do not reset, checkout, or delete unrelated changes.
- Keep changes scoped to the requested behavior. Avoid broad refactors while fixing tests or product issues.
- Prefer existing patterns in `frontend/src/components/settings/`, `frontend/tests/e2e/support/testHarness.ts`, and `frontend/tests/e2e/support/mockApi.ts`.

## Local Setup

```powershell
copy .env.example .env
py -3.12 -m venv venv312
venv312\Scripts\python.exe -m pip install -r requirements.txt

cd frontend
npm ci
npx playwright install chromium
```

For a quick local start:

```powershell
start.bat
```

## Validation

Use the smallest reliable gate first, then broaden:

```powershell
cd frontend
npm run test:unit
npm run build
npx playwright test tests/e2e/settings.spec.ts
npx playwright test
```

Backend quick checks:

```powershell
venv312\Scripts\python.exe -m pytest -q tests
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick
```

Full release-oriented validation is documented in `docs/VALIDATION.md`.

## Frontend Test Pattern

- Import Playwright from `frontend/tests/e2e/support/testHarness.ts`, not directly from `@playwright/test`.
- Add API mocks in `frontend/tests/e2e/support/mockApi.ts` when a browser flow needs backend behavior.
- Prefer stable `data-testid` selectors and resource attributes such as `data-connector-id`, `data-prompt-id`, or `data-chunk-id`.
- Do not rely on default-selected rows when a specific connector, prompt, or chunk is under test. Select by stable id first.
- Run target specs serially when using the default Playwright web server port. Multiple simultaneous `npx playwright test ...` commands can race on port `4173`.

## Recommended Change Flow

1. Inspect the existing implementation and test style.
2. Add or update stable UI selectors only where user-facing workflows need them.
3. Add focused mock API behavior for the exact route contract under test.
4. Add the narrow E2E case.
5. Run the target spec.
6. Run `npm run test:unit`, `npm run build`, and the full E2E suite before handoff when frontend behavior changed.

## Security Notes

- Redaction behavior is intentional. Tests should assert sensitive fields are not shown in UI or audit details.
- Never paste real API keys into tests, docs, screenshots, logs, or fixtures.
- Prefer mock values such as `sk-test-*`, `mock-token`, or `***redacted***`.
