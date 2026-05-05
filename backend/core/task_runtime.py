"""Task state-machine runtime helpers.

The API server module is passed as ``ctx`` while this large task orchestration
block is split out of the entrypoint.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.schemas.api_models import CreateTaskRequest
    from backend.stores import SQLiteTaskStore, TaskRecord, TaskStatus


def _update_task_progress(ctx, record: TaskRecord, progress: int) -> None:
    """线程安全之外的轻量进度更新，供同步处理阶段回调使用。"""
    if record.task_id in ctx._suppressed_task_ids:
        return
    record.progress = max(0, min(100, progress))
    record.updated_at = ctx.time.time()
    ctx._persist_task_record(record)


async def _drop_suppressed_task(ctx, record: TaskRecord) -> bool:
    if record.task_id not in ctx._suppressed_task_ids:
        return False
    async with ctx._tasks_lock:
        ctx._tasks.pop(record.task_id, None)
        ctx._prune_task_records_locked()
    return True


async def _create_inline_task_record(
    ctx,
    task_type: str,
    params: dict[str, Any],
    *,
    session_id: Optional[str] = None,
    progress: int = 10,
) -> TaskRecord:
    return await ctx.create_inline_task_record(
        ctx._tasks,
        ctx._tasks_lock,
        task_type=task_type,
        params=params,
        session_id=session_id,
        progress=progress,
        prune_in_memory=ctx._prune_task_records_locked,
        persist_record=ctx._persist_task_record,
        prune_persisted=ctx._prune_persisted_tasks,
    )


async def _set_inline_task_state(
    ctx,
    record: TaskRecord,
    *,
    status: TaskStatus,
    progress: Optional[int] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> TaskRecord:
    if record.task_id in ctx._suppressed_task_ids:
        async with ctx._tasks_lock:
            ctx._tasks.pop(record.task_id, None)
            ctx._prune_task_records_locked()
        record.status = status
        record.updated_at = ctx.time.time()
        if progress is not None:
            record.progress = max(0, min(100, progress))
        if result is not None:
            record.result = result
        if error is not None:
            record.error = error
        return record
    return await ctx.set_inline_task_state(
        ctx._tasks,
        ctx._tasks_lock,
        record=record,
        status=status,
        progress=progress,
        result=result,
        error=error,
        prune_in_memory=ctx._prune_task_records_locked,
        persist_record=ctx._persist_task_record,
        prune_persisted=ctx._prune_persisted_tasks,
    )


def _is_deep_research_task(ctx, record: TaskRecord) -> bool:
    return (
        str(record.task_type or "").strip() == "web_research"
        and str(record.params.get("research_mode") or "").strip().lower() == "deep"
    )


def _get_deep_research_semaphore(ctx) -> asyncio.Semaphore:
    loop = ctx.asyncio.get_running_loop()
    loop_key = id(loop)
    with ctx._deep_research_semaphore_lock:
        semaphore = ctx._deep_research_semaphores.get(loop_key)
        if semaphore is None:
            semaphore = ctx.asyncio.Semaphore(ctx.DEEP_RESEARCH_MAX_CONCURRENCY)
            ctx._deep_research_semaphores[loop_key] = semaphore
        return semaphore


def _get_task_store(ctx) -> SQLiteTaskStore:
    if ctx._task_store is None:
        with ctx._task_store_init_lock:
            if ctx._task_store is None:
                ctx._task_store = ctx.create_task_store(
                    history_limit=ctx.TASK_HISTORY_LIMIT,
                    ttl_seconds=ctx.TASK_HISTORY_TTL_SECONDS,
                )
    return ctx._task_store


def _persist_task_record(ctx, record: TaskRecord) -> None:
    if record.task_id in ctx._suppressed_task_ids:
        ctx.logger.info("Skip persisting suppressed task record: %s", record.task_id)
        return
    try:
        ctx._get_task_store().save(record)
    except Exception:
        ctx.logger.exception("Failed to persist task record: %s", record.task_id)


def _prune_persisted_tasks(ctx) -> None:
    try:
        ctx._get_task_store().prune()
    except Exception:
        ctx.logger.exception("Failed to prune persisted task records")


def _prune_task_records_locked(ctx, now: float | None = None) -> None:
    """Prune expired and excess terminal tasks while holding _tasks_lock."""
    ctx.prune_task_records(
        ctx._tasks,
        history_limit=ctx.TASK_HISTORY_LIMIT,
        ttl_seconds=ctx.TASK_HISTORY_TTL_SECONDS,
        now=now,
        logger=ctx.logger,
    )


async def _run_task(ctx, record: TaskRecord) -> None:
    """后台执行任务并更新状态"""
    deep_research_slot: ctx.asyncio.Semaphore | None = None
    deep_research_acquired = False
    try:
        if ctx._is_deep_research_task(record):
            deep_research_slot = ctx._get_deep_research_semaphore()
            await deep_research_slot.acquire()
            deep_research_acquired = True
        async with ctx._tasks_lock:
            ctx._prune_task_records_locked()
            record.status = ctx.TaskStatus.RUNNING
            record.updated_at = ctx.time.time()
            record.progress = 10
        if await ctx._drop_suppressed_task(record):
            return
        ctx._persist_task_record(record)
        task_type = record.task_type

        async def _set_progress(progress: int) -> None:
            if await ctx._drop_suppressed_task(record):
                return
            async with ctx._tasks_lock:
                record.progress = progress
                record.updated_at = ctx.time.time()
            ctx._persist_task_record(record)

        if task_type == "analyze_knowledge_base":
            await ctx.run_analyze_knowledge_base_task(
                record,
                set_progress=_set_progress,
                effective_vector_store_path=ctx._effective_vector_store_path,
            )
        elif task_type == "generate_report":
            await ctx.run_generate_report_task(
                record,
                set_progress=_set_progress,
                resolve_report_messages=ctx._resolve_report_messages,
                ensure_deckable_chat=ctx.ensure_deckable_chat,
                build_chat_report_title=ctx.build_chat_report_title,
                build_report_markdown=ctx.build_report_markdown,
                build_report_artifact=ctx.build_report_artifact,
                save_artifact=ctx._artifact_store.save,
            )
        elif task_type == "generate_deck":
            await ctx.run_generate_deck_task(
                record,
                set_progress=_set_progress,
                resolve_report_messages=ctx._resolve_report_messages,
                normalize_model_config=ctx._resolve_runtime_model_config,
                resolve_active_prompt_runtime=ctx._resolve_active_prompt_runtime,
                build_deck=ctx.build_deck,
                save_deck=ctx._deck_store.save,
                build_deck_artifact=ctx.build_deck_artifact,
                save_artifact=ctx._artifact_store.save,
            )
        elif task_type == "upload_documents":
            await ctx.run_upload_documents_task(
                record,
                set_progress=_set_progress,
                update_progress=ctx._update_task_progress,
                effective_vector_store_path=ctx._effective_vector_store_path,
                clear_agent_cache=ctx._clear_agent_cache,
                logger=ctx.logger,
            )
        elif task_type == "promote_attachment_to_kb":
            await ctx.run_promote_attachment_to_kb_task(
                record,
                set_progress=_set_progress,
                update_progress=ctx._update_task_progress,
                effective_vector_store_path=ctx._effective_vector_store_path,
                chat_file_suffix=ctx._chat_file_suffix,
                decode_data_url=ctx._decode_data_url,
                clear_agent_cache=ctx._clear_agent_cache,
                logger=ctx.logger,
            )
        elif task_type == "web_research":
            from backend.services.agent_core import get_llm

            await ctx.run_web_research_task(
                record,
                set_progress=_set_progress,
                normalize_model_config=ctx._resolve_runtime_model_config,
                create_llm=get_llm,
            )
        elif task_type == "multi_agent_workflow":
            from backend.services.agent_core import get_llm

            await ctx.run_multi_agent_workflow_task(
                record,
                set_progress=_set_progress,
                normalize_model_config=ctx._resolve_runtime_model_config,
                create_llm=get_llm,
                build_research_archive_artifact=ctx.build_research_archive_artifact,
                save_artifact=ctx._artifact_store.save,
                load_integrator_connectors=lambda: ctx.load_integrator_connectors(
                    ctx._get_app_config_store()
                ),
            )
        else:
            await ctx.run_placeholder_task(record, set_progress=_set_progress)
        if await ctx._drop_suppressed_task(record):
            return
        workflow_status = str(record.params.get("workflow_status") or "").strip().lower()
        if task_type == "multi_agent_workflow" and workflow_status == "waiting_approval":
            async with ctx._tasks_lock:
                record.status = ctx.TaskStatus.WAITING_APPROVAL
                record.progress = max(record.progress, 80)
                record.updated_at = ctx.time.time()
                ctx._prune_task_records_locked(record.updated_at)
            ctx._persist_task_record(record)
            ctx._prune_persisted_tasks()
            return
        async with ctx._tasks_lock:
            record.status = ctx.TaskStatus.COMPLETED
            record.progress = 100
            record.updated_at = ctx.time.time()
            ctx._prune_task_records_locked(record.updated_at)
        ctx._persist_task_record(record)
        ctx._prune_persisted_tasks()
    except Exception as exc:
        ctx.logger.exception(
            "task_id=%s task_type=%s 执行失败", record.task_id, record.task_type
        )
        if record.task_type == "upload_documents":
            for temp_path in record.params.get("temp_paths", []):
                try:
                    ctx.os.remove(str(temp_path))
                except OSError:
                    pass
        if await ctx._drop_suppressed_task(record):
            return
        async with ctx._tasks_lock:
            record.status = ctx.TaskStatus.FAILED
            record.error = str(exc)
            record.updated_at = ctx.time.time()
            ctx._prune_task_records_locked(record.updated_at)
        ctx._persist_task_record(record)
        if record.task_type == "web_research":
            ctx.persist_web_research_task_result(
                record, content=f"联网研究任务失败：{record.error}", sources=[]
            )
        ctx._prune_persisted_tasks()
    finally:
        if deep_research_slot is not None and deep_research_acquired:
            deep_research_slot.release()


async def create_task(ctx, request: CreateTaskRequest) -> dict[str, Any]:
    """Backward-compatible task creation entrypoint used by tests and scripts."""
    return await ctx.enqueue_task(
        ctx._tasks,
        ctx._tasks_lock,
        task_type=request.task_type,
        params=request.params,
        session_id=request.session_id,
        prune_in_memory=ctx._prune_task_records_locked,
        persist_record=ctx._persist_task_record,
        prune_persisted=ctx._prune_persisted_tasks,
        run_task=ctx._run_task,
        spawn_background_task=ctx.asyncio.create_task,
        logger=ctx.logger,
        task_backend=getattr(ctx, "TASK_BACKEND", None),
        enqueue_external_task=getattr(ctx, "enqueue_external_task", None),
        on_record_created=ctx.persist_web_research_task_placeholder
        if request.task_type == "web_research"
        else None,
    )


async def get_task(ctx, task_id: str) -> dict[str, Any]:
    """Backward-compatible task lookup entrypoint used by tests and scripts."""
    async with ctx._tasks_lock:
        ctx._prune_task_records_locked()
        record = ctx._tasks.get(task_id)
    if record is None:
        ctx._prune_persisted_tasks()
        record = ctx._get_task_store().get(task_id)
    if record is None:
        raise ctx.HTTPException(status_code=404, detail="Task was not found.")
    return ctx.task_record_payload(record)


async def list_tasks(ctx, limit: int = 20) -> dict[str, Any]:
    """Backward-compatible task listing entrypoint used by tests and scripts."""
    async with ctx._tasks_lock:
        ctx._prune_task_records_locked()
        in_memory_tasks = list(ctx._tasks.values())
    ctx._prune_persisted_tasks()
    queue_health = None
    runtime_config = None
    if getattr(ctx, "TASK_BACKEND", "memory") in {"arq", "redis"}:
        queue_health = await ctx.arq_queue_health_payload()
        from backend.tasks.registry import arq_runtime_config_payload

        runtime_config = arq_runtime_config_payload()
    return ctx.list_tasks_payload(
        in_memory_tasks=in_memory_tasks,
        persisted_tasks=ctx._get_task_store().list_recent(
            limit=max(limit, ctx.TASK_HISTORY_LIMIT)
        ),
        limit=limit,
        queue_health=queue_health,
        runtime_config=runtime_config,
    )
