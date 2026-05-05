"""Offline storage migration readiness validator.

This script is intentionally side-effect-free: it opens the SQLite source in
read-only mode and validates PostgreSQL/Qdrant target configuration without
connecting to either remote service.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.storage_runtime import (
    STORAGE_MIGRATION_EXECUTE_ENV,
    STORAGE_MIGRATION_ROLLBACK_ENV,
    app_database_path,
    qdrant_api_key,
    qdrant_collection_name,
    qdrant_url,
    storage_readiness_contract,
    storage_rollback_contract,
    storage_runtime_payload,
    validate_postgres_config,
    validate_qdrant_config,
)
from deploy.run_qdrant_backfill import QDRANT_BACKFILL_EXECUTE_ENV


APP_METADATA_TABLES = (
    "messages",
    "message_search",
    "sessions",
    "workspaces",
    "session_memory",
    "session_panels",
    "retrieval_feedback",
    "bookmarks",
    "system_prompts",
    "app_config",
    "tasks",
    "attachment_promotions",
    "artifacts",
    "decks",
    "security_audit_events",
    "share_links",
    "sso_sessions",
    "organizations",
    "users",
    "memberships",
    "resource_grants",
)
POSTGRES_ADAPTER_TABLES = (
    "messages",
    "message_search",
    "app_config",
    "tasks",
    "sessions",
    "workspaces",
    "session_memory",
    "session_panels",
    "retrieval_feedback",
    "bookmarks",
    "system_prompts",
    "attachment_promotions",
    "artifacts",
    "decks",
    "security_audit_events",
    "organizations",
    "users",
    "memberships",
    "share_links",
    "sso_sessions",
    "resource_grants",
)
POSTGRES_COPY_COLUMNS = {
    "messages": (
        "id",
        "session_id",
        "type",
        "content",
        "timestamp",
        "model_id",
        "panel_id",
        "answer_group_id",
        "images_json",
        "files_json",
        "sources_json",
        "workflow_json",
        "task_id",
        "task_type",
        "feedback_value",
    ),
    "message_search": ("rowid", "session_id", "content"),
    "app_config": ("key", "value", "updated_at"),
    "tasks": (
        "task_id",
        "task_type",
        "status",
        "params_json",
        "session_id",
        "created_at",
        "updated_at",
        "result",
        "error",
        "progress",
    ),
    "sessions": (
        "session_id",
        "created_at",
        "updated_at",
        "title",
        "is_archived",
        "is_favorite",
        "is_pinned",
        "session_order",
        "tags_json",
        "workspace_id",
    ),
    "workspaces": (
        "workspace_id",
        "name",
        "description",
        "color",
        "default_panels_json",
        "tool_config_json",
        "output_preset_json",
        "is_active",
        "created_at",
        "updated_at",
    ),
    "session_memory": (
        "id",
        "session_id",
        "kind",
        "content",
        "meta_json",
        "created_at",
        "updated_at",
    ),
    "session_panels": (
        "session_id",
        "panel_id",
        "provider",
        "connection_type",
        "model",
        "base_url",
        "api_key_ref",
        "temperature",
        "agent_mode",
        "display_order",
        "is_primary",
        "created_at",
        "updated_at",
    ),
    "retrieval_feedback": (
        "id",
        "session_id",
        "panel_id",
        "answer_group_id",
        "source_key",
        "source_type",
        "source_title",
        "source_url",
        "feedback_value",
        "created_at",
        "updated_at",
    ),
    "bookmarks": (
        "id",
        "session_id",
        "message_id",
        "panel_id",
        "answer_group_id",
        "role",
        "content",
        "model_id",
        "session_title",
        "created_at",
        "updated_at",
    ),
    "system_prompts": (
        "id",
        "name",
        "content",
        "is_default",
        "is_active",
        "created_at",
        "updated_at",
        "vector_store_id",
        "dashboard_template",
    ),
    "attachment_promotions": (
        "attachment_id",
        "vector_store_path",
        "task_id",
        "status",
        "attachment_name",
        "session_id",
        "created_at",
        "updated_at",
        "result",
        "error",
    ),
    "artifacts": (
        "artifact_id",
        "session_id",
        "artifact_type",
        "title",
        "status",
        "linked_resource_type",
        "linked_resource_id",
        "content_json",
        "created_at",
        "updated_at",
    ),
    "decks": (
        "deck_id",
        "session_id",
        "title",
        "spec_json",
        "created_at",
        "updated_at",
    ),
    "security_audit_events": (
        "id",
        "timestamp",
        "request_id",
        "action",
        "result",
        "ip",
        "is_local",
        "auth_mode",
        "auth_source",
        "user_id",
        "user_role",
        "details",
        "tenant_id",
        "org_id",
        "legal_hold",
    ),
    "organizations": (
        "org_id",
        "name",
        "description",
        "created_at",
        "updated_at",
    ),
    "users": (
        "user_id",
        "display_name",
        "email",
        "created_at",
        "updated_at",
    ),
    "memberships": (
        "org_id",
        "user_id",
        "role",
        "created_at",
        "updated_at",
    ),
    "share_links": (
        "share_token",
        "resource_type",
        "resource_id",
        "created_at",
        "expires_at",
        "revoked_at",
        "created_by_ip",
        "created_user_agent",
        "access_count",
        "last_accessed_at",
        "last_accessed_ip",
        "last_accessed_user_agent",
    ),
    "sso_sessions": (
        "token_hash",
        "user_id",
        "role",
        "auth_source",
        "created_at",
        "expires_at",
    ),
    "resource_grants": (
        "resource_type",
        "resource_id",
        "subject_type",
        "subject_id",
        "role",
        "created_at",
        "updated_at",
    ),
}
POSTGRES_TABLE_DDL = {
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            session_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            model_id TEXT DEFAULT '',
            panel_id TEXT DEFAULT '',
            answer_group_id TEXT DEFAULT '',
            images_json TEXT DEFAULT '',
            files_json TEXT DEFAULT '',
            sources_json TEXT DEFAULT '',
            workflow_json TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            task_type TEXT DEFAULT '',
            feedback_value INTEGER DEFAULT 0
        )
    """,
    "message_search": """
        CREATE TABLE IF NOT EXISTS message_search (
            rowid BIGINT PRIMARY KEY,
            session_id TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """,
    "app_config": """
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            params_json TEXT NOT NULL,
            session_id TEXT,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            result TEXT,
            error TEXT,
            progress INTEGER NOT NULL DEFAULT 0
        )
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            title TEXT DEFAULT '',
            is_archived INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            session_order DOUBLE PRECISION DEFAULT 0,
            tags_json TEXT DEFAULT '[]',
            workspace_id TEXT DEFAULT 'workspace-default'
        )
    """,
    "workspaces": """
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            color TEXT DEFAULT 'blue',
            default_panels_json TEXT DEFAULT '[]',
            tool_config_json TEXT DEFAULT '{}',
            output_preset_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "session_memory": """
        CREATE TABLE IF NOT EXISTS session_memory (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            meta_json TEXT DEFAULT '{}',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "session_panels": """
        CREATE TABLE IF NOT EXISTS session_panels (
            session_id TEXT NOT NULL,
            panel_id TEXT NOT NULL,
            provider TEXT DEFAULT 'ollama',
            connection_type TEXT DEFAULT '',
            model TEXT DEFAULT '',
            base_url TEXT DEFAULT '',
            api_key_ref TEXT DEFAULT '',
            temperature DOUBLE PRECISION DEFAULT 0.3,
            agent_mode TEXT DEFAULT 'auto',
            display_order INTEGER DEFAULT 0,
            is_primary INTEGER DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (session_id, panel_id)
        )
    """,
    "retrieval_feedback": """
        CREATE TABLE IF NOT EXISTS retrieval_feedback (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            session_id TEXT NOT NULL,
            panel_id TEXT NOT NULL,
            answer_group_id TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_type TEXT DEFAULT '',
            source_title TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            feedback_value INTEGER NOT NULL DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "bookmarks": """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            message_id INTEGER,
            panel_id TEXT DEFAULT '',
            answer_group_id TEXT DEFAULT '',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model_id TEXT DEFAULT '',
            session_title TEXT DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "system_prompts": """
        CREATE TABLE IF NOT EXISTS system_prompts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            vector_store_id TEXT DEFAULT '',
            dashboard_template TEXT DEFAULT ''
        )
    """,
    "attachment_promotions": """
        CREATE TABLE IF NOT EXISTS attachment_promotions (
            attachment_id TEXT NOT NULL,
            vector_store_path TEXT NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            attachment_name TEXT,
            session_id TEXT,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            result TEXT,
            error TEXT,
            PRIMARY KEY (attachment_id, vector_store_path)
        )
    """,
    "artifacts": """
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            linked_resource_type TEXT,
            linked_resource_id TEXT,
            content_json TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "organizations": """
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            email TEXT DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "memberships": """
        CREATE TABLE IF NOT EXISTS memberships (
            org_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (org_id, user_id)
        )
    """,
    "share_links": """
        CREATE TABLE IF NOT EXISTS share_links (
            share_token TEXT PRIMARY KEY,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL,
            revoked_at DOUBLE PRECISION,
            created_by_ip TEXT DEFAULT '',
            created_user_agent TEXT DEFAULT '',
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at DOUBLE PRECISION,
            last_accessed_ip TEXT DEFAULT '',
            last_accessed_user_agent TEXT DEFAULT ''
        )
    """,
    "sso_sessions": """
        CREATE TABLE IF NOT EXISTS sso_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            auth_source TEXT NOT NULL DEFAULT 'sso_oidc',
            created_at DOUBLE PRECISION NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL
        )
    """,
    "decks": """
        CREATE TABLE IF NOT EXISTS decks (
            deck_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            spec_json TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
    """,
    "security_audit_events": """
        CREATE TABLE IF NOT EXISTS security_audit_events (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            timestamp DOUBLE PRECISION NOT NULL,
            request_id TEXT DEFAULT '',
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            ip TEXT DEFAULT '',
            is_local INTEGER NOT NULL DEFAULT 0,
            auth_mode TEXT DEFAULT '',
            auth_source TEXT DEFAULT '',
            user_id TEXT DEFAULT '',
            user_role TEXT DEFAULT '',
            details TEXT DEFAULT '',
            tenant_id TEXT DEFAULT '',
            org_id TEXT DEFAULT '',
            legal_hold INTEGER NOT NULL DEFAULT 0
        )
    """,
    "resource_grants": """
        CREATE TABLE IF NOT EXISTS resource_grants (
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (resource_type, resource_id, subject_type, subject_id)
        )
    """,
}
POSTGRES_TABLE_INDEX_DDL = {
    "messages": (
        "CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_panel ON messages(session_id, panel_id)",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_human_group
        ON messages(session_id, type, panel_id, answer_group_id)
        WHERE type = 'human' AND panel_id = '' AND answer_group_id <> ''
        """,
    ),
    "message_search": (
        "CREATE INDEX IF NOT EXISTS idx_message_search_session ON message_search(session_id)",
    ),
    "session_memory": (
        "CREATE INDEX IF NOT EXISTS idx_session_memory_session ON session_memory(session_id)",
        """
        CREATE INDEX IF NOT EXISTS idx_session_memory_session_updated
        ON session_memory(session_id, updated_at DESC)
        """,
    ),
    "session_panels": (
        """
        CREATE INDEX IF NOT EXISTS idx_session_panels_session
        ON session_panels(session_id, display_order)
        """,
    ),
    "retrieval_feedback": (
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_feedback_unique
        ON retrieval_feedback(session_id, panel_id, answer_group_id, source_key)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_retrieval_feedback_lookup
        ON retrieval_feedback(session_id, answer_group_id, panel_id, updated_at DESC)
        """,
    ),
    "security_audit_events": (
        """
        CREATE INDEX IF NOT EXISTS idx_security_audit_timestamp
        ON security_audit_events(timestamp DESC, id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_security_audit_action_result
        ON security_audit_events(action, result, timestamp DESC, id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_security_audit_tenant_org
        ON security_audit_events(tenant_id, org_id, timestamp DESC, id DESC)
        """,
    ),
}
POSTGRES_CONFLICT_TARGETS = {
    "messages": ("id",),
    "message_search": ("rowid",),
    "app_config": ("key",),
    "tasks": ("task_id",),
    "sessions": ("session_id",),
    "workspaces": ("workspace_id",),
    "session_memory": ("id",),
    "session_panels": ("session_id", "panel_id"),
    "retrieval_feedback": ("id",),
    "bookmarks": ("id",),
    "system_prompts": ("id",),
    "attachment_promotions": ("attachment_id", "vector_store_path"),
    "artifacts": ("artifact_id",),
    "decks": ("deck_id",),
    "security_audit_events": ("id",),
    "organizations": ("org_id",),
    "users": ("user_id",),
    "memberships": ("org_id", "user_id"),
    "share_links": ("share_token",),
    "sso_sessions": ("token_hash",),
    "resource_grants": ("resource_type", "resource_id", "subject_type", "subject_id"),
}


