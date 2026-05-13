from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.kb_management_helpers import (
    effective_vector_store_path,
    faiss_safe_store_path,
    kb_health_payload,
    knowledge_bases_payload,
    resolve_deletable_knowledge_base,
    resolve_project_subdir,
)


def test_resolve_project_subdir_allows_relative_path_under_project_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = project_root / "vector_store"
    target.mkdir()

    resolved = resolve_project_subdir("vector_store", project_root=project_root)

    assert resolved == target.resolve()


def test_resolve_project_subdir_rejects_outside_path(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        resolve_project_subdir(str(outside), project_root=project_root)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "不允许访问项目目录之外的路径"


def test_resolve_project_subdir_rejects_project_root_itself(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        resolve_project_subdir(str(project_root), project_root=project_root)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "不允许直接操作项目根目录"


def test_faiss_safe_store_path_returns_relative_path_inside_project_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = project_root / "vector_store"
    target.mkdir()

    assert faiss_safe_store_path(target, project_root=project_root) == "vector_store"


def test_faiss_safe_store_path_keeps_absolute_path_outside_project_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    assert faiss_safe_store_path(outside, project_root=project_root) == str(
        outside.resolve()
    )


def test_resolve_deletable_knowledge_base_requires_existing_indexed_directory(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    valid_kb = project_root / "kb_valid"
    valid_kb.mkdir()
    (valid_kb / "index.faiss").write_text("faiss", encoding="utf-8")

    assert (
        resolve_deletable_knowledge_base("kb_valid", project_root=project_root)
        == valid_kb.resolve()
    )


@pytest.mark.parametrize(
    ("path_builder", "expected_status", "expected_detail"),
    [
        (lambda root: root / "missing", 404, "知识库路径不存在"),
        (lambda root: root / "not_a_dir.txt", 400, "知识库路径必须是目录"),
        (lambda root: root / "missing_index", 400, "只能删除包含 index.faiss 的目录"),
    ],
)
def test_resolve_deletable_knowledge_base_rejects_invalid_targets(
    tmp_path,
    path_builder,
    expected_status,
    expected_detail,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = path_builder(project_root)
    if target.name == "not_a_dir.txt":
        target.write_text("file", encoding="utf-8")
    elif target.name == "missing_index":
        target.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        resolve_deletable_knowledge_base(str(target), project_root=project_root)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


def test_effective_vector_store_path_prefers_candidate_over_active_and_env(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "candidate_kb").mkdir()
    (project_root / "active_kb").mkdir()
    (project_root / "env_kb").mkdir()

    resolved = effective_vector_store_path(
        "candidate_kb",
        project_root=project_root,
        active_vector_store_id="active_kb",
        env_vector_store_path="env_kb",
    )

    assert resolved == "candidate_kb"


def test_effective_vector_store_path_uses_active_before_env(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "active_kb").mkdir()
    (project_root / "env_kb").mkdir()

    resolved = effective_vector_store_path(
        project_root=project_root,
        active_vector_store_id="active_kb",
        env_vector_store_path="env_kb",
    )

    assert resolved == "active_kb"


def test_effective_vector_store_path_falls_back_to_env_path(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "env_kb").mkdir()

    resolved = effective_vector_store_path(
        project_root=project_root,
        active_vector_store_id="",
        env_vector_store_path="env_kb",
    )

    assert resolved == "env_kb"


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
