# Agent And Workflow

## Scope

This document consolidates the previous LangGraph guide, workflow visualization guide, and implementation summaries into a single engineering reference.

## Current Agent Modes

The project supports three runtime modes:

- `function_calling`
  Best for strong cloud models that natively support tool use.

- `langgraph`
  Best for local or smaller models where we want a more constrained execution flow.

- `auto`
  Current default strategy:
  local models prefer `langgraph`, cloud models prefer `function_calling`.

## Why LangGraph Exists Here

LangGraph is not just an alternate orchestration style. In this project it solves two practical problems:

- smaller local models are less reliable with unconstrained tool calling
- the product needs a workflow that can be visualized in the frontend

## Current Workflow Capabilities

- tool-routing for retrieval and search tasks
- workflow event streaming
- frontend workflow node rendering
- traceable execution steps inside chat panels

## Frontend Workflow Visualization

Key UI pieces:

- `frontend/src/components/chat/ChatPanel.tsx`
- `frontend/src/components/workflow/WorkflowVisualizer.tsx`
- `frontend/src/stores/workflowStore.ts`
- `frontend/src/api/workflowClient.ts`

The frontend currently supports:

- node start / complete / fail state rendering
- tool name, parameters, and result summary display
- per-panel workflow persistence during a conversation

## Backend Responsibilities

Key backend areas:

- `agent_core.py`
- `api_agent_stream_helpers.py`
- `api_chat_stream_helpers.py`
- `api_chat_route_helpers.py`

The backend currently handles:

- tool selection
- streaming intermediate events
- panel-specific response composition
- workflow metadata persistence into message records

## Memory And Retrieval Integration

The current implementation already connects workflow execution with:

- session-scoped memory
- document retrieval
- attachment analysis
- task generation

This is important because the product direction is not a generic chat shell. It is a working console where the workflow needs to cooperate with retrieval, memory, and delivery output.

## Current Strengths

- dual-mode agent strategy is already implemented
- workflow visualization is already shipped in the UI
- tests cover agent helpers and stream helpers
- the architecture is moving away from monolithic inline logic toward helper-based composition

## Current Gaps

- no human approval gate for high-risk actions yet
- workflow observability is UI-visible but not yet full production tracing
- MCP tools are extendable but not yet productized as a connector layer
- some behavior is still concentrated in large route/core files

## Recommended Next Steps

1. Add approval checkpoints for high-risk tools.
2. Introduce structured audit logs for tool execution.
3. Add a clearer workflow event schema contract.
4. Separate workflow orchestration from HTTP route concerns further.