PostgresMigrationExecutor = Callable[[str, str], dict[str, Any]]
QdrantMigrationExecutor = Callable[[str, str, str, int], dict[str, Any]]
PostgresRollbackExecutor = Callable[[str], dict[str, Any]]
QdrantRollbackExecutor = Callable[[str, str, str], dict[str, Any]]
DEFAULT_EVIDENCE_ID = "storage_migration"


def _evidence_id_for_mode(mode: str) -> str:
    return {
        "preflight": "storage_migration_preflight",
        "execute": "storage_real_migration_contract",
        "rollback_plan": "storage_rollback_plan",
        "rollback": "storage_real_rollback_contract",
    }.get(mode or "preflight", f"{DEFAULT_EVIDENCE_ID}_{mode or 'preflight'}")


def _check_entry(
    name: str,
    status: str,
    *,
    blocking: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "blocking": blocking,
        "details": details or {},
    }


def _action_has_errors(action: dict[str, Any]) -> bool:
    return bool(action.get("error") or action.get("errors"))


def _quote_identifier(identifier: str) -> str:
    if identifier not in APP_METADATA_TABLES:
        raise ValueError(f"Unexpected table name: {identifier}")
    return '"' + identifier.replace('"', '""') + '"'


def _readonly_sqlite_uri(db_path: str) -> str:
    return f"file:{Path(db_path).resolve(strict=False).as_posix()}?mode=ro"


