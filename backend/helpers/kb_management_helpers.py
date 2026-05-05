import os
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException


def knowledge_bases_payload(
    *,
    base_dir: str,
    active_vector_store_id: str | None,
    current_effective_path: str | None,
    env_vector_store_path: str,
    sibling_paths: list[str],
    resolve_project_subdir: Callable[[str], Path],
    faiss_safe_store_path: Callable[[str | Path], str],
    pipeline_factory: Callable[[str], Any],
) -> dict[str, list[dict[str, Any]]]:
    search_paths: list[str] = []
    for candidate in (
        active_vector_store_id,
        current_effective_path,
        env_vector_store_path,
    ):
        raw = str(candidate or "").strip()
        if raw and raw not in search_paths:
            search_paths.append(raw)

    for path in sibling_paths:
        if os.path.isdir(path) and path not in search_paths:
            search_paths.append(path)

    kb_dirs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for path in search_paths:
        try:
            abs_path = str(resolve_project_subdir(path))
        except HTTPException:
            abs_path = os.path.abspath(path)
        if abs_path in seen_paths:
            continue
        seen_paths.add(abs_path)
        if not os.path.isdir(abs_path):
            continue

        index_file = os.path.join(abs_path, "index.faiss")
        doc_count = 0
        if os.path.exists(index_file):
            try:
                pipeline = pipeline_factory(faiss_safe_store_path(abs_path))
                if pipeline.load_store():
                    stats = pipeline.get_stats()
                    doc_count = int(stats.get("total_docs", 0) or 0)
            except Exception:
                pass

        kb_dirs.append(
            {
                "id": abs_path,
                "name": os.path.basename(abs_path),
                "path": abs_path,
                "doc_count": doc_count,
                "has_index": os.path.exists(index_file),
            }
        )

    return {"knowledge_bases": kb_dirs}


def kb_health_payload(
    target_path: Path,
    *,
    embedding_model: str,
    faiss_safe_store_path: Callable[[str | Path], str],
    pipeline_factory: Callable[[str], Any],
    logger: Any,
) -> dict[str, Any]:
    abs_store = str(target_path)
    index_file = os.path.join(abs_store, "index.faiss")

    if not os.path.exists(abs_store):
        return {
            "index_status": "not_found",
            "total_chunks": 0,
            "store_path": abs_store,
            "store_size_mb": 0,
            "documents": [],
            "embedding_model": embedding_model,
            "last_updated": None,
        }

    total_size = 0
    for item in Path(abs_store).glob("*"):
        if item.is_file():
            total_size += item.stat().st_size
    size_mb = round(total_size / (1024 * 1024), 2)

    last_updated = os.path.getmtime(index_file) if os.path.exists(index_file) else None
    documents: list[dict[str, Any]] = []
    total_chunks = 0
    index_status = "empty"

    try:
        pipeline = pipeline_factory(faiss_safe_store_path(abs_store))
        loaded = pipeline.load_store()
        if loaded and getattr(pipeline, "vectorstore", None) is not None:
            stats = pipeline.get_stats()
            total_chunks = int(stats.get("total_docs", 0) or 0)
            index_status = "healthy" if total_chunks > 0 else "empty"

            doc_counts: dict[str, int] = {}
            try:
                docstore = pipeline.vectorstore.docstore
                store_dict = getattr(docstore, "_dict", {})
                for doc in store_dict.values():
                    source = (
                        doc.metadata.get("source", "未知")
                        if hasattr(doc, "metadata")
                        else "未知"
                    )
                    doc_counts[source] = doc_counts.get(source, 0) + 1
            except Exception:
                pass

            documents = [
                {"name": name, "chunks": count}
                for name, count in sorted(doc_counts.items())
            ]
    except Exception as exc:
        index_status = "error"
        logger.warning("KB health check failed: %s", exc)

    return {
        "index_status": index_status,
        "total_chunks": total_chunks,
        "store_path": abs_store,
        "store_size_mb": size_mb,
        "documents": documents,
        "embedding_model": embedding_model,
        "last_updated": last_updated,
    }
