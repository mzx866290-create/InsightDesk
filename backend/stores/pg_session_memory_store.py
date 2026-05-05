"""PostgreSQL session memory and panel store adapters."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Callable

from backend.chat_store import (
    _normalize_session_memory_content,
    _normalize_session_memory_kind,
    _normalize_session_memory_meta,
    _parse_json_object,
)
from backend.stores.pg_base import PostgresStoreMixin


class PostgresSessionMemoryStore(PostgresStoreMixin):
    """Persist session memories and multi-panel configs in PostgreSQL."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_memory (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        content TEXT NOT NULL,
                        meta_json TEXT DEFAULT '{}',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_session_memory_session
                    ON session_memory(session_id)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_session_memory_session_updated
                    ON session_memory(session_id, updated_at DESC)
                    """
                )
                cursor.execute(
                    """
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
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_session_panels_session
                    ON session_panels(session_id, display_order)
                    """
                )
            conn.commit()

    def _session_exists(self, cursor: Any, session_id: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = %s LIMIT 1",
            (session_id,),
        )
        return cursor.fetchone() is not None

    def _memory_from_row(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(self._row_value(row, 0, "id") or ""),
            "session_id": str(self._row_value(row, 1, "session_id") or ""),
            "kind": str(self._row_value(row, 2, "kind") or ""),
            "content": str(self._row_value(row, 3, "content") or ""),
            "meta": _normalize_session_memory_meta(
                _parse_json_object(self._row_value(row, 4, "meta_json"))
            ),
            "created_at": float(self._row_value(row, 5, "created_at") or 0),
            "updated_at": float(self._row_value(row, 6, "updated_at") or 0),
        }

    def list_session_memory(
        self,
        session_id: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = %s
        """
        params: list[Any] = [session_id]
        if kind is not None:
            sql += " AND kind = %s"
            params.append(_normalize_session_memory_kind(kind))

        if limit is not None and limit > 0:
            sql += "\nORDER BY updated_at DESC, created_at DESC, id DESC\nLIMIT %s"
            params.append(limit)
        else:
            direction = "DESC" if newest_first else "ASC"
            sql += f"\nORDER BY updated_at {direction}, created_at {direction}, id {direction}"

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()

        if limit is not None and limit > 0 and not newest_first:
            rows.reverse()
        return [self._memory_from_row(row) for row in rows]

    def create_session_memory(
        self,
        session_id: str,
        *,
        kind: str,
        content: Any,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_kind = _normalize_session_memory_kind(kind)
        normalized_content = _normalize_session_memory_content(content)
        normalized_meta = _normalize_session_memory_meta(meta)
        now = time.time()
        memory_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if not self._session_exists(cursor, session_id):
                    return None
                cursor.execute(
                    """
                    INSERT INTO session_memory (
                        id, session_id, kind, content, meta_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
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
                    "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
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
        self,
        session_id: str,
        *,
        content: Any,
        kind: str = "fact",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_kind = _normalize_session_memory_kind(kind)
        normalized_content = _normalize_session_memory_content(content)
        normalized_meta = _normalize_session_memory_meta(meta)
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if not self._session_exists(cursor, session_id):
                    return None
                cursor.execute(
                    """
                    SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
                    FROM session_memory
                    WHERE session_id = %s AND kind = %s AND content = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (session_id, normalized_kind, normalized_content),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    existing_meta = _normalize_session_memory_meta(
                        _parse_json_object(self._row_value(existing_row, 4, "meta_json"))
                    )
                    merged_meta = (
                        {**existing_meta, **normalized_meta}
                        if normalized_meta
                        else existing_meta
                    )
                    memory_id = self._row_value(existing_row, 0, "id")
                    cursor.execute(
                        "UPDATE session_memory SET meta_json = %s, updated_at = %s WHERE id = %s",
                        (json.dumps(merged_meta, ensure_ascii=False), now, memory_id),
                    )
                    cursor.execute(
                        "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                        (now, session_id),
                    )
                    conn.commit()
                    return {
                        "created": False,
                        "memory": {
                            **self._memory_from_row(existing_row),
                            "meta": merged_meta,
                            "updated_at": now,
                        },
                    }

        created = self.create_session_memory(
            session_id,
            kind=normalized_kind,
            content=normalized_content,
            meta=normalized_meta,
        )
        return {"created": True, "memory": created} if created else None

    def update_session_memory(
        self,
        session_id: str,
        memory_id: str,
        *,
        content: Any = None,
        kind: Any = None,
        meta: Any = None,
        update_content: bool = False,
        update_kind: bool = False,
        update_meta: bool = False,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
                    FROM session_memory
                    WHERE session_id = %s AND id = %s
                    """,
                    (session_id, memory_id),
                )
                existing_row = cursor.fetchone()
                if not existing_row:
                    return None

                updates: list[str] = []
                params: list[Any] = []
                if update_content:
                    updates.append("content = %s")
                    params.append(_normalize_session_memory_content(content))
                if update_kind:
                    updates.append("kind = %s")
                    params.append(_normalize_session_memory_kind(kind))
                if update_meta:
                    updates.append("meta_json = %s")
                    params.append(json.dumps(_normalize_session_memory_meta(meta), ensure_ascii=False))
                if not updates:
                    return self._memory_from_row(existing_row)

                now = time.time()
                updates.append("updated_at = %s")
                params.extend([now, session_id, memory_id])
                cursor.execute(
                    f"UPDATE session_memory SET {', '.join(updates)} WHERE session_id = %s AND id = %s",
                    tuple(params),
                )
                cursor.execute(
                    "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                    (now, session_id),
                )
                cursor.execute(
                    """
                    SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
                    FROM session_memory
                    WHERE session_id = %s AND id = %s
                    """,
                    (session_id, memory_id),
                )
                updated_row = cursor.fetchone()
            conn.commit()
        return self._memory_from_row(updated_row) if updated_row else None

    def delete_session_memory(self, session_id: str, memory_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM session_memory WHERE session_id = %s AND id = %s",
                    (session_id, memory_id),
                )
                deleted = int(cursor.rowcount or 0) > 0
                if deleted:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                        (time.time(), session_id),
                    )
            conn.commit()
        return deleted

    def clear_session_memory(self, session_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM session_memory WHERE session_id = %s", (session_id,))
                cursor.execute(
                    "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                    (time.time(), session_id),
                )
            conn.commit()

    def replace_session_panels(
        self,
        session_id: str,
        panel_configs: list[dict[str, Any]],
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM session_panels WHERE session_id = %s", (session_id,))
                for index, panel in enumerate(panel_configs):
                    panel_id = str(panel.get("panel_id") or "").strip()
                    if not panel_id:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO session_panels (
                            session_id, panel_id, provider, connection_type, model, base_url, api_key_ref,
                            temperature, agent_mode, display_order, is_primary, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            panel_id,
                            str(panel.get("provider") or "ollama"),
                            str(panel.get("connection_type") or panel.get("provider") or ""),
                            str(panel.get("model") or ""),
                            str(panel.get("base_url") or ""),
                            str(panel.get("api_key_ref") or ""),
                            float(panel.get("temperature") or 0.3),
                            str(panel.get("agent_mode") or "auto"),
                            index,
                            1 if index == 0 else 0,
                            now,
                            now,
                        ),
                    )
            conn.commit()

    def upsert_session_panel(
        self,
        session_id: str,
        panel_config: dict[str, Any],
    ) -> None:
        panel_id = str(panel_config.get("panel_id") or "").strip()
        if not panel_id:
            return
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COALESCE(MAX(display_order), -1) FROM session_panels WHERE session_id = %s",
                    (session_id,),
                )
                max_row = cursor.fetchone()
                max_display_order = int(self._row_value(max_row, 0, "max") or -1)
                cursor.execute(
                    """
                    SELECT display_order
                    FROM session_panels
                    WHERE session_id = %s AND panel_id = %s
                    """,
                    (session_id, panel_id),
                )
                existing_row = cursor.fetchone()
                display_order = (
                    int(self._row_value(existing_row, 0, "display_order"))
                    if existing_row
                    else max_display_order + 1
                )
                cursor.execute(
                    """
                    INSERT INTO session_panels (
                        session_id, panel_id, provider, connection_type, model, base_url, api_key_ref,
                        temperature, agent_mode, display_order, is_primary, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id, panel_id) DO UPDATE SET
                        provider = EXCLUDED.provider,
                        connection_type = EXCLUDED.connection_type,
                        model = EXCLUDED.model,
                        base_url = EXCLUDED.base_url,
                        api_key_ref = EXCLUDED.api_key_ref,
                        temperature = EXCLUDED.temperature,
                        agent_mode = EXCLUDED.agent_mode,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        session_id,
                        panel_id,
                        str(panel_config.get("provider") or "ollama"),
                        str(panel_config.get("connection_type") or panel_config.get("provider") or ""),
                        str(panel_config.get("model") or ""),
                        str(panel_config.get("base_url") or ""),
                        str(panel_config.get("api_key_ref") or ""),
                        float(panel_config.get("temperature") or 0.3),
                        str(panel_config.get("agent_mode") or "auto"),
                        display_order,
                        1 if display_order == 0 else 0,
                        now,
                        now,
                    ),
                )
            conn.commit()

    def get_session_panels(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT panel_id, provider, connection_type, model, base_url, api_key_ref,
                           temperature, agent_mode, is_primary, display_order
                    FROM session_panels
                    WHERE session_id = %s
                    ORDER BY display_order ASC, updated_at ASC
                    """,
                    (session_id,),
                )
                rows = cursor.fetchall()
        panels: list[dict[str, Any]] = []
        for row in rows:
            panel_id = self._row_value(row, 0, "panel_id")
            provider = self._row_value(row, 1, "provider")
            connection_type = self._row_value(row, 2, "connection_type")
            panels.append(
                {
                    "panel_id": panel_id,
                    "is_primary": bool(self._row_value(row, 8, "is_primary")),
                    "display_order": int(self._row_value(row, 9, "display_order") or 0),
                    "model_config": {
                        "panel_id": panel_id,
                        "provider": provider or connection_type or "ollama",
                        "connection_type": connection_type or provider or "ollama",
                        "model": self._row_value(row, 3, "model") or "",
                        "base_url": self._row_value(row, 4, "base_url") or "",
                        "api_key": "",
                        "api_key_ref": self._row_value(row, 5, "api_key_ref") or "",
                        "temperature": float(self._row_value(row, 6, "temperature") or 0.3),
                        "agent_mode": self._row_value(row, 7, "agent_mode") or "auto",
                    },
                }
            )
        return panels