def sqlite_source_snapshot(db_path: str) -> dict[str, Any]:
    """Return table-existence and row-count summary for the SQLite source."""

    normalized_path = str(db_path or "").strip()
    if not normalized_path:
        return {
            "path": "",
            "exists": False,
            "readable": False,
            "tables": {},
            "warnings": ["sqlite_source_path_missing"],
            "errors": ["sqlite_source_missing"],
        }
    if normalized_path == ":memory:":
        return {
            "path": normalized_path,
            "exists": True,
            "readable": False,
            "tables": {},
            "warnings": ["sqlite_memory_source_not_snapshotable"],
            "errors": ["sqlite_source_not_snapshotable"],
        }

    target = Path(normalized_path).expanduser()
    if not target.is_file():
        return {
            "path": normalized_path,
            "absolute_path": str(target.resolve(strict=False)),
            "exists": False,
            "readable": False,
            "tables": {},
            "warnings": ["sqlite_source_file_missing"],
            "errors": ["sqlite_source_missing"],
        }

    tables: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    try:
        with sqlite3.connect(_readonly_sqlite_uri(str(target)), uri=True) as conn:
            existing_tables = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type IN ('table', 'view')
                    """
                ).fetchall()
            }
            for table_name in APP_METADATA_TABLES:
                exists = table_name in existing_tables
                row_count: int | None = None
                if exists and table_name != "message_search":
                    try:
                        row_count = int(
                            conn.execute(
                                f"SELECT COUNT(1) FROM {_quote_identifier(table_name)}"
                            ).fetchone()[0]
                            or 0
                        )
                    except sqlite3.Error:
                        warnings.append(f"{table_name}_row_count_unavailable")
                tables[table_name] = {
                    "exists": exists,
                    "row_count": row_count,
                    "postgres_adapter_available": table_name in POSTGRES_ADAPTER_TABLES,
                }
    except sqlite3.Error as exc:
        errors.append("sqlite_source_unreadable")
        return {
            "path": normalized_path,
            "absolute_path": str(target.resolve(strict=False)),
            "exists": True,
            "readable": False,
            "tables": {},
            "warnings": warnings,
            "errors": errors,
            "error_detail": str(exc),
        }

    missing_core_tables = [
        table_name
        for table_name in ("messages", "sessions", "app_config", "tasks")
        if not tables.get(table_name, {}).get("exists")
    ]
    if missing_core_tables:
        warnings.append("sqlite_core_tables_missing")

    return {
        "path": normalized_path,
        "absolute_path": str(target.resolve(strict=False)),
        "exists": True,
        "readable": True,
        "tables": tables,
        "missing_core_tables": missing_core_tables,
        "warnings": warnings,
        "errors": errors,
    }


def _sqlite_rows(db_path: str, table_name: str) -> list[tuple[Any, ...]]:
    if table_name == "message_search":
        try:
            with sqlite3.connect(_readonly_sqlite_uri(db_path), uri=True) as conn:
                existing_tables = {
                    str(row[0])
                    for row in conn.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type IN ('table', 'view')
                        """
                    ).fetchall()
                }
                if "messages" not in existing_tables:
                    return []
                # Rebuild the search mirror from messages so stale or missing FTS
                # content does not block a metadata-only migration.
                return list(
                    conn.execute(
                        """
                        SELECT id AS rowid, session_id, COALESCE(content, '')
                        FROM messages
                        """
                    ).fetchall()
                )
        except sqlite3.Error:
            return []

    columns = POSTGRES_COPY_COLUMNS[table_name]
    quoted_columns = ", ".join('"' + column.replace('"', '""') + '"' for column in columns)
    try:
        with sqlite3.connect(_readonly_sqlite_uri(db_path), uri=True) as conn:
            return list(
                conn.execute(
                    f"SELECT {quoted_columns} FROM {_quote_identifier(table_name)}"
                ).fetchall()
            )
    except sqlite3.Error:
        return []


def _quote_pg_identifier(identifier: str) -> str:
    allowed = set(POSTGRES_ADAPTER_TABLES)
    for columns in POSTGRES_COPY_COLUMNS.values():
        allowed.update(columns)
    if identifier not in allowed:
        raise ValueError(f"Unexpected PostgreSQL identifier: {identifier}")
    return '"' + identifier.replace('"', '""') + '"'


