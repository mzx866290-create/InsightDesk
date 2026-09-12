from __future__ import annotations

import logging
from typing import Any

from backend.stores.bookmark_store import delete_bookmarks_for_session
from backend.stores.chat_schema import init_bookmarks_table
from backend.stores.pg_session_store import PostgresSessionStore
from backend.stores.sqlite_runtime import connect_sqlite


class _ScriptedCursor:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.current: list[Any] = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        normalized_sql = " ".join(str(sql).split())
        self.state["executed"].append((normalized_sql, params))
        responses = self.state["responses"]
        self.current = list(responses.pop(0)) if responses else []
        self.rowcount = len(self.current)
        return self

    def fetchone(self):
        return self.current[0] if self.current else None

    def fetchall(self):
        return list(self.current)


class _ScriptedConnection:
    def __init__(self, state: dict[str, Any]):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _ScriptedCursor(self.state)

    def commit(self):
        self.state["commits"] += 1
        self.state["events"].append("postgres_commit")


def _build_store(
    monkeypatch,
    responses: list[list[Any]],
    *,
    legacy_bookmark_cleanup=None,
):
    state = {
        "responses": list(responses),
        "executed": [],
        "commits": 0,
        "events": [],
    }
    monkeypatch.setattr(PostgresSessionStore, "_init_db", lambda self: None)
    store = PostgresSessionStore(
        dsn="postgresql://example/db",
        connection_factory=lambda: _ScriptedConnection(state),
        legacy_bookmark_cleanup=legacy_bookmark_cleanup or (lambda _session_id: 0),
    )
    return store, state


def test_postgres_session_store_lists_and_builds_message_preview(monkeypatch):
    store, state = _build_store(
        monkeypatch,
        [
            [
                (
                    "session-1",
                    "Budget review",
                    1.0,
                    2.0,
                    3,
                    0,
                    1,
                    1,
                    2.0,
                    '["Finance"]',
                    "workspace-1",
                )
            ],
            [("session-1", "Please review the quarterly budget")],
        ],
    )

    sessions = store.get_all_sessions(
        query="budget",
        favorite=True,
        tag="finance",
        workspace_id="workspace-1",
    )

    assert sessions == [
        {
            "session_id": "session-1",
            "title": "Budget review",
            "created_at": 1.0,
            "updated_at": 2.0,
            "message_count": 3,
            "is_archived": False,
            "is_favorite": True,
            "is_pinned": True,
            "session_order": 2.0,
            "tags": ["Finance"],
            "workspace_id": "workspace-1",
            "search_preview": "Please review the quarterly budget",
            "search_source": "message",
        }
    ]
    first_sql, first_params = state["executed"][0]
    assert "EXISTS ( SELECT 1 FROM messages AS search_m" in first_sql
    assert first_params[-2:] == ("workspace-default", "workspace-1")


def test_postgres_session_store_truncates_messages_and_search_rows(monkeypatch):
    store, state = _build_store(
        monkeypatch,
        [
            [(10,)],
            [],
            [],
            [(11,), (12,)],
            [],
            [],
        ],
    )

    result = store.truncate_session_from_answer_group(
        "session-1",
        answer_group_id="turn-1",
        content="Updated question",
        images=[{"url": "data:image/png;base64,AA=="}],
    )

    assert result == {
        "session_id": "session-1",
        "answer_group_id": "turn-1",
        "anchor_message_id": 10,
        "deleted_count": 2,
    }
    executed_sql = [item[0] for item in state["executed"]]
    assert any(sql.startswith("INSERT INTO message_search") for sql in executed_sql)
    assert any(
        sql.startswith("DELETE FROM message_search WHERE rowid IN")
        for sql in executed_sql
    )
    assert state["commits"] == 1


def test_postgres_session_store_promotes_answer_and_syncs_search(monkeypatch):
    store, state = _build_store(
        monkeypatch,
        [
            [("panel-main",)],
            [
                (
                    20,
                    "Promoted answer",
                    "model-a",
                    '[{"title":"Doc"}]',
                    '[{"id":"node-1"}]',
                    '{"total_tokens":3}',
                    "task-1",
                    "web_research",
                )
            ],
            [],
            [(21,)],
            [],
            [],
        ],
    )

    result = store.promote_panel_answer("session-1", "turn-1", "panel-side")

    assert result == {
        "target_panel_id": "panel-main",
        "source_panel_id": "panel-side",
        "answer_group_id": "turn-1",
        "content": "Promoted answer",
        "model_id": "model-a",
        "sources": [{"title": "Doc"}],
        "workflow_nodes": [{"id": "node-1"}],
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 3,
            "estimated": False,
        },
        "task_id": "task-1",
        "task_type": "web_research",
    }
    executed_sql = [item[0] for item in state["executed"]]
    assert any(sql.startswith("INSERT INTO messages") for sql in executed_sql)
    assert any(sql.startswith("INSERT INTO message_search") for sql in executed_sql)
    assert state["commits"] == 1


