from __future__ import annotations

import json
from pathlib import Path

from deploy import run_ops_readiness as readiness
from deploy import verify_ops_evidence as verifier


def _write_json(root: Path, relative_path: str, payload: dict[str, object]) -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_ops_evidence_verifier_is_non_blocking_without_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    report = verifier.build_evidence_verification_report(strict=False)
    strict_report = verifier.build_evidence_verification_report(strict=True)

    assert report["ok"] is True
    assert report["all_closed"] is False
    assert report["summary"]["pending"] == 8  # type: ignore[index]
    assert strict_report["ok"] is False


def test_ops_evidence_verifier_accepts_closed_reports_and_manifest_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    real_checks = [check for check in readiness.all_readiness_checks() if check.real_environment]
    manifests: dict[str, dict[str, object]] = {}

    for check in real_checks:
        _write_json(
            tmp_path,
            check.report_path,
            {
                "ok": True,
                "status": "ready",
                "skipped": False,
                "blockers": [],
                "closure": {"complete": True, "blockers": []},
            },
        )
        manifest = manifests.setdefault(
            check.evidence_manifest_path,
            {"schema_version": 1, "updated_at": "2026-05-04T00:00:00Z", "reports": {}},
        )
        reports = manifest["reports"]
        assert isinstance(reports, dict)
        reports[check.id if check.area != "4.3_deploy_ops" else Path(check.report_path).stem] = {
            "id": check.id,
            "ok": True,
            "status": "ready",
            "skipped": False,
            "blockers": [],
            "report_path": check.report_path,
            "paths": {"report_path": check.report_path},
        }

    for manifest_path, manifest in manifests.items():
        _write_json(tmp_path, manifest_path, manifest)

    report = verifier.build_evidence_verification_report(strict=True)

    assert report["ok"] is True
    assert report["all_closed"] is True
    assert report["summary"]["closed"] == 8  # type: ignore[index]
    assert report["blockers"] == []


def test_ops_evidence_verifier_rejects_skipped_or_blocked_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    check = [
        item
        for item in readiness.all_readiness_checks()
        if item.id == "arq_drain_drill"
    ][0]
    _write_json(
        tmp_path,
        check.report_path,
        {
            "ok": False,
            "status": "skipped",
            "skipped": True,
            "blockers": ["docker_daemon_unavailable"],
        },
    )
    _write_json(
        tmp_path,
        check.evidence_manifest_path,
        {
            "schema_version": 1,
            "updated_at": "2026-05-04T00:00:00Z",
            "reports": {
                check.id: {
                    "id": check.id,
                    "ok": False,
                    "status": "skipped",
                    "skipped": True,
                    "blockers": ["docker_daemon_unavailable"],
                }
            },
        },
    )

    report = verifier.build_evidence_verification_report(strict=True)
    arq_drain = [item for item in report["checks"] if item["id"] == check.id][0]  # type: ignore[index]

    assert report["ok"] is False
    assert arq_drain["closed"] is False
    assert "report:report_skipped" in arq_drain["blockers"]
    assert "manifest:manifest_skipped" in arq_drain["blockers"]
