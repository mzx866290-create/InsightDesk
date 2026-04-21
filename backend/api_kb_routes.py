from __future__ import annotations

import glob as glob_module
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class TestRetrievalRequest(BaseModel):
    query: str
    vector_store_path: str | None = None
    search_k: int | None = None
    fetch_k: int | None = None
    use_rerank: bool | None = None
    retrieval_mode: str | None = None


class UpdateKBChunkRequest(BaseModel):
    content: str | None = None
    source: str | None = None


def _request_field_set(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields or set())


def build_kb_router(
    *,
    backend_dir: str,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    effective_vector_store_path: Callable[[str | None], str],
    resolve_project_subdir: Callable[[str], Path],
    resolve_deletable_knowledge_base: Callable[[str], Path],
    active_vector_store_id: Callable[[], str | None],
    faiss_safe_store_path: Callable[[Path], str],
    build_doc_pipeline: Callable[[str], Any],
    list_kb_chunks_payload: Callable[..., dict[str, Any]],
    update_kb_chunk_payload: Callable[..., dict[str, Any]],
    delete_kb_chunk_payload: Callable[..., dict[str, Any]],
    knowledge_bases_payload: Callable[..., dict[str, Any]],
    kb_health_payload: Callable[..., dict[str, Any]],
    retrieval_test_payload: Callable[..., dict[str, Any]],
    kb_collect_chunks: Callable[..., list[dict[str, Any]]],
    filter_kb_chunks: Callable[..., list[dict[str, Any]]],
    kb_docstore_dict: Callable[[Any], dict[str, Any]],
    kb_safe_metadata: Callable[[Any], dict[str, Any]],
    kb_rebuild_from_documents: Callable[..., Any],
    doc_factory: Callable[[str, dict[str, Any]], Any],
    delete_kb_directory: Callable[..., Awaitable[dict[str, Any]]],
    clear_agent_cache: Callable[[], Awaitable[None]],
    content_hash: Callable[[Any], str],
    audit_security_event: Callable[..., Any],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/knowledge-base/chunks")
    async def list_knowledge_base_chunks(
        request: Request,
        path: str | None = None,
        query: str = "",
        source: str = "",
        offset: int = 0,
        limit: int = 20,
    ):
        require_remote_viewer(request)
        store_path = effective_vector_store_path(path)
        abs_store = str(resolve_project_subdir(store_path))
        payload = list_kb_chunks_payload(
            store_path=store_path,
            abs_store=abs_store,
            index_exists=(Path(abs_store) / "index.faiss").exists(),
            query=query,
            source=source,
            offset=offset,
            limit=limit,
            pipeline_factory=lambda vector_store_path: build_doc_pipeline(vector_store_path),
            collect_chunks=kb_collect_chunks,
            filter_chunks=filter_kb_chunks,
        )
        audit_security_event(
            "list_knowledge_base_chunks",
            request,
            details=(
                f"path={store_path} query={query or '<empty>'} source={source or '<empty>'} "
                f"offset={offset} limit={limit}"
            ),
        )
        return payload

    @router.patch("/api/knowledge-base/chunks/{chunk_id}")
    async def update_knowledge_base_chunk(
        chunk_id: str,
        request: Request,
        payload: UpdateKBChunkRequest,
        path: str | None = None,
    ):
        require_remote_editor(request)
        store_path = effective_vector_store_path(path)
        result = update_kb_chunk_payload(
            chunk_id=chunk_id,
            request=payload,
            field_set=_request_field_set(payload),
            pipeline_factory=lambda: build_doc_pipeline(store_path),
            docstore_dict=kb_docstore_dict,
            safe_metadata=kb_safe_metadata,
            rebuild_from_documents=kb_rebuild_from_documents,
            doc_factory=doc_factory,
            current_time=time.time,
        )
        audit_security_event(
            "update_knowledge_base_chunk",
            request,
            details=f"chunk_id={chunk_id} path={store_path}",
        )
        return result

    @router.delete("/api/knowledge-base/chunks/{chunk_id}")
    async def delete_knowledge_base_chunk(
        chunk_id: str,
        request: Request,
        path: str | None = None,
    ):
        require_remote_editor(request)
        store_path = effective_vector_store_path(path)
        result = delete_kb_chunk_payload(
            chunk_id=chunk_id,
            pipeline_factory=lambda: build_doc_pipeline(store_path),
            docstore_dict=kb_docstore_dict,
            rebuild_from_documents=kb_rebuild_from_documents,
        )
        audit_security_event(
            "delete_knowledge_base_chunk",
            request,
            details=f"chunk_id={chunk_id} path={store_path}",
        )
        return result

    @router.get("/api/knowledge-bases")
    async def list_knowledge_bases(request: Request):
        require_remote_viewer(request)
        try:
            current_effective_path = effective_vector_store_path(None)
        except HTTPException:
            current_effective_path = None
        payload = knowledge_bases_payload(
            base_dir=backend_dir,
            active_vector_store_id=active_vector_store_id(),
            current_effective_path=current_effective_path,
            env_vector_store_path=os.getenv("VECTOR_STORE_PATH", "./vector_store"),
            sibling_paths=list(glob_module.glob(os.path.join(backend_dir, "vector_store*"))),
            resolve_project_subdir=resolve_project_subdir,
            faiss_safe_store_path=faiss_safe_store_path,
            pipeline_factory=lambda vector_store_path: build_doc_pipeline(vector_store_path),
        )
        audit_security_event(
            "list_knowledge_bases",
            request,
            details=f"knowledge_base_count={len(payload.get('knowledge_bases', []))}",
        )
        return payload

    @router.get("/api/knowledge-base/health")
    async def get_kb_health(request: Request, path: str | None = None):
        require_remote_viewer(request)
        target_path = resolve_project_subdir(effective_vector_store_path(path))
        payload = kb_health_payload(
            target_path,
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
            faiss_safe_store_path=faiss_safe_store_path,
            pipeline_factory=lambda vector_store_path: build_doc_pipeline(vector_store_path),
            logger=logger,
        )
        audit_security_event(
            "get_knowledge_base_health",
            request,
            details=f"path={target_path}",
        )
        return payload

    @router.post("/api/knowledge-base/test-retrieval")
    async def test_retrieval(request: Request, payload: TestRetrievalRequest):
        require_remote_viewer(request)
        vector_store_path = effective_vector_store_path(payload.vector_store_path)
        pipeline = build_doc_pipeline(vector_store_path)
        try:
            result = retrieval_test_payload(
                payload.query,
                pipeline,
                current_time=time.time,
                search_k=payload.search_k or 5,
                fetch_k=payload.fetch_k or 10,
                use_rerank=payload.use_rerank or False,
                retrieval_mode=payload.retrieval_mode or "semantic",
            )
            audit_security_event(
                "test_knowledge_base_retrieval",
                request,
                details=(
                    f"path={vector_store_path} query_hash={content_hash(payload.query)} "
                    f"results_count={result.get('results_count', 0)}"
                ),
            )
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            return {
                "results_count": 0,
                "top_scores": [],
                "latency_ms": 0,
                "error": str(exc),
            }

    @router.delete("/api/knowledge-base")
    async def delete_knowledge_base(request: Request, path: str | None = None):
        require_remote_admin(request)
        target_path = resolve_deletable_knowledge_base(effective_vector_store_path(path))
        try:
            result = await delete_kb_directory(
                target_path,
                remove_tree=shutil.rmtree,
                clear_agent_cache=clear_agent_cache,
                success_message="知识库已删除：{path}",
                on_success=lambda abs_path: logger.info("Knowledge base deleted: %s", abs_path),
                on_failure=lambda: logger.exception("Failed to delete knowledge base"),
            )
            audit_security_event(
                "delete_knowledge_base",
                request,
                details=f"path={target_path}",
            )
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.delete("/api/knowledge-base/by-path")
    async def delete_knowledge_base_by_path(request: Request, path: str):
        require_remote_admin(request)
        target_path = resolve_deletable_knowledge_base(path)
        try:
            result = await delete_kb_directory(
                target_path,
                remove_tree=shutil.rmtree,
                clear_agent_cache=clear_agent_cache,
                success_message="已删除：{path}",
            )
            audit_security_event(
                "delete_knowledge_base_by_path",
                request,
                details=f"path={target_path}",
            )
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return router
