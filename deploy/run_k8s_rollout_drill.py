"""Env-gated Kubernetes rollout/config reload drill runner.

The default mode is intentionally inert: without OPS_REAL_CLUSTER_TEST=1 it
emits a JSON report with explicit blockers and does not run helm or kubectl.
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
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHART_DIR = ROOT / "deploy" / "helm" / "insightdesk"
DEFAULT_REPORT_PATH = ROOT / "runtime" / "k8s-rollout-drill-report.json"
DEFAULT_MANIFEST_PATH = ROOT / "runtime" / "k8s-rollout-evidence-manifest.json"
DEFAULT_EVIDENCE_ID = "k8s_rollout_drill"
DEFAULT_RELEASE = "insightdesk"
DEFAULT_NAMESPACE = "default"
DEFAULT_TIMEOUT = "120s"
RUN_GATE = "OPS_REAL_CLUSTER_TEST"
COMMAND_OUTPUT_LIMIT = 4000


@dataclass(frozen=True)
class DrillCommand:
    id: str
    command: tuple[str, ...]
    timeout_seconds: int


def _env_enabled(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key) or "").strip().lower() in {"1", "true", "yes", "on"}


def _tail_output(stdout: str, stderr: str, *, limit: int = COMMAND_OUTPUT_LIMIT) -> str:
    output = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    return output[-limit:]


def _run_command(
    command: Sequence[str],
    *,
    env: Mapping[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    started_at = time.perf_counter()
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
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
            "detail": _tail_output(exc.stdout or "", exc.stderr or "")
            or f"command timed out after {timeout_seconds}s",
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
            "detail": str(exc),
        }

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
        "detail": _tail_output(completed.stdout or "", completed.stderr or ""),
    }


def _tool_blockers() -> list[str]:
    blockers: list[str] = []
    for tool in ("helm", "kubectl"):
        if shutil.which(tool) is None:
            blockers.append(f"missing_tool:{tool}")
    return blockers


def _deployment_name(release: str, component: str) -> str:
    return f"{release}-{component}"


def _read_chart_file(chart_dir: Path, relative_path: str) -> str:
    path = chart_dir / relative_path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _checklist_item(
    item_id: str,
    passed: bool,
    evidence: str,
    *,
    required: bool = True,
) -> dict[str, object]:
    return {
        "id": item_id,
        "required": required,
        "passed": passed,
        "evidence": evidence,
    }


def build_config_reload_contract(chart_dir: Path = DEFAULT_CHART_DIR) -> dict[str, object]:
    """Return the chart-level config reload contract without rendering Helm."""

    values = _read_chart_file(chart_dir, "values.yaml")
    configmap = _read_chart_file(chart_dir, "templates/configmap.yaml")
    api_deployment = _read_chart_file(chart_dir, "templates/deployment-api.yaml")
    worker_deployment = _read_chart_file(chart_dir, "templates/deployment-worker.yaml")
    deployment_templates = [api_deployment, worker_deployment]
    required_hot_reload_env = [
        "CONFIG_RELOAD_STRATEGY:",
        "CONFIG_HOT_RELOAD_ENABLED:",
        "CONFIG_HOT_RELOAD_PATH:",
        "CONFIG_HOT_RELOAD_CHECK_INTERVAL_SECONDS:",
    ]
    missing_env_keys = [
        key for key in required_hot_reload_env if key not in configmap
    ]
    checksum_rollout = all(
        "checksum/config:" in template
        and 'eq .Values.config.reloadStrategy "rolloutOnConfigChange"' in template
        for template in deployment_templates
    )
    mounted_config = all(
        ".Values.config.hotReload.enabled" in template
        and "runtime-config" in template
        and ".Values.config.hotReload.mountPath" in template
        for template in deployment_templates
    )
    hot_reload_default_enabled = (
        "hotReload:" in values
        and "enabled: true" in values.split("hotReload:", 1)[1].split("serverHost:", 1)[0]
    )
    strategy_default = (
        "rolloutOnConfigChange"
        if "reloadStrategy: rolloutOnConfigChange" in values
        else "unknown"
    )
    hot_reload_checklist = [
        _checklist_item(
            "reload_strategy_defaults_to_rollout",
            strategy_default == "rolloutOnConfigChange",
            "values.yaml config.reloadStrategy",
        ),
        _checklist_item(
            "configmap_checksum_drives_rollout",
            checksum_rollout,
            "Deployment pod-template checksum/config annotation",
        ),
        _checklist_item(
            "mounted_hot_reload_is_optional",
            mounted_config,
            "runtime-config ConfigMap volume gated by config.hotReload.enabled",
        ),
        _checklist_item(
            "hot_reload_env_is_reported",
            not missing_env_keys,
            "ConfigMap CONFIG_HOT_RELOAD_* keys",
        ),
    ]
    ready = (
        strategy_default == "rolloutOnConfigChange"
        and checksum_rollout
        and mounted_config
        and not missing_env_keys
    )
    return {
        "ready": ready,
        "strategy_default": strategy_default,
        "hot_reload_default_enabled": hot_reload_default_enabled,
        "expected_refresh_mechanism": (
            "mounted_config_hot_reload"
            if hot_reload_default_enabled
            else "checksum_rollout"
        ),
        "checksum_rollout_annotation": checksum_rollout,
        "mounted_config_supported": mounted_config,
        "hot_reload_env_keys": required_hot_reload_env,
        "missing_env_keys": missing_env_keys,
        "hot_reload_checklist": hot_reload_checklist,
        "report_fields": [
            "strategy_default",
            "hot_reload_default_enabled",
            "expected_refresh_mechanism",
            "checksum_rollout_annotation",
            "mounted_config_supported",
            "hot_reload_env_keys",
            "missing_env_keys",
            "hot_reload_checklist",
        ],
    }


def build_graceful_shutdown_contract(chart_dir: Path = DEFAULT_CHART_DIR) -> dict[str, object]:
    """Return the chart-level graceful shutdown contract without a cluster."""

    values = _read_chart_file(chart_dir, "values.yaml")
    api_deployment = _read_chart_file(chart_dir, "templates/deployment-api.yaml")
    worker_deployment = _read_chart_file(chart_dir, "templates/deployment-worker.yaml")
    api_grace_configured = (
        "api:" in values and "terminationGracePeriodSeconds: 30" in values
    )
    worker_grace_configured = (
        "worker:" in values and "terminationGracePeriodSeconds: 60" in values
    )
    prestop_configured = "preStop:" in values and "sleep 5" in values
    api_template_applies_shutdown = (
        ".Values.api.terminationGracePeriodSeconds" in api_deployment
        and "lifecycle:" in api_deployment
        and ".Values.api.lifecycle" in api_deployment
    )
    worker_template_applies_shutdown = (
        ".Values.worker.terminationGracePeriodSeconds" in worker_deployment
        and "lifecycle:" in worker_deployment
        and ".Values.worker.lifecycle" in worker_deployment
    )
    graceful_shutdown_checklist = [
        _checklist_item(
            "api_termination_grace_period_configured",
            api_grace_configured,
            "values.yaml api.terminationGracePeriodSeconds",
        ),
        _checklist_item(
            "worker_termination_grace_period_configured",
            worker_grace_configured,
            "values.yaml worker.terminationGracePeriodSeconds",
        ),
        _checklist_item(
            "pre_stop_delay_configured",
            prestop_configured,
            "values.yaml api/worker lifecycle.preStop sleep",
        ),
        _checklist_item(
            "api_template_applies_shutdown_controls",
            api_template_applies_shutdown,
            "templates/deployment-api.yaml terminationGracePeriodSeconds/lifecycle",
        ),
        _checklist_item(
            "worker_template_applies_shutdown_controls",
            worker_template_applies_shutdown,
            "templates/deployment-worker.yaml terminationGracePeriodSeconds/lifecycle",
        ),
    ]
    ready = all(bool(item["passed"]) for item in graceful_shutdown_checklist)
    return {
        "ready": ready,
        "api_termination_grace_period_configured": api_grace_configured,
        "worker_termination_grace_period_configured": worker_grace_configured,
        "pre_stop_delay_configured": prestop_configured,
        "api_template_applies_shutdown_controls": api_template_applies_shutdown,
        "worker_template_applies_shutdown_controls": worker_template_applies_shutdown,
        "graceful_shutdown_checklist": graceful_shutdown_checklist,
        "report_fields": [
            "api_termination_grace_period_configured",
            "worker_termination_grace_period_configured",
            "pre_stop_delay_configured",
            "api_template_applies_shutdown_controls",
            "worker_template_applies_shutdown_controls",
            "graceful_shutdown_checklist",
        ],
    }


def build_real_cluster_contract(
    *,
    gate_enabled: bool,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> dict[str, object]:
    return {
        "gate_env": RUN_GATE,
        "gate_enabled": gate_enabled,
        "required_env": [RUN_GATE],
        "required_tools": ["helm", "kubectl"],
        "safe_without_gate": True,
        "skipped_without_gate": True,
        "commands_inert_without_gate": True,
        "archiveable_when_enabled": bool(report_path or archive_dir or history_path or manifest_path),
        "evidence_paths": {
            "report_path": report_path,
            "archive_dir": archive_dir,
            "history_path": history_path,
            "manifest_path": manifest_path,
        },
    }


def _commands(
    *,
    release: str,
    namespace: str,
    chart_dir: Path,
    timeout: str,
    include_worker: bool,
) -> list[DrillCommand]:
    # Keep the real-cluster drill explicit: helm template, kubectl probes,
    # then kubectl rollout status for deployed workloads.
    commands = [
        DrillCommand(
            id="helm_template",
            command=("helm", "template", release, str(chart_dir)),
            timeout_seconds=60,
        ),
        DrillCommand(
            id="kubectl_current_context",
            command=("kubectl", "config", "current-context"),
            timeout_seconds=15,
        ),
        DrillCommand(
            id="kubectl_namespace_probe",
            command=("kubectl", "get", "namespace", namespace),
            timeout_seconds=15,
        ),
        DrillCommand(
            id="kubectl_api_deployment_probe",
            command=(
                "kubectl",
                "get",
                "deployment",
                _deployment_name(release, "api"),
                "-n",
                namespace,
            ),
            timeout_seconds=15,
        ),
        DrillCommand(
            id="kubectl_api_rollout_status",
            command=(
                "kubectl",
                "rollout",
                "status",
                f"deployment/{_deployment_name(release, 'api')}",
                "-n",
                namespace,
                f"--timeout={timeout}",
            ),
            timeout_seconds=180,
        ),
    ]
    if include_worker:
        commands.extend(
            [
                DrillCommand(
                    id="kubectl_worker_deployment_probe",
                    command=(
                        "kubectl",
                        "get",
                        "deployment",
                        _deployment_name(release, "worker"),
                        "-n",
                        namespace,
                    ),
                    timeout_seconds=15,
                ),
                DrillCommand(
                    id="kubectl_worker_rollout_status",
                    command=(
                        "kubectl",
                        "rollout",
                        "status",
                        f"deployment/{_deployment_name(release, 'worker')}",
                        "-n",
                        namespace,
                        f"--timeout={timeout}",
                    ),
                    timeout_seconds=180,
                ),
            ]
        )
    return commands


def build_k8s_rollout_drill_report(
    *,
    env: Mapping[str, str] | None = None,
    release: str = DEFAULT_RELEASE,
    namespace: str = DEFAULT_NAMESPACE,
    chart_dir: Path = DEFAULT_CHART_DIR,
    timeout: str = DEFAULT_TIMEOUT,
    include_worker: bool = False,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> dict[str, object]:
    current_env = os.environ if env is None else env
    gate_enabled = _env_enabled(current_env, RUN_GATE)
    blockers: list[str] = []
    skipped = False
    status = "ready"

    if not gate_enabled:
        skipped = True
        status = "skipped"
        blockers.append(f"missing_env:{RUN_GATE}")

    if not chart_dir.is_dir():
        status = "blocked"
        blockers.append(f"missing_chart_dir:{chart_dir}")

    if not skipped:
        blockers.extend(_tool_blockers())
        if blockers:
            status = "blocked"

    steps: list[dict[str, object]] = []
    if not blockers:
        for item in _commands(
            release=release,
            namespace=namespace,
            chart_dir=chart_dir,
            timeout=timeout,
            include_worker=include_worker,
        ):
            execution = _run_command(item.command, env=current_env, timeout_seconds=item.timeout_seconds)
            step = {
                "id": item.id,
                "command": list(item.command),
                "ok": bool(execution["ok"]),
                "execution": execution,
            }
            if item.id == "kubectl_current_context" and not str(execution.get("detail") or "").strip():
                step["ok"] = False
                step["execution"] = {
                    **execution,
                    "ok": False,
                    "detail": "kubectl current-context is empty",
                }
            steps.append(step)
            if not bool(step["ok"]):
                status = "blocked" if item.id == "kubectl_current_context" else "failed"
                blockers.append(
                    "kubectl_current_context_missing"
                    if item.id == "kubectl_current_context"
                    else f"command_failed:{item.id}"
                )
                break

    ok = status == "ready" and not blockers
    config_reload_contract = build_config_reload_contract(chart_dir)
    graceful_shutdown_contract = build_graceful_shutdown_contract(chart_dir)
    real_cluster_contract = build_real_cluster_contract(
        gate_enabled=gate_enabled,
        report_path=report_path,
        archive_dir=archive_dir,
        history_path=history_path,
        manifest_path=manifest_path,
    )
    return {
        "ok": ok,
        "status": status,
        "skipped": skipped,
        "blockers": blockers,
        "gate": RUN_GATE,
        "release": release,
        "namespace": namespace,
        "chart_dir": str(chart_dir),
        "include_worker": include_worker,
        "steps": steps,
        "summary": {
            "total_steps": len(_commands(
                release=release,
                namespace=namespace,
                chart_dir=chart_dir,
                timeout=timeout,
                include_worker=include_worker,
            )),
            "executed_steps": len(steps),
            "ready": ok,
            "config_reload_ready": bool(config_reload_contract["ready"]),
            "graceful_shutdown_ready": bool(graceful_shutdown_contract["ready"]),
            "real_cluster_gate_enabled": gate_enabled,
            "evidence_manifest_ready": bool(manifest_path),
        },
        "contracts": {
            "config_reload": config_reload_contract,
            "graceful_shutdown": graceful_shutdown_contract,
            "real_cluster": real_cluster_contract,
            "evidence": {
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
                "manifest_path": manifest_path,
            },
        },
    }


def build_evidence_manifest(
    report: dict[str, Any],
    *,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> dict[str, object]:
    steps = report.get("steps")
    evidence_steps = steps if isinstance(steps, list) else []
    contracts = report.get("contracts")
    contract_map = contracts if isinstance(contracts, dict) else {}
    required_evidence = [
        "real_cluster_contract",
        "config_reload_contract",
        "hot_reload_checklist",
        "graceful_shutdown_contract",
        "graceful_shutdown_checklist",
        "helm_template",
        "kubectl_current_context",
        "kubectl_namespace_probe",
        "kubectl_api_deployment_probe",
        "kubectl_api_rollout_status",
        "json_report",
        "history_entry",
        "archive_entry",
    ]
    if bool(report.get("include_worker")):
        required_evidence.extend(
            ["kubectl_worker_deployment_probe", "kubectl_worker_rollout_status"]
        )
    generated_steps = [
        {
            "id": str(step.get("id")),
            "ok": bool(step.get("ok")),
            "command": step.get("command", []),
        }
        for step in evidence_steps
        if isinstance(step, dict)
    ]
    manifest = {
        "id": DEFAULT_EVIDENCE_ID,
        "status": report.get("status"),
        "ok": report.get("ok"),
        "skipped": report.get("skipped"),
        "gate": report.get("gate"),
        "release": report.get("release"),
        "namespace": report.get("namespace"),
        "blockers": report.get("blockers", []),
        "required_evidence": required_evidence,
        "generated_steps": generated_steps,
        "contracts": {
            "real_cluster": contract_map.get("real_cluster", {}),
            "config_reload": contract_map.get("config_reload", {}),
            "graceful_shutdown": contract_map.get("graceful_shutdown", {}),
        },
        "paths": {
            "report_path": report_path,
            "archive_dir": archive_dir,
            "history_path": history_path,
            "manifest_path": manifest_path,
            "archive_path": str((report.get("evidence") or {}).get("archive_path", ""))
            if isinstance(report.get("evidence"), dict)
            else "",
        },
        "recorded_at": time.time(),
    }
    manifest["reports"] = {
        Path(str(report_path or report.get("evidence", {}).get("report_path", "") or DEFAULT_REPORT_PATH)).stem: {
            **manifest,
        }
    }
    return manifest


def emit_evidence_report(
    report: dict[str, Any],
    *,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> None:
    """Persist local JSON evidence for inert and real Kubernetes rollout drills."""

    if not (report_path or archive_dir or history_path or manifest_path):
        return

    evidence_id = DEFAULT_EVIDENCE_ID
    report["evidence"] = {
        "id": evidence_id,
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "manifest_path": manifest_path,
        "archive_path": "",
    }
    contracts = report.setdefault("contracts", {})
    if isinstance(contracts, dict):
        contracts["evidence"] = {
            "report_path": report_path,
            "archive_dir": archive_dir,
            "history_path": history_path,
            "manifest_path": manifest_path,
        }

    if archive_dir:
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{evidence_id}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        archive_path = archive_root / archive_name
        report["evidence"]["archive_path"] = str(archive_path)
        archive_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if history_path:
        history = Path(history_path)
        history.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, Any]] = []
        if history.is_file():
            try:
                loaded = json.loads(history.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries = loaded
            except json.JSONDecodeError:
                entries = []
        entries.append(
            {
                "id": evidence_id,
                "ok": report["ok"],
                "status": report["status"],
                "skipped": report["skipped"],
                "release": report["release"],
                "namespace": report["namespace"],
                "executed_steps": report["summary"]["executed_steps"],
                "config_reload_ready": report["summary"].get("config_reload_ready"),
                "blockers": report["blockers"],
                "report_path": report_path,
                "archive_path": report["evidence"]["archive_path"],
                "recorded_at": time.time(),
            }
        )
        history.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if manifest_path:
        manifest = build_evidence_manifest(
            report,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        manifest_target = Path(manifest_path)
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        merged_manifest: dict[str, Any] = manifest
        if manifest_target.is_file():
            try:
                existing = json.loads(manifest_target.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    existing_reports = existing.get("reports")
                    merged_reports: dict[str, Any] = {}
                    if isinstance(existing_reports, dict):
                        merged_reports.update(existing_reports)
                    merged_reports.update(
                        manifest.get("reports") if isinstance(manifest.get("reports"), dict) else {}
                    )
                    merged_manifest = {**existing, **manifest, "reports": merged_reports}
            except json.JSONDecodeError:
                merged_manifest = manifest
        manifest_target.write_text(
            json.dumps(merged_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the env-gated Kubernetes rollout drill.")
    parser.add_argument("--release", default=DEFAULT_RELEASE, help="Helm release name.")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE, help="Kubernetes namespace.")
    parser.add_argument("--chart-dir", type=Path, default=DEFAULT_CHART_DIR, help="Helm chart directory.")
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT, help="kubectl rollout status timeout.")
    parser.add_argument("--include-worker", action="store_true", help="Also verify worker deployment rollout.")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH, help="JSON report output path.")
    parser.add_argument("--archive-dir", type=Path, default=None, help="Timestamped JSON evidence archive directory.")
    parser.add_argument("--history-path", type=Path, default=None, help="Rolling JSON evidence history path.")
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH, help="JSON evidence manifest path.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_k8s_rollout_drill_report(
        release=args.release,
        namespace=args.namespace,
        chart_dir=args.chart_dir,
        timeout=args.timeout,
        include_worker=args.include_worker,
        report_path=str(args.report_path),
        archive_dir=str(args.archive_dir or ""),
        history_path=str(args.history_path or ""),
        manifest_path=str(args.manifest_path or ""),
    )
    emit_evidence_report(
        report,
        report_path=str(args.report_path),
        archive_dir=str(args.archive_dir or ""),
        history_path=str(args.history_path or ""),
        manifest_path=str(args.manifest_path or ""),
    )
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        print(
            "summary: "
            f"status={report['status']} "
            f"executed_steps={report['summary']['executed_steps']} "
            f"blockers={','.join(report['blockers']) or 'none'}"
        )
        print(f"report_path: {args.report_path}")
    return 0 if report["ok"] or report["skipped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
