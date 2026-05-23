"""Shared SQLite connection helper for local store adapters."""

from __future__ import annotations

import sqlite3

from backend.core.storage_runtime import app_database_path, ensure_sqlite_parent

SQLITE_TIMEOUT_SECONDS = 5
SQLITE_BUSY_TIMEOUT_MS = 5000


def connect_sqlite(db_path: str | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with the project's default safety settings."""
    resolved_db_path = str(db_path or app_database_path()).strip()
    ensure_sqlite_parent(resolved_db_path)
    conn = sqlite3.connect(resolved_db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


__all__ = ["SQLITE_BUSY_TIMEOUT_MS", "SQLITE_TIMEOUT_SECONDS", "connect_sqlite"]
