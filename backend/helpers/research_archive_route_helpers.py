"""Route-level helpers for research archive endpoints."""

from typing import Any, Callable

from fastapi import HTTPException

from backend.helpers.research_archive_helpers import (
    artifact_content,
    compact_text,
    is_research_archive_artifact,
    matches_research_archive_filters,
    research_archive_payload,
    research_conflict_groups,
    research_conflict_review_records,
)


RESEARCH_ARCHIVE_REQUIRED_DETAIL = "Artifact is not a research archive."
RESOLUTION_PAYLOAD_OBJECT_DETAIL = "Resolution payload must be an object."
RESOLUTION_TARGET_REQUIRED_DETAIL = "conflict_id or claim_id is required."
RESOLUTION_STATUS_UNSUPPORTED_DETAIL = "Unsupported resolution status."
SUPPORTED_RESOLUTION_STATUSES = {"resolved", "dismissed", "needs_followup", "reviewed"}


def research_archives_list_payload(
    *,
    request: Any,
    artifacts: list[Any],
    q: str = "",
    session_id: str = "",
    task_id: str = "",
    limit: int = 100,
    filter_visible_resources: Callable[..., list[Any]],
    require_remote_viewer: Callable[[Any], dict[str, Any]],
    access_store: Any,
    identity_store: Any,
) -> dict[str, Any]:
    safe_limit = max(1, min(500, int(limit or 100)))
    query_text = str(q or "").strip()
    session_filter = str(session_id or "").strip()
    task_filter = str(task_id or "").strip()
    archive_candidates = [
        artifact
        for artifact in artifacts
        if is_research_archive_artifact(artifact)
        and matches_research_archive_filters(
            artifact,
            q=query_text,
            session_id=session_filter,
            task_id=task_filter,
        )
    ]
    visible_archives = filter_visible_resources(
        request,
        archive_candidates,
        resource_type="artifact",
        resource_id_getter=lambda artifact: str(getattr(artifact, "artifact_id", "") or ""),
        require_remote_role=require_remote_viewer,
        access_store=access_store,
        identity_store=identity_store,
    )
    limited_archives = visible_archives[:safe_limit]
    return {
        "archives": [research_archive_payload(artifact) for artifact in limited_archives],
        "conflict_groups": research_conflict_groups(visible_archives),
        "total": len(visible_archives),
        "limit": safe_limit,
    }


def upsert_research_conflict_resolution_result(
    *,
    artifact: Any,
    body: Any,
    save_artifact: Callable[[Any], Any],
    now: Callable[[], float],
) -> dict[str, Any]:
    if not is_research_archive_artifact(artifact):
        raise HTTPException(status_code=400, detail=RESEARCH_ARCHIVE_REQUIRED_DETAIL)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail=RESOLUTION_PAYLOAD_OBJECT_DETAIL)

    conflict_id = str(body.get("conflict_id") or "").strip()
    claim_id = str(body.get("claim_id") or "").strip()
    if not conflict_id and not claim_id:
        raise HTTPException(status_code=400, detail=RESOLUTION_TARGET_REQUIRED_DETAIL)

    status = str(body.get("status") or "resolved").strip() or "resolved"
    if status not in SUPPORTED_RESOLUTION_STATUSES:
        raise HTTPException(status_code=400, detail=RESOLUTION_STATUS_UNSUPPORTED_DETAIL)

    content = artifact_content(artifact)
    records = research_conflict_review_records(content)
    record = {
        "conflict_id": conflict_id or claim_id,
        "claim_id": claim_id,
        "status": status,
        "resolution": compact_text(body.get("resolution"), 1000),
        "note": compact_text(body.get("note"), 1000),
        "reviewer": compact_text(body.get("reviewer"), 120),
        "updated_at": now(),
    }
    _upsert_review_record(records, record)
    content["conflict_review_resolutions"] = records
    artifact.content = content
    save_artifact(artifact)
    return {
        "resolution": record,
        "archive": research_archive_payload(artifact),
    }


def _upsert_review_record(
    records: list[dict[str, Any]],
    record: dict[str, Any],
) -> None:
    for index, existing in enumerate(records):
        if (
            str(existing.get("conflict_id") or "") == record["conflict_id"]
            or (
                record["claim_id"]
                and str(existing.get("claim_id") or "") == record["claim_id"]
            )
        ):
            records[index] = record
            return
    records.append(record)