def execute_postgres_migration(dsn: str, sqlite_db_path: str) -> dict[str, Any]:
    """Create implemented PostgreSQL adapter tables and copy SQLite rows."""

    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is required for real PostgreSQL migration.") from exc

    copied: dict[str, int] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            for table_name in POSTGRES_ADAPTER_TABLES:
                cursor.execute(POSTGRES_TABLE_DDL[table_name])
                for index_statement in POSTGRES_TABLE_INDEX_DDL.get(table_name, ()):
                    cursor.execute(index_statement)
                rows = _sqlite_rows(sqlite_db_path, table_name)
                copied[table_name] = len(rows)
                if not rows:
                    continue

                columns = POSTGRES_COPY_COLUMNS[table_name]
                placeholders = ", ".join(["%s"] * len(columns))
                column_sql = ", ".join(_quote_pg_identifier(column) for column in columns)
                conflict_columns = POSTGRES_CONFLICT_TARGETS[table_name]
                conflict_target = (
                    "("
                    + ", ".join(_quote_pg_identifier(column) for column in conflict_columns)
                    + ")"
                )
                update_sql = ", ".join(
                    f"{_quote_pg_identifier(column)} = EXCLUDED.{_quote_pg_identifier(column)}"
                    for column in columns
                    if column not in set(conflict_columns)
                )
                cursor.executemany(
                    f"""
                    INSERT INTO {_quote_pg_identifier(table_name)} ({column_sql})
                    VALUES ({placeholders})
                    ON CONFLICT {conflict_target} DO UPDATE SET {update_sql}
                    """,
                    rows,
                )
                if table_name in {"messages", "retrieval_feedback", "security_audit_events"}:
                    cursor.execute(
                        """
                        SELECT setval(
                            pg_get_serial_sequence(%s, 'id'),
                            COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1,
                            false
                        )
                        """.format(table_name=_quote_pg_identifier(table_name)),
                        (table_name,),
                    )
        conn.commit()
    return {"checked": True, "copied_rows": copied, "errors": [], "warnings": []}


def execute_qdrant_migration(
    url: str,
    api_key: str,
    collection_name: str,
    vector_size: int,
) -> dict[str, Any]:
    """Ensure the target Qdrant collection exists for the migration cutover."""

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
    except ModuleNotFoundError as exc:
        raise RuntimeError("qdrant-client is required for real Qdrant migration.") from exc

    client = QdrantClient(url=url, api_key=api_key or None)
    collections = client.get_collections()
    collection_names = {
        str(item.name)
        for item in getattr(collections, "collections", [])
        if getattr(item, "name", None)
    }
    created = False
    if collection_name not in collection_names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=max(1, int(vector_size)), distance=Distance.COSINE),
        )
        created = True
    return {
        "checked": True,
        "collection": collection_name,
        "created": created,
        "errors": [],
        "warnings": ["qdrant_embedding_backfill_required"],
    }


def execute_postgres_rollback(dsn: str) -> dict[str, Any]:
    """Drop only the currently implemented PostgreSQL adapter tables."""

    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is required for real PostgreSQL rollback.") from exc

    dropped: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            for table_name in reversed(POSTGRES_ADAPTER_TABLES):
                cursor.execute(f"DROP TABLE IF EXISTS {_quote_pg_identifier(table_name)}")
                dropped.append(table_name)
        conn.commit()
    return {"checked": True, "dropped_tables": dropped, "errors": [], "warnings": []}


def execute_qdrant_rollback(url: str, api_key: str, collection_name: str) -> dict[str, Any]:
    """Delete a Qdrant collection only after the caller has confirmed safety."""

    try:
        from qdrant_client import QdrantClient
    except ModuleNotFoundError as exc:
        raise RuntimeError("qdrant-client is required for real Qdrant rollback.") from exc

    client = QdrantClient(url=url, api_key=api_key or None)
    result = client.delete_collection(collection_name=collection_name)
    return {
        "checked": True,
        "collection": collection_name,
        "deleted": result is not False,
        "errors": [] if result is not False else ["qdrant_delete_collection_failed"],
        "warnings": [],
    }


def build_rollback_plan(
    *,
    postgres_dsn: str,
    qdrant_target_url: str,
    qdrant_collection: str,
) -> dict[str, Any]:
    return {
        "mode": "rollback",
        "status": "planned",
        "requires": {
            "env": STORAGE_MIGRATION_ROLLBACK_ENV,
            "env_value": "1",
            "manual_window": True,
            "evidence_report": True,
        },
        "postgres": {
            "target": validate_postgres_config(postgres_dsn)["target"],
            "destructive": True,
            "blast_radius": "implemented_postgres_adapter_tables_only",
            "tables": list(POSTGRES_ADAPTER_TABLES),
            "requires": {
                "env": STORAGE_MIGRATION_ROLLBACK_ENV,
                "confirmation_flag": "--confirm-drop-postgres-adapter-tables",
            },
            "command": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--confirm-drop-postgres-adapter-tables",
                "--json",
            ],
            "pre_checks": [
                "STORAGE_MIGRATION_ROLLBACK=1",
                "postgres_target_valid",
                "manual_confirmation_present",
            ],
            "post_checks": [
                "postgres_rollback_executor_checked",
                "dropped_tables_recorded",
            ],
        },
        "qdrant": {
            "target": validate_qdrant_config(
                url=qdrant_target_url,
                collection_name=qdrant_collection,
            )["target"],
            "destructive": True,
            "blast_radius": "target_qdrant_collection",
            "collection": qdrant_collection,
            "requires": {
                "env": STORAGE_MIGRATION_ROLLBACK_ENV,
                "confirmation_flag": "--confirm-delete-qdrant-collection",
                "safe_prefix": "insightdesk_test_",
                "prod_override_flag": "--allow-prod-qdrant-rollback",
            },
            "command": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--confirm-delete-qdrant-collection",
                "--json",
            ],
            "pre_checks": [
                "STORAGE_MIGRATION_ROLLBACK=1",
                "qdrant_target_valid",
                "manual_confirmation_present",
                "safe_collection_prefix_or_prod_override",
            ],
            "post_checks": [
                "qdrant_rollback_executor_checked",
                "delete_result_recorded",
            ],
        },
        "restore_strategy": {
            "metadata": "rerun migration from the preserved SQLite source snapshot",
            "vectors": "rerun deploy/run_qdrant_backfill.py after collection recreation",
        },
        "evidence": {
            "required": True,
            "fields": [
                "checks.pre",
                "checks.post",
                "actions",
                "closure",
                "rollback_plan",
                "evidence_bundle",
            ],
        },
    }


