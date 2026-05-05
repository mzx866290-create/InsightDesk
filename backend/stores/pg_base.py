"""Shared PostgreSQL adapter helpers."""

from __future__ import annotations

from typing import Any, Callable

from backend.core.storage_runtime import postgres_dsn


class PostgresStoreMixin:
    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.dsn = str(dsn or postgres_dsn()).strip()
        self._connection_factory = connection_factory
        if not self.dsn and self._connection_factory is None:
            raise ValueError("PostgreSQL store requires DATABASE_URL or POSTGRES_DSN.")

    def _connect(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "DATABASE_PROVIDER=postgres requires psycopg. "
                "Install project requirements before enabling PostgreSQL."
            ) from exc
        return psycopg.connect(self.dsn)

    @staticmethod
    def _row_value(row: Any, index: int, key: str) -> Any:
        if row is None:
            return None
        if isinstance(row, dict):
            return row.get(key)
        return row[index]
