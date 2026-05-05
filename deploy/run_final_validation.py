"""Run the final project validation checklist.

The script is a safe orchestration layer: it runs local tests and static
validators only. Real PostgreSQL/Qdrant checks remain gated by
STORAGE_INTEGRATION_TEST inside deploy/run_storage_integration_check.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEFAULT_OUTPUT_CHAR_LIMIT = 4000
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

REMAINING_MARKERS = (
    "待增强",
    "待确认",
    "未开始",
    "进行中",
    "未完整",
    "未完成",
)

REMAINING_MARKER_CHECK = (
    "from pathlib import Path; "
    "import re, sys; "
    "text = Path('docs/IMPLEMENTATION_PLAN.md').read_text(encoding='utf-8'); "
    "pattern = re.compile('待增强|待确认|未开始|进行中|未完整|未完成'); "
    "matches = pattern.findall(text); "
    "print(len(matches)); "
    "sys.exit(0 if not matches else 1)"
)


@dataclass(frozen=True)
class ValidationStep:
    """A single validation command with enough metadata for JSON reporting."""

    id: str
    description: str
    command: tuple[str, ...]
    cwd: Path = PROJECT_ROOT
    categories: tuple[str, ...] = ("backend",)
    profiles: tuple[str, ...] = ("quick", "full")
    failure_patterns: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "description": self.description,
            "command": list(self.command),
            "cwd": str(self.cwd),
            "categories": list(self.categories),
            "profiles": list(self.profiles),
            "failure_patterns": list(self.failure_patterns),
        }


def _python_command(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


def all_validation_steps() -> list[ValidationStep]:
    """Return the ordered final acceptance checklist."""

    return [
        ValidationStep(
            id="implementation_plan_remaining_markers",
            description="Implementation plan has zero remaining-state markers.",
            command=_python_command("-c", REMAINING_MARKER_CHECK),
            categories=("docs",),
        ),
        ValidationStep(
            id="agent_core_split_regression",
            description="agent_core split compatibility and regression matrix.",
            command=_python_command("deploy/validate_agent_core_split.py", "-q"),
            categories=("backend",),
        ),
        ValidationStep(
            id="storage_orchestrator_contracts",
            description="Storage migration, runtime, and vector store contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_storage_integration_contract.py",
                "tests/test_storage_migration_execution.py",
                "tests/test_storage_migration_tools_static.py",
                "tests/test_qdrant_backfill_runner.py",
                "tests/test_qdrant_integration_contract.py",
                "tests/test_storage_runtime.py",
                "-q",
            ),
            categories=("backend", "storage"),
        ),
        ValidationStep(
            id="agent_orchestrator_contracts",
            description="Agent orchestrator and LLM metric contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_agent_orchestrator.py",
                "tests/test_agent_llm_metrics.py",
                "-q",
            ),
            categories=("backend", "agents"),
        ),
        ValidationStep(
            id="task_queue_arq_contracts",
            description="ARQ task queue, worker heartbeat, drain drill, and alert rule contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_arq_worker_heartbeat.py",
                "tests/test_arq_worker_ops_static.py",
                "tests/test_arq_alert_rules_static.py",
                "-q",
            ),
            categories=("backend", "deploy", "tasks"),
        ),
        ValidationStep(
            id="research_archive_contracts",
            description="Research V2 archive reuse, CitationPanel, and conflict review contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_research_agent.py",
                "tests/test_research_archive_api.py",
                "-q",
            ),
            categories=("backend", "agents"),
        ),
        ValidationStep(
            id="writing_review_approval_contracts",
            description="Writing, review, and human approval gate contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_writing_agent.py",
                "tests/test_review_agent.py",
                "-q",
            ),
            categories=("backend", "agents"),
        ),
        ValidationStep(
            id="model_compare_contracts",
            description="Multi-model synthesis, evaluation, and preference contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_model_compare_agent.py",
                "-q",
            ),
            categories=("backend", "agents"),
        ),
        ValidationStep(
            id="deck_delivery_contracts",
            description="Deck regeneration, slide review, and export coordination contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_deck_regeneration_and_theme.py",
                "tests/test_deck_service_pptx_export.py",
                "tests/test_artifact_api.py",
                "tests/test_api_deck_report_helpers.py",
                "tests/test_document_report_api.py",
                "-q",
            ),
            categories=("backend", "deck"),
        ),
        ValidationStep(
            id="mcp_observability_contracts",
            description="MCP connector productization and observability exporter contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_agent_mcp_helpers.py",
                "tests/test_integrator_connector_config_api.py",
                "tests/test_api_observability.py",
                "tests/test_runtime_metrics.py",
                "tests/test_core_tracing.py",
                "tests/test_logging_config_and_metrics.py",
                "-q",
            ),
            categories=("backend", "mcp", "observability"),
        ),
        ValidationStep(
            id="delivery_agent_contracts",
            description="Research, review, security, observability, and deck contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_research_agent.py",
                "tests/test_research_archive_api.py",
                "tests/test_review_agent.py",
                "tests/test_api_observability.py",
                "tests/test_api_security_audit_store.py",
                "tests/test_security_audit_summary.py",
                "tests/test_api_deck_report_helpers.py",
                "tests/test_deck_regeneration_and_theme.py",
                "-q",
            ),
            categories=("backend", "agents"),
            profiles=("full",),
        ),
        ValidationStep(
            id="helm_static_validation",
            description="Helm chart static deployment contract.",
            command=_python_command("deploy/validate_helm_static.py"),
            categories=("deploy",),
        ),
        ValidationStep(
            id="k8s_ops_readiness_contracts",
            description="K8s rollout drill and ops readiness evidence contracts.",
            command=_python_command(
                "-m",
                "pytest",
                "tests/test_deploy_helm_static.py",
                "tests/test_k8s_rollout_drill_static.py",
                "tests/test_ops_readiness.py",
                "tests/test_ops_evidence_verifier.py",
                "tests/test_real_ops_evidence_runner.py",
                "-q",
            ),
            categories=("deploy",),
        ),
        ValidationStep(
            id="ops_readiness_summary_contract",
            description="Ops readiness evidence summary for ARQ, storage, and Kubernetes drills.",
            command=_python_command("deploy/run_ops_readiness.py", "--json"),
            categories=("deploy", "storage", "tasks"),
        ),
        ValidationStep(
            id="ops_evidence_verifier_contract",
            description="Safe ops evidence closure verifier for ARQ, storage, and Kubernetes drills.",
            command=_python_command("deploy/verify_ops_evidence.py", "--json"),
            categories=("deploy", "storage", "tasks"),
        ),
        ValidationStep(
            id="real_ops_evidence_plan_contract",
            description="Dry-run real ops evidence execution plan stays inert by default.",
            command=_python_command("deploy/run_real_ops_evidence.py", "--json", "--skip-probes"),
            categories=("deploy", "storage", "tasks"),
        ),
        ValidationStep(
            id="storage_integration_default_probe",
            description="Env-gated storage probe stays inert without integration env.",
            command=_python_command("deploy/run_storage_integration_check.py", "--compact"),
            categories=("deploy", "storage"),
        ),
        ValidationStep(
            id="frontend_typecheck",
            description="Frontend TypeScript contract.",
            command=("npx", "tsc", "--noEmit", "--pretty", "false"),
            cwd=FRONTEND_DIR,
            categories=("frontend",),
        ),
        ValidationStep(
            id="frontend_build",
            description="Frontend production build.",
            command=("npm", "run", "build"),
            cwd=FRONTEND_DIR,
            categories=("frontend",),
            profiles=("full",),
            failure_patterns=("Some chunks are larger than",),
        ),
    ]


def select_steps(
    *,
    profile: str,
    categories: Sequence[str],
    include_frontend_build: bool,
) -> list[ValidationStep]:
    selected_categories = set(categories)
    steps = [
        step
        for step in all_validation_steps()
        if profile in step.profiles
        and (not selected_categories or selected_categories.intersection(step.categories))
    ]
    if not include_frontend_build:
        steps = [step for step in steps if step.id != "frontend_build"]
    return steps


def _validation_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_entries = [str(PROJECT_ROOT), str(PROJECT_ROOT / "backend")]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"
    env["TERM"] = "dumb"
    return env


def _resolve_command(command: Sequence[str]) -> tuple[str, ...]:
    executable = command[0]
    resolved = shutil.which(executable)
    if not resolved:
        return tuple(command)
    return (resolved, *command[1:])


def _truncate_output(value: str, limit: int | None) -> tuple[str, bool, int]:
    if limit is None or len(value) <= limit:
        return value, False, len(value)
    if limit <= 0:
        return "", True, len(value)
    marker = f"\n... output truncated to last {limit} chars ...\n"
    if limit <= len(marker):
        return value[-limit:], True, len(value)
    tail_limit = limit - len(marker)
    return f"{marker}{value[-tail_limit:]}", True, len(value)


def _strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def run_step(
    step: ValidationStep,
    *,
    output_char_limit: int | None = DEFAULT_OUTPUT_CHAR_LIMIT,
) -> dict[str, object]:
    started_at = time.perf_counter()
    command = _resolve_command(step.command)
    try:
        completed = subprocess.run(
            command,
            cwd=step.cwd,
            env=_validation_env(),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        return {
            **step.as_dict(),
            "command": list(command),
            "returncode": 127,
            "ok": False,
            "duration_ms": duration_ms,
            "output_failures": [],
            "stdout_truncated": False,
            "stderr_truncated": False,
            "stdout_original_chars": 0,
            "stderr_original_chars": len(str(exc.filename or step.command[0])),
            "stdout": "",
            "stderr": f"command_not_found:{exc.filename or step.command[0]}",
        }
    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    stdout = _strip_ansi((completed.stdout or "").strip())
    stderr = _strip_ansi((completed.stderr or "").strip())
    combined_output = f"{stdout}\n{stderr}"
    output_failures = [
        pattern for pattern in step.failure_patterns if pattern in combined_output
    ]
    ok = completed.returncode == 0 and not output_failures
    report_stdout, stdout_truncated, stdout_original_chars = _truncate_output(
        stdout,
        output_char_limit,
    )
    report_stderr, stderr_truncated, stderr_original_chars = _truncate_output(
        stderr,
        output_char_limit,
    )

    return {
        **step.as_dict(),
        "command": list(command),
        "returncode": completed.returncode,
        "ok": ok,
        "duration_ms": duration_ms,
        "output_failures": output_failures,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "stdout_original_chars": stdout_original_chars,
        "stderr_original_chars": stderr_original_chars,
        "stdout": report_stdout,
        "stderr": report_stderr,
    }


def effective_parallel_workers(*, requested_workers: int, fail_fast: bool) -> int:
    """Return the actual worker count used for validation execution."""

    if fail_fast:
        return 1
    return max(1, requested_workers)


def run_steps(
    steps: Iterable[ValidationStep],
    *,
    fail_fast: bool,
    output_char_limit: int | None = DEFAULT_OUTPUT_CHAR_LIMIT,
    parallel_workers: int = 1,
) -> list[dict[str, object]]:
    step_list = list(steps)
    worker_count = effective_parallel_workers(
        requested_workers=parallel_workers,
        fail_fast=fail_fast,
    )
    if worker_count <= 1 or len(step_list) <= 1:
        results: list[dict[str, object]] = []
        for step in step_list:
            result = run_step(step, output_char_limit=output_char_limit)
            results.append(result)
            if fail_fast and not result["ok"]:
                break
        return results

    results_by_index: list[dict[str, object] | None] = [None] * len(step_list)
    with ThreadPoolExecutor(max_workers=min(worker_count, len(step_list))) as executor:
        future_indexes = {
            executor.submit(run_step, step, output_char_limit=output_char_limit): index
            for index, step in enumerate(step_list)
        }
        for future in as_completed(future_indexes):
            index = future_indexes[future]
            results_by_index[index] = future.result()

    return [result for result in results_by_index if result is not None]


def build_results_summary(
    results: Sequence[dict[str, object]],
    *,
    selected_step_count: int,
    fail_fast: bool = False,
) -> dict[str, object]:
    passed = sum(1 for result in results if bool(result.get("ok")))
    failed = len(results) - passed
    duration_ms_values = [
        max(0, int(result.get("duration_ms", 0) or 0))
        for result in results
    ]
    duration_ms_total = sum(duration_ms_values)
    stdout_truncated = sum(1 for result in results if bool(result.get("stdout_truncated")))
    stderr_truncated = sum(1 for result in results if bool(result.get("stderr_truncated")))
    truncated_steps = sum(
        1
        for result in results
        if bool(result.get("stdout_truncated")) or bool(result.get("stderr_truncated"))
    )
    output_failure_results = [
        result
        for result in results
        if result.get("output_failures")
    ]
    output_failure_count = sum(
        len(result.get("output_failures", []))  # type: ignore[arg-type]
        for result in output_failure_results
    )
    fail_fast_stopped = (
        fail_fast
        and bool(results)
        and not bool(results[-1].get("ok"))
        and len(results) < selected_step_count
    )
    return {
        "selected": selected_step_count,
        "executed": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": max(0, selected_step_count - len(results)),
        "duration_ms_total": duration_ms_total,
        "duration_ms_avg": round(duration_ms_total / len(duration_ms_values)) if duration_ms_values else 0,
        "duration_ms_max": max(duration_ms_values, default=0),
        "truncated": {
            "steps": truncated_steps,
            "stdout": stdout_truncated,
            "stderr": stderr_truncated,
            "streams": stdout_truncated + stderr_truncated,
        },
        "output_failures": {
            "steps": len(output_failure_results),
            "count": output_failure_count,
        },
        "returncode_failures": {
            "steps": sum(1 for result in results if int(result.get("returncode", 0)) != 0),
        },
        "fail_fast_stopped": fail_fast_stopped,
    }


def build_report(
    *,
    steps: Sequence[ValidationStep],
    results: Sequence[dict[str, object]] | None = None,
    listed_only: bool = False,
    output_char_limit: int | None = DEFAULT_OUTPUT_CHAR_LIMIT,
    fail_fast: bool = False,
    parallel_workers: int = 1,
) -> dict[str, object]:
    effective_workers = effective_parallel_workers(
        requested_workers=parallel_workers,
        fail_fast=fail_fast,
    )
    payload: dict[str, object] = {
        "ok": True,
        "listed_only": listed_only,
        "step_count": len(steps),
        "output_char_limit": output_char_limit,
        "parallel_workers": effective_workers,
        "summary": build_results_summary(
            results or [],
            selected_step_count=len(steps),
            fail_fast=fail_fast,
        ),
        "steps": [step.as_dict() for step in steps],
    }
    if results is not None:
        payload["results"] = list(results)
        payload["ok"] = all(bool(result["ok"]) for result in results) and len(results) == len(steps)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the final local validation checklist.",
    )
    parser.add_argument(
        "--profile",
        choices=("quick", "full"),
        default="quick",
        help="Validation depth. quick skips longer full-contract and production build steps.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        choices=(
            "agents",
            "backend",
            "deck",
            "deploy",
            "docs",
            "frontend",
            "mcp",
            "observability",
            "storage",
            "tasks",
        ),
        help="Run only matching category. Repeat to include multiple categories.",
    )
    parser.add_argument(
        "--include-frontend-build",
        action="store_true",
        help="Include npm run build when it is selected by the profile/category filters.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected checklist without executing it.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at the first failing step. This forces serial execution.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Run validation steps concurrently when greater than 1. Ignored by --fail-fast.",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=DEFAULT_OUTPUT_CHAR_LIMIT,
        help=(
            "Maximum stdout/stderr characters kept per stream in reports. "
            "Use 0 to hide captured output while keeping status and original sizes."
        ),
    )
    parser.add_argument(
        "--verbose-output",
        action="store_true",
        help="Keep full stdout/stderr for every step.",
    )
    return parser.parse_args()


def _safe_print(text: object = "", *, file: object | None = None) -> None:
    stream = file or sys.stdout
    try:
        print(text, file=stream)
        return
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        safe_text = str(text).encode(encoding, errors="replace").decode(
            encoding,
            errors="replace",
        )
        print(safe_text, file=stream)


def _print_human_report(report: dict[str, object]) -> None:
    _safe_print(f"ok: {str(report['ok']).lower()}")
    _safe_print(f"listed_only: {str(report['listed_only']).lower()}")
    _safe_print(f"step_count: {report['step_count']}")
    _safe_print(f"parallel_workers: {report.get('parallel_workers', 1)}")
    summary = report.get("summary")
    if isinstance(summary, dict):
        truncated = summary.get("truncated") if isinstance(summary.get("truncated"), dict) else {}
        output_failures = (
            summary.get("output_failures")
            if isinstance(summary.get("output_failures"), dict)
            else {}
        )
        _safe_print(
            "summary: "
            f"selected={summary.get('selected', 0)} "
            f"executed={summary.get('executed', 0)} "
            f"passed={summary.get('passed', 0)} "
            f"failed={summary.get('failed', 0)} "
            f"skipped={summary.get('skipped', 0)} "
            f"duration_ms_total={summary.get('duration_ms_total', 0)} "
            f"duration_ms_avg={summary.get('duration_ms_avg', 0)} "
            f"duration_ms_max={summary.get('duration_ms_max', 0)} "
            f"truncated_steps={truncated.get('steps', 0)} "
            f"output_failure_steps={output_failures.get('steps', 0)} "
            f"fail_fast_stopped={str(summary.get('fail_fast_stopped', False)).lower()}"
        )

    results = report.get("results")
    if not isinstance(results, list):
        for step in report["steps"]:  # type: ignore[index]
            _safe_print(f"- {step['id']}: {' '.join(step['command'])}")  # type: ignore[index]
        return

    for result in results:
        status = "PASS" if result["ok"] else "FAIL"
        _safe_print(
            f"- {status} {result['id']} "
            f"({result['returncode']}) "
            f"duration_ms={result.get('duration_ms', 0)} "
            f"({result.get('duration_ms', 0)} ms)"
        )
        stdout = str(result.get("stdout") or "")
        stderr = str(result.get("stderr") or "")
        if stdout:
            _safe_print(stdout)
        if stderr:
            _safe_print(stderr, file=sys.stderr)


def _print_json_report(report: dict[str, object]) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


def main() -> int:
    args = parse_args()
    output_char_limit = None if args.verbose_output else max(0, args.max_output_chars)
    parallel_workers = effective_parallel_workers(
        requested_workers=args.parallel_workers,
        fail_fast=args.fail_fast,
    )
    steps = select_steps(
        profile=args.profile,
        categories=args.category,
        include_frontend_build=args.include_frontend_build,
    )

    if args.list:
        report = build_report(
            steps=steps,
            listed_only=True,
            output_char_limit=output_char_limit,
            fail_fast=args.fail_fast,
            parallel_workers=parallel_workers,
        )
    else:
        results = run_steps(
            steps,
            fail_fast=args.fail_fast,
            output_char_limit=output_char_limit,
            parallel_workers=parallel_workers,
        )
        report = build_report(
            steps=steps,
            results=results,
            output_char_limit=output_char_limit,
            fail_fast=args.fail_fast,
            parallel_workers=parallel_workers,
        )

    if args.json:
        _print_json_report(report)
    else:
        _print_human_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
