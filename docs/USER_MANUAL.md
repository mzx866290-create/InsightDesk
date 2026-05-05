# InsightDesk User Manual

Last updated: 2026-05-05

This manual explains what each major InsightDesk feature is for and how to use
it in day-to-day work. It is written for operators, internal users, reviewers,
and project maintainers who need a practical guide rather than an architecture
deep dive.

## 1. Product Purpose

InsightDesk is an enterprise AI workbench for knowledge Q&A, document analysis,
web research, writing/review workflows, and report or slide delivery.

Use it when you need to:

- turn internal files into searchable, citable knowledge;
- ask questions across uploaded documents, attachments, and web research;
- compare answers from multiple model configurations;
- preserve useful context as session memory;
- generate reports, decks, and exportable PPTX/PDF artifacts;
- route high-impact tasks through review or approval gates;
- monitor task, connector, trace, audit, and deployment readiness status.

## 2. First-Time Startup

### Purpose

Start the backend API and frontend UI so users can chat, upload documents, run
research, and generate deliverables.

### How To Use

1. Copy `.env.example` to `.env`.
2. Choose at least one model provider:
   - local/private mode: configure `OLLAMA_BASE_URL` and an Ollama model;
   - cloud mode: configure `OPENAI_API_KEY`, OpenRouter, or another
     OpenAI-compatible provider.
3. Start the project:
   - Windows quick path: run `start.bat`;
   - manual backend: `venv312\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000`;
   - manual frontend: run `npm run dev -- --host 0.0.0.0 --port 5173` inside
     `frontend`.
4. Open the frontend at `http://localhost:5173`.

### Notes

- Python `3.12.x` and Node.js `18+` are expected; Node.js `20 LTS` is
  recommended.
- The fastest validation path is: create a session, ask a normal question,
  upload a small document, ask a retrieval question, then generate a report or
  deck.

## 3. Workspaces

### Purpose

Workspaces separate different projects, departments, clients, or topics. They
keep sessions and related knowledge context organized.

### How To Use

1. Open the workspace selector in the sidebar.
2. Create a workspace with a clear name and optional description.
3. Activate the workspace before creating sessions or uploading project-specific
   material.
4. Rename, archive, or delete workspaces when they are no longer needed.

### Best Use

- Use one workspace per business project or team.
- Do not mix unrelated client or department material in the same workspace if
  answers need to remain traceable.

## 4. Sessions And Conversation History

### Purpose

Sessions preserve a threaded work context: questions, model answers, sources,
feedback, generated artifacts, and follow-up actions.

### How To Use

1. Create a new session from the sidebar.
2. Give it a useful title after the first meaningful question.
3. Use the same session for a continuous analysis thread.
4. Use reset/delete only when the conversation is no longer useful.
5. Use share links when a session needs to be reviewed by another person.

### Useful Actions

- `continue`: ask the system to keep working from the existing answer.
- `retry`: regenerate an answer when the result is poor or an upstream model
  failed.
- `fork`: branch from a useful point without losing the original line of work.
- bookmark/feedback: mark useful or weak answers for later review.

## 5. Chat And Agent Modes

### Purpose

The chat area is the main command surface. It routes user requests through the
selected model, optional knowledge retrieval, web research, MCP tools, memory,
and workflow logic.

### How To Use

1. Type a question or instruction in the message input.
2. Choose whether knowledge base and web search should be enabled.
3. Select quick or deep research mode when the task needs web research.
4. Send the message and watch the streamed answer, workflow nodes, citations,
   and source panels.

### Agent Modes

- `auto`: recommended default. It chooses a suitable runtime strategy.
- `function_calling`: best for cloud models that support tool/function calls.
- `langgraph`: best for predictable routing, local models, and visible workflow
  steps.

### Best Use

- Use direct chat for drafting, summarization, Q&A, and small analysis tasks.
- Use deep research for time-sensitive or source-heavy topics.
- Use knowledge base retrieval for internal documents and stable facts.

## 6. Multi-Panel And Multi-Model Comparison

### Purpose

Multi-panel chat lets you compare model configurations side by side and decide
which answer is better for the current task.

### How To Use

1. Add another chat panel.
2. Select a different model or provider profile for each panel.
3. Send the same question to compare answers.
4. Review differences with the panel comparison/diff view.
5. Keep the best answer or use it as source material for a report/deck.

### Best Use

