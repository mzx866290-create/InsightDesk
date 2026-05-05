from fastapi.testclient import TestClient

import backend.api_server as api_server
import backend.artifact_service as artifact_service
from backend.stores.identity_store import SQLiteIdentityStore
from backend.stores.resource_access_store import SQLiteResourceAccessStore


def _patch_artifact_store(monkeypatch, tmp_path):
    artifact_store = artifact_service.SQLiteArtifactStore(
        db_path=str(tmp_path / "content.db")
    )
    monkeypatch.setattr(api_server, "_artifact_store", artifact_store)
    return artifact_store


def _patch_access_stores(monkeypatch, tmp_path):
    identity_store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    access_store = SQLiteResourceAccessStore(db_path=str(tmp_path / "access.db"))
    monkeypatch.setattr(api_server, "_identity_store", identity_store)
    monkeypatch.setattr(api_server, "_resource_access_store", access_store)
    return identity_store, access_store


def _set_remote_tokens(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        '{"tokens":[{"token":"viewer-token","role":"viewer","user_id":"viewer","auth_source":"test"},{"token":"editor-token","role":"editor","user_id":"editor","auth_source":"test"}]}',
    )


def _research_archive(
    artifact_id: str,
    *,
    session_id: str = "session-research",
    task_id: str = "task-research",
    title: str = "AI slide market",
) -> artifact_service.ArtifactRecord:
    return artifact_service.ArtifactRecord(
        artifact_id=artifact_id,
        session_id=session_id,
        artifact_type="report",
        title=title,
        status="ready",
        linked_resource_type="task",
        linked_resource_id=task_id,
        content={
            "markdown": "Research markdown about AI slide tools.",
            "research_archive": True,
            "task_id": task_id,
            "research_report": {
                "type": "research_report",
                "version": "v2",
                "query": "AI slide market",
                "summary": "AI slide tools are gaining enterprise usage.",
                "sources": [
                    {
                        "source_id": "source-1",
                        "title": "Enterprise AI Slides Report",
                        "url": "https://example.com/ai-slides",
                        "provider": "bing",
                        "capabilities": ["web_search", "freshness_filter"],
                        "source_tier": "secondary",
                        "freshness_band": "30d",
                        "snippet": "Enterprise buyers are testing AI slide tools.",
                    }
                ],
                "paragraph_citations": [
                    {
                        "paragraph_id": "p-1",
                        "section_id": "market-overview",
                        "text": "Enterprise procurement teams are piloting AI slide workflows.",
                        "claim_ids": ["claim-001"],
                        "source_ids": ["source-1"],
                        "anchor_id": "overview-p1",
                    }
                ],
                "delivery_quality": {
                    "coverage": {"claim_count": 1, "verification_ratio": 1.0}
                },
            },
            "claim_evidence_chains": [
                {
                    "claim_id": "claim-001",
                    "claim_text": "AI slide tools are gaining enterprise usage.",
                    "status": "verified",
                    "supporting_source_count": 1,
                    "has_primary_source": False,
                    "supporting_source_ids": ["source-1"],
                }
            ],
            "claim_verification_summary": {
                "total_claims": 1,
                "verified_claims": 1,
            },
        },
    )


