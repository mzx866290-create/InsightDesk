import asyncio
import os
import tempfile
from typing import Any, Awaitable, Callable

from api_task_store import TaskRecord


async def run_analyze_knowledge_base_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    effective_vector_store_path: Callable[[str | None], str],
) -> None:
    from doc_pipeline import DocPipeline

    vector_store_path = effective_vector_store_path(
        str(record.params.get("vector_store_path") or "").strip() or None
    )
    pipeline = DocPipeline(vector_store_path=vector_store_path)

    await set_progress(30)
    await asyncio.sleep(0)
    pipeline.load_store()
    stats = pipeline.get_stats()
    await set_progress(80)

    total = stats.get("total_docs", 0)
    store_path = stats.get("store_path", vector_store_path)
    record.result = f"知识库分析完成。共 {total} 个文档片段，存储路径：{store_path}"


async def run_generate_report_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
) -> None:
    from chat_store import SQLiteChatMessageHistory

    session_id = record.session_id or "default"
    history = SQLiteChatMessageHistory(session_id=session_id)

    await set_progress(40)
    messages = list(history.messages)
    msg_count = len(messages)
    await set_progress(90)

    record.result = f"报告生成完成。当前会话共 {msg_count} 条消息记录。"


async def run_upload_documents_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    update_progress: Callable[[TaskRecord, int], None],
    effective_vector_store_path: Callable[[str | None], str],
    clear_agent_cache: Callable[[], Awaitable[None]],
    logger: Any,
) -> None:
    from doc_pipeline import DocPipeline

    file_paths = [str(p) for p in record.params.get("temp_paths", []) if p]
    original_names = [str(n) for n in record.params.get("file_names", []) if n]

    if not file_paths:
        raise ValueError("未找到可导入的临时文件")

    vector_store_path = effective_vector_store_path(
        str(record.params.get("vector_store_path") or "").strip() or None
    )
    pipeline = DocPipeline(vector_store_path=vector_store_path)

    await set_progress(15)
    count = await asyncio.to_thread(
        pipeline.ingest,
        file_paths,
        lambda progress: update_progress(record, progress),
    )

    for temp_path in file_paths:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("task_id=%s 临时文件删除失败: %s", record.task_id, temp_path)

    uploaded_count = len(original_names) or len(file_paths)
    record.result = (
        f"已导入 {uploaded_count} 个文件，共 {count} 个文档片段，知识库路径：{vector_store_path}"
    )
    await clear_agent_cache()


async def run_promote_attachment_to_kb_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    update_progress: Callable[[TaskRecord, int], None],
    effective_vector_store_path: Callable[[str | None], str],
    chat_file_suffix: Callable[[str], str],
    decode_data_url: Callable[[str, str], bytes],
    clear_agent_cache: Callable[[], Awaitable[None]],
    logger: Any,
) -> None:
    from doc_pipeline import DocPipeline

    attachment_name = str(record.params.get("attachment_name") or "").strip()
    attachment_data_url = str(record.params.get("attachment_data_url") or "").strip()
    attachment_kind = str(record.params.get("attachment_kind") or "").strip()

    if attachment_kind != "file":
        raise ValueError("Only file attachments can be promoted to the knowledge base.")
    if not attachment_name or not attachment_data_url:
        raise ValueError("Attachment payload is incomplete.")

    suffix = chat_file_suffix(attachment_name)
    payload = decode_data_url(attachment_data_url, attachment_name)
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        vector_store_path = effective_vector_store_path(
            str(record.params.get("vector_store_path") or "").strip() or None
        )
        pipeline = DocPipeline(vector_store_path=vector_store_path)

        await set_progress(15)
        count = await asyncio.to_thread(
            pipeline.ingest,
            [temp_path],
            lambda progress: update_progress(record, progress),
        )

        record.result = (
            f"Attachment {attachment_name} has been added to the knowledge base. "
            f"Chunks: {count}. Path: {vector_store_path}"
        )
        await clear_agent_cache()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning(
                "task_id=%s failed to delete promoted attachment temp file: %s",
                record.task_id,
                temp_path,
            )


async def run_placeholder_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
) -> None:
    for pct in (20, 50, 80):
        await asyncio.sleep(0.5)
        await set_progress(pct)
    record.result = f"任务 '{record.task_type}' 已完成（通用执行路径）"