- Compare local vs cloud model quality.
- Compare concise vs deep reasoning configurations.
- Use review results and user feedback to build preference knowledge over time.

## 7. Model Profiles And Presets

### Purpose

Profiles make model selection repeatable. They store provider, base URL, model
name, temperature, and related parameters.

### How To Use

1. Open Settings.
2. Configure local or OpenAI-compatible profiles.
3. Save frequently used model configurations as presets.
4. Apply presets to individual panels when comparing models.

### Notes

- Store secrets in `.env` or protected settings, not in shared docs.
- Local models are better for privacy-sensitive data; cloud models are usually
  stronger and faster for complex reasoning.

## 8. Knowledge Base Documents

### Purpose

The knowledge base turns files into searchable chunks so answers can cite
internal documents.

### Supported Files

`PDF`, `DOC`, `DOCX`, `TXT`, `Markdown`, `CSV`, and Excel files are supported by
the documented ingestion path.

### How To Use

1. Open Settings -> Knowledge Base Documents.
2. Upload one or more files.
3. Wait for the upload/import task to complete.
4. Check document statistics or knowledge base health.
5. Ask a question with knowledge base retrieval enabled.
6. Review the source panel to confirm cited chunks support the answer.

### Maintenance

- Use knowledge base monitoring to inspect chunks.
- Edit or delete bad chunks when source extraction is noisy.
- Delete a knowledge base only after confirming no active role or workflow
  depends on it.

## 9. Retrieval Testing And Source Review

### Purpose

Retrieval testing helps confirm whether the right document chunks are being
found before relying on an answer.

### How To Use

1. Open Settings -> Knowledge Base Monitoring.
2. Enter a query similar to the user question.
3. Compare semantic, keyword, and hybrid retrieval results.
4. Inspect source titles, chunk text, scores, and warnings.
5. Adjust or remove weak chunks when needed.

### Best Use

- Use this before demos, client reviews, or high-stakes internal decisions.
- If retrieval returns nothing, confirm upload completion and the active
  workspace/role binding.

## 10. Attachments

### Purpose

Attachments let users analyze files inside a session without necessarily turning
them into a long-term knowledge base.

### How To Use

1. Add files from the chat input or attachment workspace.
2. Ask direct questions about the uploaded files.
3. Preview attachment contents when supported.
4. Promote important attachments to the knowledge base if they should be reused.

### Best Use

- Use attachments for one-off analysis.
- Use the knowledge base for reusable organizational material.

## 11. Session Memory

### Purpose

Session memory preserves important facts, decisions, preferences, and summaries
so later answers stay consistent.

### How To Use

1. Open the memory workspace from the chat UI.
2. Pin important facts manually when they should remain active.
3. Review generated summaries after long sessions.
4. Remove outdated memory to prevent stale assumptions.

### Best Use

- Pin project goals, glossary definitions, stakeholder constraints, and writing
  style preferences.
- Do not pin temporary assumptions or unverified claims.

## 12. Web Research

### Purpose

Web research gathers external evidence, ranks sources, detects caveats, and
produces research-style answers with citations.

### How To Use

1. Enable web search or research mode.
2. Choose `quick` for lightweight current-context questions.
3. Choose `deep` for industry, policy, market, or time-sensitive research.
4. Ask a specific question with date, geography, industry, and output format
   when possible.
5. Review the research metadata, citations, caveats, and contradiction notes.

### Best Use

- Use research mode for latest information, regulations, market updates, vendor
  comparisons, and fact-heavy briefs.
- Treat caveats and unresolved conflicts as review prompts, not as noise.

## 13. Research Archives And Conflict Review

### Purpose

Research archives preserve previous research outputs so future work can reuse
evidence and spot cross-report conflicts.

### How To Use

1. Generate a research-backed answer or artifact.
2. Open archived research entries from the artifact/research panel when
   available.
3. Search archives by topic or session.
4. Review conflicts and add conflict-resolution notes.

### Best Use

- Reuse prior research for recurring market, policy, or competitor briefs.
- Record why a conflict was accepted, rejected, or deferred.

## 14. Reports And Artifacts

### Purpose

Reports turn a conversation, selected sources, or research results into a
structured deliverable.

### How To Use

1. Work inside a session until the needed context is present.
2. Generate a report from the session or selected scope.
3. Preview the report.
4. Export the artifact in a supported format when needed.
5. Revisit artifacts from the session artifact list.

### Best Use

- Use reports for memos, analysis summaries, decision records, and internal
  handoffs.
