"""SQLite-backed persistence for deck specs."""

from __future__ import annotations

import json
import time

from backend.core.storage_runtime import app_database_path
from backend.deck_models import DeckSpec, refresh_deck_evidence_coverage
from backend.stores.sqlite_runtime import connect_sqlite


class SQLiteDeckStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decks (
                    deck_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_decks_session
                ON decks(session_id)
                """
            )
            conn.commit()

    def save(self, deck: DeckSpec) -> DeckSpec:
        self._init_db()
        refresh_deck_evidence_coverage(deck)
        now = time.time()
        payload = json.dumps(deck.model_dump(mode="json"), ensure_ascii=False)
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decks (deck_id, session_id, title, spec_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(deck_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    title = excluded.title,
                    spec_json = excluded.spec_json,
                    updated_at = excluded.updated_at
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
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT spec_json FROM decks WHERE deck_id = ?",
                (deck_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise KeyError(deck_id)
        return refresh_deck_evidence_coverage(DeckSpec.model_validate_json(row[0]))

    def list_recent(self, *, limit: int = 100) -> list[DeckSpec]:
        self._init_db()
        safe_limit = max(1, min(500, int(limit or 100)))
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                "SELECT deck_id FROM decks ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self.get(str(row[0] or "")) for row in rows if row and row[0]]

    def list_ids_by_session(self, session_id: str) -> list[str]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                "SELECT deck_id FROM decks WHERE session_id = ? ORDER BY updated_at DESC, created_at DESC",
                (normalized_session_id,),
            ).fetchall()
        return [str(row[0] or "") for row in rows if row and row[0]]

    def delete_by_session(self, session_id: str) -> int:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return 0

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM decks WHERE session_id = ?",
                (normalized_session_id,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