def test_research_archive_list_returns_v2_archive_summaries(monkeypatch, tmp_path):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    artifact_store.save(_research_archive("artifact-research-1"))
    artifact_store.save(
        artifact_service.ArtifactRecord(
            artifact_id="artifact-report-plain",
            session_id="session-research",
            artifact_type="report",
            title="Plain report",
            status="ready",
            content={"markdown": "# Plain report", "qa_pairs": []},
        )
    )

    client = TestClient(api_server.app)
    response = client.get("/api/research/archives")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 100
    assert [item["artifact_id"] for item in payload["archives"]] == [
        "artifact-research-1"
    ]

    archive = payload["archives"][0]
    assert archive["title"] == "AI slide market"
    assert archive["session_id"] == "session-research"
    assert archive["task_id"] == "task-research"
    assert archive["claim_count"] == 1
    assert archive["source_count"] == 1
    assert archive["verification_summary"]["verified_claims"] == 1
    assert archive["delivery_quality"]["coverage"]["verification_ratio"] == 1.0
    assert archive["preview_claims"][0]["claim_id"] == "claim-001"
    assert archive["preview_sources"][0]["source_id"] == "source-1"
    assert archive["provider_capabilities"] == {
        "total_sources": 1,
        "declared_sources": 1,
        "providers": ["bing"],
        "items": [
            {
                "source_id": "source-1",
                "provider": "bing",
                "capabilities": ["web_search", "freshness_filter"],
                "declared": True,
            }
        ],
    }
    assert archive["citation_panel"]["version"] == "v2"
    assert archive["citation_panel"]["source_index"]["source-1"]["provider"] == "bing"
    assert archive["citation_panel"]["claim_source_links"] == [
        {"claim_id": "claim-001", "source_id": "source-1", "link_type": "supports"}
    ]
    assert archive["paragraph_citations"] == [
        {
            "paragraph_id": "p-1",
            "section_id": "market-overview",
            "text": "Enterprise procurement teams are piloting AI slide workflows.",
            "claim_ids": ["claim-001"],
            "source_ids": ["source-1"],
            "anchor_id": "overview-p1",
        }
    ]
    assert archive["paragraph_claim_links"] == [
        {
            "paragraph_id": "p-1",
            "anchor_id": "overview-p1",
            "claim_id": "claim-001",
            "link_type": "claim",
        },
        {
            "paragraph_id": "p-1",
            "anchor_id": "overview-p1",
            "source_id": "source-1",
            "link_type": "source",
        },
    ]
    assert archive["navigation_index"]["paragraph_to_claims"] == {
        "p-1": ["claim-001"]
    }
    assert archive["navigation_index"]["claim_to_paragraphs"] == {
        "claim-001": ["p-1"]
    }
    assert {
        "id": "paragraph:p-1",
        "type": "paragraph",
        "paragraph_id": "p-1",
        "anchor_id": "overview-p1",
        "text": "Enterprise procurement teams are piloting AI slide workflows.",
    } in archive["citation_graph"]["nodes"]
    assert {
        "id": "claim:claim-001",
        "type": "claim",
        "claim_id": "claim-001",
        "text": "AI slide tools are gaining enterprise usage.",
    } in archive["citation_graph"]["nodes"]
    assert {
        "source": "source:source-1",
        "target": "claim:claim-001",
        "type": "supports",
    } in archive["citation_graph"]["edges"]
    assert archive["conflict_summary"]["total"] == 0
    assert archive["conflict_summary"]["conflicting_claims"] == []
    assert archive["conflict_summary"]["items"] == []
    assert archive["conflict_summary"]["reviewed"] == 0
    assert archive["conflict_summary"]["unreviewed"] == 0
    assert payload["conflict_groups"] == []


def test_research_archive_list_filters_by_query_session_task_and_limit(
    monkeypatch,
    tmp_path,
):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    artifact_store.save(_research_archive("artifact-ai", session_id="session-a"))
    artifact_store.save(
        _research_archive(
            "artifact-energy",
            session_id="session-b",
            task_id="task-energy",
            title="Energy market",
        )
    )

    client = TestClient(api_server.app)

    query_response = client.get("/api/research/archives?q=enterprise")
    assert query_response.status_code == 200
    assert query_response.json()["total"] == 2

    paragraph_response = client.get("/api/research/archives?q=procurement")
    assert paragraph_response.status_code == 200
    assert paragraph_response.json()["total"] == 2

    scoped_response = client.get(
        "/api/research/archives?session_id=session-b&task_id=task-energy&limit=1"
    )
    assert scoped_response.status_code == 200
    scoped_payload = scoped_response.json()
    assert scoped_payload["limit"] == 1
    assert scoped_payload["total"] == 1
    assert scoped_payload["archives"][0]["artifact_id"] == "artifact-energy"