- Review citations before sharing externally.

## 15. Deck And PPT Delivery

### Purpose

Deck delivery converts conversation and evidence into editable slide specs and
exportable PPTX/PDF files.

### How To Use

1. Generate a deck draft from the current session.
2. Choose title, theme, audience, and slide scope.
3. Open the deck editor.
4. Review each slide, content block, source binding, and evidence coverage.
5. Regenerate a weak slide when needed.
6. Manually confirm slides that pass human review.
7. Export PPTX or PDF after export gates are satisfied.

### Export Gates

The deck editor shows citation and evidence-review status. If a slide lacks
source coverage or requires review, resolve the issue before export or apply the
documented manual confirmation path.

## 16. Writing Agent

### Purpose

The writing workflow helps turn source material into outlines, drafts, and
style-adjusted content.

### How To Use

1. Ask for an outline before requesting a full draft.
2. Provide audience, tone, length, required sections, and source constraints.
3. Review the outline and ask for changes.
4. Generate the draft.
5. Ask for style correction, shortening, expansion, or executive-summary
   variants.

### Best Use

- Use it for reports, emails, summaries, policies, scripts, and briefing notes.
- Keep factual claims grounded in citations or known session evidence.

## 17. Quality Review Agent

### Purpose

The quality review workflow checks answer quality, citation consistency,
coverage gaps, and risk before content is approved or exported.

### How To Use

1. Ask for a review of an answer, report, slide, or source-backed section.
2. Include review criteria: factuality, citation match, tone, completeness,
   security, or compliance.
3. Review findings and recommended actions.
4. Revise content and rerun review when needed.

### Best Use

- Use before external sharing, executive review, compliance-sensitive output, or
  any generated deck export.

## 18. Human Approval Gates

### Purpose

Approval gates prevent sensitive or high-impact tasks from executing without a
human decision.

### How To Use

1. Open the Task Center or relevant approval panel.
2. Review pending tasks and their risk level.
3. Approve, reject, or batch-decide tasks.
4. Update approval policy from the admin/settings path when governance rules
   change.

### Best Use

- Gate destructive operations, connector access, high-risk MCP tools, external
  delivery, and production-operation actions.

## 19. Task Center And Async Queue

### Purpose

The task center tracks background work such as document ingestion, reports,
multi-agent workflows, and long-running operations.

### How To Use

1. Open Task Center.
2. Filter by status: pending, running, completed, failed, or awaiting approval.
3. Open a task to inspect progress, result, warnings, or errors.
4. Retry or approve tasks when the UI exposes that action.

### Runtime Notes

- The default task backend remains `memory` for release safety.
- ARQ/Redis can be enabled for worker-backed execution after operational
  approval.
- Readiness reports `eligible_for_arq_default` only when
  `TASK_BACKEND_SWITCH_READY=1` and the required ARQ evidence is accepted.

## 20. MCP Connectors

### Purpose

MCP connectors expose controlled tools such as knowledge base, web search,
database, calendar, and notification integrations to the agent runtime.

### How To Use

1. Open Settings -> MCP Approvals or Integrations.
2. Review connector metadata, category, risk level, and health.
3. Approve only connectors that are needed for the current workspace.
4. Configure connector settings through the MCP config panel when required.
5. Revoke unused or high-risk connectors.

### Best Use

- Keep the default connector set small.
- Require approval for high-risk or external-action connectors.

## 21. Integrations

### Purpose

Integrator connectors manage external systems, credential rotation, probes,
audit events, and scheduled sync-style operations.

### How To Use

1. Open Settings -> Integrations.
2. Add or edit connector settings.
3. Test or probe the connector before enabling operational use.
4. Rotate credentials when secrets change.
5. Review integration audit events.
6. Configure and manually trigger schedules when needed.

### Best Use

- Use dry-run schedule triggers before live execution.
- Keep credentials scoped to the minimum required permission.

## 22. Identity, Organizations, And Resource Access

### Purpose

Identity and resource access features provide a lightweight governance layer for
organizations, users, memberships, and resource grants.

### How To Use

1. Open the identity/admin panel.
2. Create or update organizations and users.
3. Assign memberships.
4. Open resource access settings.
5. Grant or revoke access to workspaces, sessions, artifacts, or other governed
   resources.

### Best Use

- Use organization and grant records to prepare for enterprise-style operation.
- Treat this as RBAC-lite, not a full SaaS tenant system.