def build_qdrant_backfill_plan(
    *,
    vector_store_path: str,
    qdrant_target_url: str,
    qdrant_collection: str,
    qdrant_target_api_key: str,
    vector_size: int,
) -> dict[str, Any]:
    return {
        "target": validate_qdrant_config(
            url=qdrant_target_url,
            collection_name=qdrant_collection,
            api_key=qdrant_target_api_key,
        )["target"],
        "source": {
            "provider": "faiss",
            "vector_store_path": vector_store_path,
        },
        "destructive": False,
        "dry_run_default": True,
        "execute_env": QDRANT_BACKFILL_EXECUTE_ENV,
        "command": [
            "python",
            "deploy/run_qdrant_backfill.py",
            "--execute",
            "--allow-dangerous-faiss-deserialization",
            "--qdrant-vector-size",
            str(vector_size),
            "--json",
        ],
    }


def build_migration_checks(
    args: argparse.Namespace,
    *,
    mode: str,
    source: dict[str, Any],
    postgres: dict[str, Any],
    qdrant: dict[str, Any],
    actions: dict[str, Any],
    errors: list[str],
    report_path: str,
    archive_dir: str,
    history_path: str,
    manifest_path: str,
) -> dict[str, list[dict[str, Any]]]:
    execute_gate_open = os.getenv(STORAGE_MIGRATION_EXECUTE_ENV) == "1"
    rollback_gate_open = os.getenv(STORAGE_MIGRATION_ROLLBACK_ENV) == "1"
    evidence_configured = bool(report_path or archive_dir or history_path or manifest_path)
    execute_like = mode == "execute"
    rollback_like = mode == "rollback"

    pre_checks = [
        _check_entry(
            "sqlite_source_readable",
            "passed" if source.get("readable") else "blocked" if execute_like else "skipped",
            blocking=execute_like and not bool(source.get("readable")),
            details={
                "path": source.get("absolute_path") or source.get("path") or "",
                "required_for_execute": execute_like,
            },
        ),
        _check_entry(
            "postgres_target_valid",
            "passed"
            if postgres.get("valid")
            else "blocked"
            if execute_like or rollback_like or args.require_postgres_target
            else "skipped",
            blocking=(
                not bool(postgres.get("valid"))
                and (execute_like or rollback_like or args.require_postgres_target)
            ),
            details={"target": postgres.get("target", {})},
        ),
        _check_entry(
            "qdrant_target_valid",
            "passed"
            if qdrant.get("valid")
            else "blocked"
            if execute_like
            or (rollback_like and args.confirm_delete_qdrant_collection)
            or args.require_qdrant_target
            else "skipped",
            blocking=(
                not bool(qdrant.get("valid"))
                and (
                    execute_like
                    or (rollback_like and args.confirm_delete_qdrant_collection)
                    or args.require_qdrant_target
                )
            ),
            details={"target": qdrant.get("target", {})},
        ),
        _check_entry(
            "execute_env_gate",
            "passed" if execute_like and execute_gate_open else "blocked" if execute_like else "skipped",
            blocking=execute_like and not execute_gate_open,
            details={
                "env": STORAGE_MIGRATION_EXECUTE_ENV,
                "required_value": "1",
                "configured": execute_gate_open,
            },
        ),
        _check_entry(
            "rollback_env_gate",
            "passed" if rollback_like and rollback_gate_open else "blocked" if rollback_like else "skipped",
            blocking=rollback_like and not rollback_gate_open,
            details={
                "env": STORAGE_MIGRATION_ROLLBACK_ENV,
                "required_value": "1",
                "configured": rollback_gate_open,
            },
        ),
        _check_entry(
            "rollback_postgres_confirmation",
            "passed"
            if rollback_like and args.confirm_drop_postgres_adapter_tables
            else "blocked"
            if rollback_like
            else "skipped",
            blocking=rollback_like and not args.confirm_drop_postgres_adapter_tables,
            details={"flag": "--confirm-drop-postgres-adapter-tables"},
        ),
        _check_entry(
            "rollback_qdrant_confirmation",
            "passed"
            if rollback_like and args.confirm_delete_qdrant_collection
            else "skipped",
            details={"flag": "--confirm-delete-qdrant-collection"},
        ),
        _check_entry(
            "rollback_qdrant_safety",
            "passed"
            if (
                rollback_like
                and args.confirm_delete_qdrant_collection
                and (
                    str(args.qdrant_collection or qdrant.get("target", {}).get("collection_name") or "")
                    .strip()
                    .startswith("insightdesk_test_")
                    or args.allow_prod_qdrant_rollback
                )
            )
            else "blocked"
            if rollback_like and args.confirm_delete_qdrant_collection
            else "skipped",
            blocking=(
                rollback_like
                and args.confirm_delete_qdrant_collection
                and not (
                    str(args.qdrant_collection or qdrant.get("target", {}).get("collection_name") or "")
                    .strip()
                    .startswith("insightdesk_test_")
                    or args.allow_prod_qdrant_rollback
                )
            ),
            details={
                "safe_prefix": "insightdesk_test_",
                "prod_override": args.allow_prod_qdrant_rollback,
            },
        ),
        _check_entry(
            "evidence_targets_configured",
            "passed" if evidence_configured else "skipped",
            details={
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
                "manifest_path": manifest_path,
            },
        ),
    ]

    post_required = execute_like or rollback_like
    blocked_before_actions = bool(errors) and not bool(actions.get("executed"))
    post_checks = []
    for target_name in ("postgres", "qdrant"):
        action = actions.get(target_name, {})
        checked = bool(action.get("checked"))
        skipped = bool(action.get("skipped"))
        if checked and not skipped and not _action_has_errors(action):
            status = "passed"
        elif checked and _action_has_errors(action):
            status = "failed"
        elif post_required and blocked_before_actions:
            status = "skipped"
        else:
            status = "skipped"
        post_checks.append(
            _check_entry(
                f"{target_name}_{mode}_action",
                status,
                blocking=status == "failed",
                details={
                    "checked": checked,
                    "skipped": skipped,
                    "errors": action.get("errors", []),
                    "error": action.get("error", ""),
                },
            )
        )
    post_checks.append(
        _check_entry(
            "evidence_persistence",
            "pending" if evidence_configured else "skipped",
            details={
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
            },
        )
    )
    return {"pre": pre_checks, "post": post_checks}


