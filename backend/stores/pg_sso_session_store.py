"""PostgreSQL SSO session store adapter."""

from __future__ import annotations

import time
from typing import Any, Callable

from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.sso_session_store import SsoSessionRecord, SQLiteSsoSessionStore


class PostgresSsoSessionStore(PostgresStoreMixin, SQLiteSsoSessionStore):
    """PostgreSQL implementation for SSO session metadata."""

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
                    CREATE TABLE IF NOT EXISTS sso_sessions (
                        token_hash TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        auth_source TEXT NOT NULL DEFAULT 'sso_oidc',
                        created_at DOUBLE PRECISION NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sso_sessions_expires_at
                    ON sso_sessions(expires_at)
                    """
                )
            conn.commit()

    def save(
        self,
        *,
        token_hash: str,
        user_id: str,
        role: str,
        auth_source: str,
        created_at: float,
        expires_at: float,
    ) -> SsoSessionRecord:
        normalized_token_hash = str(token_hash or "").strip()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sso_sessions (
                        token_hash, user_id, role, auth_source, created_at, expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(token_hash) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        role = EXCLUDED.role,
                        auth_source = EXCLUDED.auth_source,
                        created_at = EXCLUDED.created_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (
                        normalized_token_hash,
                        str(user_id or "").strip(),
                        str(role or "").strip(),
                        str(auth_source or "sso_oidc").strip(),
                        float(created_at or 0.0),
                        float(expires_at or 0.0),
                    ),
                )
            conn.commit()
        record = self.get(normalized_token_hash)
        if record is None:
            raise RuntimeError("Failed to persist SSO session")
        return record

    def get(self, token_hash: str) -> SsoSessionRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT token_hash, user_id, role, auth_source, created_at, expires_at
                    FROM sso_sessions
                    WHERE token_hash = %s
                    """,
                    (str(token_hash or "").strip(),),
                )
                row = cursor.fetchone()
        return self._from_row(row)

    def get_active(
        self,
        token_hash: str,
        *,
        now: float | None = None,
    ) -> SsoSessionRecord | None:
        record = self.get(token_hash)
        if record is None:
            return None
        current_time = time.time() if now is None else float(now)
        if record.expires_at <= current_time:
            self.delete(token_hash)
            return None
        return record

    def delete(self, token_hash: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sso_sessions WHERE token_hash = %s",
                    (str(token_hash or "").strip(),),
                )
                deleted = int(cursor.rowcount or 0) > 0
            conn.commit()
        return deleted

    def prune(self, *, now: float | None = None) -> int:
        current_time = time.time() if now is None else float(now)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sso_sessions WHERE expires_at <= %s",
                    (current_time,),
                )
                deleted = int(cursor.rowcount or 0)
            conn.commit()
        return deleted
