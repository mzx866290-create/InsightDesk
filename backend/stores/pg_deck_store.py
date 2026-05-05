"""PostgreSQL deck store adapter."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from backend.deck_service import DeckSpec, SQLiteDeckStore, refresh_deck_evidence_coverage
from backend.stores.pg_base import PostgresStoreMixin


class PostgresDeckStore(PostgresStoreMixin, SQLiteDeckStore):
    """PostgreSQL implementation for structured deck specs."""

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
                    CREATE TABLE IF NOT EXISTS decks (
                        deck_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        spec_json TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decks_session ON decks(session_id)"
                )
            conn.commit()

    def save(self, deck: DeckSpec) -> DeckSpec:
        refresh_deck_evidence_coverage(deck)
        now = time.time()
        payload = json.dumps(deck.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO decks (deck_id, session_id, title, spec_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(deck_id) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        title = EXCLUDED.title,
                        spec_json = EXCLUDED.spec_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        deck.deck_id,
                        deck.meta.session_id,
                        deck.meta.title,
                        payload,
                        now,
                        now,
                    ),
                )
            conn.commit()
        return deck

    def get(self, deck_id: str) -> DeckSpec:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT spec_json FROM decks WHERE deck_id = %s",
                    (deck_id,),
                )
                row = cursor.fetchone()
        if not row:
            raise KeyError(deck_id)
        return refresh_deck_evidence_coverage(
            DeckSpec.model_validate_json(str(self._row_value(row, 0, "spec_json") or "{}"))
        )

    def list_recent(self, *, limit: int = 100) -> list[DeckSpec]:
        safe_limit = max(1, min(500, int(limit or 100)))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT deck_id
                    FROM decks
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()
        return [self.get(str(self._row_value(row, 0, "deck_id") or "")) for row in rows]

    def list_ids_by_session(self, session_id: str) -> list[str]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT deck_id
                    FROM decks
                    WHERE session_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    """,
                    (normalized_session_id,),
                )
                rows = cursor.fetchall()
        return [str(self._row_value(row, 0, "deck_id") or "") for row in rows]

    def delete_by_session(self, session_id: str) -> int:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM decks WHERE session_id = %s",
                    (normalized_session_id,),
                )
                deleted = int(cursor.rowcount or 0)
            conn.commit()
        return deleted
