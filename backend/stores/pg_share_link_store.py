"""PostgreSQL share link store adapter."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.share_link_store import ShareLinkRecord, SQLiteShareLinkStore


class PostgresShareLinkStore(PostgresStoreMixin, SQLiteShareLinkStore):
    """PostgreSQL implementation for share link metadata."""

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
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_share_links_resource
                    ON share_links(resource_type, resource_id, created_at DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_share_links_expires
                    ON share_links(expires_at)
                    """
                )
            conn.commit()

    def upsert(
        self,
        *,
        share_token: str,
        resource_type: str,
        resource_id: str,
        expires_at: float,
        created_by_ip: str = "",
        created_user_agent: str = "",
    ) -> ShareLinkRecord:
        now = time.time()
        normalized_share_token = str(share_token or "").strip()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO share_links (
                        share_token, resource_type, resource_id, created_at,
                        expires_at, revoked_at, created_by_ip, created_user_agent,
                        access_count, last_accessed_at, last_accessed_ip,
                        last_accessed_user_agent
                    )
                    VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, 0, NULL, '', '')
                    ON CONFLICT(share_token) DO UPDATE SET
                        resource_type = EXCLUDED.resource_type,
                        resource_id = EXCLUDED.resource_id,
                        expires_at = EXCLUDED.expires_at,
                        revoked_at = NULL,
                        created_by_ip = EXCLUDED.created_by_ip,
                        created_user_agent = EXCLUDED.created_user_agent
                    """,
                    (
                        normalized_share_token,
                        str(resource_type or "").strip(),
                        str(resource_id or "").strip(),
                        now,
                        float(expires_at),
                        str(created_by_ip or ""),
                        str(created_user_agent or ""),
                    ),
                )
            conn.commit()
        record = self.get(normalized_share_token)
        if record is None:
            raise RuntimeError("Failed to persist share link")
        return record

    def get(self, share_token: str) -> ShareLinkRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        share_token, resource_type, resource_id, created_at,
                        expires_at, revoked_at, created_by_ip, created_user_agent,
                        access_count, last_accessed_at, last_accessed_ip,
                        last_accessed_user_agent
                    FROM share_links
                    WHERE share_token = %s
                    """,
                    (str(share_token or "").strip(),),
                )
                row = cursor.fetchone()
        return self._from_row(row)

    def get_active(
        self, share_token: str, *, now: Optional[float] = None
    ) -> ShareLinkRecord | None:
        record = self.get(share_token)
        if record is None:
            return None
        current_time = time.time() if now is None else float(now)
        if record.revoked_at is not None or record.expires_at <= current_time:
            return None
        return record

    def list_links(
        self,
        *,
        resource_type: str = "",
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ShareLinkRecord]:
        normalized_resource_type = str(resource_type or "").strip()
        normalized_limit = max(1, min(int(limit or 100), 500))
        normalized_offset = max(0, int(offset or 0))
        clauses: list[str] = []
        params: list[Any] = []
        if normalized_resource_type:
            clauses.append("resource_type = %s")
            params.append(normalized_resource_type)
        if active_only:
            clauses.append("revoked_at IS NULL")
            clauses.append("expires_at > %s")
            params.append(time.time())
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        share_token, resource_type, resource_id, created_at,
                        expires_at, revoked_at, created_by_ip, created_user_agent,
                        access_count, last_accessed_at, last_accessed_ip,
                        last_accessed_user_agent
                    FROM share_links
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (*params, normalized_limit, normalized_offset),
                )
                rows = cursor.fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def revoke(self, share_token: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE share_links
                    SET revoked_at = COALESCE(revoked_at, %s)
                    WHERE share_token = %s
                    """,
                    (time.time(), str(share_token or "").strip()),
                )
                updated = int(cursor.rowcount or 0) > 0
            conn.commit()
        return updated

    def delete_for_resource(self, resource_type: str, resource_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM share_links
                    WHERE resource_type = %s AND resource_id = %s
                    """,
                    (str(resource_type or "").strip(), str(resource_id or "").strip()),
                )
                deleted = int(cursor.rowcount or 0)
            conn.commit()
        return deleted

    def record_access(
        self,
        share_token: str,
        *,
        accessed_ip: str = "",
        accessed_user_agent: str = "",
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE share_links
                    SET access_count = COALESCE(access_count, 0) + 1,
                        last_accessed_at = %s,
                        last_accessed_ip = %s,
                        last_accessed_user_agent = %s
                    WHERE share_token = %s
                    """,
                    (
                        time.time(),
                        str(accessed_ip or ""),
                        str(accessed_user_agent or ""),
                        str(share_token or "").strip(),
                    ),
                )
            conn.commit()
