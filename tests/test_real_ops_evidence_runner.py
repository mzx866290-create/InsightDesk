from __future__ import annotations

import json
from pathlib import Path

from deploy import run_real_ops_evidence as runner


def test_real_ops_evidence_plan_is_inert_when_checks_are_blocked(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(runner, "_run_command", lambda command, **_: calls.append(tuple(command)))

    report = runner.run_real_evidence(
        env={},
        only=("storage_real_integration",),
        execute=False,
    )

    assert report["ok"] is True
    assert report["mode"] == "plan"
    assert report["summary"]["selected"] == 1  # type: ignore[index]
    assert report["summary"]["blocked"] == 1  # type: ignore[index]
    assert report["summary"]["executed"] == 0  # type: ignore[index]
    assert calls == []


def test_real_ops_evidence_skip_probes_avoids_live_tool_checks(monkeypatch) -> None:
    probe_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runner.readiness,
        "_run_probe",
        lambda command, *, env: probe_calls.append(tuple(command)) or {"ok": False},
    )
    monkeypatch.setattr(runner.readiness.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    report = runner.run_real_evidence(
        env={},
        only=("arq_drain_drill",),
        execute=False,
        probe_tools=False,
    )

    check = report["plan"]["checks"][0]  # type: ignore[index]
    assert report["probe_tools"] is False
    assert report["plan"]["probe_tools"] is False  # type: ignore[index]
    assert check["probes_skipped"] is True
    assert check["runnable"] is True
    assert probe_calls == []


def test_real_ops_evidence_execute_refuses_partial_execution(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(runner, "_run_command", lambda command, **_: calls.append(tuple(command)))

    report = runner.run_real_evidence(
        env={},
        only=("storage_real_integration",),
        execute=True,
    )

    assert report["ok"] is False
    assert report["mode"] == "execute"
    assert report["summary"]["blocked_ids"] == ["storage_real_integration"]  # type: ignore[index]
    assert report["summary"]["executed"] == 0  # type: ignore[index]
    assert calls == []


def test_real_ops_evidence_strict_plan_fails_before_execution(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(runner, "_run_command", lambda command, **_: calls.append(tuple(command)))

    report = runner.run_real_evidence(
        env={},
        only=("storage_real_integration",),
        execute=False,
        strict_plan=True,
    )

    assert report["ok"] is False
    assert report["strict_plan"] is True
    assert report["summary"]["blocked_ids"] == ["storage_real_integration"]  # type: ignore[index]
    assert report["summary"]["executed"] == 0  # type: ignore[index]
    assert calls == []


def test_real_ops_evidence_execute_runs_when_selected_check_is_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        runner.readiness,
        "_run_probe",
        lambda command, *, env: {"ok": True, "returncode": 0, "detail": "ok"},
    )
    monkeypatch.setattr(runner.readiness.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, timeout_seconds):
        calls.append(tuple(command))
        return {
            "ok": True,
            "returncode": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
            "error": "",
        }

    monkeypatch.setattr(runner, "_run_command", fake_run)

    report = runner.run_real_evidence(
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        only=("k8s_real_cluster_probe",),
        execute=True,
        timeout_seconds=1,
    )

    assert report["ok"] is True
    assert report["summary"]["executed"] == 1  # type: ignore[index]
    assert report["results"][0]["id"] == "k8s_real_cluster_probe"  # type: ignore[index]
    assert calls[0][1] == "deploy/run_k8s_rollout_drill.py"


def test_real_ops_evidence_strict_verifier_can_fail_after_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        runner.readiness,
        "_run_probe",
        lambda command, *, env: {"ok": True, "returncode": 0, "detail": "ok"},
    )
    monkeypatch.setattr(runner.readiness.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        runner,
        "_run_command",
        lambda command, *, timeout_seconds: {
            "ok": True,
            "returncode": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
            "error": "",
        },
    )
    monkeypatch.setattr(
        runner.verify_ops_evidence,
        "build_evidence_verification_report",
        lambda *, strict: {"ok": False, "strict": strict, "summary": {"pending": 1}},
    )

    report = runner.run_real_evidence(
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        only=("k8s_real_cluster_probe",),
        execute=True,
        strict_verifier=True,
    )

    assert report["ok"] is False
    assert report["summary"]["executed"] == 1  # type: ignore[index]
    assert report["verifier"]["ok"] is False  # type: ignore[index]


def test_real_ops_evidence_unknown_or_empty_selection_fails() -> None:
    unknown = runner.run_real_evidence(only=("does_not_exist",), execute=False)
    empty = runner.run_real_evidence(
        only=("storage_real_integration",),
        skip=("storage_real_integration",),
        execute=False,
    )

    assert unknown["ok"] is False
    assert unknown["summary"]["unknown_ids"] == ["does_not_exist"]  # type: ignore[index]
    assert empty["ok"] is False
    assert empty["summary"]["selected"] == 0  # type: ignore[index]


def test_real_ops_evidence_runner_writes_report_archive_and_history(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "runner-report.json"
    archive_dir = tmp_path / "archive"
    history_path = tmp_path / "history.json"
    report = runner.run_real_evidence(
        env={},
        only=("storage_real_integration",),
        execute=False,
        strict_plan=True,
    )

    runner.emit_evidence_report(
        report,
        report_path=str(report_path),
        archive_dir=str(archive_dir),
        history_path=str(history_path),
    )

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    archives = list(archive_dir.glob("real_ops_evidence_runner-*.json"))

    assert persisted["evidence"]["report_path"] == str(report_path)
    assert persisted["evidence"]["history_path"] == str(history_path)
    assert persisted["evidence"]["archive_path"] == str(archives[0])
    assert history[-1]["id"] == "real_ops_evidence_runner"
    assert history[-1]["strict_plan"] is True
    assert history[-1]["probe_tools"] is True
    assert history[-1]["selected"] == 1
    assert history[-1]["blocked"] == 1
    assert history[-1]["summary"]["selected"] == 1
    assert history[-1]["plan"]["checks"][0]["id"] == "storage_real_integration"
    assert history[-1]["results"] == []
    assert history[-1]["verifier"] is None
    assert len(archives) == 1