def test_postgres_session_store_updates_reorders_and_deletes(monkeypatch):
    updated_row = (
        "session-1",
        "Renamed",
        1.0,
        3.0,
        0,
        0,
        0,
        0,
        0.0,
        '["One"]',
        "workspace-1",
    )
    store, state = _build_store(
        monkeypatch,
        [
            [(1,)],
            [],
            [updated_row],
            [("session-1", "workspace-1"), ("session-2", "workspace-1")],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ],
    )

    updated = store.update_session_meta(
        "session-1",
        title="Renamed",
        tags=["One", "one"],
    )
    reordered = store.reorder_sessions(
        ["session-1", "session-2"],
        workspace_id="workspace-1",
    )
    store.delete_session("session-1")

    assert updated is not None
    assert updated["title"] == "Renamed"
    assert updated["tags"] == ["One"]
    assert reordered == {
        "count": 2,
        "orders": [
            {"session_id": "session-1", "session_order": 2.0},
            {"session_id": "session-2", "session_order": 1.0},
        ],
    }
    delete_sql = [
        sql for sql, _ in state["executed"] if sql.startswith("DELETE FROM")
    ]
    assert delete_sql[-6:] == [
        "DELETE FROM message_search WHERE session_id = %s",
        "DELETE FROM messages WHERE session_id = %s",
        "DELETE FROM session_panels WHERE session_id = %s",
        "DELETE FROM session_memory WHERE session_id = %s",
        "DELETE FROM retrieval_feedback WHERE session_id = %s",
        "DELETE FROM sessions WHERE session_id = %s",
    ]


def test_postgres_session_store_reassigns_workspace_sessions(monkeypatch):
    store, state = _build_store(
        monkeypatch,
        [[("session-1",), ("session-2",)], []],
    )

    moved_count = store.reassign_workspace_sessions(
        "workspace-source",
        "workspace-target",
    )

    assert moved_count == 2
    assert state["commits"] == 1
    assert state["executed"][0][0].startswith("UPDATE sessions SET workspace_id")
    assert state["executed"][0][1][0] == "workspace-target"
    assert state["executed"][0][1][-1] == "workspace-source"
    assert state["executed"][1] == (
        "DELETE FROM workspaces WHERE workspace_id = %s",
        ("workspace-source",),
    )


def test_postgres_session_store_cleans_legacy_bookmarks_after_commit(monkeypatch):
    cleanup_calls: list[str] = []
    state_ref: dict[str, Any] = {}

    def cleanup(session_id: str) -> int:
        cleanup_calls.append(session_id)
        state_ref["state"]["events"].append("bookmark_cleanup")
        return 2

    store, state = _build_store(
        monkeypatch,
        [[], [], [], [], [], []],
        legacy_bookmark_cleanup=cleanup,
    )
    state_ref["state"] = state

    store.delete_session("session-1")

    assert cleanup_calls == ["session-1"]
    assert state["commits"] == 1
    assert state["events"] == ["postgres_commit", "bookmark_cleanup"]


def test_postgres_session_delete_keeps_success_when_bookmark_cleanup_fails(
    monkeypatch,
    caplog,
):
    def cleanup(_session_id: str) -> int:
        raise RuntimeError("sqlite unavailable")

    store, state = _build_store(
        monkeypatch,
        [[], [], [], [], [], []],
        legacy_bookmark_cleanup=cleanup,
    )

    with caplog.at_level(logging.ERROR, logger="backend.stores.pg_session_store"):
        store.delete_session("session-1")

    assert state["commits"] == 1
    assert "failed to clean legacy bookmarks" in caplog.text


def test_delete_bookmarks_for_session_preserves_other_sessions(tmp_path):
    db_path = str(tmp_path / "bookmarks.db")
    with connect_sqlite(db_path) as conn:
        init_bookmarks_table(conn)
        conn.executemany(
            """
            INSERT INTO bookmarks (
                id, session_id, role, content, created_at, updated_at
            ) VALUES (?, ?, 'assistant', 'saved', 1, 1)
            """,
            [
                ("bookmark-1", "session-1"),
                ("bookmark-2", "session-1"),
                ("bookmark-3", "session-2"),
            ],
        )
        conn.commit()

    assert delete_bookmarks_for_session("session-1", db_path=db_path) == 2

    with connect_sqlite(db_path) as conn:
        remaining = conn.execute(
            "SELECT id, session_id FROM bookmarks ORDER BY id"
        ).fetchall()
    assert remaining == [("bookmark-3", "session-2")]
