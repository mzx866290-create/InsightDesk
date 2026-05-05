from __future__ import annotations

import pytest

from deploy import run_ops_readiness as readiness


@pytest.fixture(autouse=True)
def _stable_tool_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep readiness unit tests independent from the developer workstation."""

    monkeypatch.setattr(readiness.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        readiness,
        "_run_probe",
        lambda command, *, env: {"ok": True, "returncode": 0, "detail": "ok"},
    )


def test_ops_readiness_covers_remaining_runtime_drills() -> None:
    checks = {check.id: check for check in readiness.all_readiness_checks()}

    required = {
        "arq_long_running_smoke",
        "arq_long_running_validation",
        "arq_drain_drill",
        "storage_migration_preflight",
        "storage_real_migration_contract",
        "storage_real_integration",
        "storage_rollback_plan",
        "storage_real_rollback_contract",
        "helm_static_validation",
        "helm_config_hot_reload_contract",
        "k8s_real_cluster_probe",
        "k8s_config_reload_drill",
        "final_validation_quick",
        "task_backend_default_switch_contract",
    }

    assert required.issubset(checks)
    assert checks["arq_drain_drill"].real_environment is True
    assert checks["arq_drain_drill"].report_path == "runtime\\ops-readiness\\arq\\arq-drain-drill.json" or checks["arq_drain_drill"].report_path == "runtime/ops-readiness/arq/arq-drain-drill.json"
    assert "--history-path" in checks["arq_drain_drill"].command
    assert "--manifest-path" in checks["arq_drain_drill"].command
    assert "--docker-start-hint" in checks["arq_drain_drill"].command
    assert "--skip-if-unavailable" in checks["arq_drain_drill"].command
    assert checks["arq_drain_drill"].evidence_manifest_path
    assert "drain_closed" in checks["arq_drain_drill"].checklist
    assert "closure.decision" in checks["arq_drain_drill"].report_fields
    assert checks["arq_long_running_validation"].required_env == ("ARQ_LONG_RUNNING_TEST",)
    assert "--report-path" in checks["arq_long_running_validation"].command
    assert "--manifest-path" in checks["arq_long_running_validation"].command
    assert "--skip-if-unavailable" in checks["arq_long_running_validation"].command
    assert checks["arq_long_running_validation"].evidence_manifest_path
    assert "iteration_completion" in checks["arq_long_running_validation"].checklist
    assert checks["arq_long_running_smoke"].report_path
    assert "--manifest-path" in checks["arq_long_running_smoke"].command
    assert "--skip-if-unavailable" in checks["arq_long_running_smoke"].command
    assert checks["arq_long_running_smoke"].evidence_manifest_path
    assert "persisted_task_completed" in checks["arq_long_running_smoke"].checklist
    assert checks["storage_real_integration"].required_env == (
        "STORAGE_INTEGRATION_TEST",
        "DATABASE_URL",
        "QDRANT_URL",
    )
    assert checks["storage_real_integration"].report_path
    assert checks["storage_real_integration"].archive_dir
    assert "--report-path" in checks["storage_real_integration"].command
    assert "--archive-dir" in checks["storage_real_integration"].command
    assert "--history-path" in checks["storage_real_integration"].command
    assert "--manifest-path" in checks["storage_real_integration"].command
    assert checks["storage_real_integration"].evidence_manifest_path
    assert "postgres_real_check" in checks["storage_real_integration"].checklist
    assert "evidence_bundle" in checks["storage_real_integration"].report_fields
    assert checks["storage_real_migration_contract"].required_env == (
        "STORAGE_MIGRATION_EXECUTE",
        "DATABASE_URL",
        "QDRANT_URL",
    )
    assert checks["storage_real_migration_contract"].real_environment is True
    assert "--execute" in checks["storage_real_migration_contract"].command
    assert "--manifest-path" in checks["storage_real_migration_contract"].command
    assert checks["storage_real_migration_contract"].evidence_manifest_path
    assert checks["storage_rollback_plan"].safe_to_run is True
    assert checks["storage_rollback_plan"].report_path
    assert checks["storage_rollback_plan"].evidence_manifest_path
    assert checks["storage_real_rollback_contract"].required_env == (
        "STORAGE_MIGRATION_ROLLBACK",
        "DATABASE_URL",
    )
    assert checks["storage_real_rollback_contract"].history_path
    assert checks["storage_real_rollback_contract"].evidence_manifest_path
    assert checks["helm_static_validation"].safe_to_run is True
    assert checks["task_backend_default_switch_contract"].safe_to_run is True
    assert checks["k8s_real_cluster_probe"].command[:3] == (
        checks["k8s_real_cluster_probe"].command[0],
        "deploy/run_k8s_rollout_drill.py",
        "--json",
    )
    assert "--report-path" in checks["k8s_real_cluster_probe"].command
    assert "--archive-dir" in checks["k8s_real_cluster_probe"].command
    assert "--history-path" in checks["k8s_real_cluster_probe"].command
    assert "--manifest-path" in checks["k8s_real_cluster_probe"].command
    assert checks["k8s_real_cluster_probe"].report_path
    assert checks["k8s_real_cluster_probe"].archive_dir
    assert checks["k8s_real_cluster_probe"].history_path
    assert checks["k8s_real_cluster_probe"].evidence_manifest_path
    assert "hot_reload_checklist" in checks["k8s_real_cluster_probe"].checklist
    assert "contracts.real_cluster" in checks["k8s_real_cluster_probe"].report_fields
    assert checks["k8s_real_cluster_probe"].required_tools == ("helm", "kubectl")
    assert checks["k8s_config_reload_drill"].required_tools == ("helm", "kubectl")
    assert checks["k8s_config_reload_drill"].report_path
    assert checks["k8s_config_reload_drill"].evidence_manifest_path
    assert "graceful_shutdown_checklist" in checks["k8s_config_reload_drill"].checklist


def test_ops_readiness_default_report_excludes_real_environment() -> None:
    report = readiness.build_readiness_report(env={}, include_real=False, run_safe=False)

    assert report["ok"] is True
    assert report["summary"]["included"] == 6  # type: ignore[index]
    assert report["summary"]["blocked"] == 0  # type: ignore[index]
    assert report["summary"]["arq_report_history_path"]  # type: ignore[index]
    assert report["summary"]["arq_evidence_manifest_path"]  # type: ignore[index]
    assert "arq_drain_drill" in report["summary"]["arq_report_paths"]  # type: ignore[index]
    assert "arq_drain_drill" in report["summary"]["arq_evidence_manifest_paths"]  # type: ignore[index]
    assert report["summary"]["storage_report_history_path"]  # type: ignore[index]
    assert report["summary"]["storage_evidence_manifest_path"]  # type: ignore[index]
    assert "storage_real_integration" in report["summary"]["storage_report_paths"]  # type: ignore[index]
    assert "storage_real_integration" in report["summary"]["storage_evidence_manifest_paths"]  # type: ignore[index]
    assert report["summary"]["k8s_report_history_path"]  # type: ignore[index]
    assert report["summary"]["k8s_evidence_manifest_path"]  # type: ignore[index]
    default_switch = report["summary"]["task_backend_default_switch"]  # type: ignore[index]
    assert default_switch["decision"] == "keep_memory_default"
    assert default_switch["switch_ready"] is False
    assert default_switch["blockers"] == []
    assert "k8s_real_cluster_probe" in report["summary"]["k8s_report_paths"]  # type: ignore[index]
    assert "k8s_config_reload_drill" in report["summary"]["k8s_report_paths"]  # type: ignore[index]
    assert "k8s_real_cluster_probe" in report["summary"]["k8s_evidence_manifest_paths"]  # type: ignore[index]
    manifest = report["evidence_manifest"]  # type: ignore[index]
    assert manifest["id"] == "ops_readiness_evidence_manifest"
    assert manifest["areas"]["arq"]["manifest_path"] == report["summary"]["arq_evidence_manifest_path"]  # type: ignore[index]
    assert manifest["areas"]["storage"]["manifest_path"] == report["summary"]["storage_evidence_manifest_path"]  # type: ignore[index]
    assert manifest["areas"]["k8s"]["manifest_path"] == report["summary"]["k8s_evidence_manifest_path"]  # type: ignore[index]
    assert manifest["areas"]["arq"]["remaining_real_drills"] == []
    assert manifest["areas"]["storage"]["remaining_real_drills"] == []
    assert manifest["areas"]["k8s"]["remaining_real_drills"] == []
    assert "arq_drain_drill" in manifest["areas"]["arq"]["execution_remaining_real_drills"]
    assert "storage_real_integration" in manifest["areas"]["storage"]["execution_remaining_real_drills"]
    assert "k8s_real_cluster_probe" in manifest["areas"]["k8s"]["execution_remaining_real_drills"]
    blocked_real = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "arq_drain_drill"
    ][0]
    assert blocked_real["included"] is False
    assert blocked_real["blockers"] == ["real_environment_not_included"]

    long_running = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "arq_long_running_validation"
    ][0]
    assert long_running["included"] is False
    assert long_running["blockers"] == ["real_environment_not_included"]


def test_ops_readiness_real_report_names_missing_gates() -> None:
    report = readiness.build_readiness_report(env={}, include_real=True, run_safe=False)

    assert report["ok"] is False
    assert report["summary"]["blocked"] >= 2  # type: ignore[index]

    storage = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "storage_real_integration"
    ][0]
    assert "missing_env:STORAGE_INTEGRATION_TEST" in storage["blockers"]
    assert "missing_env:DATABASE_URL" in storage["blockers"]
    assert "missing_env:QDRANT_URL" in storage["blockers"]

    migration = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "storage_real_migration_contract"
    ][0]
    assert "missing_env:STORAGE_MIGRATION_EXECUTE" in migration["blockers"]
    assert "missing_env:DATABASE_URL" in migration["blockers"]
    assert "missing_env:QDRANT_URL" in migration["blockers"]

    rollback = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "storage_real_rollback_contract"
    ][0]
    assert "missing_env:STORAGE_MIGRATION_ROLLBACK" in rollback["blockers"]
    assert "missing_env:DATABASE_URL" in rollback["blockers"]

    long_running = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "arq_long_running_validation"
    ][0]
    assert "missing_env:ARQ_LONG_RUNNING_TEST" in long_running["blockers"]


def test_ops_readiness_blocks_default_switch_until_arq_evidence_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        readiness,
        "_read_json_report",
        lambda path: {"exists": False, "ok": False, "blocker": "missing_evidence"},
    )

    report = readiness.build_readiness_report(
        env={"TASK_BACKEND_SWITCH_READY": "1", "ARQ_LONG_RUNNING_TEST": "1"},
        include_real=True,
        run_safe=False,
    )

    default_switch = report["summary"]["task_backend_default_switch"]  # type: ignore[index]
    assert default_switch["switch_ready"] is True
    assert default_switch["decision"] == "blocked_until_arq_evidence_closes"
    assert any(
        str(blocker).startswith("default_switch_blocked:arq_long_running_validation")
        for blocker in default_switch["blockers"]
    )

    gate = [
        check
        for check in report["checks"]  # type: ignore[index]
        if check["id"] == "task_backend_default_switch_contract"
    ][0]
    assert gate["status"] == "blocked"
    assert gate["runnable"] is False


def test_ops_readiness_allows_default_switch_with_closed_arq_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        readiness,
        "_read_json_report",
        lambda path: {
            "exists": True,
            "ok": True,
            "skipped": False,
            "blocker": "",
            "archive_path": "runtime/ops-readiness/arq/archive/report.json",
        },
    )
    report = readiness.build_readiness_report(
        env={"TASK_BACKEND_SWITCH_READY": "1", "ARQ_LONG_RUNNING_TEST": "1"},
        include_real=True,
        run_safe=False,
    )

    default_switch = report["summary"]["task_backend_default_switch"]  # type: ignore[index]
    assert default_switch["decision"] == "eligible_for_arq_default"
    assert default_switch["blockers"] == []


def test_ops_readiness_storage_gate_accepts_enabled_env() -> None:
    storage_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "storage_real_integration"
    ][0]
    described = readiness.describe_check(
        storage_check,
        env={
            "STORAGE_INTEGRATION_TEST": "1",
            "DATABASE_URL": "postgresql://user:pass@db/app",
            "QDRANT_URL": "http://qdrant:6333",
        },
        include_real=True,
    )

    assert "missing_env:ARQ_LONG_RUNNING_TEST" not in described["blockers"]


def test_ops_readiness_storage_migration_gate_accepts_enabled_env() -> None:
    migration_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "storage_real_migration_contract"
    ][0]
    described = readiness.describe_check(
        migration_check,
        env={
            "STORAGE_MIGRATION_EXECUTE": "1",
            "DATABASE_URL": "postgresql://user:pass@db/app",
            "QDRANT_URL": "http://qdrant:6333",
        },
        include_real=True,
    )

    assert described["status"] == "ready"
    assert described["runnable"] is True
    assert described["blockers"] == []


def test_ops_readiness_arq_long_running_gate_accepts_enabled_env() -> None:
    long_running_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "arq_long_running_validation"
    ][0]
    described = readiness.describe_check(
        long_running_check,
        env={"ARQ_LONG_RUNNING_TEST": "1"},
        include_real=True,
    )

    assert described["status"] == "ready"
    assert described["runnable"] is True
    assert described["blockers"] == []


def test_ops_readiness_storage_rollback_gate_accepts_enabled_env() -> None:
    rollback_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "storage_real_rollback_contract"
    ][0]
    described = readiness.describe_check(
        rollback_check,
        env={
            "STORAGE_MIGRATION_ROLLBACK": "1",
            "DATABASE_URL": "postgresql://user:pass@db/app",
        },
        include_real=True,
    )

    assert described["status"] == "ready"
    assert described["runnable"] is True
    assert described["blockers"] == []


def test_ops_readiness_reports_docker_cli_present_but_daemon_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(command: tuple[str, ...], *, env: dict[str, str]) -> dict[str, object]:
        assert command[:2] == ("docker", "info")
        return {
            "ok": False,
            "returncode": 1,
            "detail": "Cannot connect to the Docker daemon",
        }

    monkeypatch.setattr(readiness, "_run_probe", fake_probe)
    smoke_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "arq_long_running_smoke"
    ][0]

    described = readiness.describe_check(smoke_check, env={}, include_real=True)

    assert described["status"] == "blocked"
    assert described["runnable"] is False
    assert "docker_daemon_unavailable" in described["blockers"]
    assert described["probes"]["docker"]["detail"] == "Cannot connect to the Docker daemon"  # type: ignore[index]
    assert "start_contract" in described["probes"]["docker"]  # type: ignore[index]


def test_ops_readiness_can_skip_live_tool_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        readiness,
        "_run_probe",
        lambda command, *, env: calls.append(command) or {"ok": False},
    )
    smoke_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "arq_long_running_smoke"
    ][0]

    described = readiness.describe_check(
        smoke_check,
        env={},
        include_real=True,
        probe_tools=False,
    )

    assert described["status"] == "ready"
    assert described["runnable"] is True
    assert described["probes_skipped"] is True
    assert calls == []


def test_ops_readiness_reports_kubectl_without_current_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(command: tuple[str, ...], *, env: dict[str, str]) -> dict[str, object]:
        assert command == ("kubectl", "config", "current-context")
        return {"ok": False, "returncode": 1, "detail": "current-context is not set"}

    monkeypatch.setattr(readiness, "_run_probe", fake_probe)
    k8s_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "k8s_real_cluster_probe"
    ][0]

    described = readiness.describe_check(
        k8s_check,
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        include_real=True,
    )

    assert described["status"] == "blocked"
    assert described["runnable"] is False
    assert "kubectl_current_context_missing" in described["blockers"]
    assert described["probes"]["kubectl"]["detail"] == "current-context is not set"  # type: ignore[index]


def test_ops_readiness_k8s_gate_accepts_enabled_env() -> None:
    k8s_check = [
        check
        for check in readiness.all_readiness_checks()
        if check.id == "k8s_real_cluster_probe"
    ][0]
    described = readiness.describe_check(
        k8s_check,
        env={"OPS_REAL_CLUSTER_TEST": "1"},
        include_real=True,
    )

    assert described["status"] == "ready"
    assert described["runnable"] is True
    assert described["blockers"] == []