def test_research_archive_list_reuses_artifact_acl_filter(monkeypatch, tmp_path):
    _patch_access_stores(monkeypatch, tmp_path)
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)

    artifact_store.save(_research_archive("artifact-viewer"))
    artifact_store.save(_research_archive("artifact-editor"))
    api_server._resource_access_store.upsert_grant(
        resource_type="artifact",
        resource_id="artifact-viewer",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    api_server._resource_access_store.upsert_grant(
        resource_type="artifact",
        resource_id="artifact-editor",
        user_id="editor",
        role="owner",
        now=1.0,
    )

    client = TestClient(api_server.app)
    response = client.get(
        "/api/research/archives",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 200
    assert [item["artifact_id"] for item in response.json()["archives"]] == [
        "artifact-viewer"
    ]


def test_research_archive_list_returns_conflict_summary_and_searches_conflicts(
    monkeypatch,
    tmp_path,
):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    archive = _research_archive("artifact-conflict")
    archive.content["claim_evidence_chains"].append(
        {
            "claim_id": "claim-002",
            "claim_text": "Adoption is flat in regulated industries.",
            "status": "needs_attention",
            "supporting_source_ids": ["source-1"],
            "conflict_text": "Regulated industry adoption conflicts with enterprise pilot growth.",
        }
    )
    artifact_store.save(archive)

    client = TestClient(api_server.app)
    response = client.get("/api/research/archives?q=regulated")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    archive_payload = payload["archives"][0]
    assert archive_payload["conflict_summary"]["total"] == 1
    assert archive_payload["conflict_summary"]["conflicting_claims"] == ["claim-002"]
    assert archive_payload["conflict_summary"]["items"][0]["conflict_id"] == "claim-002"
    assert archive_payload["conflict_summary"]["items"][0]["review_status"] == "unreviewed"
    assert archive_payload["conflict_summary"]["items"][0]["text"] == (
        "Regulated industry adoption conflicts with enterprise pilot growth."
    )
    assert payload["conflict_groups"][0]["normalized_conflict_text"] == (
        "regulated industry adoption conflicts with enterprise pilot growth"
    )
    assert payload["conflict_groups"][0]["archives"][0]["artifact_id"] == "artifact-conflict"


def test_research_archive_list_surfaces_archive_conflict_review(
    monkeypatch,
    tmp_path,
):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    archive = _research_archive("artifact-archive-conflict")
    archive.content["research_report"]["archive_conflict_review"] = {
        "status": "conflicts_found",
        "conflict_count": 1,
        "review_action": "resolve_archive_conflicts",
        "conflicts": [
            {
                "claim_id": "claim-001",
                "claim_text": "Enterprise buyers are not adopting AI slide tools.",
                "archive_id": "archive-prior",
                "archive_claim_id": "claim-old",
                "archive_claim_text": "Enterprise buyers pilot AI slide tools.",
                "severity": "needs_review",
                "resolution_action": "compare_current_and_archive_sources",
            }
        ],
    }
    artifact_store.save(archive)

    client = TestClient(api_server.app)
    response = client.get("/api/research/archives?q=not%20adopting")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    summary = payload["archives"][0]["conflict_summary"]
    assert summary["total"] == 1
    assert summary["conflicting_claims"] == ["claim-001"]
    assert summary["items"][0]["conflict_id"] == "archive:archive-prior:claim-old:claim-001"
    assert summary["items"][0]["archive_id"] == "archive-prior"
    assert summary["items"][0]["archive_claim_id"] == "claim-old"
    assert summary["items"][0]["review_status"] == "unreviewed"
    assert payload["conflict_groups"][0]["archives"][0]["artifact_id"] == "artifact-archive-conflict"


def test_research_archive_conflict_groups_aggregate_across_archives(
    monkeypatch,
    tmp_path,
):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    for artifact_id, session_id in (
        ("artifact-conflict-a", "session-a"),
        ("artifact-conflict-b", "session-b"),
    ):
        archive = _research_archive(artifact_id, session_id=session_id)
        archive.content["claim_evidence_chains"].append(
            {
                "claim_id": "claim-shared",
                "claim_text": "Regulated industries are slower to adopt AI slides.",
                "status": "needs_attention",
                "supporting_source_ids": ["source-1"],
                "conflict_text": "Regulated industry adoption conflicts with enterprise pilot growth.",
            }
        )
        artifact_store.save(archive)

    client = TestClient(api_server.app)
    response = client.get("/api/research/archives?q=regulated")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["conflict_groups"][0]["total"] == 2
    assert payload["conflict_groups"][0]["claim_ids"] == ["claim-shared"]
    assert {
        item["artifact_id"] for item in payload["conflict_groups"][0]["archives"]
    } == {"artifact-conflict-a", "artifact-conflict-b"}


def test_research_archive_conflict_resolution_persists_to_artifact_content(
    monkeypatch,
    tmp_path,
):
    artifact_store = _patch_artifact_store(monkeypatch, tmp_path)
    archive = _research_archive("artifact-review")
    archive.content["claim_evidence_chains"].append(
        {
            "claim_id": "claim-review",
            "claim_text": "Adoption is flat in regulated industries.",
            "status": "needs_attention",
            "supporting_source_ids": ["source-1"],
            "conflict_text": "Regulated industry adoption conflicts with enterprise pilot growth.",
        }
    )
    artifact_store.save(archive)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/research/archives/artifact-review/conflict-resolutions",
        json={
            "claim_id": "claim-review",
            "status": "resolved",
            "resolution": "Accepted enterprise pilot growth and noted regulated lag.",
            "reviewer": "qa",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"]["status"] == "resolved"
    stored = artifact_store.get("artifact-review")
    assert stored.content["conflict_review_resolutions"][0]["claim_id"] == "claim-review"
    reviewed_item = payload["archive"]["conflict_summary"]["items"][0]
    assert reviewed_item["review_status"] == "resolved"
    assert reviewed_item["review"]["resolution"] == (
        "Accepted enterprise pilot growth and noted regulated lag."
    )
