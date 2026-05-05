"""Build an ops readiness report for production-only rollout drills.

The default mode is intentionally non-invasive: it lists the required commands,
environment gates, and blockers without connecting to Docker, PostgreSQL,
Qdrant, or Kubernetes. Use --run-safe to execute local static checks only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SAFE_CHECK_TIMEOUT_SECONDS = 180
PROBE_TIMEOUT_SECONDS = 15
ARQ_REPORT_DIR = Path("runtime") / "ops-readiness" / "arq"
ARQ_REPORT_HISTORY_PATH = ARQ_REPORT_DIR / "history.json"
ARQ_EVIDENCE_MANIFEST_PATH = ARQ_REPORT_DIR / "evidence-manifest.json"
TASK_BACKEND_SWITCH_READY_ENV = "TASK_BACKEND_SWITCH_READY"
TASK_BACKEND_DEFAULT_SWITCH_CHECK_ID = "task_backend_default_switch_contract"
ARQ_DEFAULT_SWITCH_REQUIRED_CHECKS = (
    "arq_long_running_smoke",
    "arq_long_running_validation",
    "arq_drain_drill",
)
STORAGE_REPORT_DIR = Path("runtime") / "ops-readiness" / "storage"
STORAGE_REPORT_ARCHIVE_DIR = STORAGE_REPORT_DIR / "archive"
STORAGE_REPORT_HISTORY_PATH = STORAGE_REPORT_DIR / "history.json"
STORAGE_EVIDENCE_MANIFEST_PATH = STORAGE_REPORT_DIR / "evidence-manifest.json"
K8S_REPORT_DIR = Path("runtime") / "ops-readiness" / "k8s"
K8S_REPORT_ARCHIVE_DIR = K8S_REPORT_DIR / "archive"
K8S_REPORT_HISTORY_PATH = K8S_REPORT_DIR / "history.json"
K8S_EVIDENCE_MANIFEST_PATH = K8S_REPORT_DIR / "evidence-manifest.json"
DOCKER_DESKTOP_START_COMMANDS = {
    "windows": "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'",
    "macos": "open -a Docker",
    "linux": "sudo systemctl start docker",
}


@dataclass(frozen=True)
class OpsReadinessCheck:
    """A rollout drill or validation gate with explicit execution safety."""

    id: str
    area: str
    description: str
    command: tuple[str, ...]
    required_env: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    report_path: str = ""
    archive_dir: str = ""
    history_path: str = ""
    evidence_manifest_path: str = ""
    checklist: tuple[str, ...] = ()
    report_fields: tuple[str, ...] = ()
    safe_to_run: bool = False
    real_environment: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "area": self.area,
            "description": self.description,
            "command": list(self.command),
            "required_env": list(self.required_env),
            "required_tools": list(self.required_tools),
            "report_path": self.report_path,
            "archive_dir": self.archive_dir,
            "history_path": self.history_path,
            "evidence_manifest_path": self.evidence_manifest_path,
            "checklist": list(self.checklist),
            "report_fields": list(self.report_fields),
            "safe_to_run": self.safe_to_run,
            "real_environment": self.real_environment,
        }


def _python_command(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


def _arq_report_path(name: str) -> str:
    return str(ARQ_REPORT_DIR / f"{name}.json")


def _storage_report_path(name: str) -> str:
    return str(STORAGE_REPORT_DIR / f"{name}.json")


def _k8s_report_path(name: str) -> str:
    return str(K8S_REPORT_DIR / f"{name}.json")


def all_readiness_checks() -> list[OpsReadinessCheck]:
    """Return the production rollout closure matrix."""

    return [
        OpsReadinessCheck(
            id="arq_long_running_smoke",
            area="1.2_async_queue",
            description="Run Redis/ARQ worker E2E smoke and confirm persisted task completion.",
            command=_python_command(
                "deploy/run_arq_e2e_smoke.py",
                "--timeout-seconds",
                "90",
                "--compose-timeout-seconds",
                "600",
                "--json",
                "--report-path",
                _arq_report_path("arq-long-running-smoke"),
                "--archive-dir",
                str(ARQ_REPORT_DIR / "archive"),
                "--history-path",
                str(ARQ_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(ARQ_EVIDENCE_MANIFEST_PATH),
                "--docker-start-hint",
                "--skip-if-unavailable",
            ),
            required_tools=("docker",),
            report_path=_arq_report_path("arq-long-running-smoke"),
            archive_dir=str(ARQ_REPORT_DIR / "archive"),
            history_path=str(ARQ_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(ARQ_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "docker_cli",
                "docker_daemon",
                "redis_service",
                "arq_worker_started",
                "persisted_task_completed",
                "evidence_archive",
            ),
            report_fields=(
                "ok",
                "skipped",
                "blockers",
                "task_id",
                "job_id",
                "evidence.decision",
                "archive_path",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="arq_long_running_validation",
            area="1.2_async_queue",
            description="Run the env-gated Redis/ARQ validation loop for sustained worker execution.",
            command=_python_command(
                "deploy/run_arq_long_running_validation.py",
                "--duration-seconds",
                "900",
                "--json",
                "--report-path",
                _arq_report_path("arq-long-running-validation"),
                "--archive-dir",
                str(ARQ_REPORT_DIR / "archive"),
                "--history-path",
                str(ARQ_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(ARQ_EVIDENCE_MANIFEST_PATH),
                "--docker-start-hint",
                "--skip-if-unavailable",
            ),
            required_env=("ARQ_LONG_RUNNING_TEST",),
            required_tools=("docker",),
            report_path=_arq_report_path("arq-long-running-validation"),
            archive_dir=str(ARQ_REPORT_DIR / "archive"),
            history_path=str(ARQ_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(ARQ_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "real_environment_gate",
                "docker_cli",
                "docker_daemon",
                "iteration_completion",
                "worker_heartbeat",
                "evidence_archive",
            ),
            report_fields=(
                "ok",
                "skipped",
                "closure.complete",
                "closure.decision",
                "completed_iterations",
                "failed_iterations",
                "evidence.archive_ready",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="arq_drain_drill",
            area="1.2_async_queue",
            description="Stop the ARQ worker during an active job and emit a drain closure report.",
            command=_python_command(
                "deploy/run_arq_drain_drill.py",
                "--timeout-seconds",
                "120",
                "--compose-timeout-seconds",
                "600",
                "--json",
                "--report-path",
                _arq_report_path("arq-drain-drill"),
                "--archive-dir",
                str(ARQ_REPORT_DIR / "archive"),
                "--history-path",
                str(ARQ_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(ARQ_EVIDENCE_MANIFEST_PATH),
                "--docker-start-hint",
                "--skip-if-unavailable",
            ),
            required_tools=("docker",),
            report_path=_arq_report_path("arq-drain-drill"),
            archive_dir=str(ARQ_REPORT_DIR / "archive"),
            history_path=str(ARQ_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(ARQ_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "docker_cli",
                "docker_daemon",
                "active_job_started",
                "worker_stop_requested",
                "drain_closed",
                "evidence_archive",
            ),
            report_fields=(
                "ok",
                "skipped",
                "closure.complete",
                "closure.decision",
                "closure.evidence",
                "archive_path",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="storage_migration_preflight",
            area="1.3_storage_runtime",
            description="Validate storage provider configuration before real PostgreSQL/Qdrant rollout.",
            command=_python_command(
                "deploy/validate_storage_migration.py",
                "--json",
                "--report-path",
                _storage_report_path("storage-migration-preflight"),
                "--archive-dir",
                str(STORAGE_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(STORAGE_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(STORAGE_EVIDENCE_MANIFEST_PATH),
            ),
            report_path=_storage_report_path("storage-migration-preflight"),
            archive_dir=str(STORAGE_REPORT_ARCHIVE_DIR),
            history_path=str(STORAGE_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(STORAGE_EVIDENCE_MANIFEST_PATH),
            checklist=("provider_config", "sqlite_snapshot", "rollback_plan", "evidence_bundle"),
            report_fields=("ok", "closure.status", "checks.pre", "checks.post", "evidence_bundle"),
            safe_to_run=True,
        ),
        OpsReadinessCheck(
            id="storage_real_migration_contract",
            area="1.3_storage_runtime",
            description="Execute the guarded PostgreSQL/Qdrant migration only during a real migration drill.",
            command=_python_command(
                "deploy/validate_storage_migration.py",
                "--execute",
                "--json",
                "--report-path",
                _storage_report_path("storage-real-migration"),
                "--archive-dir",
                str(STORAGE_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(STORAGE_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(STORAGE_EVIDENCE_MANIFEST_PATH),
            ),
            required_env=("STORAGE_MIGRATION_EXECUTE", "DATABASE_URL", "QDRANT_URL"),
            report_path=_storage_report_path("storage-real-migration"),
            archive_dir=str(STORAGE_REPORT_ARCHIVE_DIR),
            history_path=str(STORAGE_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(STORAGE_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "real_environment_gate",
                "postgres_config",
                "qdrant_config",
                "pre_checks",
                "post_checks",
                "evidence_bundle",
            ),
            report_fields=(
                "ok",
                "real_environment_gate",
                "closure.status",
                "closure.pre_checks_blocked",
                "closure.post_checks_failed",
                "evidence_bundle",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="storage_real_integration",
            area="1.3_storage_runtime",
            description="Connect to real PostgreSQL/Qdrant targets and run the guarded integration probe.",
            command=_python_command(
                "deploy/run_storage_integration_check.py",
                "--report-path",
                _storage_report_path("storage-real-integration"),
                "--archive-dir",
                str(STORAGE_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(STORAGE_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(STORAGE_EVIDENCE_MANIFEST_PATH),
            ),
            required_env=("STORAGE_INTEGRATION_TEST", "DATABASE_URL", "QDRANT_URL"),
            report_path=_storage_report_path("storage-real-integration"),
            archive_dir=str(STORAGE_REPORT_ARCHIVE_DIR),
            history_path=str(STORAGE_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(STORAGE_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "storage_integration_env_gate",
                "postgres_real_check",
                "qdrant_real_check",
                "qdrant_test_collection_safety",
                "evidence_bundle",
            ),
            report_fields=("status", "gate", "pre_checks", "post_checks", "evidence_bundle"),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="storage_rollback_plan",
            area="1.3_storage_runtime",
            description="Render the destructive storage rollback plan without executing it.",
            command=_python_command(
                "deploy/validate_storage_migration.py",
                "--rollback-plan",
                "--json",
                "--report-path",
                _storage_report_path("storage-rollback-plan"),
                "--archive-dir",
                str(STORAGE_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(STORAGE_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(STORAGE_EVIDENCE_MANIFEST_PATH),
            ),
            report_path=_storage_report_path("storage-rollback-plan"),
            archive_dir=str(STORAGE_REPORT_ARCHIVE_DIR),
            history_path=str(STORAGE_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(STORAGE_EVIDENCE_MANIFEST_PATH),
            checklist=("rollback_requires", "blast_radius", "restore_strategy", "evidence_fields"),
            report_fields=("rollback_plan", "closure.status", "evidence_bundle"),
            safe_to_run=True,
        ),
        OpsReadinessCheck(
            id="storage_real_rollback_contract",
            area="1.3_storage_runtime",
            description="Execute the guarded PostgreSQL/Qdrant rollback only during a real rollback drill.",
            command=_python_command(
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--json",
                "--report-path",
                _storage_report_path("storage-real-rollback"),
                "--archive-dir",
                str(STORAGE_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(STORAGE_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(STORAGE_EVIDENCE_MANIFEST_PATH),
            ),
            required_env=("STORAGE_MIGRATION_ROLLBACK", "DATABASE_URL"),
            report_path=_storage_report_path("storage-real-rollback"),
            archive_dir=str(STORAGE_REPORT_ARCHIVE_DIR),
            history_path=str(STORAGE_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(STORAGE_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "rollback_gate",
                "postgres_confirm_drop",
                "qdrant_safe_prefix",
                "pre_checks",
                "post_checks",
                "evidence_bundle",
            ),
            report_fields=(
                "ok",
                "real_environment_gate",
                "rollback_plan",
                "closure.status",
                "evidence_bundle",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="helm_static_validation",
            area="4.3_deploy_ops",
            description="Validate Helm chart static contracts for rollout, config changes, and shutdown.",
            command=_python_command("deploy/validate_helm_static.py"),
            safe_to_run=True,
        ),
        OpsReadinessCheck(
            id="helm_config_hot_reload_contract",
            area="4.3_deploy_ops",
            description="Validate Helm ConfigMap checksum rollout and optional mounted config hot-reload contract.",
            command=_python_command("deploy/validate_helm_static.py"),
            safe_to_run=True,
        ),
        OpsReadinessCheck(
            id="k8s_real_cluster_probe",
            area="4.3_deploy_ops",
            description="Run the env-gated Kubernetes rollout drill and emit a JSON evidence report.",
            command=_python_command(
                "deploy/run_k8s_rollout_drill.py",
                "--json",
                "--report-path",
                _k8s_report_path("k8s-real-cluster-probe"),
                "--archive-dir",
                str(K8S_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(K8S_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(K8S_EVIDENCE_MANIFEST_PATH),
            ),
            required_env=("OPS_REAL_CLUSTER_TEST",),
            required_tools=("helm", "kubectl"),
            report_path=_k8s_report_path("k8s-real-cluster-probe"),
            archive_dir=str(K8S_REPORT_ARCHIVE_DIR),
            history_path=str(K8S_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(K8S_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "real_cluster_gate",
                "helm_template",
                "kubectl_current_context",
                "kubectl_namespace_probe",
                "api_deployment_probe",
                "api_rollout_status",
                "hot_reload_checklist",
                "graceful_shutdown_checklist",
                "evidence_manifest",
            ),
            report_fields=(
                "status",
                "skipped",
                "blockers",
                "steps",
                "summary.real_cluster_gate_enabled",
                "summary.config_reload_ready",
                "summary.graceful_shutdown_ready",
                "contracts.real_cluster",
                "contracts.config_reload.hot_reload_checklist",
                "contracts.graceful_shutdown.graceful_shutdown_checklist",
                "evidence.manifest_path",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="k8s_config_reload_drill",
            area="4.3_deploy_ops",
            description="Verify API pods are rolled or refreshed according to config.reloadStrategy.",
            command=_python_command(
                "deploy/run_k8s_rollout_drill.py",
                "--json",
                "--report-path",
                _k8s_report_path("k8s-config-reload-drill"),
                "--archive-dir",
                str(K8S_REPORT_ARCHIVE_DIR),
                "--history-path",
                str(K8S_REPORT_HISTORY_PATH),
                "--manifest-path",
                str(K8S_EVIDENCE_MANIFEST_PATH),
            ),
            required_env=("OPS_REAL_CLUSTER_TEST",),
            required_tools=("helm", "kubectl"),
            report_path=_k8s_report_path("k8s-config-reload-drill"),
            archive_dir=str(K8S_REPORT_ARCHIVE_DIR),
            history_path=str(K8S_REPORT_HISTORY_PATH),
            evidence_manifest_path=str(K8S_EVIDENCE_MANIFEST_PATH),
            checklist=(
                "real_cluster_gate",
                "config_reload_strategy",
                "checksum_rollout_annotation",
                "mounted_hot_reload_optional",
                "hot_reload_env_keys",
                "graceful_shutdown_checklist",
                "evidence_manifest",
            ),
            report_fields=(
                "summary.config_reload_ready",
                "summary.graceful_shutdown_ready",
                "contracts.config_reload.report_fields",
                "contracts.config_reload.hot_reload_checklist",
                "contracts.graceful_shutdown.report_fields",
                "contracts.graceful_shutdown.graceful_shutdown_checklist",
            ),
            real_environment=True,
        ),
        OpsReadinessCheck(
            id="final_validation_quick",
            area="release_gate",
            description="Run the quick release validation profile after ops changes.",
            command=_python_command("deploy/run_final_validation.py", "--profile", "quick"),
            safe_to_run=True,
        ),
        OpsReadinessCheck(
            id="task_backend_default_switch_contract",
            area="1.2_async_queue",
            description="Document the explicit gate for changing the production default from memory to ARQ.",
            command=_python_command(
                "-c",
                "import json; from backend.tasks.settings import task_backend_default_switch_contract_from_env as f; print(json.dumps(f(), sort_keys=True))",
            ),
            safe_to_run=True,
        ),
    ]


def _env_enabled(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key) or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_json_report(path: str) -> dict[str, object]:
    report_path = ROOT / path
    if not report_path.is_file():
        return {"exists": False, "ok": False, "blocker": "missing_evidence"}
    try:
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "exists": True,
            "ok": False,
            "blocker": "invalid_evidence_json",
            "detail": str(exc),
        }
    if not isinstance(loaded, dict):
        return {"exists": True, "ok": False, "blocker": "invalid_evidence_shape"}

    closure = loaded.get("closure")
    closure_complete = (
        bool(closure.get("complete")) if isinstance(closure, dict) else None
    )
    skipped = bool(loaded.get("skipped"))
    ok = bool(loaded.get("ok")) and not skipped
    if closure_complete is False:
        ok = False

    blocker = ""
    if skipped:
        blocker = "skipped_evidence"
    elif not bool(loaded.get("ok")):
        blocker = "failed_evidence"
    elif closure_complete is False:
        blocker = "incomplete_evidence_closure"

    return {
        "exists": True,
        "ok": ok,
        "skipped": skipped,
        "blocker": blocker,
        "exit_code": loaded.get("exit_code"),
        "archive_path": loaded.get("archive_path", ""),
        "closure_decision": (
            closure.get("decision") if isinstance(closure, dict) else ""
        ),
    }


def _read_json_file(path: str) -> tuple[dict[str, object] | None, str]:
    target = ROOT / path
    if not target.is_file():
        return None, "missing"
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"
    if not isinstance(loaded, dict):
        return None, "invalid_shape"
    return loaded, ""


def _manifest_entry_for_check(
    manifest: Mapping[str, object] | None,
    *,
    check_id: str,
    report_path: str,
) -> tuple[dict[str, object] | None, str]:
    if manifest is None:
        return None, "manifest_missing"

    reports = manifest.get("reports")
    if isinstance(reports, dict):
        report_stem = Path(report_path).stem
        entry = reports.get(check_id) or reports.get(report_stem)
        if isinstance(entry, dict):
            return entry, ""
        for value in reports.values():
            if not isinstance(value, dict):
                continue
            paths = value.get("paths")
            entry_report_path = (
                str(paths.get("report_path") or "") if isinstance(paths, dict) else ""
            )
            if entry_report_path and Path(entry_report_path) == Path(report_path):
                return value, ""
        return None, "manifest_entry_missing"

    paths = manifest.get("paths")
    manifest_report_path = (
        str(paths.get("report_path") or "") if isinstance(paths, dict) else ""
    )
    if manifest_report_path and Path(manifest_report_path) == Path(report_path):
        return dict(manifest), ""
    if str(manifest.get("id") or "") and not manifest_report_path:
        return dict(manifest), ""
    return None, "manifest_entry_missing"


def _report_closed(report: Mapping[str, object] | None) -> tuple[bool, list[str]]:
    if report is None:
        return False, ["report_missing"]

    blockers: list[str] = []
    if bool(report.get("skipped")):
        blockers.append("report_skipped")
    if report.get("ok") is not True:
        blockers.append("report_not_ok")

    status = str(report.get("status") or "")
    if status in {"failed", "blocked", "skipped", "error"}:
        blockers.append(f"report_status:{status}")

    report_blockers = report.get("blockers")
    if isinstance(report_blockers, list) and report_blockers:
        blockers.append("report_has_blockers")

    closure = report.get("closure")
    if isinstance(closure, dict):
        if closure.get("complete") is False:
            blockers.append("closure_incomplete")
        closure_blockers = closure.get("blockers")
        if isinstance(closure_blockers, list) and closure_blockers:
            blockers.append("closure_has_blockers")

    return not blockers, blockers


def _manifest_entry_closed(
    entry: Mapping[str, object] | None,
    *,
    entry_problem: str,
) -> tuple[bool, list[str]]:
    if entry is None:
        return False, [entry_problem]

    blockers: list[str] = []
    if bool(entry.get("skipped")):
        blockers.append("manifest_skipped")
    if "ok" in entry and entry.get("ok") is not True:
        blockers.append("manifest_not_ok")

    status = str(entry.get("status") or "")
    if status in {"failed", "blocked", "skipped", "error"}:
        blockers.append(f"manifest_status:{status}")

    entry_blockers = entry.get("blockers")
    if isinstance(entry_blockers, list) and entry_blockers:
        blockers.append("manifest_has_blockers")

    return not blockers, blockers


def _persisted_evidence_state(check: OpsReadinessCheck) -> dict[str, object]:
    if not check.real_environment or not check.report_path or not check.evidence_manifest_path:
        return {"closed": False, "status": "not_required", "blockers": []}

    report, report_problem = _read_json_file(check.report_path)
    report_ok, report_blockers = (
        (False, []) if report_problem else _report_closed(report)
    )
    manifest, manifest_problem = _read_json_file(check.evidence_manifest_path)
    entry, entry_problem = _manifest_entry_for_check(
        manifest,
        check_id=check.id,
        report_path=check.report_path,
    )
    manifest_ok, manifest_blockers = _manifest_entry_closed(
        entry,
        entry_problem=manifest_problem or entry_problem,
    )

    blockers: list[str] = []
    if report_problem:
        blockers.append(f"report:{report_problem}")
    blockers.extend(f"report:{item}" for item in report_blockers)
    blockers.extend(f"manifest:{item}" for item in manifest_blockers)
    closed = report_ok and manifest_ok and not blockers
    return {
        "closed": closed,
        "status": "closed" if closed else "pending",
        "blockers": blockers,
        "report_exists": report is not None,
        "manifest_exists": manifest is not None,
        "manifest_entry_exists": entry is not None,
    }


def _build_task_backend_default_switch_decision(
    checks: Sequence[dict[str, object]],
    *,
    env: Mapping[str, str],
) -> dict[str, object]:
    by_id = {str(item["id"]): item for item in checks}
    switch_ready = _env_enabled(env, TASK_BACKEND_SWITCH_READY_ENV)
    required: dict[str, dict[str, object]] = {}
    blockers: list[str] = []

    for check_id in ARQ_DEFAULT_SWITCH_REQUIRED_CHECKS:
        item = by_id.get(check_id, {})
        report_path = str(item.get("report_path") or "")
        evidence = (
            _read_json_report(report_path)
            if report_path
            else {"exists": False, "ok": False, "blocker": "missing_report_path"}
        )
        status = str(item.get("status") or "blocked")
        ready = status == "ready" and bool(evidence.get("ok"))
        required[check_id] = {
            "status": status,
            "report_path": report_path,
            "evidence": evidence,
            "ready": ready,
        }
        if switch_ready and not ready:
            evidence_blocker = str(evidence.get("blocker") or "not_ready")
            blockers.append(f"default_switch_blocked:{check_id}:{evidence_blocker}")

    decision = (
        "eligible_for_arq_default"
        if switch_ready and not blockers
        else "blocked_until_arq_evidence_closes"
        if switch_ready
        else "keep_memory_default"
    )
    return {
        "current_default": "memory",
        "target_default": "arq",
        "switch_gate_env": TASK_BACKEND_SWITCH_READY_ENV,
        "switch_ready": switch_ready,
        "decision": decision,
        "required_checks": required,
        "blockers": blockers,
    }


def _missing_env(check: OpsReadinessCheck, env: Mapping[str, str]) -> list[str]:
    missing: list[str] = []
    for key in check.required_env:
        if key == "STORAGE_INTEGRATION_TEST":
            if not _env_enabled(env, key):
                missing.append(key)
            continue
        if key in {"OPS_REAL_CLUSTER_TEST", "ARQ_LONG_RUNNING_TEST"}:
            if not _env_enabled(env, key):
                missing.append(key)
            continue
        if key == "STORAGE_MIGRATION_ROLLBACK":
            if not _env_enabled(env, key):
                missing.append(key)
            continue
        if key == "STORAGE_MIGRATION_EXECUTE":
            if not _env_enabled(env, key):
                missing.append(key)
            continue
        if not str(env.get(key) or "").strip():
            missing.append(key)
    return missing


def _missing_tools(check: OpsReadinessCheck) -> list[str]:
    return [tool for tool in check.required_tools if shutil.which(tool) is None]


def _tail_output(stdout: str, stderr: str, *, limit: int = 1200) -> str:
    output = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    return output[-limit:]


def _run_probe(command: Sequence[str], *, env: Mapping[str, str]) -> dict[str, object]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env={**os.environ, **dict(env), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "detail": _tail_output(exc.stdout or "", exc.stderr or "")
            or f"probe timed out after {PROBE_TIMEOUT_SECONDS}s",
        }
    except OSError as exc:
        return {"ok": False, "returncode": None, "detail": str(exc)}

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "detail": _tail_output(completed.stdout or "", completed.stderr or ""),
    }


def _docker_daemon_probe(env: Mapping[str, str]) -> dict[str, object]:
    result = _run_probe(("docker", "info", "--format", "{{json .ServerVersion}}"), env=env)
    result["blocker"] = "docker_daemon_unavailable"
    if not bool(result.get("ok")):
        result["start_contract"] = {
            "message": "Docker CLI is installed, but the Docker daemon is not reachable.",
            "start_commands": DOCKER_DESKTOP_START_COMMANDS,
        }
    return result


def _kubectl_context_probe(env: Mapping[str, str]) -> dict[str, object]:
    result = _run_probe(("kubectl", "config", "current-context"), env=env)
    if result["ok"] and not str(result.get("detail") or "").strip():
        result = {**result, "ok": False, "detail": "kubectl current-context is empty"}
    result["blocker"] = "kubectl_current_context_missing"
    return result


def _tool_probe_results(
    check: OpsReadinessCheck,
    *,
    env: Mapping[str, str],
    missing_tools: Sequence[str],
) -> dict[str, dict[str, object]]:
    missing = set(missing_tools)
    results: dict[str, dict[str, object]] = {}
    if "docker" in check.required_tools and "docker" not in missing:
        results["docker"] = _docker_daemon_probe(env)
    if "kubectl" in check.required_tools and "kubectl" not in missing:
        results["kubectl"] = _kubectl_context_probe(env)
    return results


def describe_check(
    check: OpsReadinessCheck,
    *,
    env: Mapping[str, str],
    include_real: bool,
    probe_tools: bool = True,
) -> dict[str, object]:
    missing_env = _missing_env(check, env)
    missing_tools = _missing_tools(check)
    included = include_real or not check.real_environment
    probe_results = (
        _tool_probe_results(check, env=env, missing_tools=missing_tools)
        if included and probe_tools
        else {}
    )
    probe_blockers = [
        str(result["blocker"])
        for result in probe_results.values()
        if not bool(result.get("ok"))
    ]
    runnable = included and not missing_env and not missing_tools and not probe_blockers
    if not included:
        status = "blocked"
        blockers = ["real_environment_not_included"]
    else:
        blockers = [f"missing_env:{key}" for key in missing_env]
        blockers.extend(f"missing_tool:{tool}" for tool in missing_tools)
        blockers.extend(probe_blockers)
        status = "ready" if not blockers else "blocked"
    evidence_state = _persisted_evidence_state(check)
    result = {
        **check.as_dict(),
        "included": included,
        "runnable": runnable,
        "status": status,
        "blockers": blockers,
        "evidence": evidence_state,
        "evidence_closed": bool(evidence_state.get("closed")),
    }
    if probe_results:
        result["probes"] = probe_results
    elif included and not probe_tools and check.required_tools:
        result["probes_skipped"] = True
    return result


def _run_command(command: Sequence[str]) -> dict[str, object]:
    started_at = time.perf_counter()
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SAFE_CHECK_TIMEOUT_SECONDS,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
        "stdout": (completed.stdout or "").strip()[-2000:],
        "stderr": (completed.stderr or "").strip()[-2000:],
    }


def _area_evidence_manifest(
    *,
    manifest_id: str,
    area: str,
    manifest_path: Path,
    archive_dir: Path,
    history_path: Path,
    checks: Sequence[dict[str, object]],
) -> dict[str, object]:
    area_checks = [item for item in checks if str(item.get("area") or "") == area]
    return {
        "id": manifest_id,
        "schema_version": 1,
        "area": area,
        "manifest_path": str(manifest_path),
        "archive_dir": str(archive_dir),
        "history_path": str(history_path),
        "report_paths": {
            str(item["id"]): item["report_path"]
            for item in area_checks
            if str(item.get("report_path") or "")
        },
        "checks": [
            {
                "id": str(item["id"]),
                "status": str(item["status"]),
                "included": bool(item["included"]),
                "runnable": bool(item["runnable"]),
                "real_environment": bool(item["real_environment"]),
                "report_path": str(item.get("report_path") or ""),
                "evidence_manifest_path": str(item.get("evidence_manifest_path") or ""),
                "blockers": list(item.get("blockers") or []),
                "evidence": item.get("evidence", {}),
                "evidence_closed": bool(item.get("evidence_closed")),
                "checklist": list(item.get("checklist") or []),
                "report_fields": list(item.get("report_fields") or []),
            }
            for item in area_checks
            if str(item["id"]) != TASK_BACKEND_DEFAULT_SWITCH_CHECK_ID
        ],
        "remaining_real_drills": [
            str(item["id"])
            for item in area_checks
            if bool(item["real_environment"]) and not bool(item.get("evidence_closed"))
        ],
        "execution_remaining_real_drills": [
            str(item["id"])
            for item in area_checks
            if bool(item["real_environment"]) and str(item["status"]) != "ready"
        ],
    }


def build_evidence_manifest(checks: Sequence[dict[str, object]]) -> dict[str, object]:
    """Build a unified evidence manifest without executing real-environment drills."""

    area_manifests = {
        "arq": _area_evidence_manifest(
            manifest_id="arq_evidence_manifest",
            area="1.2_async_queue",
            manifest_path=ARQ_EVIDENCE_MANIFEST_PATH,
            archive_dir=ARQ_REPORT_DIR / "archive",
            history_path=ARQ_REPORT_HISTORY_PATH,
            checks=checks,
        ),
        "storage": _area_evidence_manifest(
            manifest_id="storage_evidence_manifest",
            area="1.3_storage_runtime",
            manifest_path=STORAGE_EVIDENCE_MANIFEST_PATH,
            archive_dir=STORAGE_REPORT_ARCHIVE_DIR,
            history_path=STORAGE_REPORT_HISTORY_PATH,
            checks=checks,
        ),
        "k8s": _area_evidence_manifest(
            manifest_id="k8s_evidence_manifest",
            area="4.3_deploy_ops",
            manifest_path=K8S_EVIDENCE_MANIFEST_PATH,
            archive_dir=K8S_REPORT_ARCHIVE_DIR,
            history_path=K8S_REPORT_HISTORY_PATH,
            checks=checks,
        ),
    }
    return {
        "schema_version": 1,
        "id": "ops_readiness_evidence_manifest",
        "areas": area_manifests,
        "remaining_real_drills": [
            check_id
            for manifest in area_manifests.values()
            for check_id in list(manifest["remaining_real_drills"])
        ],
        "execution_remaining_real_drills": [
            check_id
            for manifest in area_manifests.values()
            for check_id in list(manifest["execution_remaining_real_drills"])
        ],
    }


def build_readiness_report(
    *,
    env: Mapping[str, str] | None = None,
    include_real: bool = False,
    run_safe: bool = False,
) -> dict[str, object]:
    current_env = os.environ if env is None else env
    described = [
        describe_check(check, env=current_env, include_real=include_real)
        for check in all_readiness_checks()
    ]

    if run_safe:
        safe_checks = {
            check.id: check
            for check in all_readiness_checks()
            if check.safe_to_run and not check.real_environment
        }
        for item in described:
            check = safe_checks.get(str(item["id"]))
            if check is None or not bool(item["runnable"]):
                continue
            item["execution"] = _run_command(check.command)
            if not bool(item["execution"]["ok"]):  # type: ignore[index]
                item["status"] = "failed"

    default_switch = _build_task_backend_default_switch_decision(
        described,
        env=current_env,
    )
    if default_switch["blockers"]:
        for item in described:
            if item["id"] == TASK_BACKEND_DEFAULT_SWITCH_CHECK_ID:
                item["status"] = "blocked"
                item["runnable"] = False
                item["blockers"] = list(default_switch["blockers"])
                item["decision"] = default_switch
                break

    evidence_manifest = build_evidence_manifest(described)
    included = [item for item in described if bool(item["included"])]
    ready = [item for item in included if item["status"] == "ready"]
    failed = [item for item in included if item["status"] == "failed"]
    blocked = [item for item in included if item["status"] == "blocked"]
    summary = {
        "total": len(described),
        "included": len(included),
        "ready": len(ready),
        "blocked": len(blocked),
        "failed": len(failed),
        "real_environment_included": include_real,
        "safe_checks_executed": run_safe,
        "remaining_real_drills": [
            item["id"]
            for item in described
            if bool(item["real_environment"]) and not bool(item.get("evidence_closed"))
        ],
        "execution_remaining_real_drills": [
            item["id"]
            for item in described
            if bool(item["real_environment"]) and item["status"] != "ready"
        ],
        "arq_report_paths": {
            str(item["id"]): item["report_path"]
            for item in described
            if str(item["area"]) == "1.2_async_queue" and str(item.get("report_path") or "")
        },
        "arq_report_history_path": str(ARQ_REPORT_HISTORY_PATH),
        "arq_archive_dir": str(ARQ_REPORT_DIR / "archive"),
        "arq_evidence_manifest_path": str(ARQ_EVIDENCE_MANIFEST_PATH),
        "arq_evidence_manifest_paths": {
            str(item["id"]): item["evidence_manifest_path"]
            for item in described
            if str(item["area"]) == "1.2_async_queue"
            and str(item.get("evidence_manifest_path") or "")
        },
        "storage_report_paths": {
            str(item["id"]): item["report_path"]
            for item in described
            if str(item["area"]) == "1.3_storage_runtime" and str(item.get("report_path") or "")
        },
        "storage_archive_dir": str(STORAGE_REPORT_ARCHIVE_DIR),
        "storage_report_history_path": str(STORAGE_REPORT_HISTORY_PATH),
        "storage_evidence_manifest_path": str(STORAGE_EVIDENCE_MANIFEST_PATH),
        "storage_evidence_manifest_paths": {
            str(item["id"]): item["evidence_manifest_path"]
            for item in described
            if str(item["area"]) == "1.3_storage_runtime"
            and str(item.get("evidence_manifest_path") or "")
        },
        "k8s_report_paths": {
            str(item["id"]): item["report_path"]
            for item in described
            if str(item["area"]) == "4.3_deploy_ops" and str(item.get("report_path") or "")
        },
        "k8s_archive_dir": str(K8S_REPORT_ARCHIVE_DIR),
        "k8s_report_history_path": str(K8S_REPORT_HISTORY_PATH),
        "k8s_evidence_manifest_path": str(K8S_EVIDENCE_MANIFEST_PATH),
        "k8s_evidence_manifest_paths": {
            str(item["id"]): item["evidence_manifest_path"]
            for item in described
            if str(item["area"]) == "4.3_deploy_ops"
            and str(item.get("evidence_manifest_path") or "")
        },
        "task_backend_default_switch": default_switch,
    }
    return {
        "ok": not failed and not blocked,
        "summary": summary,
        "evidence_manifest": evidence_manifest,
        "checks": described,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the ops readiness closure report.")
    parser.add_argument("--include-real", action="store_true", help="Include real environment drills.")
    parser.add_argument("--run-safe", action="store_true", help="Execute safe local checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_readiness_report(include_real=args.include_real, run_safe=args.run_safe)
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        summary = report["summary"]
        print(
            "summary: "
            f"included={summary['included']} "
            f"ready={summary['ready']} "
            f"blocked={summary['blocked']} "
            f"failed={summary['failed']}"
        )
        for check in report["checks"]:
            print(f"- {check['status']} {check['id']}: {' '.join(check['command'])}")
            blockers = check.get("blockers") or []
            if blockers:
                print(f"  blockers: {', '.join(blockers)}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
