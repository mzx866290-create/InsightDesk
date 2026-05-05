"""PostgreSQL app config store adapter."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from backend.stores.config_store import SQLiteAppConfigStore, StoredConfigValue
from backend.stores.pg_base import PostgresStoreMixin


class PostgresAppConfigStore(PostgresStoreMixin, SQLiteAppConfigStore):
    """Persist app config values in PostgreSQL while reusing local encryption."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self._master_key = self._load_master_key()
        self._init_db()

    def _default_master_key_path(self) -> Path:
        configured = str(os.getenv("APP_CONFIG_MASTER_KEY_PATH") or "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path(os.getenv("APP_CONFIG_KEY_PATH") or ".app_config.key").expanduser()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_config (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT '',
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_app_config_updated_at
                    ON app_config(updated_at DESC)
                    """
                )
            conn.commit()

    def get(self, key: str) -> StoredConfigValue | None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT key, value, updated_at FROM app_config WHERE key = %s",
                    (normalized_key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return StoredConfigValue(
            key=str(self._row_value(row, 0, "key") or ""),
            value=self._decrypt_value(str(self._row_value(row, 1, "value") or "")),
            updated_at=float(self._row_value(row, 2, "updated_at") or 0.0),
        )

    def set(self, key: str, value: str) -> StoredConfigValue:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise ValueError("config key must not be empty")
        normalized_value = str(value or "").strip()
        updated_at = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_config(key, value, updated_at)
                    VALUES(%s, %s, %s)
                    ON CONFLICT(key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (normalized_key, self._encrypt_value(normalized_value), updated_at),
                )
            conn.commit()
        return StoredConfigValue(
            key=normalized_key,
            value=normalized_value,
            updated_at=updated_at,
        )

    def delete(self, key: str) -> bool:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return False
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM app_config WHERE key = %s", (normalized_key,))
                deleted = int(cursor.rowcount or 0) > 0
            conn.commit()
        return deleted
