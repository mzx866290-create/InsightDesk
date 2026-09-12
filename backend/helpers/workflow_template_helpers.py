"""Workflow template persistence: save, list, reuse and delete plan templates.

Templates are stored as a JSON document under ``runtime/`` (same layout
philosophy as the MCP server config): a list of
``{"template_id", "name", "description", "plan", "created_at"}`` records.
Plans follow the multi-agent workflow step shape (task_type / agent /
depends_on / parallel_group / requires_approval) and are validated loosely on
save so the UI can evolve the schema independently.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

TEMPLATES_FILENAME = "workflow_templates.json"


def _project_root(project_root: str | Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root)
    return Path(__file__).resolve().parents[2]


def templates_path(project_root: str | Path | None = None) -> Path:
    return _project_root(project_root) / "runtime" / TEMPLATES_FILENAME


def _read_documents(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return raw if isinstance(raw, list) else []


def _write_documents(path: Path, documents: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False, suffix=".tmp"
    )
    try:
        json.dump(documents, handle, ensure_ascii=False, indent=2)
        handle.flush()
    finally:
        handle.close()
    os.replace(handle.name, path)


def _normalize_plan(plan: Any) -> list[dict] | None:
    if not isinstance(plan, list) or not plan:
        return None
    normalized: list[dict] = []
    for step in plan:
        if not isinstance(step, dict):
            continue
        entry: dict[str, Any] = {
            "task_type": str(step.get("task_type") or "general").strip() or "general",
            "agent": str(step.get("agent") or "").strip(),
            "description": str(step.get("description") or "").strip(),
        }
        if step.get("depends_on"):
            entry["depends_on"] = step["depends_on"]
        if step.get("parallel_group"):
            entry["parallel_group"] = str(step["parallel_group"])
        entry["requires_approval"] = bool(step.get("requires_approval", False))
        normalized.append(entry)
    return normalized or None


def save_workflow_template(payload: dict, project_root: str | Path | None = None) -> dict:
    """Create a template from a workflow payload; returns the stored record."""
    if not isinstance(payload, dict):
        raise ValueError("Workflow template payload must be an object.")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Workflow template name is required.")
    plan = _normalize_plan(payload.get("plan"))
    if plan is None:
        raise ValueError("Workflow template requires a non-empty plan list.")

    record = {
        "template_id": uuid.uuid4().hex[:12],
        "name": name,
        "description": str(payload.get("description") or "").strip(),
        "plan": plan,
        "created_at": time.time(),
    }
    path = templates_path(project_root)
    documents = _read_documents(path)
    documents.append(record)
    _write_documents(path, documents)
    return record


def list_workflow_templates(project_root: str | Path | None = None) -> list[dict]:
    documents = _read_documents(templates_path(project_root))
    return sorted(documents, key=lambda item: item.get("created_at") or 0, reverse=True)


def get_workflow_template(template_id: str, project_root: str | Path | None = None) -> dict | None:
    key = str(template_id or "").strip()
    for document in _read_documents(templates_path(project_root)):
        if str(document.get("template_id") or "") == key:
            return document
    return None


def delete_workflow_template(template_id: str, project_root: str | Path | None = None) -> bool:
    key = str(template_id or "").strip()
    path = templates_path(project_root)
    documents = _read_documents(path)
    remaining = [
        document
        for document in documents
        if str(document.get("template_id") or "") != key
    ]
    if len(remaining) == len(documents):
        return False
    _write_documents(path, remaining)
    return True
