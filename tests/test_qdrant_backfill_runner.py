from __future__ import annotations

import argparse

from deploy.run_qdrant_backfill import BackfillDocument, build_backfill_report


def _args(**overrides):
    defaults = {
        "json": True,
        "execute": False,
        "vector_store_path": "",
        "qdrant_url": "http://qdrant.example:6333",
        "qdrant_collection": "insightdesk_kb",
        "qdrant_api_key": "",
        "qdrant_vector_size": 4,
        "batch_size": 2,
        "embedding_model": "test-embedding",
        "device": "cpu",
        "allow_dangerous_faiss_deserialization": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _faiss_source(tmp_path):
    source = tmp_path / "vector_store"
    source.mkdir()
    (source / "index.faiss").write_bytes(b"placeholder")
    (source / "index.pkl").write_bytes(b"placeholder")
    return source


def test_qdrant_backfill_default_plan_is_side_effect_free(tmp_path, monkeypatch):
    source = _faiss_source(tmp_path)
    monkeypatch.delenv("QDRANT_BACKFILL_EXECUTE", raising=False)
    calls = {"loader": 0, "executor": 0}

    report = build_backfill_report(
        _args(vector_store_path=str(source)),
        document_loader=lambda *args, **kwargs: calls.__setitem__("loader", 1) or [],
        executor=lambda **kwargs: calls.__setitem__("executor", 1) or {},
    )

    assert report["ok"] is True
    assert report["actions"]["mode"] == "plan"
    assert report["actions"]["dry_run"] is True
    assert report["plan"]["side_effect_free"] is True
    assert report["execution"]["skipped"] is True
    assert calls == {"loader": 0, "executor": 0}


def test_qdrant_backfill_execute_requires_env_gate(tmp_path, monkeypatch):
    source = _faiss_source(tmp_path)
    monkeypatch.delenv("QDRANT_BACKFILL_EXECUTE", raising=False)

    report = build_backfill_report(
        _args(
            vector_store_path=str(source),
            execute=True,
            allow_dangerous_faiss_deserialization=True,
        )
    )

    assert report["ok"] is False
    assert report["actions"]["executed"] is False
    assert "missing_env:QDRANT_BACKFILL_EXECUTE" in report["errors"]


def test_qdrant_backfill_execute_requires_faiss_deserialization_opt_in(tmp_path, monkeypatch):
    source = _faiss_source(tmp_path)
    monkeypatch.setenv("QDRANT_BACKFILL_EXECUTE", "1")

    report = build_backfill_report(_args(vector_store_path=str(source), execute=True))

    assert report["ok"] is False
    assert "allow_dangerous_faiss_deserialization_required" in report["errors"]


def test_qdrant_backfill_execute_uses_injected_loader_and_executor(tmp_path, monkeypatch):
    source = _faiss_source(tmp_path)
    monkeypatch.setenv("QDRANT_BACKFILL_EXECUTE", "1")
    calls = {"loader": [], "executor": []}
    documents = [
        BackfillDocument(page_content="alpha", metadata={"source": "a.md"}),
        BackfillDocument(page_content="beta", metadata={"source": "b.md"}),
    ]

    def fake_loader(*args, **kwargs):
        calls["loader"].append((args, kwargs))
        return documents

    def fake_executor(**kwargs):
        calls["executor"].append(kwargs)
        return {
            "checked": True,
            "collection": kwargs["collection_name"],
            "created_collection": False,
            "documents_loaded": len(kwargs["documents"]),
            "upserted": 2,
            "remaining": 0,
            "errors": [],
            "warnings": [],
        }

    report = build_backfill_report(
        _args(
            vector_store_path=str(source),
            execute=True,
            allow_dangerous_faiss_deserialization=True,
        ),
        document_loader=fake_loader,
        executor=fake_executor,
    )

    assert report["ok"] is True
    assert report["actions"]["executed"] is True
    assert report["execution"]["upserted"] == 2
    assert report["plan"]["remaining"] == 0
    assert calls["loader"][0][0][0] == str(source)
    assert calls["executor"][0]["collection_name"] == "insightdesk_kb"
