"""Persistent SSO session store."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from backend.chat_store import connect_sqlite
from backend.core.storage_runtime import app_database_path


@dataclass
class SsoSessionRecord:
    token_hash: str
    user_id: str
    role: str
    auth_source: str
    created_at: float
    expires_at: float


class SQLiteSsoSessionStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sso_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    auth_source TEXT NOT NULL DEFAULT 'sso_oidc',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
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

    @staticmethod
    def _from_row(row: tuple[Any, ...] | None) -> SsoSessionRecord | None:
        if row is None:
            return None
        return SsoSessionRecord(
            token_hash=str(row[0] or ""),
            user_id=str(row[1] or ""),
            role=str(row[2] or ""),
            auth_source=str(row[3] or "sso_oidc"),
            created_at=float(row[4] or 0.0),
            expires_at=float(row[5] or 0.0),
        )

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
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sso_sessions (
                    token_hash,
                    user_id,
                    role,
                    auth_source,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(token_hash) DO UPDATE SET
                    user_id = excluded.user_id,
                    role = excluded.role,
                    auth_source = excluded.auth_source,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    str(token_hash or "").strip(),
                    str(user_id or "").strip(),
                    str(role or "").strip(),
                    str(auth_source or "sso_oidc").strip(),
                    float(created_at or 0.0),
                    float(expires_at or 0.0),
                ),
            )
            conn.commit()
        record = self.get(str(token_hash or "").strip())
        if record is None:
            raise RuntimeError("Failed to persist SSO session")
        return record

    def get(self, token_hash: str) -> SsoSessionRecord | None:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    token_hash,
                    user_id,
                    role,
                    auth_source,
                    created_at,
                    expires_at
                FROM sso_sessions
                WHERE token_hash = ?
                """,
                (str(token_hash or "").strip(),),
            ).fetchone()
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
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM sso_sessions WHERE token_hash = ?",
                (str(token_hash or "").strip(),),
            )
            conn.commit()
            return int(cursor.rowcount or 0) > 0

    def prune(self, *, now: float | None = None) -> int:
        self._init_db()
        current_time = time.time() if now is None else float(now)
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM sso_sessions WHERE expires_at <= ?",
                (current_time,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