## 23. Security Audit

### Purpose

Security audit records help operators understand sensitive actions, admin
changes, connector activity, and cleanup status.

### How To Use

1. Open Settings -> Security Audit.
2. Filter audit events by time, actor, action, or resource when supported.
3. Review high-risk actions.
4. Run cleanup only according to retention policy.

### Best Use

- Review audit events after connector changes, approval decisions, share-link
  creation, or admin operations.
- Export or forward audit data to a SIEM in production environments when
  required.

## 24. Trace And Observability

### Purpose

Trace and observability panels expose runtime events, workflow traces, health
snapshots, and operational diagnostics.

### How To Use

1. Open Settings -> Trace Operations.
2. Load recent traces.
3. Filter by source, process, level, or trace type when available.
4. Ingest trace events from supported runtime paths.
5. Clear local traces only when they are no longer needed.

### Best Use

- Use traces to debug failed retrieval, connector calls, workflow routing, and
  background task behavior.
- Use production exporters for long-term monitoring.

## 25. Health, Readiness, And Deployment Operations

### Purpose

Operations endpoints and validation scripts show whether the project is safe to
run, ship, or promote to a target environment.

### How To Use

1. Use `/healthz` for liveness checks.
2. Use `/readyz` for readiness checks.
3. Use Docker Compose profiles for optional services:
   - `tasks` for Redis/ARQ worker;
   - `storage` for Qdrant;
   - `search` for local SearXNG when explicitly enabled.
4. Run validation before release:
   - `venv312\Scripts\python.exe deploy\run_final_validation.py --profile quick --parallel-workers 2`
   - `venv312\Scripts\python.exe deploy\run_final_validation.py --profile full --include-frontend-build --parallel-workers 2`
   - `venv312\Scripts\python.exe deploy\verify_ops_evidence.py --json --strict`

### Best Use

- Run quick validation during normal development.
- Run full validation before handoff, release, or GitHub push.
- Keep real-environment drills gated by explicit environment variables.

## 26. Typical Workflows

### Internal Knowledge Q&A

1. Create or activate a workspace.
2. Upload documents to the knowledge base.
3. Confirm ingestion task completion.
4. Ask a question with knowledge base retrieval enabled.
5. Review citations and source chunks.
6. Save useful answers or generate a report.

### Research Brief

1. Start a session for the topic.
2. Enable web research and choose deep mode.
3. Ask for a structured brief with dates and scope.
4. Review citations, caveats, and contradictions.
5. Archive or reuse research findings.
6. Generate a report or deck.

### Multi-Model Decision

1. Add two or more panels.
2. Assign different model profiles.
3. Ask the same question across panels.
4. Compare quality, citations, and style.
5. Choose the best answer and provide feedback.

### PPT Delivery

1. Build enough session context through chat, documents, or research.
2. Generate a deck draft.
3. Edit slides and source bindings.
4. Regenerate weak pages.
5. Review export gates.
6. Export PPTX/PDF.

### Governed Operation

1. Configure approval policy.
2. Trigger a task or connector action.
3. Review pending approval.
4. Approve or reject.
5. Check audit and task result.

## 27. Troubleshooting

### Model Answers Fail

- Confirm `.env` model configuration.
- Confirm local Ollama or cloud API endpoint is reachable.
- Switch to another model profile to isolate provider issues.

### Retrieval Is Empty

- Confirm document upload task completed.
- Check knowledge base health and chunk count.
- Verify the active workspace or role is bound to the intended knowledge base.
- Run retrieval testing with the same query.

### Web Research Is Weak

- Confirm `TAVILY_API_KEY` or search provider configuration.
- Add date range, geography, company names, and source expectations to the
  prompt.
- Use deep mode for source-heavy work.

### Deck Export Is Blocked

- Open the deck editor evidence panel.
- Fix slides with missing citations or review actions.
- Manually confirm only after human review.
- Retry export after gates are cleared.

### Tasks Stay Pending

- Check Task Center status and warnings.
- Confirm the selected backend is intended.
- If using ARQ, confirm Redis and worker are running.
- Review queue health and worker heartbeat.

## 28. Current Delivery Boundary

The project is currently code/product closed for the previously tracked 11
remaining sections. The remaining non-code decision is whether operators approve
the ARQ default-backend switch after accepting the archived evidence.

For the current source-of-truth status, read `docs/DELIVERY_STATUS.md`.

