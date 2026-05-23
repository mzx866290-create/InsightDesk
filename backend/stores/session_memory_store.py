"""Session memory helpers for SQLite and PostgreSQL runtimes."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import TYPE_CHECKING, Any, Optional

from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.chat_normalization import (
    normalize_session_memory_content,
    normalize_session_memory_kind,
    normalize_session_memory_meta,
)
from backend.stores.chat_rows import row_to_session_memory
from backend.stores.chat_schema import init_session_memory_table, init_sessions_table
from backend.stores.chat_serialization import parse_json_object
from backend.stores.sqlite_runtime import connect_sqlite

if TYPE_CHECKING:
    from backend.stores.protocols import SessionMemoryStore

DB_PATH = app_database_path()
_UNSET = object()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def _session_memory_store() -> "SessionMemoryStore":
    from backend.stores.factory import create_session_memory_store

    return create_session_memory_store()


def _session_exists(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return cursor.fetchone() is not None


def list_session_memory(
    session_id: str,
    *,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
    newest_first: bool = False,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().list_session_memory(
            session_id,
            kind=kind,
            limit=limit,
            newest_first=newest_first,
        )

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_session_memory_table(conn)
        cursor = conn.cursor()

        sql = """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]

        if kind is not None:
            sql += " AND kind = ?"
            params.append(normalize_session_memory_kind(kind))

        if limit is not None and limit > 0:
            sql += "\nORDER BY updated_at DESC, created_at DESC, id DESC\nLIMIT ?"
            params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            if not newest_first:
                rows.reverse()
        else:
            direction = "DESC" if newest_first else "ASC"
            sql += f"\nORDER BY updated_at {direction}, created_at {direction}, id {direction}"
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        return [row_to_session_memory(row) for row in rows]


def create_session_memory(
    session_id: str,
    *,
    kind: str,
    content: Any,
    meta: Optional[dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().create_session_memory(
            session_id,
            kind=kind,
            content=content,
            meta=meta,
        )

    normalized_kind = normalize_session_memory_kind(kind)
    normalized_content = normalize_session_memory_content(content)
    normalized_meta = normalize_session_memory_meta(meta)
    now = time.time()
    memory_id = str(uuid.uuid4())

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_session_memory_table(conn)
        cursor = conn.cursor()

        if not _session_exists(cursor, session_id):
            return None

        cursor.execute(
            """
            INSERT INTO session_memory (
                id, session_id, kind, content, meta_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                session_id,
                normalized_kind,
                normalized_content,
                json.dumps(normalized_meta, ensure_ascii=False),
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    return {
        "id": memory_id,
        "session_id": session_id,
        "kind": normalized_kind,
        "content": normalized_content,
        "meta": normalized_meta,
        "created_at": now,
        "updated_at": now,
    }


def pin_session_memory(
    session_id: str,
    *,
    content: Any,
    kind: str = "fact",
    meta: Optional[dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().pin_session_memory(
            session_id,
            content=content,
            kind=kind,
            meta=meta,
        )

    normalized_kind = normalize_session_memory_kind(kind)
    normalized_content = normalize_session_memory_content(content)
    normalized_meta = normalize_session_memory_meta(meta)
    now = time.time()

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_session_memory_table(conn)
        cursor = conn.cursor()

        if not _session_exists(cursor, session_id):
            return None

        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ?
              AND kind = ?
              AND content = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (session_id, normalized_kind, normalized_content),
        )
        existing_row = cursor.fetchone()

        if existing_row:
            existing_meta = normalize_session_memory_meta(
                parse_json_object(existing_row[4])
            )
            merged_meta = (
                {**existing_meta, **normalized_meta}
                if normalized_meta
                else existing_meta
            )
            cursor.execute(
                "UPDATE session_memory SET meta_json = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(merged_meta, ensure_ascii=False),
                    now,
                    existing_row[0],
                ),
            )
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()
            return {
                "created": False,
                "memory": {
                    **row_to_session_memory(existing_row),
                    "meta": merged_meta,
                    "updated_at": now,
                },
            }

    created_memory = create_session_memory(
        session_id,
        kind=normalized_kind,
        content=normalized_content,
        meta=normalized_meta,
        db_path=db_path,
    )
    if not created_memory:
        return None

    return {
        "created": True,
        "memory": created_memory,
    }


def update_session_memory(
    session_id: str,
    memory_id: str,
    *,
    content: Any = _UNSET,
    kind: Any = _UNSET,
    meta: Any = _UNSET,
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().update_session_memory(
            session_id,
            memory_id,
            content=None if content is _UNSET else content,
            kind=None if kind is _UNSET else kind,
            meta=None if meta is _UNSET else meta,
            update_content=content is not _UNSET,
            update_kind=kind is not _UNSET,
            update_meta=meta is not _UNSET,
        )

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        existing_row = cursor.fetchone()
        if not existing_row:
            return None

        updates: list[str] = []
        params: list[Any] = []

        if content is not _UNSET:
            updates.append("content = ?")
            params.append(normalize_session_memory_content(content))

        if kind is not _UNSET:
            updates.append("kind = ?")
            params.append(normalize_session_memory_kind(kind))

        if meta is not _UNSET:
            updates.append("meta_json = ?")
            params.append(
                json.dumps(normalize_session_memory_meta(meta), ensure_ascii=False)
            )

        if not updates:
            return row_to_session_memory(existing_row)

        now = time.time()
        updates.append("updated_at = ?")
        params.append(now)
        params.append(session_id)
        params.append(memory_id)

        cursor.execute(
            f"UPDATE session_memory SET {', '.join(updates)} WHERE session_id = ? AND id = ?",
            tuple(params),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        updated_row = cursor.fetchone()
        return row_to_session_memory(updated_row) if updated_row else None


def delete_session_memory(
    session_id: str,
    memory_id: str,
    *,
    db_path: str | None = None,
) -> bool:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().delete_session_memory(session_id, memory_id)

    with connect_sqlite(db_path) as conn:
        init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        deleted = cursor.rowcount > 0
        if deleted:
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (time.time(), session_id),
            )
        conn.commit()
        return deleted


def clear_session_memory(
    session_id: str,
    *,
    db_path: str | None = None,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().clear_session_memory(session_id)
        return

    with connect_sqlite(db_path) as conn:
        init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM session_memory WHERE session_id = ?",
            (session_id,),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        conn.commit()


__all__ = [
    "clear_session_memory",
    "create_session_memory",
    "delete_session_memory",
    "list_session_memory",
    "pin_session_memory",
    "update_session_memory",
]
