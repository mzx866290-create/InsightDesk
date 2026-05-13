import sqlite3

from backend.stores.config_store import (
    SQLiteAppConfigStore,
    append_mcp_runtime_health_history,
    mcp_runtime_health_history_limit,
    read_mcp_runtime_health_history,
    sanitize_mcp_runtime_health_history_item,
)


def test_app_config_store_encrypts_values_at_rest(tmp_path, monkeypatch):
    db_path = tmp_path / "chat_history.db"
    key_path = tmp_path / ".app_config.key"
    monkeypatch.setenv("APP_CONFIG_MASTER_KEY_PATH", str(key_path))

    store = SQLiteAppConfigStore(db_path=str(db_path))
    store.set("tavily_api_key", "tvly-secret-key")

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            ("tavily_api_key",),
        ).fetchone()

    assert row is not None
    assert row[0] != "tvly-secret-key"
    assert str(row[0]).startswith("enc:v1:")
    assert store.get_value("tavily_api_key") == "tvly-secret-key"


def test_app_config_store_reads_legacy_plaintext_values(tmp_path, monkeypatch):
    db_path = tmp_path / "chat_history.db"
    key_path = tmp_path / ".app_config.key"
    monkeypatch.setenv("APP_CONFIG_MASTER_KEY_PATH", str(key_path))

    store = SQLiteAppConfigStore(db_path=str(db_path))
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO app_config(key, value, updated_at) VALUES(?, ?, ?)",
            ("tavily_api_key", "legacy-plain-text", 1.0),
        )
        conn.commit()

    assert store.get_value("tavily_api_key") == "legacy-plain-text"


def test_mcp_runtime_health_history_helpers_sanitize_and_limit(tmp_path, monkeypatch):
    db_path = tmp_path / "chat_history.db"
    key_path = tmp_path / ".app_config.key"
    monkeypatch.setenv("APP_CONFIG_MASTER_KEY_PATH", str(key_path))

    store = SQLiteAppConfigStore(db_path=str(db_path))
    snapshot = {
        "timestamp": "123.5",
        "status": "warning",
        "summary": {
            "total": "2",
            "healthy": 1,
            "unhealthy": 1,
            "tool_count": 4,
            "status_counts": {"ok": 1, "error": 1},
            "alert_count": 1,
            "unhealthy_connectors": ["github"],
            "slow_connectors": ["notion"],
        },
        "servers": [
            {
                "name": "github",
                "status": "error",
                "healthy": False,
                "tool_count": "3",
                "duration_ms": "42.5",
                "error": "token missing",
                "secret": "must-not-leak",
            }
        ],
    }

    assert mcp_runtime_health_history_limit("999") == 200
    assert mcp_runtime_health_history_limit("bad") == 20
    assert sanitize_mcp_runtime_health_history_item("bad") is None

    history = append_mcp_runtime_health_history(store, snapshot, limit=1)
    loaded = read_mcp_runtime_health_history(store, limit=5)

    assert history == loaded
    assert loaded[0]["timestamp"] == 123.5
    assert loaded[0]["summary"]["total"] == 2
    assert loaded[0]["servers"][0] == {
        "name": "github",
        "status": "error",
        "healthy": False,
        "tool_count": 3,
        "duration_ms": 42.5,
        "error": "token missing",
    }
