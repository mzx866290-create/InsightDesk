"""Document upload and report helper utilities."""

import os
import tempfile
import time
import uuid
from typing import Any, Callable, Iterable

from backend.stores.task_store import TaskRecord, TaskStatus


DEFAULT_UPLOAD_ALLOWED_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xls",
    ".xlsx",
}
DEFAULT_UPLOAD_MAX_FILE_COUNT = 20
DEFAULT_UPLOAD_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_UPLOAD_MAX_TOTAL_BYTES = 100 * 1024 * 1024


def upload_file_suffix(name: str | None) -> str:
    if not name:
        return ""
    base_name = name.replace("\\", "/").split("/")[-1]
    _, ext = os.path.splitext(base_name)
    return ext


def cleanup_temp_paths(paths: Iterable[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            continue


def ensure_upload_staging_dir(staging_dir: Any | None) -> str | None:
    if staging_dir is None:
        return None
    normalized = os.fspath(staging_dir).strip()
    if not normalized:
        return None
    os.makedirs(normalized, exist_ok=True)
    return normalized


async def stage_upload_files(
    files: list[Any],
    *,
    allowed_suffixes: set[str] | None = None,
    max_file_count: int = DEFAULT_UPLOAD_MAX_FILE_COUNT,
    max_file_bytes: int = DEFAULT_UPLOAD_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_UPLOAD_MAX_TOTAL_BYTES,
    staging_dir: Any | None = None,
) -> tuple[list[str], list[str]]:
    return await stage_upload_files_with_limits(
        files,
        allowed_suffixes=allowed_suffixes,
        max_file_count=max_file_count,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        staging_dir=staging_dir,
    )


async def stage_upload_files_with_limits(
    files: list[Any],
    *,
    allowed_suffixes: set[str] | None = None,
    max_file_count: int = DEFAULT_UPLOAD_MAX_FILE_COUNT,
    max_file_bytes: int = DEFAULT_UPLOAD_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_UPLOAD_MAX_TOTAL_BYTES,
    staging_dir: Any | None = None,
) -> tuple[list[str], list[str]]:
    temp_paths: list[str] = []
    file_names: list[str] = []
    resolved_staging_dir = ensure_upload_staging_dir(staging_dir)
    normalized_allowed_suffixes = {
        str(item or "").strip().lower()
        for item in (allowed_suffixes or DEFAULT_UPLOAD_ALLOWED_SUFFIXES)
        if str(item or "").strip()
    }
    uploads = list(files or [])
    if not uploads:
        raise ValueError("至少上传一个文件")
    if len(uploads) > max(1, int(max_file_count)):
        raise ValueError(f"单次最多上传 {int(max_file_count)} 个文件")

    total_bytes = 0

    try:
        for upload in uploads:
            file_name = str(getattr(upload, "filename", "") or "").strip()
            if not file_name:
                raise ValueError("存在缺少文件名的上传项")
            suffix = upload_file_suffix(file_name).lower()
            if normalized_allowed_suffixes and suffix not in normalized_allowed_suffixes:
                raise ValueError(f"不支持的文件类型: {suffix or '无扩展名'}")
            fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=resolved_staging_dir)
            try:
                content = await upload.read()
                if not isinstance(content, (bytes, bytearray)):
                    raise ValueError(f"文件读取失败: {file_name}")
                file_size = len(content)
                if file_size <= 0:
                    raise ValueError(f"文件内容为空: {file_name}")
                if file_size > max(1, int(max_file_bytes)):
                    raise ValueError(
                        f"文件过大: {file_name}，单文件限制 {int(max_file_bytes)} 字节"
                    )
                total_bytes += file_size
                if total_bytes > max(1, int(max_total_bytes)):
                    raise ValueError(
                        f"上传总大小超限，最多 {int(max_total_bytes)} 字节"
                    )
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                cleanup_temp_paths([temp_path, *temp_paths])
                raise

            temp_paths.append(temp_path)
            file_names.append(file_name or os.path.basename(temp_path))
    except Exception:
        cleanup_temp_paths(temp_paths)
        raise

    return temp_paths, file_names


def build_upload_documents_task_record(
    *,
    temp_paths: list[str],
    file_names: list[str],
    vector_store_path: str,
    task_id_factory: Callable[[], Any] = uuid.uuid4,
    current_time: Callable[[], float] = time.time,
) -> TaskRecord:
    task_id = str(task_id_factory())
    now = current_time()
    return TaskRecord(
        task_id=task_id,
        task_type="upload_documents",
        status=TaskStatus.PENDING,
        params={
            "temp_paths": temp_paths,
            "file_names": file_names,
            "vector_store_path": vector_store_path,
        },
        session_id=None,
        created_at=now,
        updated_at=now,
    )


def upload_documents_response(
    record: TaskRecord,
    *,
    file_count: int,
    vector_store_path: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "task_id": record.task_id,
        "task_type": record.task_type,
        "status": record.status,
        "message": (
            f"已接收 {file_count} 个文件，正在后台构建知识库"
            f"（目标路径：{vector_store_path}）"
        ),
    }


def build_chat_report_title(messages: list[Any], default_title: str = "AI 对话报告") -> str:
    for message in messages:
        content = str(getattr(message, "content", "") or "").strip()
        if message.__class__.__name__ == "HumanMessage" and content:
            return content[:50]
    return default_title


def safe_report_filename(title: str, default_name: str = "report") -> str:
    return (
        "".join(char for char in title if char.isalnum() or char in (" ", "-", "_")).strip()[
            :40
        ]
        or default_name
    )


def populate_chat_report_presentation(
    presentation: Any,
    *,
    title: str,
    qa_pairs: list[tuple[str, str]],
    body_font_size: Any,
) -> None:
    title_slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    title_slide.shapes.title.text = title
    if len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = "InsightDesk Conversation Report"

    for index, (question, answer) in enumerate(qa_pairs, start=1):
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = f"主题 {index}: {question[:48]}"
        body = slide.placeholders[1]
        text_frame = body.text_frame
        text_frame.word_wrap = True
        answer_text = answer[:1200]
        if len(answer) > 1200:
            answer_text += "...（内容已截断）"
        text_frame.text = answer_text
        for paragraph in text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.size = body_font_size


def retrieval_test_payload(
    query: str,
    pipeline: Any,
    *,
    current_time: Callable[[], float] = time.time,
    search_k: int = 5,
    fetch_k: int = 10,
    use_rerank: bool = False,
    retrieval_mode: str = "semantic",
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("查询内容不能为空")

    started_at = current_time()
    try:
        loaded = pipeline.load_store()
        if not loaded:
            return {
                "results_count": 0,
                "top_scores": [],
                "latency_ms": 0,
                "error": "知识库未初始化",
            }

        normalized_mode = str(retrieval_mode or "semantic").strip().lower() or "semantic"
        if hasattr(pipeline, "debug_retrieval"):
            effective_fetch_k = max(fetch_k, search_k * 2) if use_rerank else max(fetch_k, search_k)
            payload = pipeline.debug_retrieval(
                query,
                search_k=search_k,
                fetch_k=effective_fetch_k,
                retrieval_mode=normalized_mode,
                use_rerank=use_rerank,
            )
        else:
            if normalized_mode == "keyword" and hasattr(pipeline, "keyword_search"):
                docs = pipeline.keyword_search(query, k=search_k)
                search_mode = "keyword"
                effective_fetch_k = search_k
            elif normalized_mode == "hybrid" and hasattr(pipeline, "hybrid_search"):
                effective_fetch_k = max(fetch_k, search_k * 2) if use_rerank else max(fetch_k, search_k)
                docs = pipeline.hybrid_search(
                    query,
                    k=search_k,
                    fetch_k=effective_fetch_k,
                    use_rerank=use_rerank,
                )
                search_mode = "hybrid_rerank" if use_rerank else "hybrid"
            elif use_rerank:
                effective_fetch_k = max(fetch_k, search_k * 2)
                docs = pipeline.search_with_rerank(query, k=search_k, fetch_k=effective_fetch_k)
                search_mode = "semantic_rerank"
            else:
                docs = pipeline.search(query, k=search_k)
                effective_fetch_k = search_k
                search_mode = "semantic"

            payload = {
                "results_count": len(docs),
                "search_mode": search_mode,
                "retrieval_mode": normalized_mode,
                "search_k": search_k,
                "top_k": search_k,
                "fetch_k": effective_fetch_k,
                "rewrite_query": query.strip(),
                "rewrite_applied": False,
                "query_terms": [],
                "top_results": [
                    {
                        "source": doc.metadata.get("source", "未知"),
                        "snippet": doc.page_content[:120],
                    }
                    for doc in docs
                ],
                "coverage": {
                    "unique_sources": len(
                        {
                            str(doc.metadata.get("source", "") or "").strip()
                            for doc in docs
                            if str(doc.metadata.get("source", "") or "").strip()
                        }
                    ),
                    "source_ratio": 0 if not docs else 1.0,
                    "matched_terms": [],
                    "matched_term_count": 0,
                },
                "semantic_candidates": [],
                "keyword_candidates": [],
                "fused_candidates": [],
            }

        latency = round((current_time() - started_at) * 1000, 1)
        return {**payload, "latency_ms": latency}
    except Exception as exc:
        return {
            "results_count": 0,
            "top_scores": [],
            "latency_ms": 0,
            "error": str(exc),
        }


__all__ = [
    "DEFAULT_UPLOAD_ALLOWED_SUFFIXES",
    "DEFAULT_UPLOAD_MAX_FILE_COUNT",
    "DEFAULT_UPLOAD_MAX_FILE_BYTES",
    "DEFAULT_UPLOAD_MAX_TOTAL_BYTES",
    "upload_file_suffix",
    "cleanup_temp_paths",
    "ensure_upload_staging_dir",
    "stage_upload_files",
    "stage_upload_files_with_limits",
    "build_upload_documents_task_record",
    "upload_documents_response",
    "build_chat_report_title",
    "safe_report_filename",
    "populate_chat_report_presentation",
    "retrieval_test_payload",
]
