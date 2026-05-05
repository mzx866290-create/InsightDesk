from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from backend.helpers.kb_helpers import (
    filter_kb_chunks,
    kb_collect_chunks,
    kb_docstore_dict,
    kb_rebuild_from_documents,
    kb_safe_metadata,
)


def test_kb_docstore_dict_rejects_unsupported_docstore():
    vectorstore = SimpleNamespace(docstore=SimpleNamespace(_dict=[]))

    with pytest.raises(HTTPException) as exc:
        kb_docstore_dict(vectorstore)

    assert exc.value.status_code == 500
    assert exc.value.detail == "不支持的知识库 docstore 类型"


def test_kb_collect_chunks_sorts_and_sanitizes_metadata():
    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-b": Document(
                    page_content="Beta content",
                    metadata={"source": "beta.md", "score": 0.8},
                ),
                "chunk-a": Document(
                    page_content="Alpha    content\nwith space",
                    metadata={"source": "alpha.md", "extra": object()},
                ),
            }
        ),
        index_to_docstore_id={1: "chunk-b", 0: "chunk-a"},
    )
    pipeline = SimpleNamespace(vectorstore=vectorstore)

    chunks = kb_collect_chunks(pipeline, preview_char_limit=16)

    assert [item["chunk_id"] for item in chunks] == ["chunk-a", "chunk-b"]
    assert chunks[0]["preview"] == "Alpha content..."
    assert chunks[0]["source"] == "alpha.md"
    assert isinstance(chunks[0]["metadata"]["extra"], str)


def test_filter_kb_chunks_applies_filters_and_pagination():
    payload = filter_kb_chunks(
        [
            {"chunk_id": "1", "source": "alpha.md", "content": "first alpha note"},
            {"chunk_id": "2", "source": "beta.md", "content": "second beta note"},
            {"chunk_id": "3", "source": "alpha.md", "content": "third alpha note"},
        ],
        query="alpha",
        source="alpha",
        offset=1,
        limit=1,
    )

    assert payload == {
        "items": [{"chunk_id": "3", "source": "alpha.md", "content": "third alpha note"}],
        "total": 2,
        "offset": 1,
        "limit": 1,
        "has_more": False,
    }


def test_kb_safe_metadata_normalizes_non_dict():
    assert kb_safe_metadata(None) == {}
    assert kb_safe_metadata("bad") == {}


def test_kb_rebuild_from_documents_clears_local_index_files(tmp_path):
    (tmp_path / "index.faiss").write_text("faiss", encoding="utf-8")
    (tmp_path / "index.pkl").write_text("pkl", encoding="utf-8")
    pipeline = SimpleNamespace(vector_store_path=str(tmp_path), vectorstore=object())

    kb_rebuild_from_documents(pipeline, [])

    assert pipeline.vectorstore is None
    assert not (tmp_path / "index.faiss").exists()
    assert not (tmp_path / "index.pkl").exists()


def test_kb_rebuild_from_documents_uses_existing_vector_class():
    calls: list[object] = []

    class FakeVectorStore:
        @classmethod
        def from_documents(cls, documents, embeddings):
            calls.append((documents, embeddings))
            return "rebuilt-store"

    pipeline = SimpleNamespace(
        vector_store_path=str(Path.cwd()),
        vectorstore=FakeVectorStore(),
        embeddings="embedder",
        _save_vectorstore_local=lambda: calls.append("saved"),
    )
    docs = [Document(page_content="alpha", metadata={"source": "alpha.md"})]

    kb_rebuild_from_documents(pipeline, docs)

    assert pipeline.vectorstore == "rebuilt-store"
    assert calls[0][1] == "embedder"
    assert calls[1] == "saved"
