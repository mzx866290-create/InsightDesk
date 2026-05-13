"""Document runtime adapters used by API routes."""

from __future__ import annotations

from typing import Any


def build_doc_pipeline(vector_store_path: str):
    from backend.doc_pipeline import DocPipeline

    return DocPipeline(vector_store_path=vector_store_path)


def build_langchain_document(page_content: str, metadata: dict[str, Any]):
    from langchain_core.documents import Document

    return Document(page_content=page_content, metadata=metadata)
