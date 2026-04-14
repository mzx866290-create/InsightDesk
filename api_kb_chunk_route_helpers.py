import time
from typing import Any, Callable

from fastapi import HTTPException


def _empty_chunk_page_payload(
    *,
    abs_store: str,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    return {
        "items": [],
        "total": 0,
        "offset": offset,
        "limit": limit,
        "has_more": False,
        "store_path": abs_store,
    }


def list_kb_chunks_payload(
    *,
    store_path: str,
    abs_store: str,
    index_exists: bool,
    query: str,
    source: str,
    offset: int,
    limit: int,
    pipeline_factory: Callable[[str], Any],
    collect_chunks: Callable[[Any], list[dict[str, Any]]],
    filter_chunks: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset 不能小于 0")
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit 必须在 1 到 200 之间")
    if not index_exists:
        return _empty_chunk_page_payload(abs_store=abs_store, offset=offset, limit=limit)

    pipeline = pipeline_factory(store_path)
    loaded = pipeline.load_store()
    if not loaded or getattr(pipeline, "vectorstore", None) is None:
        return _empty_chunk_page_payload(abs_store=abs_store, offset=offset, limit=limit)

    page_payload = filter_chunks(
        collect_chunks(pipeline),
        query=query,
        source=source,
        offset=offset,
        limit=limit,
    )
    return {
        **page_payload,
        "store_path": abs_store,
    }


def update_kb_chunk_payload(
    *,
    chunk_id: str,
    request: Any,
    field_set: set[str],
    pipeline_factory: Callable[[], Any],
    docstore_dict: Callable[[Any], dict[Any, Any]],
    safe_metadata: Callable[[Any], dict[str, Any]],
    rebuild_from_documents: Callable[[Any, list[Any]], None],
    doc_factory: Callable[[str, dict[str, Any]], Any],
    current_time: Callable[[], float] = time.time,
) -> dict[str, Any]:
    clean_chunk_id = chunk_id.strip()
    if not clean_chunk_id:
        raise HTTPException(status_code=400, detail="缺少 chunk_id")
    if "content" not in field_set and "source" not in field_set:
        raise HTTPException(
            status_code=400,
            detail="至少需要提供一个字段：content 或 source",
        )

    pipeline = pipeline_factory()
    loaded = pipeline.load_store()
    if not loaded or getattr(pipeline, "vectorstore", None) is None:
        raise HTTPException(status_code=404, detail="知识库为空")

    entries = docstore_dict(pipeline.vectorstore)
    current_doc = entries.get(clean_chunk_id)
    if current_doc is None:
        raise HTTPException(status_code=404, detail="未找到对应分块")

    current_content = str(getattr(current_doc, "page_content", "") or "")
    updated_content = current_content
    if "content" in field_set:
        if request.content is None:
            raise HTTPException(status_code=400, detail="content 不能为空")
        if not request.content.strip():
            raise HTTPException(status_code=400, detail="content 不能为空字符串")
        updated_content = request.content

    metadata = safe_metadata(getattr(current_doc, "metadata", {}) or {})
    if "source" in field_set:
        if request.source is None:
            raise HTTPException(status_code=400, detail="source 不能为空")
        normalized_source = request.source.strip()
        if not normalized_source:
            raise HTTPException(status_code=400, detail="source 不能为空字符串")
        metadata["source"] = normalized_source
    metadata["kb_last_edited_at"] = int(current_time())

    entries[clean_chunk_id] = doc_factory(updated_content, metadata)
    content_changed = updated_content != current_content

    if content_changed:
        rebuild_from_documents(
            pipeline,
            [doc for doc in entries.values() if doc is not None],
        )
    else:
        pipeline._save_vectorstore_local()

    return {
        "ok": True,
        "chunk_id": clean_chunk_id,
        "reindexed": content_changed,
    }


def delete_kb_chunk_payload(
    *,
    chunk_id: str,
    pipeline_factory: Callable[[], Any],
    docstore_dict: Callable[[Any], dict[Any, Any]],
    rebuild_from_documents: Callable[[Any, list[Any]], None],
) -> dict[str, Any]:
    clean_chunk_id = chunk_id.strip()
    if not clean_chunk_id:
        raise HTTPException(status_code=400, detail="缺少 chunk_id")

    pipeline = pipeline_factory()
    loaded = pipeline.load_store()
    if not loaded or getattr(pipeline, "vectorstore", None) is None:
        raise HTTPException(status_code=404, detail="知识库为空")

    entries = docstore_dict(pipeline.vectorstore)
    removed = entries.pop(clean_chunk_id, None)
    if removed is None:
        raise HTTPException(status_code=404, detail="未找到对应分块")

    remaining_docs = [doc for doc in entries.values() if doc is not None]
    rebuild_from_documents(pipeline, remaining_docs)

    return {
        "ok": True,
        "deleted_chunk_id": clean_chunk_id,
        "remaining_chunks": len(remaining_docs),
    }
