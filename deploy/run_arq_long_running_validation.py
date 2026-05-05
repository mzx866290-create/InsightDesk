"""Run an env-gated long-running Redis/ARQ worker validation loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "deploy" / "compose.arq-worker.yml"
PROBE_PATH = "/app/deploy/arq_e2e_probe.py"
LONG_RUNNING_GATE_ENV = "ARQ_LONG_RUNNING_TEST"
DOCKER_DAEMON_BLOCKER = "docker_daemon_unavailable"
DOCKER_DESKTOP_START_COMMANDS = {
    "windows": "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'",
    "macos": "open -a Docker",
    "linux": "sudo systemctl start docker",
}


def _compose_command(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), *args]


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command))
    return subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def _enabled(env: dict[str, str], key: str) -> bool:
    return str(env.get(key) or "").strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_evidence_manifest(
    *,
    manifest_path: str,
    report: dict[str, Any],
    report_path: str,
    archive_path: str,
    history_path: str,
) -> None:
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"schema_version": 1, "reports": {}}
    if target.is_file():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest.update(loaded)
        except json.JSONDecodeError:
            manifest = {"schema_version": 1, "reports": {}}
    reports = manifest.setdefault("reports", {})
    if not isinstance(reports, dict):
        reports = {}
        manifest["reports"] = reports
    decision = str(report.get("evidence", {}).get("decision") or "")
    reports[str(report["id"])] = {
        "id": report["id"],
        "ok": bool(report.get("ok")),
        "skipped": bool(report.get("skipped")),
        "decision": decision,
        "status": decision,
        "report_path": report_path,
        "archive_path": archive_path,
        "history_path": history_path,
        "blockers": list(report.get("blockers") or []),
        "finished_at": report.get("finished_at"),
    }
    manifest["schema_version"] = 1
    manifest["updated_at"] = _utc_now()
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _emit_report(
    report: dict[str, Any],
    *,
    json_output: bool,
    report_path: str,
    archive_dir: str,
    history_path: str,
    manifest_path: str = "",
) -> None:
    if archive_dir and not report.get("archive_path"):
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{report['id']}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        report["archive_path"] = str(archive_root / archive_name)
    iterations = [
        item for item in report.get("iterations", []) if isinstance(item, dict)
    ]
    failed_iterations = [
        int(item.get("index") or 0) for item in iterations if not bool(item.get("ok"))
    ]
    completed_iterations = len(iterations)
    report["completed_iterations"] = completed_iterations
    report.setdefault("closure", {})
    report["closure"].update(
        {
            "complete": bool(report.get("ok")) and completed_iterations > 0,
            "completed_iterations": completed_iterations,
            "failed_iterations": failed_iterations,
            "decision": (
                "skipped_no_real_environment"
                if bool(report.get("skipped"))
                else "long_running_validation_passed"
                if bool(report.get("ok")) and completed_iterations > 0
                else "long_running_validation_failed"
            ),
        }
    )
    report.setdefault("evidence", {})
    report["evidence"].update(
        {
            "schema_version": 1,
            "archive_ready": bool(report_path or archive_dir or history_path),
            "compose_file": str(COMPOSE_FILE),
            "probe_path": PROBE_PATH,
            "blockers": list(report.get("blockers") or []),
            "duration_seconds": int(report.get("duration_seconds") or 0),
            "max_iterations": int(report.get("max_iterations") or 0),
            "completed_iterations": completed_iterations,
            "decision": str(report["closure"]["decision"]),
        }
    )
    if manifest_path:
        report["evidence"]["manifest_path"] = manifest_path
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if archive_dir:
        Path(str(report["archive_path"])).write_text(
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
                "id": report["id"],
                "ok": report["ok"],
                "exit_code": report.get("exit_code", 0 if report["ok"] else 1),
                "started_at": report["started_at"],
                "finished_at": report["finished_at"],
                "completed_iterations": report.get("completed_iterations", 0),
                "report_path": report_path,
                "archive_path": report.get("archive_path", ""),
                "blockers": report.get("blockers", []),
                "skipped": bool(report.get("skipped")),
                "closure_decision": str(report.get("closure", {}).get("decision") or ""),
            }
        )
        history.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if manifest_path:
        _write_evidence_manifest(
            manifest_path=manifest_path,
            report=report,
            report_path=report_path,
            archive_path=str(report.get("archive_path", "")),
            history_path=history_path,
        )
    if json_output:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_engine_available(*, env: dict[str, str]) -> tuple[bool, str]:
    result = _run(["docker", "info"], env=env, timeout=30)
    if result.returncode == 0:
        return True, ""
    print(result.stdout, end="")
    return False, result.stdout or ""


def _docker_start_contract(*, include_hint: bool) -> dict[str, object]:
    return {
        "blocker": DOCKER_DAEMON_BLOCKER,
        "message": "Docker CLI is installed, but the Docker daemon is not reachable.",
        "start_commands": DOCKER_DESKTOP_START_COMMANDS if include_hint else {},
    }


def _base_report(*, duration_seconds: int, max_iterations: int) -> dict[str, Any]:
    return {
        "id": "arq_long_running_validation",
        "ok": False,
        "skipped": False,
        "gate_env": LONG_RUNNING_GATE_ENV,
        "duration_seconds": duration_seconds,
        "max_iterations": max_iterations,
        "started_at": time.time(),
        "finished_at": None,
        "iterations": [],
        "error": None,
        "blockers": [],
        "docker_start_contract": {},
    }


def run_long_running_validation(
    *,
    duration_seconds: int,
    max_iterations: int,
    probe_timeout_seconds: int,
    probe_step_seconds: float,
    poll_seconds: float,
    build: bool,
    cleanup: bool,
    json_output: bool,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
    docker_start_hint: bool = False,
    skip_if_unavailable: bool = False,
) -> int:
    env = os.environ.copy()
    report = _base_report(
        duration_seconds=duration_seconds,
        max_iterations=max_iterations,
    )
    if not _enabled(env, LONG_RUNNING_GATE_ENV):
        report.update(
            {
                "ok": True,
                "skipped": True,
                "error": f"Set {LONG_RUNNING_GATE_ENV}=1 to run the real Docker validation.",
                "finished_at": time.time(),
                "exit_code": 0,
            }
        )
        print(report["error"])
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return 0

    if not docker_available():
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "error": "docker command is not available.",
                "finished_at": time.time(),
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "blockers": ["missing_tool:docker"],
            }
        )
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        print(f"ERROR: {report['error']}")
        return 0 if skipped else 2
    if not COMPOSE_FILE.is_file():
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "error": f"compose file is missing: {COMPOSE_FILE}",
                "finished_at": time.time(),
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "blockers": ["missing_file:compose.arq-worker.yml"],
            }
        )
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        print(f"ERROR: {report['error']}")
        return 0 if skipped else 2

    env.setdefault("TASK_STORE_FAIL_INCOMPLETE_ON_START", "false")
    env.setdefault("TASK_BACKEND", "arq")
    env.setdefault("ARQ_QUEUE_NAME", "insightdesk:tasks")
    env.setdefault("ARQ_WORKER_HEARTBEAT_SECONDS", "5")
    env.setdefault("ARQ_WORKER_DRAIN_SECONDS", "30")
    engine_ok, engine_detail = docker_engine_available(env=env)
    if not engine_ok:
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "error": "docker engine is not available.",
                "finished_at": time.time(),
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "blockers": [DOCKER_DAEMON_BLOCKER],
                "docker_detail_tail": engine_detail.strip()[-1200:],
                "docker_start_contract": _docker_start_contract(include_hint=docker_start_hint),
            }
        )
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        print("ERROR: docker engine is not available. Start Docker Desktop or your Docker daemon.")
        return 0 if skipped else 2

    up_args = ["up"]
    if build:
        up_args.append("--build")
    up_args.extend(["-d", "redis", "arq-worker"])
    result = _run(_compose_command(*up_args), env=env, timeout=max(120, probe_timeout_seconds * 2))
    print(result.stdout, end="")
    if result.returncode != 0:
        report.update(
            {
                "error": "compose up failed",
                "finished_at": time.time(),
                "exit_code": result.returncode,
            }
        )
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return result.returncode

    deadline = time.monotonic() + max(1, int(duration_seconds))
    completed = 0
    exit_code = 0
    try:
        while time.monotonic() < deadline and completed < max(1, int(max_iterations)):
            started = time.perf_counter()
            probe = _run(
                _compose_command(
                    "run",
                    "--rm",
                    "-e",
                    "TASK_STORE_FAIL_INCOMPLETE_ON_START=false",
                    "-e",
                    "TASK_BACKEND=arq",
                    "arq-worker",
                    "python",
                    PROBE_PATH,
                    "--timeout-seconds",
                    str(probe_timeout_seconds),
                    "--poll-seconds",
                    str(poll_seconds),
                    "--probe-step-seconds",
                    str(probe_step_seconds),
                ),
                env=env,
                timeout=max(30, probe_timeout_seconds + 30),
            )
            print(probe.stdout, end="")
            completed += 1
            iteration = {
                "index": completed,
                "ok": probe.returncode == 0,
                "returncode": probe.returncode,
                "duration_ms": max(0, round((time.perf_counter() - started) * 1000)),
            }
            report["iterations"].append(iteration)
            if probe.returncode != 0:
                logs = _run(_compose_command("logs", "--tail", "160", "arq-worker"), env=env)
                print(logs.stdout, end="")
                report["error"] = "probe iteration failed"
                exit_code = probe.returncode
                break
    finally:
        if cleanup:
            down = _run(_compose_command("down"), env=env, timeout=120)
            print(down.stdout, end="")

    report["finished_at"] = time.time()
    report["ok"] = exit_code == 0 and completed > 0
    report["exit_code"] = exit_code
    if report["ok"]:
        report["completed_iterations"] = completed
    _emit_report(
        report,
        json_output=json_output,
        report_path=report_path,
        archive_dir=archive_dir,
        history_path=history_path,
        manifest_path=manifest_path,
    )
    return exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run env-gated long-running ARQ validation.")
    parser.add_argument("--duration-seconds", type=int, default=900)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--probe-timeout-seconds", type=int, default=90)
    parser.add_argument("--probe-step-seconds", type=float, default=0.5)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--archive-dir", default="")
    parser.add_argument("--history-path", default="")
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--docker-start-hint", action="store_true")
    parser.add_argument(
        "--skip-if-unavailable",
        action="store_true",
        help="Emit skipped evidence and exit 0 when Docker or the compose file is unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_long_running_validation(
        duration_seconds=args.duration_seconds,
        max_iterations=args.max_iterations,
        probe_timeout_seconds=args.probe_timeout_seconds,
        probe_step_seconds=args.probe_step_seconds,
        poll_seconds=args.poll_seconds,
        build=not args.no_build,
        cleanup=not args.keep_running,
        json_output=args.json,
        report_path=args.report_path,
        archive_dir=args.archive_dir,
        history_path=args.history_path,
        manifest_path=args.manifest_path,
        docker_start_hint=args.docker_start_hint,
        skip_if_unavailable=args.skip_if_unavailable,
    )


if __name__ == "__main__":
    raise SystemExit(main())
