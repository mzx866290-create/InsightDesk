"""Delivery template catalog for reports and Deck/PPT workflows."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DELIVERY_TEMPLATE_DIRS_ENV = "DELIVERY_TEMPLATE_MANIFEST_DIRS"
DELIVERY_TEMPLATE_ENABLED_ENV = "DELIVERY_TEMPLATE_MANIFESTS_ENABLED"
_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_ARTIFACT_TYPES = {"report", "deck"}
_TEMPLATE_METADATA_RESERVED_KEYS = {
    "manifest",
    "source",
    "version",
}


@dataclass(frozen=True, slots=True)
class DeliveryTemplate:
    """Serializable catalog entry; it does not execute template code."""

    id: str
    name: str
    description: str
    artifact_type: str
    category: str
    tags: list[str]
    target_format: str
    preview: str = ""
    suggested_options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "artifact_type": self.artifact_type,
            "category": self.category,
            "tags": list(self.tags),
            "target_format": self.target_format,
            "preview": self.preview,
            "suggested_options": dict(self.suggested_options),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class DeliveryTemplateManifestIssue:
    file: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "code": self.code,
            "message": self.message,
        }


@dataclass(slots=True)
class DeliveryTemplateManifestLoadReport:
    templates: list[DeliveryTemplate] = field(default_factory=list)
    issues: list[DeliveryTemplateManifestIssue] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)
    scanned_count: int = 0


def builtin_delivery_templates() -> list[DeliveryTemplate]:
    """Return built-in productized delivery templates in stable order."""

    return [
        DeliveryTemplate(
            id="executive_report",
            name="Executive Report",
            description="Concise decision-ready report with context, findings, risks, and next actions.",
            artifact_type="report",
            category="business",
            tags=["executive", "decision", "markdown"],
            target_format="markdown",
            preview="Summary → Key findings → Risks → Recommended next actions",
            suggested_options={
                "scope": "session",
                "tone": "executive",
                "include_sources": True,
            },
            metadata={"source": "builtin"},
        ),
        DeliveryTemplate(
            id="research_brief",
            name="Research Brief",
            description="Evidence-first research summary optimized for source review and conflict checks.",
            artifact_type="report",
            category="research",
            tags=["research", "evidence", "citations"],
            target_format="markdown",
            preview="Question → Evidence matrix → Synthesis → Open questions",
            suggested_options={
                "scope": "answer_group",
                "include_citations": True,
                "conflict_review": True,
            },
            metadata={"source": "builtin"},
        ),
        DeliveryTemplate(
            id="board_deck",
            name="Board Deck",
            description="Structured Deck/PPT outline with evidence coverage and export-gate readiness.",
            artifact_type="deck",
            category="presentation",
            tags=["deck", "pptx", "board"],
            target_format="pptx",
            preview="Cover → Agenda → Insights → Evidence appendix",
            suggested_options={
                "target_slide_count": 8,
                "theme": "midnight",
                "knowledge_base_enabled": True,
            },
            metadata={"source": "builtin"},
        ),
    ]


def delivery_template_manifests_enabled() -> bool:
    raw_value = str(os.getenv(DELIVERY_TEMPLATE_ENABLED_ENV, "true") or "").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def default_delivery_template_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    configured = [
        item.strip()
        for item in str(os.getenv(DELIVERY_TEMPLATE_DIRS_ENV, "") or "").split(os.pathsep)
        if item.strip()
    ]
    candidates = configured or [str(root / "config" / "delivery_templates")]
    return [Path(item).expanduser() for item in candidates]


def _delivery_template_install_dir(
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> Path:
    directories = (
        [Path(item).expanduser() for item in template_dirs]
        if template_dirs is not None
        else default_delivery_template_dirs()
    )
    if not directories:
        raise ValueError("Delivery template manifest directory is required")
    return directories[0]


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if not isinstance(raw_value, list):
        raise ValueError(f"Delivery template field '{field_name}' must be a list")
    values = [str(item).strip() for item in raw_value if str(item).strip()]
    if not values:
        raise ValueError(f"Delivery template field '{field_name}' cannot be empty")
    return values


def _safe_mapping(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in raw_value.items():
        safe_key = str(key or "").strip()
        if not safe_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[safe_key] = value
        elif isinstance(value, list):
            safe[safe_key] = [
                item for item in value if isinstance(item, (str, int, float, bool))
            ]
        elif isinstance(value, dict):
            nested = _safe_mapping(value)
            if nested:
                safe[safe_key] = nested
    return safe


def _safe_metadata(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in raw_value.items():
        safe_key = str(key or "").strip()
        if not safe_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[safe_key] = value
        elif isinstance(value, list):
            safe[safe_key] = [
                item for item in value if isinstance(item, (str, int, float, bool))
            ]
    return safe


def _template_from_manifest(payload: dict[str, Any]) -> DeliveryTemplate | None:
    if payload.get("enabled") is False:
        return None

    template_id = str(payload.get("id") or "").strip()
    if not _TEMPLATE_ID_PATTERN.fullmatch(template_id):
        raise ValueError(
            "Delivery template id must be 1-80 characters and use only "
            "letters, numbers, dots, underscores, or hyphens"
        )

    artifact_type = str(payload.get("artifact_type") or "").strip().lower()
    if artifact_type not in _ARTIFACT_TYPES:
        raise ValueError("Delivery template artifact_type must be 'report' or 'deck'")

    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not name:
        raise ValueError("Delivery template field 'name' cannot be empty")
    if not description:
        raise ValueError("Delivery template field 'description' cannot be empty")

    tags = _normalize_string_list(payload.get("tags"), field_name="tags")
    target_format = str(payload.get("target_format") or "").strip()
    if not target_format:
        raise ValueError("Delivery template field 'target_format' cannot be empty")

    metadata = _safe_metadata(payload.get("metadata"))
    version = str(payload.get("version") or "").strip()
    if version:
        metadata["version"] = version

    return DeliveryTemplate(
        id=template_id,
        name=name,
        description=description,
        artifact_type=artifact_type,
        category=str(payload.get("category") or "custom").strip() or "custom",
        tags=tags,
        target_format=target_format,
        preview=str(payload.get("preview") or "").strip(),
        suggested_options=_safe_mapping(payload.get("suggested_options")),
        metadata={
            **metadata,
            "source": "template_manifest",
            "manifest": True,
        },
    )


def _sanitized_delivery_template_manifest(manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(manifest, dict):
        raise ValueError("Delivery template manifest must be a JSON object")
    if manifest.get("enabled") is False:
        raise ValueError("Delivery template install requires an enabled manifest")

    template = _template_from_manifest(manifest)
    if template is None:
        raise ValueError("Delivery template install requires an enabled manifest")

    builtin_ids = {item.id for item in builtin_delivery_templates()}
    if template.id in builtin_ids:
        raise ValueError(f"Delivery template id conflicts with built-in template: {template.id}")

    safe_metadata = {
        key: value
        for key, value in _safe_metadata(manifest.get("metadata")).items()
        if key not in _TEMPLATE_METADATA_RESERVED_KEYS
    }
    sanitized: dict[str, Any] = {
        "enabled": True,
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "artifact_type": template.artifact_type,
        "category": template.category,
        "tags": list(template.tags),
        "target_format": template.target_format,
    }
    version = str(manifest.get("version") or "").strip()
    if version:
        sanitized["version"] = version
    if template.preview:
        sanitized["preview"] = template.preview
    if template.suggested_options:
        sanitized["suggested_options"] = dict(template.suggested_options)
    if safe_metadata:
        sanitized["metadata"] = safe_metadata
    return template.id, sanitized


def install_delivery_template_manifest_payload(
    manifest: dict[str, Any],
    *,
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    """Persist a declarative report/deck template manifest without executing code."""

    template_id, sanitized = _sanitized_delivery_template_manifest(manifest)
    install_dir = _delivery_template_install_dir(template_dirs)
    install_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = install_dir / f"{template_id}.json"
    tmp_path = manifest_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(manifest_path)

    catalog = list_delivery_template_catalog(template_dirs=template_dirs)
    installed = next(
        (
            item
            for item in catalog.get("templates", [])
            if isinstance(item, dict) and item.get("id") == template_id
        ),
        {
            "id": template_id,
            "name": sanitized.get("name", ""),
            "description": sanitized.get("description", ""),
            "artifact_type": sanitized.get("artifact_type", "report"),
            "category": sanitized.get("category", "custom"),
            "tags": list(sanitized.get("tags", [])),
            "target_format": sanitized.get("target_format", ""),
            "preview": sanitized.get("preview", ""),
            "suggested_options": dict(sanitized.get("suggested_options", {})),
            "metadata": {},
        },
    )
    catalog["installed"] = {
        "id": template_id,
        "template": installed,
        "manifest_path": str(manifest_path),
        "executed_template_code": False,
    }
    return catalog


def _find_delivery_template_manifest_path(
    template_id: str,
    *,
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> Path | None:
    directories = (
        [Path(item).expanduser() for item in template_dirs]
        if template_dirs is not None
        else default_delivery_template_dirs()
    )
    expected_path = _delivery_template_install_dir(template_dirs) / f"{template_id}.json"
    if expected_path.exists():
        return expected_path

    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue
        for manifest_path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict) and str(payload.get("id") or "").strip() == template_id:
                return manifest_path
    return None


def uninstall_delivery_template_manifest_payload(
    template_id: str,
    *,
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    """Delete a declared delivery template manifest without touching generated artifacts."""

    normalized_id = str(template_id or "").strip()
    if not _TEMPLATE_ID_PATTERN.fullmatch(normalized_id):
        raise ValueError(
            "Delivery template id must be 1-80 characters and use only "
            "letters, numbers, dots, underscores, or hyphens"
        )
    builtin_ids = {item.id for item in builtin_delivery_templates()}
    if normalized_id in builtin_ids:
        raise ValueError(f"Delivery template id conflicts with built-in template: {normalized_id}")

    manifest_path = _find_delivery_template_manifest_path(
        normalized_id,
        template_dirs=template_dirs,
    )
    if manifest_path is None:
        raise ValueError(f"Delivery template manifest not found: {normalized_id}")

    manifest_path.unlink()
    catalog = list_delivery_template_catalog(template_dirs=template_dirs)
    catalog["uninstalled"] = {
        "id": normalized_id,
        "manifest_path": str(manifest_path),
        "deleted_manifest": True,
        "existed": True,
    }
    return catalog


def _manifest_issue(
    manifest_path: Path,
    *,
    code: str,
    message: str,
) -> DeliveryTemplateManifestIssue:
    return DeliveryTemplateManifestIssue(
        file=str(manifest_path),
        code=code,
        message=message,
    )


def load_delivery_template_manifest_report(
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> DeliveryTemplateManifestLoadReport:
    directories = (
        [Path(item).expanduser() for item in template_dirs]
        if template_dirs is not None
        else default_delivery_template_dirs()
    )
    report = DeliveryTemplateManifestLoadReport(directories=directories)
    if not delivery_template_manifests_enabled():
        return report

    seen_ids: set[str] = set()
    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue
        for manifest_path in sorted(directory.glob("*.json")):
            report.scanned_count += 1
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Delivery template manifest root must be an object")
                template = _template_from_manifest(payload)
            except json.JSONDecodeError as exc:
                report.issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_json",
                        message=str(exc),
                    )
                )
                continue
            except Exception as exc:
                report.issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_manifest",
                        message=f"Manifest does not match the delivery template schema: {exc}",
                    )
                )
                continue

            if template is None:
                continue
            if template.id in seen_ids:
                report.issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="duplicate_id",
                        message=f"Duplicate delivery template id skipped: {template.id}",
                    )
                )
                continue
            seen_ids.add(template.id)
            report.templates.append(template)

    return report


def list_delivery_template_catalog(
    *,
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    builtins = builtin_delivery_templates()
    report = load_delivery_template_manifest_report(template_dirs)
    templates_by_id = {template.id: template for template in builtins}
    for template in report.templates:
        if template.id in templates_by_id:
            report.issues.append(
                DeliveryTemplateManifestIssue(
                    file="",
                    code="builtin_id_conflict",
                    message=f"Manifest template conflicts with built-in id: {template.id}",
                )
            )
            continue
        templates_by_id[template.id] = template

    templates = list(templates_by_id.values())
    manifest_count = sum(
        1 for template in templates if template.metadata.get("source") == "template_manifest"
    )
    directories = (
        default_delivery_template_dirs()
        if template_dirs is None
        else [Path(item).expanduser() for item in template_dirs]
    )
    return {
        "templates": [template.as_dict() for template in templates],
        "summary": {
            "total": len(templates),
            "builtin": len(templates) - manifest_count,
            "manifest": manifest_count,
            "report": sum(1 for template in templates if template.artifact_type == "report"),
            "deck": sum(1 for template in templates if template.artifact_type == "deck"),
        },
        "manifests": {
            "enabled": delivery_template_manifests_enabled(),
            "directory_count": len(directories),
            "scanned_count": report.scanned_count,
            "loaded_count": len(report.templates),
            "issue_count": len(report.issues),
            "issues": [issue.as_dict() for issue in report.issues],
        },
    }


def validate_delivery_template_selection(
    template_id: Any,
    *,
    artifact_type: str,
    template_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any] | None:
    """Validate an optional template ID against the catalog and artifact type."""

    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return None

    normalized_artifact_type = str(artifact_type or "").strip().lower()
    if normalized_artifact_type not in _ARTIFACT_TYPES:
        raise ValueError("Delivery template artifact_type must be 'report' or 'deck'")

    catalog = list_delivery_template_catalog(template_dirs=template_dirs)
    for template in list(catalog.get("templates") or []):
        if not isinstance(template, dict):
            continue
        if str(template.get("id") or "").strip() != normalized_id:
            continue
        actual_type = str(template.get("artifact_type") or "").strip().lower()
        if actual_type != normalized_artifact_type:
            raise ValueError(
                f"Delivery template '{normalized_id}' is for {actual_type} "
                f"artifacts, not {normalized_artifact_type}."
            )
        return dict(template)

    raise ValueError(f"Unknown delivery template: {normalized_id}")
