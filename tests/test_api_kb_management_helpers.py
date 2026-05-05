from pathlib import Path
from types import SimpleNamespace

from backend.helpers.kb_management_helpers import kb_health_payload, knowledge_bases_payload


def test_knowledge_bases_payload_collects_unique_paths_and_doc_counts(tmp_path):
    active_dir = tmp_path / "vector_store"
    sibling_dir = tmp_path / "vector_store_extra"
    ignored_dir = tmp_path / "notes"
    active_dir.mkdir()
    sibling_dir.mkdir()
    ignored_dir.mkdir()
    (active_dir / "index.faiss").write_text("faiss", encoding="utf-8")
    (sibling_dir / "index.faiss").write_text("faiss", encoding="utf-8")

    calls = []

    def pipeline_factory(vector_store_path: str):
        calls.append(vector_store_path)
        total_docs = 3 if "vector_store_extra" in vector_store_path else 5
        return SimpleNamespace(
            load_store=lambda: True,
            get_stats=lambda: {"total_docs": total_docs},
        )

    payload = knowledge_bases_payload(
        base_dir=str(tmp_path),
        active_vector_store_id=str(active_dir),
        current_effective_path=str(active_dir),
        env_vector_store_path="",
        sibling_paths=[str(active_dir), str(sibling_dir), str(ignored_dir)],
        resolve_project_subdir=lambda candidate: Path(candidate).resolve(),
        faiss_safe_store_path=lambda path: str(path),
        pipeline_factory=pipeline_factory,
    )

    assert payload["knowledge_bases"] == [
        {
            "id": str(active_dir.resolve()),
            "name": "vector_store",
            "path": str(active_dir.resolve()),
            "doc_count": 5,
            "has_index": True,
        },
        {
            "id": str(sibling_dir.resolve()),
            "name": "vector_store_extra",
            "path": str(sibling_dir.resolve()),
            "doc_count": 3,
            "has_index": True,
        },
        {
            "id": str(ignored_dir.resolve()),
            "name": "notes",
            "path": str(ignored_dir.resolve()),
            "doc_count": 0,
            "has_index": False,
        },
    ]
    assert len(calls) == 2


def test_kb_health_payload_returns_not_found_state(tmp_path):
    payload = kb_health_payload(
        tmp_path / "missing-store",
        embedding_model="embed-model",
        faiss_safe_store_path=lambda path: str(path),
        pipeline_factory=lambda vector_store_path: None,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert payload == {
        "index_status": "not_found",
        "total_chunks": 0,
        "store_path": str((tmp_path / "missing-store")),
        "store_size_mb": 0,
        "documents": [],
        "embedding_model": "embed-model",
        "last_updated": None,
    }


def test_kb_health_payload_reports_document_chunk_counts(tmp_path):
    store_dir = tmp_path / "vector_store"
    store_dir.mkdir()
    (store_dir / "index.faiss").write_text("faiss", encoding="utf-8")
    (store_dir / "extra.bin").write_bytes(b"1234")

    pipeline = SimpleNamespace(
        vectorstore=SimpleNamespace(
            docstore=SimpleNamespace(
                _dict={
                    "1": SimpleNamespace(metadata={"source": "alpha.md"}),
                    "2": SimpleNamespace(metadata={"source": "alpha.md"}),
                    "3": SimpleNamespace(metadata={"source": "beta.md"}),
                }
            )
        ),
        load_store=lambda: True,
        get_stats=lambda: {"total_docs": 3},
    )

    payload = kb_health_payload(
        store_dir,
        embedding_model="embed-model",
        faiss_safe_store_path=lambda path: str(path),
        pipeline_factory=lambda vector_store_path: pipeline,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert payload["index_status"] == "healthy"
    assert payload["total_chunks"] == 3
    assert payload["embedding_model"] == "embed-model"
    assert payload["store_size_mb"] >= 0
    assert payload["documents"] == [
        {"name": "alpha.md", "chunks": 2},
        {"name": "beta.md", "chunks": 1},
    ]
    assert payload["last_updated"] is not None


def test_kb_health_payload_reports_error_when_pipeline_load_fails(tmp_path):
    store_dir = tmp_path / "vector_store"
    store_dir.mkdir()
    (store_dir / "index.faiss").write_text("faiss", encoding="utf-8")
    warnings = []

    def pipeline_factory(vector_store_path: str):
        raise RuntimeError("boom")

    payload = kb_health_payload(
        store_dir,
        embedding_model="embed-model",
        faiss_safe_store_path=lambda path: str(path),
        pipeline_factory=pipeline_factory,
        logger=SimpleNamespace(warning=lambda *args: warnings.append(args)),
    )

    assert payload["index_status"] == "error"
    assert payload["total_chunks"] == 0
    assert payload["documents"] == []
    assert warnings
