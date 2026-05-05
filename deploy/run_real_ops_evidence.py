"""Run or plan real-environment ops evidence drills.

Default mode is a dry-run planner. It reads the real-environment checks from
run_ops_readiness, reports missing gates/tools, and never executes drill
commands. Use --execute during a controlled deployment window.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy import run_ops_readiness as readiness
from deploy import verify_ops_evidence


DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_EVIDENCE_ID = "real_ops_evidence_runner"


def _selected_real_checks(
    *,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
) -> list[readiness.OpsReadinessCheck]:
    only_set = {item.strip() for item in only if item.strip()}
    skip_set = {item.strip() for item in skip if item.strip()}
    checks = [check for check in readiness.all_readiness_checks() if check.real_environment]
    if only_set:
        checks = [check for check in checks if check.id in only_set]
    if skip_set:
        checks = [check for check in checks if check.id not in skip_set]
    return checks


def _unknown_ids(*, only: Sequence[str], skip: Sequence[str]) -> list[str]:
    known = {check.id for check in readiness.all_readiness_checks() if check.real_environment}
    requested = {item.strip() for item in [*only, *skip] if item.strip()}
    return sorted(requested - known)


def build_execution_plan(
    *,
    env: Mapping[str, str] | None = None,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
    probe_tools: bool = True,
) -> dict[str, object]:
    current_env = os.environ if env is None else env
    unknown = _unknown_ids(only=only, skip=skip)
    checks = [
        readiness.describe_check(
            check,
            env=current_env,
            include_real=True,
            probe_tools=probe_tools,
        )
        for check in _selected_real_checks(only=only, skip=skip)
    ]
    runnable = [item for item in checks if bool(item.get("runnable"))]
    blocked = [item for item in checks if not bool(item.get("runnable"))]
    return {
        "ok": not unknown and bool(checks),
        "mode": "plan",
        "execute": False,
        "probe_tools": probe_tools,
        "unknown_ids": unknown,
        "summary": {
            "selected": len(checks),
            "runnable": len(runnable),
            "blocked": len(blocked),
            "all_runnable": not blocked and bool(checks),
        },
        "checks": checks,
    }


def _run_command(command: Sequence[str], *, timeout_seconds: int) -> dict[str, object]:
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            },
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
            "stdout": (exc.stdout or "").strip()[-4000:],
            "stderr": (exc.stderr or "").strip()[-4000:],
            "error": f"timed out after {timeout_seconds}s",
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "duration_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
        "stdout": (completed.stdout or "").strip()[-4000:],
        "stderr": (completed.stderr or "").strip()[-4000:],
        "error": "",
    }


def run_real_evidence(
    *,
    env: Mapping[str, str] | None = None,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
    execute: bool = False,
    continue_on_error: bool = False,
    strict_plan: bool = False,
    strict_verifier: bool = False,
    probe_tools: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    plan = build_execution_plan(env=env, only=only, skip=skip, probe_tools=probe_tools)
    results: list[dict[str, object]] = []
    blocked = [item for item in plan["checks"] if not bool(item.get("runnable"))]  # type: ignore[index]

    can_execute = (
        execute
        and bool(plan["ok"])
        and not blocked
        and bool(plan["checks"])  # type: ignore[index]
    )
    if can_execute:
        for item in plan["checks"]:  # type: ignore[index]
            execution = _run_command(
                item["command"],  # type: ignore[arg-type]
                timeout_seconds=timeout_seconds,
            )
            results.append(
                {
                    "id": item["id"],
                    "area": item["area"],
                    "ok": execution["ok"],
                    "command": item["command"],
                    "execution": execution,
                }
            )
            if not bool(execution["ok"]) and not continue_on_error:
                break

    verifier_report: dict[str, object] | None = None
    if execute and strict_verifier:
        verifier_report = verify_ops_evidence.build_evidence_verification_report(strict=True)

    failed_results = [item for item in results if not bool(item["ok"])]
    blocked_ids = [str(item["id"]) for item in blocked]
    plan_ready = bool(plan["ok"]) and not blocked and bool(plan["checks"])  # type: ignore[index]
    ok = bool(plan["ok"])
    if strict_plan and not plan_ready:
        ok = False
    if execute and (not can_execute or blocked_ids or failed_results):
        ok = False
    if verifier_report is not None and not bool(verifier_report.get("ok")):
        ok = False

    return {
        "ok": ok,
        "mode": "execute" if execute else "plan",
        "execute": execute,
        "strict_plan": strict_plan,
        "strict_verifier": strict_verifier,
        "probe_tools": probe_tools,
        "continue_on_error": continue_on_error,
        "timeout_seconds": timeout_seconds,
        "summary": {
            **plan["summary"],  # type: ignore[arg-type]
            "executed": len(results),
            "passed": len(results) - len(failed_results),
            "failed": len(failed_results),
            "blocked_ids": blocked_ids,
            "unknown_ids": plan["unknown_ids"],
        },
        "plan": plan,
        "results": results,
        "verifier": verifier_report,
    }


def emit_evidence_report(
    report: dict[str, object],
    *,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
) -> None:
    """Persist the runner plan/execution batch for rollout audit trails."""

    if not (report_path or archive_dir or history_path):
        return

    report["evidence"] = {
        "id": DEFAULT_EVIDENCE_ID,
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "archive_path": "",
    }
    if archive_dir:
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{DEFAULT_EVIDENCE_ID}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        archive_path = archive_root / archive_name
        report["evidence"]["archive_path"] = str(archive_path)  # type: ignore[index]
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
        entries: list[dict[str, object]] = []
        if history.is_file():
            try:
                loaded = json.loads(history.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries = [item for item in loaded if isinstance(item, dict)]
            except json.JSONDecodeError:
                entries = []
        summary = report.get("summary")
        summary_map = summary if isinstance(summary, dict) else {}
        evidence = report.get("evidence")
        evidence_map = evidence if isinstance(evidence, dict) else {}
        entries.append(
            {
                "id": DEFAULT_EVIDENCE_ID,
                "ok": bool(report.get("ok")),
                "mode": str(report.get("mode") or ""),
                "execute": bool(report.get("execute")),
                "strict_plan": bool(report.get("strict_plan")),
                "strict_verifier": bool(report.get("strict_verifier")),
                "probe_tools": bool(report.get("probe_tools")),
                "selected": int(summary_map.get("selected") or 0),
                "blocked": int(summary_map.get("blocked") or 0),
                "executed": int(summary_map.get("executed") or 0),
                "failed": int(summary_map.get("failed") or 0),
                "summary": summary_map,
                "plan": report.get("plan"),
                "results": report.get("results"),
                "verifier": report.get("verifier"),
                "report_path": report_path,
                "archive_path": str(evidence_map.get("archive_path") or ""),
                "history_path": history_path,
                "recorded_at": time.time(),
            }
        )
        history.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or run real ops evidence drills.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--execute", action="store_true", help="Execute runnable real-environment drills.")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only a real drill id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Skip a real drill id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue executing selected runnable drills after a command failure.",
    )
    parser.add_argument(
        "--strict-plan",
        action="store_true",
        help="Return non-zero when the selected dry-run/preflight plan has blockers.",
    )
    parser.add_argument(
        "--strict-verifier",
        action="store_true",
        help="After execution, require verify_ops_evidence.py --json --strict semantics.",
    )
    parser.add_argument(
        "--skip-probes",
        action="store_true",
        help="Skip Docker/Kubectl live probes for fast local dry-run planning.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-drill command timeout.",
    )
    parser.add_argument("--report-path", default="", help="Persist the full runner report JSON.")
    parser.add_argument("--archive-dir", default="", help="Persist a timestamped runner report copy.")
    parser.add_argument("--history-path", default="", help="Persist a rolling runner history JSON list.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_real_evidence(
        only=args.only,
        skip=args.skip,
        execute=args.execute,
        continue_on_error=args.continue_on_error,
        strict_plan=args.strict_plan,
        strict_verifier=args.strict_verifier,
        probe_tools=not args.skip_probes,
        timeout_seconds=max(1, int(args.timeout_seconds)),
    )
    emit_evidence_report(
        report,
        report_path=str(args.report_path or ""),
        archive_dir=str(args.archive_dir or ""),
        history_path=str(args.history_path or ""),
    )
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        summary = report["summary"]
        print(
            "summary: "
            f"mode={report['mode']} "
            f"selected={summary['selected']} "
            f"runnable={summary['runnable']} "
            f"blocked={summary['blocked']} "
            f"executed={summary['executed']} "
            f"failed={summary['failed']}"
        )
        for item in report["plan"]["checks"]:  # type: ignore[index]
            print(f"- {item['status']} {item['id']}: {' '.join(item['command'])}")
            blockers = item.get("blockers") or []
            if blockers:
                print(f"  blockers: {', '.join(blockers)}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
