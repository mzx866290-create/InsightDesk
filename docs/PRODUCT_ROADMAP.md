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

- authentication
- RBAC
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

### Sprint 3

- diff/comparison views
- best-answer synthesis
- continue / retry / fork lifecycle

### Sprint 4

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

## What Should Be Avoided

- over-investing in chat-shell polish before workbench depth
- adding more isolated features without workflow closure
- mixing roadmap notes and implementation notes across many top-level markdown files
