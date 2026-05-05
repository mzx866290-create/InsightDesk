"""Run an ARQ worker graceful shutdown drain drill through Docker Compose."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "deploy" / "compose.arq-worker.yml"
PROBE_PATH = "/app/deploy/arq_e2e_probe.py"
TASK_ID_PATTERN = re.compile(r"^TASK_ID=(?P<task_id>\S+)\s*$", re.MULTILINE)
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


def _parse_task_id(output: str) -> str:
    match = TASK_ID_PATTERN.search(output)
    return match.group("task_id") if match else ""


def _record_step(
    report: dict[str, Any],
    name: str,
    result: subprocess.CompletedProcess[str],
    *,
    started_at: float,
) -> None:
    report["steps"].append(
        {
            "name": name,
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
            "output_tail": (result.stdout or "").strip()[-1200:],
        }
    )


def _finish_report(
    report: dict[str, Any],
    *,
    ok: bool,
    exit_code: int,
) -> None:
    report["ok"] = ok
    report["exit_code"] = exit_code
    report["finished_at"] = time.time()


def _apply_closure_summary(report: dict[str, Any]) -> None:
    closure = report.setdefault("closure", {})
    required = (
        "enqueued",
        "worker_stopped",
        "task_reached_terminal_state",
        "cleanup_completed",
    )
    missing = [name for name in required if not bool(closure.get(name))]
    failed_steps = [
        str(step.get("name") or "")
        for step in report.get("steps", [])
        if isinstance(step, dict) and not bool(step.get("ok"))
    ]
    successful_steps = [
        str(step.get("name") or "")
        for step in report.get("steps", [])
        if isinstance(step, dict) and bool(step.get("ok"))
    ]
    closure["complete"] = not missing
    closure["missing"] = missing
    closure["decision"] = (
        "skipped_no_real_environment"
        if bool(report.get("skipped"))
        else
        "drain_closed"
        if bool(report.get("ok")) and not missing
        else "drain_incomplete"
    )
    closure["evidence"] = {
        "task_id": str(report.get("task_id") or ""),
        "drain_seconds": int(report.get("drain_seconds") or 0),
        "step_count": len([step for step in report.get("steps", []) if isinstance(step, dict)]),
        "successful_steps": successful_steps,
        "failed_steps": failed_steps,
        "blockers": list(report.get("blockers") or []),
        "archive_ready": bool(report.get("archive_ready")),
    }


def _emit_report(
    report: dict[str, Any],
    *,
    json_output: bool,
    report_path: str,
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
) -> None:
    if archive_dir and not report.get("archive_path"):
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{report['id']}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        report["archive_path"] = str(archive_root / archive_name)
    report["archive_ready"] = bool(report_path or archive_dir or history_path)
    _apply_closure_summary(report)
    report.setdefault("evidence", {})
    report["evidence"].update(
        {
            "schema_version": 1,
            "decision": str(report.get("closure", {}).get("decision") or ""),
            "archive_ready": bool(report.get("archive_ready")),
            "compose_file": str(COMPOSE_FILE),
            "probe_path": PROBE_PATH,
            "task_id": str(report.get("task_id") or ""),
            "blockers": list(report.get("blockers") or []),
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
                "exit_code": report["exit_code"],
                "started_at": report["started_at"],
                "finished_at": report["finished_at"],
                "task_id": report.get("task_id", ""),
                "report_path": report_path,
                "archive_path": report.get("archive_path", ""),
                "blockers": report.get("blockers", []),
                "closure_complete": bool(report.get("closure", {}).get("complete")),
                "closure_decision": str(report.get("closure", {}).get("decision") or ""),
                "skipped": bool(report.get("skipped")),
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


def _probe_env_args() -> list[str]:
    return [
        "-e",
        "TASK_STORE_FAIL_INCOMPLETE_ON_START=false",
        "-e",
        "TASK_BACKEND=arq",
    ]


def _print_worker_logs(*, env: dict[str, str]) -> None:
    logs = _run(_compose_command("logs", "--tail", "160", "arq-worker"), env=env)
    print(logs.stdout, end="")


def run_drain_drill(
    *,
    timeout_seconds: int,
    compose_timeout_seconds: int,
    build: bool,
    cleanup: bool,
    drain_seconds: int,
    pickup_wait_seconds: float,
    probe_step_seconds: float,
    json_output: bool = False,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
    docker_start_hint: bool = False,
    skip_if_unavailable: bool = False,
) -> int:
    report: dict[str, Any] = {
        "id": "arq_drain_drill",
        "ok": False,
        "skipped": False,
        "exit_code": 1,
        "started_at": time.time(),
        "finished_at": None,
        "task_id": "",
        "drain_seconds": drain_seconds,
        "pickup_wait_seconds": pickup_wait_seconds,
        "probe_step_seconds": probe_step_seconds,
        "steps": [],
        "blockers": [],
        "docker_start_contract": {},
        "closure": {
            "enqueued": False,
            "worker_stopped": False,
            "task_reached_terminal_state": False,
            "cleanup_completed": False,
        },
    }
    if not docker_available():
        print("ERROR: docker command is not available.")
        skipped = bool(skip_if_unavailable)
        report["ok"] = skipped
        report["skipped"] = skipped
        report["error"] = "docker command is not available."
        report["blockers"] = ["missing_tool:docker"]
        _finish_report(report, ok=skipped, exit_code=0 if skipped else 2)
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return 0 if skipped else 2
    if not COMPOSE_FILE.is_file():
        print(f"ERROR: compose file is missing: {COMPOSE_FILE}")
        skipped = bool(skip_if_unavailable)
        report["ok"] = skipped
        report["skipped"] = skipped
        report["error"] = f"compose file is missing: {COMPOSE_FILE}"
        report["blockers"] = ["missing_file:compose.arq-worker.yml"]
        _finish_report(report, ok=skipped, exit_code=0 if skipped else 2)
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return 0 if skipped else 2

    env = os.environ.copy()
    env.setdefault("TASK_STORE_FAIL_INCOMPLETE_ON_START", "false")
    env.setdefault("TASK_BACKEND", "arq")
    env.setdefault("ARQ_QUEUE_NAME", "insightdesk:tasks")
    env.setdefault("ARQ_WORKER_HEARTBEAT_SECONDS", "5")
    env.setdefault("ARQ_WORKER_DRAIN_SECONDS", str(max(1, int(drain_seconds))))
    env.setdefault(
        "ARQ_WORKER_STOP_GRACE_PERIOD",
        f"{max(30, int(drain_seconds) + 15)}s",
    )
    engine_ok, engine_detail = docker_engine_available(env=env)
    if not engine_ok:
        print("ERROR: docker engine is not available. Start Docker Desktop or your Docker daemon.")
        skipped = bool(skip_if_unavailable)
        report["ok"] = skipped
        report["skipped"] = skipped
        report["error"] = "docker engine is not available."
        report["blockers"] = [DOCKER_DAEMON_BLOCKER]
        report["docker_detail_tail"] = engine_detail.strip()[-1200:]
        report["docker_start_contract"] = _docker_start_contract(include_hint=docker_start_hint)
        _finish_report(report, ok=skipped, exit_code=0 if skipped else 2)
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return 0 if skipped else 2

    up_args = ["up"]
    if build:
        up_args.append("--build")
    up_args.extend(["-d", "redis", "arq-worker"])
    started = time.perf_counter()
    result = _run(
        _compose_command(*up_args),
        env=env,
        timeout=max(120, compose_timeout_seconds, timeout_seconds * 2),
    )
    _record_step(report, "compose_up", result, started_at=started)
    print(result.stdout, end="")
    if result.returncode != 0:
        _finish_report(report, ok=False, exit_code=result.returncode)
        _emit_report(
            report,
            json_output=json_output,
            report_path=report_path,
            archive_dir=archive_dir,
            history_path=history_path,
            manifest_path=manifest_path,
        )
        return result.returncode

    task_id = ""
    wait_result = 1
    try:
        # Keep "--mode enqueue" visible for static contract checks.
        started = time.perf_counter()
        enqueue = _run(
            _compose_command(
                "run",
                "--rm",
                *_probe_env_args(),
                "arq-worker",
                "python",
                PROBE_PATH,
                "--mode",
                "enqueue",
                "--probe-step-seconds",
                str(probe_step_seconds),
            ),
            env=env,
            timeout=max(30, timeout_seconds),
        )
        _record_step(report, "enqueue_probe", enqueue, started_at=started)
        print(enqueue.stdout, end="")
        if enqueue.returncode != 0:
            _print_worker_logs(env=env)
            _finish_report(report, ok=False, exit_code=enqueue.returncode)
            return enqueue.returncode

        task_id = _parse_task_id(enqueue.stdout)
        if not task_id:
            print("ERROR: probe did not print TASK_ID=...")
            _print_worker_logs(env=env)
            report["error"] = "probe did not print TASK_ID"
            _finish_report(report, ok=False, exit_code=1)
            return 1
        report["task_id"] = task_id
        report["closure"]["enqueued"] = True

        print(f"Waiting {pickup_wait_seconds:.1f}s for worker pickup before stopping arq-worker.")
        time.sleep(max(0.0, float(pickup_wait_seconds)))

        started = time.perf_counter()
        stop = _run(
            _compose_command("stop", "arq-worker"),
            env=env,
            timeout=max(60, int(drain_seconds) + 45),
        )
        _record_step(report, "stop_worker", stop, started_at=started)
        print(stop.stdout, end="")
        if stop.returncode != 0:
            _print_worker_logs(env=env)
            _finish_report(report, ok=False, exit_code=stop.returncode)
            return stop.returncode
        report["closure"]["worker_stopped"] = True

        # Keep "--mode wait" visible for static contract checks.
        started = time.perf_counter()
        wait = _run(
            _compose_command(
                "run",
                "--rm",
                *_probe_env_args(),
                "arq-worker",
                "python",
                PROBE_PATH,
                "--mode",
                "wait",
                "--task-id",
                task_id,
                "--timeout-seconds",
                str(timeout_seconds),
                "--poll-seconds",
                "1",
            ),
            env=env,
            timeout=max(30, timeout_seconds + 30),
        )
        _record_step(report, "wait_for_terminal_task", wait, started_at=started)
        print(wait.stdout, end="")
        wait_result = wait.returncode
        if wait_result != 0:
            _print_worker_logs(env=env)
        report["closure"]["task_reached_terminal_state"] = wait_result == 0
        _finish_report(report, ok=wait_result == 0, exit_code=wait_result)
        return wait_result
    finally:
        if cleanup:
            down = _run(_compose_command("down"), env=env, timeout=120)
            print(down.stdout, end="")
            report["closure"]["cleanup_completed"] = down.returncode == 0
        else:
            up_worker = _run(_compose_command("up", "-d", "arq-worker"), env=env, timeout=120)
            print(up_worker.stdout, end="")
            report["closure"]["cleanup_completed"] = up_worker.returncode == 0
        if report["finished_at"] is not None:
            _emit_report(
                report,
                json_output=json_output,
                report_path=report_path,
                archive_dir=archive_dir,
                history_path=history_path,
                manifest_path=manifest_path,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ARQ graceful shutdown drain drill.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--compose-timeout-seconds",
        type=int,
        default=600,
        help="Maximum time allowed for Docker Compose build/start during cold real-environment drills.",
    )
    parser.add_argument("--drain-seconds", type=int, default=15)
    parser.add_argument("--pickup-wait-seconds", type=float, default=1.5)
    parser.add_argument("--probe-step-seconds", type=float, default=3.0)
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
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--keep-running", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_drain_drill(
        timeout_seconds=args.timeout_seconds,
        compose_timeout_seconds=args.compose_timeout_seconds,
        build=not args.no_build,
        cleanup=not args.keep_running,
        drain_seconds=args.drain_seconds,
        pickup_wait_seconds=args.pickup_wait_seconds,
        probe_step_seconds=args.probe_step_seconds,
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
