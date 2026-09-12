from __future__ import annotations

import pytest

from backend.stores import factory, workspace_store
from backend.stores.chat_normalization import DEFAULT_WORKSPACE_ID
from backend.stores.chat_schema import init_sessions_table
from backend.stores.sqlite_runtime import connect_sqlite


class _FakePostgresSessionStore:
    def __init__(self, *, moved_count: int = 0, error: Exception | None = None):
        self.moved_count = moved_count
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def reassign_workspace_sessions(
        self,
        source_workspace_id: str,
        target_workspace_id: str,
    ) -> int:
        self.calls.append((source_workspace_id, target_workspace_id))
        if self.error is not None:
            raise self.error
        return self.moved_count


def _configure_postgres_workspace_runtime(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    return db_path


def _create_workspace_session(db_path, workspace_id: str) -> None:
    with connect_sqlite(str(db_path)) as conn:
        init_sessions_table(conn)
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, created_at, updated_at, title, workspace_id
            ) VALUES ('legacy-session', 1, 1, 'Legacy', ?)
            """,
            (workspace_id,),
        )
        conn.commit()


def test_delete_workspace_reassigns_postgres_and_legacy_sqlite_sessions(
    monkeypatch,
    tmp_path,
):
    db_path = _configure_postgres_workspace_runtime(monkeypatch, tmp_path)
    source = workspace_store.create_workspace("Source", activate=True)
    _create_workspace_session(db_path, source["workspace_id"])
    postgres_store = _FakePostgresSessionStore(moved_count=2)
    monkeypatch.setattr(factory, "create_session_store", lambda: postgres_store)

    result = workspace_store.delete_workspace(source["workspace_id"])

    assert result is not None
    assert result["migrated_postgres_sessions"] == 2
    assert postgres_store.calls == [(source["workspace_id"], DEFAULT_WORKSPACE_ID)]
    assert workspace_store.get_workspace(source["workspace_id"]) is None
    with connect_sqlite(str(db_path)) as conn:
        workspace_id = conn.execute(
            "SELECT workspace_id FROM sessions WHERE session_id = 'legacy-session'"
        ).fetchone()[0]
    assert workspace_id == DEFAULT_WORKSPACE_ID


def test_delete_workspace_aborts_when_postgres_migration_fails(monkeypatch, tmp_path):
    db_path = _configure_postgres_workspace_runtime(monkeypatch, tmp_path)
    source = workspace_store.create_workspace("Source", activate=True)
    _create_workspace_session(db_path, source["workspace_id"])
    postgres_store = _FakePostgresSessionStore(error=RuntimeError("postgres unavailable"))
    monkeypatch.setattr(factory, "create_session_store", lambda: postgres_store)

    with pytest.raises(RuntimeError, match="postgres unavailable"):
        workspace_store.delete_workspace(source["workspace_id"])

    assert workspace_store.get_workspace(source["workspace_id"]) is not None
    with connect_sqlite(str(db_path)) as conn:
        workspace_id = conn.execute(
            "SELECT workspace_id FROM sessions WHERE session_id = 'legacy-session'"
        ).fetchone()[0]
    assert workspace_id == source["workspace_id"]
