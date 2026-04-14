from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.documents import Document

import api_server


def _install_fake_kb_pipeline(monkeypatch, vectorstore, events):
    import doc_pipeline

    class FakePipeline:
        def __init__(self, vector_store_path=None):
            self.vector_store_path = vector_store_path
            self.vectorstore = vectorstore
            self.embeddings = "fake-embeddings"

        def load_store(self):
            events.append(("load_store", self.vector_store_path))
            return True

        def _save_vectorstore_local(self):
            events.append(("save_store", self.vector_store_path))

    monkeypatch.setattr(doc_pipeline, "DocPipeline", FakePipeline)


def test_list_knowledge_base_chunks_returns_filtered_page(monkeypatch, tmp_path):
    events: list[tuple[str, object]] = []
    kb_path = tmp_path / "kb"
    kb_path.mkdir()
    (kb_path / "index.faiss").write_text("ok", encoding="utf-8")

    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Alpha findings with detail",
                    metadata={"source": "alpha.md"},
                ),
                "chunk-2": Document(
                    page_content="Beta findings with detail",
                    metadata={"source": "beta.md"},
                ),
                "chunk-3": Document(
                    page_content="Alpha appendix note",
                    metadata={"source": "alpha.md"},
                ),
            }
        ),
        index_to_docstore_id={0: "chunk-1", 1: "chunk-2", 2: "chunk-3"},
    )

    monkeypatch.setattr(api_server, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "kb")
    _install_fake_kb_pipeline(monkeypatch, vectorstore, events)

    client = TestClient(api_server.app)
    response = client.get(
        "/api/knowledge-base/chunks",
        params={"query": "alpha", "source": "alpha", "offset": 1, "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["offset"] == 1
    assert payload["limit"] == 1
    assert payload["has_more"] is False
    assert payload["items"][0]["chunk_id"] == "chunk-3"
    assert payload["items"][0]["source"] == "alpha.md"
    assert payload["store_path"] == str(kb_path.resolve())
    assert events == [("load_store", "kb")]


def test_update_knowledge_base_chunk_rebuilds_index_when_content_changes(monkeypatch, tmp_path):
    events: list[tuple[str, object]] = []
    kb_path = tmp_path / "kb"
    kb_path.mkdir()

    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Old content",
                    metadata={"source": "alpha.md"},
                ),
                "chunk-2": Document(
                    page_content="Keep me",
                    metadata={"source": "beta.md"},
                ),
            }
        ),
        index_to_docstore_id={0: "chunk-1", 1: "chunk-2"},
    )

    monkeypatch.setattr(api_server, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "kb")
    _install_fake_kb_pipeline(monkeypatch, vectorstore, events)

    def fake_rebuild(pipeline, documents):
        events.append(
            (
                "rebuild",
                [(doc.page_content, dict(doc.metadata)) for doc in documents],
            )
        )

    monkeypatch.setattr(api_server, "_kb_rebuild_from_documents", fake_rebuild)

    client = TestClient(api_server.app)
    response = client.patch(
        "/api/knowledge-base/chunks/chunk-1",
        json={"content": "Updated content", "source": "updated.md"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True, "chunk_id": "chunk-1", "reindexed": True}
    assert events[0] == ("load_store", "kb")
    assert events[1][0] == "rebuild"
    rebuilt_docs = events[1][1]
    assert rebuilt_docs[0][0] == "Updated content"
    assert rebuilt_docs[0][1]["source"] == "updated.md"
    assert "kb_last_edited_at" in rebuilt_docs[0][1]


def test_update_knowledge_base_chunk_source_only_saves_without_rebuild(monkeypatch, tmp_path):
    events: list[tuple[str, object]] = []
    kb_path = tmp_path / "kb"
    kb_path.mkdir()

    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Stable content",
                    metadata={"source": "alpha.md"},
                )
            }
        ),
        index_to_docstore_id={0: "chunk-1"},
    )

    monkeypatch.setattr(api_server, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "kb")
    _install_fake_kb_pipeline(monkeypatch, vectorstore, events)

    def fail_rebuild(pipeline, documents):
        raise AssertionError("rebuild should not run when content is unchanged")

    monkeypatch.setattr(api_server, "_kb_rebuild_from_documents", fail_rebuild)

    client = TestClient(api_server.app)
    response = client.patch(
        "/api/knowledge-base/chunks/chunk-1",
        json={"source": "renamed.md"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "chunk_id": "chunk-1", "reindexed": False}
    assert events == [("load_store", "kb"), ("save_store", "kb")]


def test_delete_knowledge_base_chunk_rebuilds_remaining_docs(monkeypatch, tmp_path):
    events: list[tuple[str, object]] = []
    kb_path = tmp_path / "kb"
    kb_path.mkdir()

    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Delete me",
                    metadata={"source": "alpha.md"},
                ),
                "chunk-2": Document(
                    page_content="Keep me",
                    metadata={"source": "beta.md"},
                ),
            }
        ),
        index_to_docstore_id={0: "chunk-1", 1: "chunk-2"},
    )

    monkeypatch.setattr(api_server, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "kb")
    _install_fake_kb_pipeline(monkeypatch, vectorstore, events)

    def fake_rebuild(pipeline, documents):
        events.append(("rebuild", [doc.page_content for doc in documents]))

    monkeypatch.setattr(api_server, "_kb_rebuild_from_documents", fake_rebuild)

    client = TestClient(api_server.app)
    response = client.delete("/api/knowledge-base/chunks/chunk-1")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "deleted_chunk_id": "chunk-1",
        "remaining_chunks": 1,
    }
    assert events == [("load_store", "kb"), ("rebuild", ["Keep me"])]
