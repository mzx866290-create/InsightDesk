"""Run the Redis/ARQ worker E2E smoke drill through Docker Compose."""

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
DOCKER_DAEMON_BLOCKER = "docker_daemon_unavailable"
DOCKER_DESKTOP_START_COMMANDS = {
    "windows": "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'",
    "macos": "open -a Docker",
    "linux": "sudo systemctl start docker",
}


def _compose_command(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), *args]


def _run(command: list[str], *, env: dict[str, str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
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
    report.setdefault("evidence", {})
    report["evidence"].update(
        {
            "schema_version": 1,
            "decision": (
                "skipped_no_real_environment"
                if bool(report.get("skipped"))
                else "smoke_passed"
                if bool(report.get("ok"))
                else "smoke_failed"
            ),
            "archive_ready": bool(report_path or archive_dir or history_path),
            "compose_file": str(COMPOSE_FILE),
            "probe_path": PROBE_PATH,
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
                "report_path": report_path,
                "archive_path": report.get("archive_path", ""),
                "blockers": report.get("blockers", []),
                "skipped": bool(report.get("skipped")),
                "decision": str(report.get("evidence", {}).get("decision") or ""),
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


def run_smoke(
    *,
    timeout_seconds: int,
    compose_timeout_seconds: int,
    build: bool,
    cleanup: bool,
    json_output: bool = False,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
    docker_start_hint: bool = False,
    skip_if_unavailable: bool = False,
) -> int:
    report: dict[str, Any] = {
        "id": "arq_long_running_smoke",
        "ok": False,
        "skipped": False,
        "exit_code": 1,
        "started_at": time.time(),
        "finished_at": None,
        "blockers": [],
        "docker_start_contract": {},
    }
    if not docker_available():
        print("ERROR: docker command is not available.")
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "finished_at": time.time(),
                "blockers": ["missing_tool:docker"],
                "error": "docker command is not available.",
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
        return 0 if skipped else 2
    if not COMPOSE_FILE.is_file():
        print(f"ERROR: compose file is missing: {COMPOSE_FILE}")
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "finished_at": time.time(),
                "error": f"compose file is missing: {COMPOSE_FILE}",
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
        return 0 if skipped else 2

    env = os.environ.copy()
    env.setdefault("TASK_STORE_FAIL_INCOMPLETE_ON_START", "false")
    env.setdefault("TASK_BACKEND", "arq")
    env.setdefault("ARQ_QUEUE_NAME", "insightdesk:tasks")
    env.setdefault("ARQ_WORKER_HEARTBEAT_SECONDS", "5")
    env.setdefault("ARQ_WORKER_DRAIN_SECONDS", "10")
    engine_ok, engine_detail = docker_engine_available(env=env)
    if not engine_ok:
        print("ERROR: docker engine is not available. Start Docker Desktop or your Docker daemon.")
        skipped = bool(skip_if_unavailable)
        report.update(
            {
                "ok": skipped,
                "skipped": skipped,
                "exit_code": 0 if skipped else 2,
                "finished_at": time.time(),
                "blockers": [DOCKER_DAEMON_BLOCKER],
                "error": "docker engine is not available.",
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
        return 0 if skipped else 2

    up_args = ["up"]
    if build:
        up_args.append("--build")
    up_args.extend(["-d", "redis", "arq-worker"])
    result = _run(
        _compose_command(*up_args),
        env=env,
        timeout=max(120, compose_timeout_seconds, timeout_seconds * 2),
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        report.update(
            {
                "exit_code": result.returncode,
                "finished_at": time.time(),
                "error": "compose up failed",
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

    try:
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
                str(timeout_seconds),
            ),
            env=env,
            timeout=max(30, timeout_seconds + 30),
        )
        print(probe.stdout, end="")
        if probe.returncode != 0:
            logs = _run(_compose_command("logs", "--tail", "120", "arq-worker"), env=env)
            print(logs.stdout, end="")
        report.update(
            {
                "ok": probe.returncode == 0,
                "exit_code": probe.returncode,
                "finished_at": time.time(),
                "task_backend": env.get("TASK_BACKEND", "arq"),
                "queue_name": env.get("ARQ_QUEUE_NAME", "insightdesk:tasks"),
                "probe_output_tail": (probe.stdout or "").strip()[-1200:],
            }
        )
        return probe.returncode
    finally:
        if cleanup:
            down = _run(_compose_command("down"), env=env, timeout=120)
            print(down.stdout, end="")
            report["cleanup_completed"] = down.returncode == 0
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
    parser = argparse.ArgumentParser(description="Run the ARQ E2E smoke drill.")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument(
        "--compose-timeout-seconds",
        type=int,
        default=600,
        help="Maximum time allowed for Docker Compose build/start during cold real-environment drills.",
    )
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
    return run_smoke(
        timeout_seconds=args.timeout_seconds,
        compose_timeout_seconds=args.compose_timeout_seconds,
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
