"""Public seam between the arq worker and the API-server task runtime.

Task state (stores, caches, semaphores) currently lives on the api_server
module; the worker needs exactly two operations from it. This bridge is the
single documented access point -- when the state moves into
backend.core.task_runtime, only this module changes.
"""

from __future__ import annotations

import importlib
from typing import Any


def load_task_store() -> Any:
    """Return the API server's configured task store singleton."""
    api_server = importlib.import_module("backend.api_server")
    return api_server._get_task_store()


async def execute_task_record(record: Any) -> None:
    """Execute a persisted task record through the API server runtime."""
    api_server = importlib.import_module("backend.api_server")
    await api_server._run_task(record)