def build_evidence_bundle(
    *,
    mode: str,
    closure: dict[str, Any],
    checks: dict[str, list[dict[str, Any]]],
    actions: dict[str, Any],
    report_path: str,
    archive_dir: str,
    history_path: str,
    manifest_path: str,
) -> dict[str, Any]:
    return {
        "id": _evidence_id_for_mode(mode),
        "mode": mode,
        "status": closure["status"],
        "executed": bool(actions.get("executed")),
        "targets": {
            "report_path": report_path,
            "archive_dir": archive_dir,
            "history_path": history_path,
            "manifest_path": manifest_path,
        },
        "artifacts": {
            "report": {"path": report_path, "written": False},
            "archive": {"dir": archive_dir, "path": "", "written": False},
            "history": {"path": history_path, "written": False},
            "manifest": {"path": manifest_path, "written": False},
        },
        "checks": checks,
        "commands": {
            "execute": [
                "python",
                "deploy/validate_storage_migration.py",
                "--execute",
                "--json",
            ],
            "rollback": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--json",
            ],
        },
        "gate": actions.get("real_environment_gate", {}),
    }


def build_migration_closure(
    *,
    mode: str,
    actions: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    report_path: str,
    archive_dir: str,
    history_path: str,
    manifest_path: str,
) -> dict[str, Any]:
    executed = bool(actions.get("executed"))
    blockers = list(errors)
    return {
        "mode": mode,
        "status": "blocked" if blockers else "executed" if executed else "ready",
        "executed": executed,
        "migration_ready": mode in {"preflight", "execute"} and not blockers,
        "rollback_ready": mode in {"rollback_plan", "rollback"} and not blockers,
        "postgres_checked": bool(actions.get("postgres", {}).get("checked")),
        "qdrant_checked": bool(actions.get("qdrant", {}).get("checked")),
        "evidence_ready": bool(report_path or archive_dir or history_path or manifest_path),
        "evidence_targets": {
            "report_path": report_path,
            "archive_dir": archive_dir,
            "history_path": history_path,
            "manifest_path": manifest_path,
        },
        "blockers": blockers,
        "warnings": list(warnings),
    }


