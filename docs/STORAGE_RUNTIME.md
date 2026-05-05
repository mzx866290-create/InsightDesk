# Storage Runtime Notes

## Current provider

The application metadata store defaults to SQLite. `DATABASE_PROVIDER=postgres` is partially implemented for `app_config` and task records; other store groups still fail fast through explicit unsupported adapters, so PostgreSQL should not be treated as full coverage yet.

## Database path

Use `APP_DB_PATH` to set the SQLite source database file used by chat history, sessions, workspaces, config, tasks, share links, artifacts, decks, and audit records.

Fallback order:

1. `APP_DB_PATH`
2. `CHAT_HISTORY_DB_PATH` legacy alias
3. `./chat_history.db`

For production-like local or Docker deployments, prefer a runtime volume path, for example:

```env
DATABASE_PROVIDER=sqlite
APP_DB_PATH=./runtime/chat_history.db
VECTOR_STORE_PATH=./runtime/vector_store
```

The code creates the SQLite parent directory automatically when the path has an explicit parent.

## Vector store maintenance

`VECTOR_STORE_PROVIDER=faiss` keeps the existing local directory lifecycle. `DocPipeline.delete_store()` removes the configured `VECTOR_STORE_PATH` directory and resets the in-memory vector store.

`VECTOR_STORE_PROVIDER=qdrant` delegates deletion to `QdrantVectorStoreAdapter.delete()`, which calls `delete_collection(collection_name=QDRANT_COLLECTION)`. The adapter also exposes `clear()` for all-point deletion when a caller wants to empty a collection without deleting the collection itself.

The Qdrant adapter accepts an injectable client factory for tests, so unit tests can validate delete success and failure semantics without a running Qdrant service.


## Lightweight validation payload

`backend/core/storage_runtime.py` exposes side-effect-free helpers for runtime diagnostics:

- `validate_postgres_config()` validates the configured PostgreSQL DSN shape, redacts credentials, and reports `missing_dsn` / `invalid_config` / `configured_not_connected` without opening a database connection.
- `validate_qdrant_config()` validates the Qdrant URL, collection name, and API-key presence without creating a Qdrant client.
- `database_runtime_summary()` reports the configured database provider, SQLite path or redacted PostgreSQL DSN status, local availability hints, and warnings/risks.
- `vector_store_runtime_summary()` reports the configured vector provider, FAISS path/index-file hints or Qdrant URL/collection config, delete/clear support declarations, and warnings/risks.
- `storage_runtime_payload()` combines both summaries for admin/debug endpoints or scripts.

The validation helpers intentionally do not connect to PostgreSQL or Qdrant. Qdrant availability means the URL and collection name pass static validation, not that the remote collection exists. FAISS availability checks only the local `VECTOR_STORE_PATH` and the expected `index.faiss` / `index.pkl` files.

Invalid remote config stays visible in the same payload shape. For example, `VECTOR_STORE_PROVIDER=qdrant` with `url="qdrant:6333"` returns `availability.status="invalid_config"` and `warnings=["qdrant_url_invalid_scheme"]` without attempting any network I/O.

`DocPipeline.get_stats()` now includes `storage_validation`, so callers can surface the provider, target, operation support, and risk list without loading extra services.

Before a storage migration, run the local preflight script and archive the JSON output with the rollout notes:

```bash
python deploy/validate_storage_migration.py --json \
  --report-path runtime/ops-readiness/storage/storage-migration-preflight.json \
  --archive-dir runtime/ops-readiness/storage/archive \
  --history-path runtime/ops-readiness/storage/history.json
```

The script does not connect to remote PostgreSQL or Qdrant in preflight mode. It only validates configuration and inspects the local SQLite snapshot, so it is safe to run before remote database or vector-store credentials are live. The report/archive/history options only write local JSON evidence files.

To execute the currently supported real migration, set the explicit execution gate and pass `--execute`:

```bash
STORAGE_MIGRATION_EXECUTE=1 \
DATABASE_URL=postgresql://app_user:secret@postgres:5432/insightdesk \
QDRANT_URL=http://qdrant:6333 \
QDRANT_COLLECTION=insightdesk_kb \
python deploy/validate_storage_migration.py --execute --json \
  --report-path runtime/ops-readiness/storage/storage-real-migration.json \
  --archive-dir runtime/ops-readiness/storage/archive \
  --history-path runtime/ops-readiness/storage/history.json
```

