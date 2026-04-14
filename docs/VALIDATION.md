# Validation

## Scope

This document consolidates the smoke checklist and release validation notes into one place.

## Pre-Release Checks

### Environment

- backend starts
- frontend starts
- model endpoint is reachable
- `.env` is configured

### Core Functional Checks

- health endpoint works
- single-panel chat works
- multi-panel chat works
- retrieval works
- attachment upload works
- session memory works
- task center updates work
- deck/report generation works

### Mode Checks

- local + langgraph
- cloud + function_calling
- auto mode routing

### Delivery Checks

- report generation
- deck export
- download filename behavior
- shared links if enabled

## Regression Baseline

Run:

```bash
venv312\Scripts\python.exe -m pytest -q
cd frontend && npm run build
```

## Security Regression

Validate:

- remote admin routes require `ADMIN_API_TOKEN`
- frontend admin flows automatically send the browser-saved `ADMIN_API_TOKEN`
- weak remote share secret is rejected
- response security headers are present

## Recommended Release Rule

Only treat a build as demo-ready when:

- backend tests pass
- frontend build passes
- at least one local end-to-end manual flow is verified
