import os
import tempfile
import time
import uuid
from typing import Any, Callable, Iterable

from api_task_store import TaskRecord, TaskStatus


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


async def stage_upload_files(files: list[Any]) -> tuple[list[str], list[str]]:
    temp_paths: list[str] = []
    file_names: list[str] = []

    try:
        for upload in files:
            suffix = upload_file_suffix(getattr(upload, "filename", None))
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            try:
                content = await upload.read()
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
            file_names.append(
                str(getattr(upload, "filename", "") or os.path.basename(temp_path))
            )
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
        title_slide.placeholders[1].text = "AI 知识库对话报告"

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

        if use_rerank:
            effective_fetch_k = max(fetch_k, search_k * 2)
            docs = pipeline.search_with_rerank(query, k=search_k, fetch_k=effective_fetch_k)
            search_mode = "vector_rerank"
        else:
            docs = pipeline.search(query, k=search_k)
            effective_fetch_k = search_k
            search_mode = "vector"

        latency = round((current_time() - started_at) * 1000, 1)
        return {
            "results_count": len(docs),
            "latency_ms": latency,
            "search_mode": search_mode,
            "search_k": search_k,
            "fetch_k": effective_fetch_k,
            "top_results": [
                {
                    "source": doc.metadata.get("source", "未知"),
                    "snippet": doc.page_content[:120],
                }
                for doc in docs
            ],
        }
    except Exception as exc:
        return {
            "results_count": 0,
            "top_scores": [],
            "latency_ms": 0,
            "error": str(exc),
        }