Execution is intentionally narrow. PostgreSQL creates and upserts only the implemented adapter tables listed in the JSON coverage block. SQLite remains the source snapshot. Qdrant execution ensures the target collection exists with `--qdrant-vector-size` (default `1536`), then reports `qdrant_embedding_backfill_required`; embedding/vector backfill is still a separate rollout step.

The JSON includes `contracts.readiness`, `contracts.rollback`, `rollback_plan`, `actions`, `checks`, `closure`, and `evidence_bundle`. `actions.executed=false` means no external writes occurred. `checks.pre` captures source readability, PostgreSQL/Qdrant target validation, execute/rollback env gates, rollback confirmations, Qdrant rollback safety, and evidence target configuration. `checks.post` records whether PostgreSQL/Qdrant actions ran, passed, failed, or were skipped because a pre-check blocked execution.

Status semantics:

- `closure.status=ready`: preflight or rollback plan is valid but no external writes were requested.
- `closure.status=blocked`: execute/rollback was requested without the required gate, valid target config, readable SQLite source, or rollback confirmations.
- `closure.status=executed`: the requested execute/rollback path ran and the action evidence is in `actions`.

`evidence_bundle` mirrors the same mode/status, embeds pre/post checks, records the execute/rollback command contracts, and tracks report/archive/history artifact paths. When `--report-path`, `--archive-dir`, or `--history-path` is supplied, `emit_evidence_report()` marks the matching artifact entries as written and records the bundle id in history.

Rollback is destructive and must be a separate, gated command. First render the plan:

```bash
python deploy/validate_storage_migration.py --rollback-plan --json \
  --report-path runtime/ops-readiness/storage/storage-rollback-plan.json \
  --archive-dir runtime/ops-readiness/storage/archive \
  --history-path runtime/ops-readiness/storage/history.json
```

Then execute only during a rollback drill/window:

```bash
STORAGE_MIGRATION_ROLLBACK=1 \
DATABASE_URL=postgresql://app_user:secret@postgres:5432/insightdesk \
QDRANT_URL=http://qdrant:6333 \
QDRANT_COLLECTION=insightdesk_test_kb \
python deploy/validate_storage_migration.py \
  --rollback \
  --confirm-drop-postgres-adapter-tables \
  --confirm-delete-qdrant-collection \
  --json \
  --report-path runtime/ops-readiness/storage/storage-real-rollback.json \
  --archive-dir runtime/ops-readiness/storage/archive \
  --history-path runtime/ops-readiness/storage/history.json
```

PostgreSQL rollback drops only the implemented adapter tables listed in the rollback plan. Qdrant rollback only deletes collections named with the `insightdesk_test_` prefix unless `--allow-prod-qdrant-rollback` is also provided.

The rollback plan now carries explicit audit fields:

- global `requires`: `STORAGE_MIGRATION_ROLLBACK=1`, manual rollback window, and evidence report requirement
- per-target `requires`: confirmation flag, destructive scope, and Qdrant safe-prefix/prod-override policy
- per-target `pre_checks` and `post_checks`
- `restore_strategy`: rerun migration from preserved SQLite metadata and rerun Qdrant backfill after collection recreation
- `evidence.fields`: required report fields for closure review

For a real deployment/CI smoke check against live PostgreSQL and Qdrant, use the env-gated integration contract script:

```bash
STORAGE_INTEGRATION_TEST=1 \
DATABASE_URL=postgresql://app_user:secret@postgres:5432/insightdesk \
QDRANT_URL=http://qdrant:6333 \
QDRANT_COLLECTION=insightdesk_kb \
python deploy/run_storage_integration_check.py \
  --report-path runtime/ops-readiness/storage/storage-real-integration.json \
  --archive-dir runtime/ops-readiness/storage/archive \
  --history-path runtime/ops-readiness/storage/history.json
```

Default behavior is a JSON contract pass with `status=skipped`, `gate.status=skipped`, and both targets marked as skipped. The script only connects when `STORAGE_INTEGRATION_TEST=1` is set. If the gate is enabled but real PostgreSQL/Qdrant config is missing or unsafe, the report returns `status=blocked` and does not call the corresponding checker. PostgreSQL checks `SELECT 1` plus readiness for the currently implemented adapter tables. Qdrant checks the collections endpoint and performs a create/upsert/count/delete roundtrip against a test collection. Any explicit `QDRANT_TEST_COLLECTION` must start with `insightdesk_test_`; the script never deletes a collection outside that prefix.