def build_migration_report(
    args: argparse.Namespace,
    *,
    postgres_executor: PostgresMigrationExecutor = execute_postgres_migration,
    qdrant_executor: QdrantMigrationExecutor = execute_qdrant_migration,
    postgres_rollback_executor: PostgresRollbackExecutor = execute_postgres_rollback,
    qdrant_rollback_executor: QdrantRollbackExecutor = execute_qdrant_rollback,
) -> dict[str, Any]:
    """Build a complete offline migration readiness report."""

    sqlite_db_path = str(args.sqlite_db_path or app_database_path()).strip()
    vector_store_path = str(
        args.vector_store_path
        or os.getenv("VECTOR_STORE_PATH")
        or "./vector_store"
    ).strip()
    postgres_dsn = str(
        args.postgres_dsn
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("POSTGRES_URL")
        or ""
    ).strip()
    qdrant_target_url = str(args.qdrant_url or qdrant_url()).strip()
    qdrant_collection = str(args.qdrant_collection or qdrant_collection_name()).strip()
    qdrant_target_api_key = str(args.qdrant_api_key or qdrant_api_key()).strip()
    report_path = str(getattr(args, "report_path", "") or "").strip()
    archive_dir = str(getattr(args, "archive_dir", "") or "").strip()
    history_path = str(getattr(args, "history_path", "") or "").strip()
    manifest_path = str(getattr(args, "manifest_path", "") or "").strip()

    source = sqlite_source_snapshot(sqlite_db_path)
    postgres = validate_postgres_config(postgres_dsn)
    qdrant = validate_qdrant_config(
        url=qdrant_target_url,
        collection_name=qdrant_collection,
        api_key=qdrant_target_api_key,
    )
    runtime = storage_runtime_payload(
        vector_store_path=vector_store_path,
        vector_provider=args.vector_provider,
        collection_name=qdrant_collection,
    )

    warnings = list(source.get("warnings", []))
    errors = list(source.get("errors", []))
    mode = "rollback" if args.rollback else "execute" if args.execute else "preflight"
    if args.rollback_plan and not (args.execute or args.rollback):
        mode = "rollback_plan"
    execute_gate_open = os.getenv(STORAGE_MIGRATION_EXECUTE_ENV) == "1"
    rollback_gate_open = os.getenv(STORAGE_MIGRATION_ROLLBACK_ENV) == "1"
    actions: dict[str, Any] = {
        "mode": mode,
        "executed": False,
        "real_environment_gate": {
            "execute": {
                "env": STORAGE_MIGRATION_EXECUTE_ENV,
                "required": args.execute,
                "configured": execute_gate_open,
                "status": "passed"
                if args.execute and execute_gate_open
                else "blocked"
                if args.execute
                else "skipped",
            },
            "rollback": {
                "env": STORAGE_MIGRATION_ROLLBACK_ENV,
                "required": args.rollback,
                "configured": rollback_gate_open,
                "status": "passed"
                if args.rollback and rollback_gate_open
                else "blocked"
                if args.rollback
                else "skipped",
            },
        },
        "postgres": {"checked": False, "skipped": True},
        "qdrant": {"checked": False, "skipped": True},
    }
    if args.require_postgres_target and not postgres["valid"]:
        errors.append("postgres_target_invalid")
    elif postgres["warnings"]:
        warnings.extend(f"postgres:{warning}" for warning in postgres["warnings"])
    if args.require_qdrant_target and not qdrant["valid"]:
        errors.append("qdrant_target_invalid")
    elif qdrant["warnings"]:
        warnings.extend(f"qdrant:{warning}" for warning in qdrant["warnings"])

    pending_postgres_tables = [
        table_name
        for table_name in APP_METADATA_TABLES
        if table_name not in POSTGRES_ADAPTER_TABLES
    ]

    if args.execute and args.rollback:
        errors.append("migration_mode_conflict")
    if args.execute and not execute_gate_open:
        errors.append(f"missing_env:{STORAGE_MIGRATION_EXECUTE_ENV}")
    if args.execute and not source.get("readable"):
        errors.append("sqlite_source_not_readable")
    if args.execute and not postgres["valid"]:
        errors.append("postgres_target_invalid")
    if args.execute and not qdrant["valid"]:
        errors.append("qdrant_target_invalid")
    if args.rollback and not rollback_gate_open:
        errors.append(f"missing_env:{STORAGE_MIGRATION_ROLLBACK_ENV}")
    if args.rollback and not postgres["valid"]:
        errors.append("postgres_target_invalid")
    if args.rollback and args.confirm_delete_qdrant_collection and not qdrant["valid"]:
        errors.append("qdrant_target_invalid")

    rollback_plan = build_rollback_plan(
        postgres_dsn=postgres_dsn,
        qdrant_target_url=qdrant_target_url,
        qdrant_collection=qdrant_collection,
    )
    qdrant_backfill_plan = build_qdrant_backfill_plan(
        vector_store_path=vector_store_path,
        qdrant_target_url=qdrant_target_url,
        qdrant_collection=qdrant_collection,
        qdrant_target_api_key=qdrant_target_api_key,
        vector_size=int(args.qdrant_vector_size),
    )

    if args.execute and not errors:
        actions["executed"] = True
        try:
            postgres_action = postgres_executor(postgres_dsn, sqlite_db_path)
            errors.extend(f"postgres:{error}" for error in postgres_action.get("errors", []))
            warnings.extend(f"postgres:{warning}" for warning in postgres_action.get("warnings", []))
            actions["postgres"] = {**postgres_action, "skipped": False}
        except Exception as exc:  # pragma: no cover - deployment failure path.
            errors.append(f"postgres_migration_failed:{type(exc).__name__}")
            actions["postgres"] = {"checked": True, "skipped": False, "error": str(exc)}

        try:
            qdrant_action = qdrant_executor(
                qdrant_target_url,
                qdrant_target_api_key,
                qdrant_collection,
                int(args.qdrant_vector_size),
            )
            errors.extend(f"qdrant:{error}" for error in qdrant_action.get("errors", []))
            warnings.extend(f"qdrant:{warning}" for warning in qdrant_action.get("warnings", []))
            actions["qdrant"] = {**qdrant_action, "skipped": False}
        except Exception as exc:  # pragma: no cover - deployment failure path.
            errors.append(f"qdrant_migration_failed:{type(exc).__name__}")
            actions["qdrant"] = {"checked": True, "skipped": False, "error": str(exc)}

    if args.rollback and not errors:
        actions["executed"] = True
        if args.confirm_drop_postgres_adapter_tables:
            try:
                postgres_action = postgres_rollback_executor(postgres_dsn)
                errors.extend(f"postgres:{error}" for error in postgres_action.get("errors", []))
                warnings.extend(f"postgres:{warning}" for warning in postgres_action.get("warnings", []))
                actions["postgres"] = {**postgres_action, "skipped": False}
            except Exception as exc:  # pragma: no cover - deployment failure path.
                errors.append(f"postgres_rollback_failed:{type(exc).__name__}")
                actions["postgres"] = {"checked": True, "skipped": False, "error": str(exc)}
        else:
            errors.append("rollback_requires_confirm_drop_postgres_adapter_tables")

        if args.confirm_delete_qdrant_collection:
            if not qdrant_collection.startswith("insightdesk_test_") and not args.allow_prod_qdrant_rollback:
                errors.append("rollback_requires_allow_prod_qdrant_rollback")
            else:
                try:
                    qdrant_action = qdrant_rollback_executor(
                        qdrant_target_url,
                        qdrant_target_api_key,
                        qdrant_collection,
                    )
                    errors.extend(f"qdrant:{error}" for error in qdrant_action.get("errors", []))
                    warnings.extend(f"qdrant:{warning}" for warning in qdrant_action.get("warnings", []))
                    actions["qdrant"] = {**qdrant_action, "skipped": False}
                except Exception as exc:  # pragma: no cover - deployment failure path.
                    errors.append(f"qdrant_rollback_failed:{type(exc).__name__}")
                    actions["qdrant"] = {"checked": True, "skipped": False, "error": str(exc)}

    closure = build_migration_closure(
        mode=str(actions["mode"]),
        actions=actions,
        errors=errors,
        warnings=warnings,
        report_path=report_path,
        archive_dir=archive_dir,
        history_path=history_path,
        manifest_path=manifest_path,
    )
    checks = build_migration_checks(
        args,
        mode=str(actions["mode"]),
        source=source,
        postgres=postgres,
        qdrant=qdrant,
        actions=actions,
        errors=errors,
        report_path=report_path,
        archive_dir=archive_dir,
        history_path=history_path,
        manifest_path=manifest_path,
    )
    closure["pre_checks_blocked"] = [
        check["name"] for check in checks["pre"] if check["status"] == "blocked"
    ]
    closure["post_checks_failed"] = [
        check["name"] for check in checks["post"] if check["status"] == "failed"
    ]
    evidence_bundle = build_evidence_bundle(
        mode=str(actions["mode"]),
        closure=closure,
        checks=checks,
        actions=actions,
        report_path=report_path,
        archive_dir=archive_dir,
        history_path=history_path,
        manifest_path=manifest_path,
    )

    return {
        "ok": not errors and not (args.fail_on_warnings and warnings),
        "environment": {
            "DATABASE_PROVIDER": os.getenv("DATABASE_PROVIDER", "sqlite"),
            "APP_DB_PATH": sqlite_db_path,
            "DATABASE_URL_configured": bool(os.getenv("DATABASE_URL")),
            "POSTGRES_DSN_configured": bool(os.getenv("POSTGRES_DSN")),
            "VECTOR_STORE_PROVIDER": os.getenv("VECTOR_STORE_PROVIDER", "faiss"),
            "QDRANT_URL": qdrant_target_url,
            "QDRANT_COLLECTION": qdrant_collection,
        },
        "source": {"sqlite": source},
        "targets": {
            "postgres": postgres,
            "qdrant": qdrant,
        },
        "runtime": runtime,
        "coverage": {
            "postgres_adapter_tables": list(POSTGRES_ADAPTER_TABLES),
            "pending_postgres_adapter_tables": pending_postgres_tables,
            "postgres_adapter_coverage_ratio": round(
                len(POSTGRES_ADAPTER_TABLES) / len(APP_METADATA_TABLES),
                4,
            ),
        },
        "contracts": {
            "readiness": storage_readiness_contract(),
            "rollback": storage_rollback_contract(),
            "evidence": {
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
                "manifest_path": manifest_path,
            },
        },
        "rollback_plan": rollback_plan,
        "qdrant_backfill_plan": qdrant_backfill_plan,
        "actions": actions,
        "checks": checks,
        "closure": closure,
        "evidence_bundle": evidence_bundle,
        "warnings": warnings,
        "errors": errors,
    }


