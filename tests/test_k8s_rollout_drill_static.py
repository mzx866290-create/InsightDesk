from __future__ import annotations

import json
from pathlib import Path

import pytest

from deploy import run_k8s_rollout_drill as drill


def test_k8s_rollout_drill_skips_without_real_cluster_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(drill, "_run_command", lambda command, **_: calls.append(tuple(command)))

    report = drill.build_k8s_rollout_drill_report(env={})

    assert report["ok"] is False
    assert report["status"] == "skipped"
    assert report["skipped"] is True
    assert report["blockers"] == ["missing_env:OPS_REAL_CLUSTER_TEST"]
    assert report["steps"] == []
    assert report["contracts"]["evidence"] == {  # type: ignore[index]
        "report_path": "",
        "archive_dir": "",
        "history_path": "",
        "manifest_path": "",
    }
    assert report["contracts"]["real_cluster"]["safe_without_gate"] is True  # type: ignore[index]
    assert report["contracts"]["real_cluster"]["commands_inert_without_gate"] is True  # type: ignore[index]
    assert calls == []


def test_k8s_rollout_drill_blocks_when_tools_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drill.shutil, "which", lambda _tool: None)

    report = drill.build_k8s_rollout_drill_report(env={"OPS_REAL_CLUSTER_TEST": "1"})

    assert report["status"] == "blocked"
    assert "missing_tool:helm" in report["blockers"]
    assert "missing_tool:kubectl" in report["blockers"]
    assert report["steps"] == []


def test_k8s_rollout_drill_reports_missing_current_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drill.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command: tuple[str, ...], **_: object) -> dict[str, object]:
        if command == ("kubectl", "config", "current-context"):
            return {"ok": True, "returncode": 0, "duration_ms": 1, "detail": ""}
        return {"ok": True, "returncode": 0, "duration_ms": 1, "detail": "ok"}

    monkeypatch.setattr(drill, "_run_command", fake_run)

    report = drill.build_k8s_rollout_drill_report(env={"OPS_REAL_CLUSTER_TEST": "1"})

    assert report["status"] == "blocked"
    assert report["blockers"] == ["kubectl_current_context_missing"]
    assert report["steps"][1]["id"] == "kubectl_current_context"  # type: ignore[index]
    assert report["steps"][1]["execution"]["detail"] == "kubectl current-context is empty"  # type: ignore[index]


def test_k8s_rollout_drill_runs_helm_and_rollout_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(drill.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command: tuple[str, ...], **_: object) -> dict[str, object]:
        commands.append(command)
        return {"ok": True, "returncode": 0, "duration_ms": 1, "detail": "ok"}

    monkeypatch.setattr(drill, "_run_command", fake_run)

    report = drill.build_k8s_rollout_drill_report(
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        release="insightdesk",
        namespace="prod",
        chart_dir=Path("deploy/helm/insightdesk"),
    )

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert commands[0][:3] == ("helm", "template", "insightdesk")
    assert ("kubectl", "get", "namespace", "prod") in commands
    assert (
        "kubectl",
        "rollout",
        "status",
        "deployment/insightdesk-api",
        "-n",
        "prod",
        "--timeout=120s",
    ) in commands


def test_k8s_rollout_drill_runs_worker_rollout_when_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(drill.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command: tuple[str, ...], **_: object) -> dict[str, object]:
        commands.append(command)
        return {"ok": True, "returncode": 0, "duration_ms": 1, "detail": "ok"}

    monkeypatch.setattr(drill, "_run_command", fake_run)

    report = drill.build_k8s_rollout_drill_report(
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        release="insightdesk",
        namespace="prod",
        chart_dir=Path("deploy/helm/insightdesk"),
        include_worker=True,
    )

    assert report["ok"] is True
    assert report["include_worker"] is True
    assert report["summary"]["total_steps"] == 7  # type: ignore[index]
    assert (
        "kubectl",
        "get",
        "deployment",
        "insightdesk-worker",
        "-n",
        "prod",
    ) in commands
    assert (
        "kubectl",
        "rollout",
        "status",
        "deployment/insightdesk-worker",
        "-n",
        "prod",
        "--timeout=120s",
    ) in commands


def test_k8s_rollout_drill_emits_local_evidence_without_real_cluster_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(drill, "_run_command", lambda command, **_: calls.append(tuple(command)))
    report_path = tmp_path / "report.json"
    archive_dir = tmp_path / "archive"
    history_path = tmp_path / "history.json"
    manifest_path = tmp_path / "manifest.json"

    report = drill.build_k8s_rollout_drill_report(
        env={},
        report_path=str(report_path),
        archive_dir=str(archive_dir),
        history_path=str(history_path),
        manifest_path=str(manifest_path),
    )
    drill.emit_evidence_report(
        report,
        report_path=str(report_path),
        archive_dir=str(archive_dir),
        history_path=str(history_path),
        manifest_path=str(manifest_path),
    )

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archives = list(archive_dir.glob("k8s_rollout_drill-*.json"))

    assert calls == []
    assert persisted["status"] == "skipped"
    assert persisted["evidence"]["report_path"] == str(report_path)
    assert persisted["evidence"]["manifest_path"] == str(manifest_path)
    assert persisted["contracts"]["evidence"]["archive_dir"] == str(archive_dir)
    assert history[-1]["status"] == "skipped"
    assert history[-1]["blockers"] == ["missing_env:OPS_REAL_CLUSTER_TEST"]
    assert manifest["status"] == "skipped"
    assert manifest["paths"]["manifest_path"] == str(manifest_path)
    assert "hot_reload_checklist" in manifest["required_evidence"]
    assert "graceful_shutdown_checklist" in manifest["required_evidence"]
    assert len(archives) == 1


def test_k8s_rollout_drill_manifest_accumulates_multiple_report_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drill, "_run_command", lambda command, **_: None)
    manifest_path = tmp_path / "manifest.json"
    history_path = tmp_path / "history.json"

    for report_name in ("k8s-real-cluster-probe.json", "k8s-config-reload-drill.json"):
        report_path = tmp_path / report_name
        report = drill.build_k8s_rollout_drill_report(
            env={},
            report_path=str(report_path),
            history_path=str(history_path),
            manifest_path=str(manifest_path),
        )
        drill.emit_evidence_report(
            report,
            report_path=str(report_path),
            history_path=str(history_path),
            manifest_path=str(manifest_path),
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert set(manifest["reports"]) == {
        "k8s-real-cluster-probe",
        "k8s-config-reload-drill",
    }
    assert manifest["reports"]["k8s-real-cluster-probe"]["paths"]["report_path"].endswith(
        "k8s-real-cluster-probe.json"
    )
    assert manifest["reports"]["k8s-config-reload-drill"]["paths"]["report_path"].endswith(
        "k8s-config-reload-drill.json"
    )