The JSON payload always includes `status`, `gate`, `pre_checks`, `post_checks`, `checked`, `skipped`, `errors`, `warnings`, a redacted PostgreSQL DSN, the redacted Qdrant URL, and the target/test collection names. When report paths are provided, it also writes the current report, a timestamped archive entry, and a rolling history file under the requested local paths, with the same artifact paths reflected in `evidence_bundle.artifacts`. Use `--compact` when CI log size matters:

```bash
python deploy/run_storage_integration_check.py --compact
```

Example vector payload shape:

```json
{
  "kind": "vector_store",
  "provider": "qdrant",
  "configured": true,
  "target": {
    "url": "http://qdrant:6333",
    "collection_name": "insightdesk_kb",
    "api_key_configured": false
  },
  "availability": {
    "available": true,
    "status": "configured_not_connected",
    "collection_configured": true,
    "connectivity_checked": false
  },
  "operations": {
    "delete_supported": true,
    "clear_supported": true
  },
  "warnings": ["qdrant_collection_not_verified"],
  "risks": ["qdrant_delete_removes_collection"]
}
```


## Store factory boundary

`backend/stores/factory.py` is the single construction point for application stores used by `backend/api_server.py` and task runtime code. New persistence implementations should be introduced behind this factory instead of being instantiated directly from route or runtime modules.

Current factory functions:

- `create_app_config_store()`
- `create_security_audit_store()`
- `create_share_link_store()`
- `create_task_store()`
- `create_artifact_store()`
- `create_deck_store()`
- `create_chat_message_history(session_id)`

## Chat message runtime status

SQLite remains the default chat runtime. Most route and helper call sites still
instantiate `SQLiteChatMessageHistory` directly from `backend/chat_store.py`, so
`DATABASE_PROVIDER=postgres` should not yet be treated as a full chat runtime
cutover.

The migration layer already includes `messages` and `message_search`.
`backend/stores/pg_chat_store.py` now provides a minimal PostgreSQL runtime
adapter for the same low-risk message history contract:

- add human/AI/system messages to `messages`
- maintain the plain `message_search` mirror on writes and clears
- read model-facing history with the same context-window limit
- read full message records for UI/session surfaces
- upsert one shared human turn per `answer_group_id` via
  `add_user_message_once()`, including the search mirror update used by rerun
  paths
- delete a panel's previous AI response for an answer group via
  `delete_ai_messages_for_answer_group()`, including matching search mirror
  rows
- clear a session's message history
- perform session-scoped content search with `LIKE` against the search mirror

Known gaps before a full cutover:

- session/workspace/bookmark/feedback helper functions in `chat_store.py` are
  still SQLite-first unless individually routed to a PostgreSQL store
- many runtime imports still reference `SQLiteChatMessageHistory` directly
- PostgreSQL `message_search` is a plain mirror table, not SQLite FTS5; search
  semantics are substring-based until a Postgres full-text index/query layer is
  introduced
- storage pruning parity for `MAX_HISTORY_MESSAGES` is not yet implemented in
  the PostgreSQL adapter
- wider SQLite-only helper parity such as complex truncate/promote/session
  maintenance helpers remains intentionally out of scope for the current
  low-risk chat runtime adapter


## Store protocol contracts

`backend/stores/protocols.py` defines the method contracts that store adapters must satisfy. The factory returns these protocol types instead of concrete SQLite classes, so new adapters can be checked against the same route-facing surface.

Protocol groups:

- `AppConfigStore`
- `SecurityAuditStore`
- `ShareLinkStore`
- `TaskStore`
- `ArtifactStore`
- `DeckStore`

## Future PostgreSQL migration boundary

Do not add PostgreSQL conditionals inside route handlers. Add a store adapter behind the same store-facing APIs instead:

- chat/session/workspace history currently lives in `backend/chat_store.py`
- task/config/share/audit stores live in `backend/stores/`
- artifact/deck stores live in `backend/artifact_service.py` and `backend/deck_service.py`

Route builders should keep depending on store objects/functions, not on raw database drivers.
