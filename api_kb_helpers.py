import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def _clip_text(text: Any, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 3)].rstrip() + "..."


def kb_docstore_dict(vectorstore: Any) -> dict[Any, Any]:
    docstore = getattr(vectorstore, "docstore", None)
    raw = getattr(docstore, "_dict", None)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail="不支持的知识库 docstore 类型")
    return raw


def kb_safe_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    try:
        return json.loads(json.dumps(metadata, ensure_ascii=False, default=str))
    except Exception:
        return {str(k): str(v) for k, v in metadata.items()}


def kb_collect_chunks(
    pipeline: Any,
    *,
    preview_char_limit: int = 180,
) -> list[dict[str, Any]]:
    if pipeline.vectorstore is None:
        return []

    doc_entries = kb_docstore_dict(pipeline.vectorstore)
    index_map_raw = getattr(pipeline.vectorstore, "index_to_docstore_id", {}) or {}
    position_by_chunk_id: dict[str, int] = {}
    if isinstance(index_map_raw, dict):
        for raw_index, raw_chunk_id in index_map_raw.items():
            if raw_chunk_id is None:
                continue
            try:
                position_by_chunk_id[str(raw_chunk_id)] = int(raw_index)
            except (TypeError, ValueError):
                continue

    items: list[dict[str, Any]] = []
    for raw_chunk_id, doc in doc_entries.items():
        chunk_id = str(raw_chunk_id)
        content = str(getattr(doc, "page_content", "") or "")
        metadata = kb_safe_metadata(getattr(doc, "metadata", {}) or {})
        source = str(metadata.get("source") or "unknown")
        position = position_by_chunk_id.get(chunk_id, -1)
        items.append(
            {
                "chunk_id": chunk_id,
                "position": position,
                "source": source,
                "content": content,
                "preview": _clip_text(content, preview_char_limit),
                "char_count": len(content),
                "metadata": metadata,
            }
        )

    items.sort(
        key=lambda item: (
            item["position"] if item["position"] >= 0 else 10**12,
            item["chunk_id"],
        )
    )
    return items


def filter_kb_chunks(
    chunks: list[dict[str, Any]],
    *,
    query: str = "",
    source: str = "",
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    normalized_query = query.strip().lower()
    normalized_source = source.strip().lower()

    filtered = list(chunks)
    if normalized_source:
        filtered = [
            chunk
            for chunk in filtered
            if normalized_source in str(chunk.get("source", "")).lower()
        ]
    if normalized_query:
        filtered = [
            chunk
            for chunk in filtered
            if normalized_query in str(chunk.get("content", "")).lower()
            or normalized_query in str(chunk.get("source", "")).lower()
        ]

    total = len(filtered)
    items = filtered[offset : offset + limit]
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


def kb_rebuild_from_documents(pipeline: Any, documents: list[Any]) -> None:
    if documents:
        vector_class = pipeline.vectorstore.__class__ if pipeline.vectorstore is not None else None
        if vector_class is None:
            from langchain_community.vectorstores import FAISS as vector_class

        pipeline.vectorstore = vector_class.from_documents(documents, pipeline.embeddings)
        pipeline._save_vectorstore_local()
        return

    pipeline.vectorstore = None
    target_dir = Path(pipeline.vector_store_path)
    for file_name in ("index.faiss", "index.pkl"):
        file_path = target_dir / file_name
        if file_path.exists():
            file_path.unlink()
