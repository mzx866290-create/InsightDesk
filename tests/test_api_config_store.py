import sqlite3

from backend.stores.config_store import SQLiteAppConfigStore


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