def _evidence_id_for_report(report: dict[str, Any]) -> str:
    mode = str(report.get("actions", {}).get("mode") or "preflight")
    return _evidence_id_for_mode(mode)


def emit_evidence_report(
    report: dict[str, Any],
    *,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> None:
    """Persist local JSON evidence files for migration/preflight/rollback runs."""

    if not (report_path or archive_dir or history_path or manifest_path):
        return

    evidence_id = _evidence_id_for_report(report)
    bundle = report.setdefault(
        "evidence_bundle",
        {
            "id": evidence_id,
            "mode": report.get("actions", {}).get("mode"),
            "status": report.get("closure", {}).get("status", "unknown"),
            "artifacts": {},
            "checks": report.get("checks", {}),
        },
    )
    bundle["id"] = evidence_id
    bundle["status"] = report.get("closure", {}).get("status", bundle.get("status"))
    bundle["targets"] = {
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "manifest_path": manifest_path,
    }
    artifacts = bundle.setdefault("artifacts", {})
    artifacts["report"] = {"path": report_path, "written": bool(report_path)}
    artifacts["archive"] = {"dir": archive_dir, "path": "", "written": bool(archive_dir)}
    artifacts["history"] = {"path": history_path, "written": bool(history_path)}
    artifacts["manifest"] = {"path": manifest_path, "written": bool(manifest_path)}
    for check in bundle.get("checks", {}).get("post", []):
        if check.get("name") == "evidence_persistence":
            check["status"] = "passed"
            check["details"] = {
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
                "manifest_path": manifest_path,
            }
    report["evidence"] = {
        "id": evidence_id,
        "bundle_id": evidence_id,
        "status": report.get("closure", {}).get("status", "unknown"),
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "manifest_path": manifest_path,
        "archive_path": "",
    }
    if archive_dir:
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{evidence_id}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        archive_path = archive_root / archive_name
        report["evidence"]["archive_path"] = str(archive_path)
        artifacts["archive"]["path"] = str(archive_path)
        archive_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if history_path:
        history = Path(history_path)
        history.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, Any]] = []
        if history.is_file():
            try:
                loaded = json.loads(history.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries = loaded
            except json.JSONDecodeError:
                entries = []
        entries.append(
            {
                "id": evidence_id,
                "ok": report["ok"],
                "mode": report.get("actions", {}).get("mode"),
                "status": report.get("closure", {}).get("status"),
                "executed": report.get("actions", {}).get("executed"),
                "evidence_bundle_id": evidence_id,
                "errors": report["errors"],
                "warnings": report["warnings"],
                "report_path": report_path,
                "archive_path": report["evidence"]["archive_path"],
                "history_path": history_path,
                "manifest_path": manifest_path,
                "recorded_at": time.time(),
            }
        )
        history.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if manifest_path:
        _write_evidence_manifest(
            report,
            evidence_id=evidence_id,
            manifest_path=manifest_path,
            report_path=report_path,
            history_path=history_path,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_evidence_manifest(
    report: dict[str, Any],
    *,
    evidence_id: str,
    manifest_path: str,
    report_path: str,
    history_path: str,
) -> None:
    """Update the evidence manifest while preserving other check entries."""

    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}
    if manifest_file.is_file():
        try:
            loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except json.JSONDecodeError:
            manifest = {}

    finished_at = _utc_now_iso()
    manifest["schema_version"] = str(manifest.get("schema_version") or "1")
    manifest["updated_at"] = finished_at
    reports = manifest.setdefault("reports", {})
    if not isinstance(reports, dict):
        reports = {}
        manifest["reports"] = reports
    reports[evidence_id] = {
        "id": evidence_id,
        "status": report.get("closure", {}).get("status"),
        "gate": report.get("actions", {}).get("real_environment_gate", {}),
        "ok": report.get("ok"),
        "report_path": report_path,
        "archive_path": report.get("evidence", {}).get("archive_path", ""),
        "history_path": history_path,
        "manifest_path": manifest_path,
        "blockers": list(report.get("closure", {}).get("blockers", report.get("errors", []))),
        "finished_at": finished_at,
    }
    report["evidence_bundle"]["artifacts"]["manifest"]["written"] = True
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_text_report(report: dict[str, Any]) -> None:
    source = report["source"]["sqlite"]
    coverage = report["coverage"]
    print("Storage migration readiness")
    print(f"- SQLite source: {source.get('absolute_path') or source.get('path')}")
    print(f"- SQLite readable: {source.get('readable')}")
    print(
        "- PostgreSQL adapter tables: "
        + ", ".join(coverage["postgres_adapter_tables"])
    )
    print(
        "- Pending PostgreSQL adapter tables: "
        + ", ".join(coverage["pending_postgres_adapter_tables"])
    )
    if report["warnings"]:
        print("- Warnings: " + ", ".join(report["warnings"]))
    if report["errors"]:
        print("- Errors: " + ", ".join(report["errors"]))
    print(f"- Mode: {report['actions']['mode']}")
    print(f"- OK: {report['ok']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate storage migration readiness without remote connections."
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--sqlite-db-path", default="")
    parser.add_argument("--vector-store-path", default="")
    parser.add_argument("--vector-provider", default=None)
    parser.add_argument("--postgres-dsn", default="")
    parser.add_argument("--qdrant-url", default="")
    parser.add_argument("--qdrant-collection", default="")
    parser.add_argument("--qdrant-api-key", default="")
    parser.add_argument("--qdrant-vector-size", type=int, default=1536)
    parser.add_argument("--require-postgres-target", action="store_true")
    parser.add_argument("--require-qdrant-target", action="store_true")
    parser.add_argument("--fail-on-warnings", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rollback-plan", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--confirm-drop-postgres-adapter-tables", action="store_true")
    parser.add_argument("--confirm-delete-qdrant-collection", action="store_true")
    parser.add_argument("--allow-prod-qdrant-rollback", action="store_true")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--archive-dir", default="")
    parser.add_argument("--history-path", default="")
    parser.add_argument("--manifest-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_migration_report(args)
    emit_evidence_report(
        report,
        report_path=args.report_path,
        archive_dir=args.archive_dir,
        history_path=args.history_path,
        manifest_path=args.manifest_path,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    if report["ok"]:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
