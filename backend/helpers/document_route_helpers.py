"""Route-level helpers for document endpoints."""

from typing import Any, Awaitable, Callable, Optional

from fastapi import HTTPException


async def upload_documents_result(
    *,
    request: Any,
    files: list[Any],
    vector_store_path: Optional[str],
    effective_vector_store_path: Callable[[Optional[str]], str],
    stage_upload_files: Callable[..., Awaitable[Any]],
    build_upload_documents_task_record: Callable[..., Any],
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    prune_task_records_locked: Callable[..., None],
    persist_task_record: Callable[[Any], None],
    prune_persisted_tasks: Callable[[], None],
    dispatch_existing_task_record: Callable[[Any], Awaitable[str]],
    logger: Any,
    audit_security_event: Callable[..., Any],
    upload_documents_response: Callable[..., dict[str, Any]],
    cleanup_temp_paths: Callable[[list[str]], None],
    document_upload_max_count: int,
    document_upload_max_file_bytes: int,
    document_upload_max_total_bytes: int,
) -> dict[str, Any]:
    temp_paths: list[str] = []
    try:
        resolved_vector_store_path = effective_vector_store_path(vector_store_path)
        temp_paths, file_names = await stage_upload_files(
            files,
            max_file_count=document_upload_max_count,
            max_file_bytes=document_upload_max_file_bytes,
            max_total_bytes=document_upload_max_total_bytes,
        )
        record = build_upload_documents_task_record(
            temp_paths=temp_paths,
            file_names=file_names,
            vector_store_path=resolved_vector_store_path,
        )
        task_state = resolve_tasks()
        async with tasks_lock:
            task_state[record.task_id] = record
            prune_task_records_locked(record.created_at)
        persist_task_record(record)
        prune_persisted_tasks()
        await dispatch_existing_task_record(record)
        logger.info(
            "task_id=%s task_type=upload_documents created",
            record.task_id,
        )
        audit_security_event(
            "upload_documents",
            request,
            details=(
                f"file_count={len(file_names)} "
                f"vector_store_path={resolved_vector_store_path}"
            ),
        )
        return upload_documents_response(
            record,
            file_count=len(file_names),
            vector_store_path=resolved_vector_store_path,
        )
    except ValueError as exc:
        if temp_paths:
            cleanup_temp_paths(temp_paths)
        audit_security_event(
            "upload_documents",
            request,
            result="rejected",
            details=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if temp_paths:
            cleanup_temp_paths(temp_paths)
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def document_stats_payload(
    *,
    request: Any,
    path: Optional[str],
    effective_vector_store_path: Callable[[Optional[str]], str],
    doc_pipeline_factory: Callable[..., Any],
    audit_security_event: Callable[..., Any],
) -> dict[str, Any]:
    pipeline = doc_pipeline_factory(vector_store_path=effective_vector_store_path(path))
    try:
        pipeline.load_store()
        stats: dict[str, Any] = dict(pipeline.get_stats())
        stats.setdefault("store_path", pipeline.vector_store_path)
        audit_security_event(
            "get_document_stats",
            request,
            details=f"path={pipeline.vector_store_path}",
        )
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


__all__ = [
    "document_stats_payload",
    "upload_documents_result",
]
