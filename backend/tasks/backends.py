"""Task queue backend abstraction for persisted task records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from backend.stores.task_store import TaskRecord
from backend.tasks.enqueue import enqueue_arq_task
from backend.tasks.settings import TaskBackendName, normalize_task_backend

RunTask = Callable[[TaskRecord], Awaitable[None]]
SpawnBackgroundTask = Callable[[Awaitable[None]], Any]
ExternalTaskEnqueue = Callable[[TaskRecord], Awaitable[Any]]


class TaskQueueBackend(Protocol):
    name: TaskBackendName

    async def enqueue(
        self,
        record: TaskRecord,
        *,
        run_task: RunTask,
        spawn_background_task: SpawnBackgroundTask,
    ) -> Any:
        """Dispatch a persisted task record to the configured backend."""


@dataclass(slots=True)
class MemoryTaskQueueBackend:
    """Local development backend using the current event loop."""

    name: TaskBackendName = "memory"

    async def enqueue(
        self,
        record: TaskRecord,
        *,
        run_task: RunTask,
        spawn_background_task: SpawnBackgroundTask,
    ) -> Any:
        return spawn_background_task(run_task(record))


@dataclass(slots=True)
class ArqTaskQueueBackend:
    """Redis/ARQ backend for out-of-process workers."""

    enqueue_external_task: ExternalTaskEnqueue | None = None
    name: TaskBackendName = "arq"

    async def enqueue(
        self,
        record: TaskRecord,
        *,
        run_task: RunTask,
        spawn_background_task: SpawnBackgroundTask,
    ) -> Any:
        enqueue = self.enqueue_external_task or enqueue_arq_task
        return await enqueue(record)


def build_task_queue_backend(
    task_backend: str | None = None,
    *,
    enqueue_external_task: ExternalTaskEnqueue | None = None,
) -> TaskQueueBackend:
    backend = normalize_task_backend(task_backend)
    if backend == "arq":
        return ArqTaskQueueBackend(enqueue_external_task=enqueue_external_task)
    return MemoryTaskQueueBackend()


async def dispatch_task_record(
    record: TaskRecord,
    *,
    task_backend: str | None = None,
    run_task: RunTask,
    spawn_background_task: SpawnBackgroundTask,
    enqueue_external_task: ExternalTaskEnqueue | None = None,
) -> TaskBackendName:
    backend = build_task_queue_backend(
        task_backend,
        enqueue_external_task=enqueue_external_task,
    )
    await backend.enqueue(
        record,
        run_task=run_task,
        spawn_background_task=spawn_background_task,
    )
    return backend.name
