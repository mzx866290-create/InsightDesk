from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.research_archive_route_helpers import (
    RESEARCH_ARCHIVE_REQUIRED_DETAIL,
    RESOLUTION_PAYLOAD_OBJECT_DETAIL,
    RESOLUTION_STATUS_UNSUPPORTED_DETAIL,
    RESOLUTION_TARGET_REQUIRED_DETAIL,
    research_archives_list_payload,
    upsert_research_conflict_resolution_result,
)


def _archive(
    artifact_id: str = "artifact-research",
    *,
    session_id: str = "session-1",
    task_id: str = "task-1",
    title: str = "AI slide market",
):
    return SimpleNamespace(
        artifact_id=artifact_id,
        session_id=session_id,
        linked_resource_type="task",
        linked_resource_id=task_id,
        artifact_type="report",
        title=title,
        created_at=1.0,
        updated_at=2.0,
        content={
            "research_archive": True,
            "task_id": task_id,
            "markdown": "Enterprise procurement teams are piloting AI slide workflows.",
            "claim_evidence_chains": [
                {
                    "claim_id": "claim-1",
                    "claim_text": "Enterprise teams are piloting AI slide workflows.",
                    "status": "needs_attention",
                    "conflict_text": "Procurement adoption evidence needs review.",
                }
            ],
            "claim_verification_summary": {"total_claims": 1},
        },
    )


def test_research_archives_list_payload_filters_visibility_and_builds_payload():
    archive = _archive()
    hidden = _archive("artifact-hidden", session_id="session-hidden")
    plain_report = SimpleNamespace(
        artifact_id="artifact-report",
        artifact_type="report",
        title="Plain report",
        session_id="session-1",
        content={"markdown": "enterprise"},
    )
    visible_inputs = []

    def filter_visible_resources(request, resources, **kwargs):
        visible_inputs.append(
            {
                "request": request,
                "resource_type": kwargs["resource_type"],
                "access_store": kwargs["access_store"],
                "identity_store": kwargs["identity_store"],
                "ids": [kwargs["resource_id_getter"](resource) for resource in resources],
            }
        )
        return [resource for resource in resources if resource.artifact_id != "artifact-hidden"]

    request = SimpleNamespace(user="viewer")
    payload = research_archives_list_payload(
        request=request,
        artifacts=[archive, hidden, plain_report],
        q="procurement",
        session_id="",
        task_id="",
        limit=1,
        filter_visible_resources=filter_visible_resources,
        require_remote_viewer=lambda req: {"role": "viewer"},
        access_store="access-store",
        identity_store="identity-store",
    )

    assert visible_inputs == [
        {
            "request": request,
            "resource_type": "artifact",
            "access_store": "access-store",
            "identity_store": "identity-store",
            "ids": ["artifact-research", "artifact-hidden"],
        }
    ]
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert [item["artifact_id"] for item in payload["archives"]] == ["artifact-research"]
    assert payload["conflict_groups"][0]["archives"][0]["artifact_id"] == "artifact-research"


def test_upsert_research_conflict_resolution_result_appends_and_replaces_records():
    archive = _archive()
    saved = []

    first = upsert_research_conflict_resolution_result(
        artifact=archive,
        body={
            "claim_id": "claim-1",
            "status": "resolved",
            "resolution": "Accepted with caveat.",
            "reviewer": "qa",
        },
        save_artifact=saved.append,
        now=lambda: 123.0,
    )

    assert first["resolution"] == {
        "conflict_id": "claim-1",
        "claim_id": "claim-1",
        "status": "resolved",
        "resolution": "Accepted with caveat.",
        "note": "",
        "reviewer": "qa",
        "updated_at": 123.0,
    }
    assert saved == [archive]
    assert archive.content["conflict_review_resolutions"] == [first["resolution"]]
    assert first["archive"]["conflict_summary"]["items"][0]["review_status"] == "resolved"

    second = upsert_research_conflict_resolution_result(
        artifact=archive,
        body={
            "conflict_id": "claim-1",
            "claim_id": "claim-1",
            "status": "dismissed",
            "note": "No longer relevant.",
        },
        save_artifact=saved.append,
        now=lambda: 456.0,
    )

    assert len(archive.content["conflict_review_resolutions"]) == 1
    assert second["resolution"]["status"] == "dismissed"
    assert second["resolution"]["updated_at"] == 456.0
    assert saved == [archive, archive]


def test_upsert_research_conflict_resolution_result_validates_payload():
    archive = _archive()

    with pytest.raises(HTTPException) as not_archive_exc:
        upsert_research_conflict_resolution_result(
            artifact=SimpleNamespace(artifact_type="report", content={}),
            body={},
            save_artifact=lambda artifact: None,
            now=lambda: 1.0,
        )
    assert not_archive_exc.value.status_code == 400
    assert not_archive_exc.value.detail == RESEARCH_ARCHIVE_REQUIRED_DETAIL

    with pytest.raises(HTTPException) as object_exc:
        upsert_research_conflict_resolution_result(
            artifact=archive,
            body=[],
            save_artifact=lambda artifact: None,
            now=lambda: 1.0,
        )
    assert object_exc.value.status_code == 400
    assert object_exc.value.detail == RESOLUTION_PAYLOAD_OBJECT_DETAIL

    with pytest.raises(HTTPException) as target_exc:
        upsert_research_conflict_resolution_result(
            artifact=archive,
            body={"status": "resolved"},
            save_artifact=lambda artifact: None,
            now=lambda: 1.0,
        )
    assert target_exc.value.status_code == 400
    assert target_exc.value.detail == RESOLUTION_TARGET_REQUIRED_DETAIL

    with pytest.raises(HTTPException) as status_exc:
        upsert_research_conflict_resolution_result(
            artifact=archive,
            body={"claim_id": "claim-1", "status": "invalid"},
            save_artifact=lambda artifact: None,
            now=lambda: 1.0,
        )
    assert status_exc.value.status_code == 400
    assert status_exc.value.detail == RESOLUTION_STATUS_UNSUPPORTED_DETAIL
