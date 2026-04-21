# Product Roadmap

## Scope

This document consolidates the former migration plan, retention blueprint, sprint backlog, and session workbench spec into one roadmap.

## Product Direction

The project should continue evolving from:

- "AI chat + knowledge base prototype"

to:

- "AI workbench for knowledge analysis and delivery"

That means the strongest long-term product value is not generic chat. It is the combination of:

- reusable sessions
- attachment-centered work
- inspectable retrieval
- structured delivery output

## Priority Order

### P0: Production Readiness

- managed authentication and token lifecycle
- organization-grade RBAC and policy enforcement
- audit logging
- safer file / share / admin boundaries
- monitoring and error visibility

### P1: Core Product Loop

- stronger session workbench
- long-session memory governance
- retrieval control console
- attachment workspace completeness
- task-center feedback loop

### P2: Differentiation

- multi-model comparison and answer synthesis
- artifacts and delivery matrix
- workspace presets
- MCP / connector productization

## Session Workbench

The session workbench direction is already partially implemented.

Current target capabilities:

- search
- rename
- favorite
- archive
- tags
- workspace-based organization

Why it matters:

- it turns sessions into reusable assets instead of disposable chat history

## Retention Strategy

The retention goal is to create features users do not want to leave after migrating in.

The most defensible areas are:

- session assets
- memory and continuity
- retrieval transparency
- evidence-grounded delivery output

## Recommended Execution Order

1. Finish the workbench-level daily workflow.
2. Make retrieval more controllable and explainable.
3. Strengthen attachment-first work paths.
4. Improve multi-model answer operations.
5. Expand delivery artifacts and workspace presets.

## Sprint View

### Sprint 1

- session metadata and filters
- sidebar/workbench upgrade
- memory schema and manual pinning

### Sprint 2

- retrieval diagnostics
- keyword/BM25 or hybrid retrieval
- retrieval control UI
- attachment workspace data isolation

### Sprint 3 (completed)

- continue / retry / fork lifecycle

### Sprint 4 (completed)

- artifact abstraction
- delivery matrix
- workspace presets

### Sprint 5+

- connector ecosystem
- experience hardening
- enterprise polish

## What Is Already Done

- workspaces
- session memory
- task center
- workflow visualization
- deck/report generation path
- retrieval diagnostics API
- retrieval control UI (v1)
- semantic / keyword / hybrid retrieval debug modes
- citation retrieval feedback
- attachment workspace data isolation
- answer-group comparison review
- recommended-answer promotion
- continue / retry / fork lifecycle
- artifact abstraction (v1)
- delivery matrix (v1)
- workspace presets (v1)
- MCP connector catalog and workspace-scoped selection (v1)
- security status, share-link audit, and token-safe request logging (v1)
- token-based authentication, `/api/auth/whoami`, and RBAC lite for viewer / editor / admin routes
- admin visibility for the effective auth token catalog via `/api/auth/tokens` with masked previews and fingerprints
- auth token hygiene visibility for weak / legacy token configuration in `/api/security/status` and `/api/auth/tokens`
- basic fixed-window rate limiting for remote management APIs, with config visibility in `/api/security/status`
- runtime operations status, request/error counters, and recent-error visibility (v1)
- security audit event visibility for recent admin / auth operations (v1)
- SQLite-backed persistence for recent security audit events (v1)
- audit retention/status visibility in `/api/security/status` (v1)
- safe fallback for invalid `SECURITY_AUDIT_HISTORY_LIMIT` values, with config-source visibility in `/api/security/status`
- admin cleanup control for persisted / in-memory security audit windows

## Current Retrieval State

- the production answer path defaults to semantic retrieval plus rerank, with automatic hybrid escalation for keyword-like queries
- the retrieval console can already compare semantic / keyword / hybrid modes
- fetch/top-k controls, candidate inspection, and basic coverage signals are available in the debug flow
- answer citations and workflow nodes now expose basic retrieval observability metadata
- citation thumbs-up / thumbs-down now feed back into lightweight source-level retrieval ranking
- citation panels and retrieval debug lists now expose source-level feedback counts, net signal, and boost summary

## What Should Be Avoided

- over-investing in chat-shell polish before workbench depth
- adding more isolated features without workflow closure
- mixing roadmap notes and implementation notes across many top-level markdown files
