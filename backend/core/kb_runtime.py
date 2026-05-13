"""Knowledge-base path adapters for API route wiring."""

from __future__ import annotations

from pathlib import Path

from backend.helpers.kb_management_helpers import (
    faiss_safe_store_path as faiss_safe_store_path_impl,
    resolve_deletable_knowledge_base as resolve_deletable_knowledge_base_impl,
    resolve_project_subdir as resolve_project_subdir_impl,
)

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_subdir(
    candidate: str,
    *,
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
) -> Path:
    return resolve_project_subdir_impl(candidate, project_root=project_root)


def faiss_safe_store_path(
    path: str | Path,
    *,
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
) -> str:
    return faiss_safe_store_path_impl(path, project_root=project_root)


def resolve_deletable_knowledge_base(
    candidate: str,
    *,
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
) -> Path:
    return resolve_deletable_knowledge_base_impl(
        candidate,
        project_root=project_root,
    )
