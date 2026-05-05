from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

from deploy.run_final_validation import (
    DEFAULT_OUTPUT_CHAR_LIMIT,
    ValidationStep,
    _strip_ansi,
    _truncate_output,
    all_validation_steps,
    build_report,
    build_results_summary,
    _print_human_report,
    _print_json_report,
    effective_parallel_workers,
    run_step,
    run_steps,
    select_steps,
    _validation_env,
)


ROOT = Path(__file__).resolve().parents[1]
FINAL_VALIDATION_FILE = ROOT / "deploy" / "run_final_validation.py"
VALIDATION_DOC = ROOT / "docs" / "VALIDATION.md"


def _read_validator() -> str:
    assert FINAL_VALIDATION_FILE.exists(), "deploy/run_final_validation.py must exist"
    return FINAL_VALIDATION_FILE.read_text(encoding="utf-8")


def test_final_validation_cli_json_contract() -> None:
    content = _read_validator()

    required_snippets = [
        "json.dumps",
        "ensure_ascii=False",
        '"ok"',
        '"listed_only"',
        '"step_count"',
        '"steps"',
        '"results"',
        '"summary"',
        '"selected"',
        '"executed"',
        '"passed"',
        '"failed"',
        '"skipped"',
        '"truncated"',
        '"streams"',
        '"output_failures"',
        '"returncode_failures"',
        '"fail_fast_stopped"',
        '"duration_ms"',
        '"duration_ms_total"',
        '"duration_ms_avg"',
        '"duration_ms_max"',
        '"output_failures"',
        '"stdout_truncated"',
        '"stderr_truncated"',
        '"output_char_limit"',
        "DEFAULT_OUTPUT_CHAR_LIMIT",
        "DEFAULT_OUTPUT_CHAR_LIMIT = 4000",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "NO_COLOR",
        "FORCE_COLOR",
        "TERM",
        "ANSI_ESCAPE_RE",
        "_strip_ansi",
        "time.perf_counter",
        "duration_ms=",
        " ms",
        '"dumb"',
        "--max-output-chars",
        "--verbose-output",
        "--parallel-workers",
        "ThreadPoolExecutor",
        "as_completed",
        '"parallel_workers"',
        "This forces serial execution",
        "Use 0 to hide captured output",
        "failure_patterns",
        "Some chunks are larger than",
        "return 0 if report",
        "else 1",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_final_validation_entrypoint_propagates_nonzero_exit_code() -> None:
    tree = ast.parse(_read_validator())

    main_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert len(main_defs) == 1

    main_def = main_defs[0]
    assert isinstance(main_def.returns, ast.Name)
    assert main_def.returns.id == "int"

    system_exit_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Call)
        and isinstance(node.exc.args[0].func, ast.Name)
        and node.exc.args[0].func.id == "main"
    ]
    assert len(system_exit_calls) == 1


def test_final_validation_locks_deployment_check_coverage() -> None:
    step_ids = {step.id for step in all_validation_steps()}
    required_step_ids = {
        "implementation_plan_remaining_markers",
        "agent_core_split_regression",
        "storage_orchestrator_contracts",
        "agent_orchestrator_contracts",
        "task_queue_arq_contracts",
        "research_archive_contracts",
        "writing_review_approval_contracts",
        "model_compare_contracts",
        "deck_delivery_contracts",
        "mcp_observability_contracts",
        "delivery_agent_contracts",
        "helm_static_validation",
        "k8s_ops_readiness_contracts",
        "ops_readiness_summary_contract",
        "ops_evidence_verifier_contract",
        "real_ops_evidence_plan_contract",
        "storage_integration_default_probe",
        "frontend_typecheck",
        "frontend_build",
    }

    assert required_step_ids.issubset(step_ids)

    commands = [" ".join(step.command) for step in all_validation_steps()]
    required_snippets = [
        "docs/IMPLEMENTATION_PLAN.md",
        "deploy/validate_agent_core_split.py",
        "tests/test_storage_migration_execution.py",
        "tests/test_qdrant_backfill_runner.py",
        "tests/test_storage_runtime.py",
        "tests/test_arq_worker_heartbeat.py",
        "tests/test_arq_worker_ops_static.py",
        "tests/test_arq_alert_rules_static.py",
        "tests/test_agent_orchestrator.py",
        "tests/test_agent_llm_metrics.py",
        "tests/test_research_agent.py",
        "tests/test_research_archive_api.py",
        "tests/test_writing_agent.py",
        "tests/test_review_agent.py",
        "tests/test_model_compare_agent.py",
        "tests/test_deck_regeneration_and_theme.py",
        "tests/test_agent_mcp_helpers.py",
        "tests/test_integrator_connector_config_api.py",
        "tests/test_core_tracing.py",
        "tests/test_logging_config_and_metrics.py",
        "tests/test_api_observability.py",
        "tests/test_api_deck_report_helpers.py",
        "deploy/validate_helm_static.py",
        "tests/test_k8s_rollout_drill_static.py",
        "tests/test_ops_readiness.py",
        "tests/test_ops_evidence_verifier.py",
        "tests/test_real_ops_evidence_runner.py",
        "deploy/run_ops_readiness.py --json",
        "deploy/verify_ops_evidence.py --json",
        "deploy/run_real_ops_evidence.py --json",
        "deploy/run_storage_integration_check.py --compact",
        "npx tsc --noEmit --pretty false",
        "npm run build",
    ]

    missing = [
        snippet
        for snippet in required_snippets
        if not any(snippet in command for command in commands)
    ]
    assert missing == []


def test_final_validation_quick_profile_is_safe_for_local_acceptance() -> None:
    steps = select_steps(
        profile="quick",
        categories=[],
        include_frontend_build=False,
    )
    step_ids = {step.id for step in steps}

    assert "frontend_build" not in step_ids
    assert "delivery_agent_contracts" not in step_ids
    assert "task_queue_arq_contracts" in step_ids
    assert "research_archive_contracts" in step_ids
    assert "writing_review_approval_contracts" in step_ids
    assert "model_compare_contracts" in step_ids
    assert "deck_delivery_contracts" in step_ids
    assert "mcp_observability_contracts" in step_ids
    assert "k8s_ops_readiness_contracts" in step_ids
    assert "ops_readiness_summary_contract" in step_ids
    assert "ops_evidence_verifier_contract" in step_ids
    assert "real_ops_evidence_plan_contract" in step_ids
    assert "storage_integration_default_probe" in step_ids

    destructive_fragments = [" rm ", " del ", "Remove-Item", "DROP DATABASE", "delete_collection"]
    commands = [" ".join(step.command) for step in steps]
    assert [
        fragment
        for fragment in destructive_fragments
        if any(fragment in command for command in commands)
    ] == []


def test_final_validation_frontend_build_fails_on_chunk_warning() -> None:
    frontend_build = next(step for step in all_validation_steps() if step.id == "frontend_build")

    assert frontend_build.failure_patterns == ("Some chunks are larger than",)


def test_final_validation_report_output_can_be_truncated_without_losing_status() -> None:
    steps = [
        step
        for step in all_validation_steps()
        if step.id == "implementation_plan_remaining_markers"
    ]

    results = run_steps(steps, fail_fast=False, output_char_limit=1)
    report = build_report(steps=steps, results=results, output_char_limit=1)

    assert report["ok"] is True
    assert report["summary"]["selected"] == 1  # type: ignore[index]
    assert report["summary"]["executed"] == 1  # type: ignore[index]
    assert report["summary"]["passed"] == 1  # type: ignore[index]
    assert report["summary"]["failed"] == 0  # type: ignore[index]
    assert report["output_char_limit"] == 1
    assert results[0]["stdout_original_chars"] >= 1
    assert "output_failures" in results[0]


def test_final_validation_results_summary_counts_status_and_truncation() -> None:
    summary = build_results_summary(
        [
            {
                "id": "passed_step",
                "ok": True,
                "returncode": 0,
                "duration_ms": 10,
                "stdout_truncated": True,
                "stderr_truncated": False,
                "output_failures": [],
            },
            {
                "id": "failed_step",
                "ok": False,
                "returncode": 1,
                "duration_ms": 30,
                "stdout_truncated": False,
                "stderr_truncated": True,
                "output_failures": ["warning"],
            },
        ],
        selected_step_count=3,
        fail_fast=True,
    )

    assert summary == {
        "selected": 3,
        "executed": 2,
        "passed": 1,
        "failed": 1,
        "skipped": 1,
        "truncated": {"steps": 2, "stdout": 1, "stderr": 1, "streams": 2},
        "output_failures": {"steps": 1, "count": 1},
        "returncode_failures": {"steps": 1},
        "fail_fast_stopped": True,
        "duration_ms_total": 40,
        "duration_ms_avg": 20,
        "duration_ms_max": 30,
    }


def test_final_validation_run_step_reports_duration_ms() -> None:
    step = ValidationStep(
        id="synthetic_timing",
        description="Synthetic timing check.",
        command=(sys.executable, "-c", "print('ok')"),
    )

    result = run_step(step)

    assert result["ok"] is True
    assert "duration_ms" in result
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0


def test_final_validation_parallel_run_preserves_step_order() -> None:
    steps = [
        ValidationStep(
            id="slow_first",
            description="Synthetic slow first check.",
            command=(sys.executable, "-c", "import time; time.sleep(0.2); print('first')"),
        ),
        ValidationStep(
            id="fast_second",
            description="Synthetic fast second check.",
            command=(sys.executable, "-c", "print('second')"),
        ),
    ]

    results = run_steps(
        steps,
        fail_fast=False,
        parallel_workers=2,
    )

    assert [result["id"] for result in results] == ["slow_first", "fast_second"]
    assert [result["ok"] for result in results] == [True, True]


def test_final_validation_fail_fast_forces_serial_workers() -> None:
    assert effective_parallel_workers(requested_workers=4, fail_fast=True) == 1
    assert effective_parallel_workers(requested_workers=4, fail_fast=False) == 4


def test_final_validation_report_timing_semantics_for_list_only_and_results() -> None:
    step = ValidationStep(
        id="synthetic_timing",
        description="Synthetic timing report check.",
        command=(sys.executable, "-c", "print('ok')"),
    )

    list_report = build_report(steps=[step], listed_only=True)
    list_summary = list_report["summary"]

    assert list_report["ok"] is True
    assert list_report["listed_only"] is True
    assert "results" not in list_report
    assert list_summary["executed"] == 0  # type: ignore[index]
    assert list_summary["skipped"] == 1  # type: ignore[index]
    assert list_summary["duration_ms_total"] == 0  # type: ignore[index]
    assert list_summary["duration_ms_avg"] == 0  # type: ignore[index]
    assert list_summary["duration_ms_max"] == 0  # type: ignore[index]

    executed_report = build_report(
        steps=[step],
        results=[
            {
                **step.as_dict(),
                "returncode": 0,
                "ok": True,
                "duration_ms": 42,
                "output_failures": [],
                "stdout_truncated": False,
                "stderr_truncated": False,
                "stdout_original_chars": 2,
                "stderr_original_chars": 0,
                "stdout": "ok",
                "stderr": "",
            }
        ],
    )
    executed_summary = executed_report["summary"]

    assert executed_report["ok"] is True
    assert executed_report["listed_only"] is False
    assert executed_summary["executed"] == 1  # type: ignore[index]
    assert executed_summary["skipped"] == 0  # type: ignore[index]
    assert executed_summary["duration_ms_total"] == 42  # type: ignore[index]
    assert executed_summary["duration_ms_avg"] == 42  # type: ignore[index]
    assert executed_summary["duration_ms_max"] == 42  # type: ignore[index]
    assert executed_report["results"][0]["duration_ms"] == 42  # type: ignore[index]


def test_final_validation_human_and_json_reports_include_timing(capfd) -> None:
    step = ValidationStep(
        id="synthetic_timing",
        description="Synthetic timing output check.",
        command=(sys.executable, "-c", "print('ok')"),
    )
    report = build_report(
        steps=[step],
        results=[
            {
                **step.as_dict(),
                "returncode": 0,
                "ok": True,
                "duration_ms": 42,
                "output_failures": [],
                "stdout_truncated": False,
                "stderr_truncated": False,
                "stdout_original_chars": 2,
                "stderr_original_chars": 0,
                "stdout": "ok",
                "stderr": "",
            }
        ],
    )

    _print_human_report(report)
    human = capfd.readouterr().out
    summary_lines = [line for line in human.splitlines() if line.startswith("summary:")]
    step_lines = [line for line in human.splitlines() if "synthetic_timing" in line]

    assert len(summary_lines) == 1
    assert "duration_ms_total=42" in summary_lines[0]
    assert "duration_ms_avg=42" in summary_lines[0]
    assert "duration_ms_max=42" in summary_lines[0]
    assert len(step_lines) == 1
    assert "duration_ms=42" in step_lines[0]
    assert "42 ms" in step_lines[0]

    _print_json_report(report)
    payload = json.loads(capfd.readouterr().out)

    assert payload["summary"]["duration_ms_total"] == 42
    assert payload["summary"]["duration_ms_avg"] == 42
    assert payload["summary"]["duration_ms_max"] == 42
    assert payload["results"][0]["duration_ms"] == 42


def test_final_validation_output_truncation_contract() -> None:
    assert DEFAULT_OUTPUT_CHAR_LIMIT == 4000

    assert _truncate_output("abc", 10) == ("abc", False, 3)
    assert _truncate_output("abcdef", 0) == ("", True, 6)
    assert _truncate_output("abc", None) == ("abc", False, 3)

    truncated, was_truncated, original_chars = _truncate_output("abcdef", 3)
    assert was_truncated is True
    assert original_chars == 6
    assert truncated.endswith("ef")


def test_final_validation_subprocess_env_forces_utf8_python_output() -> None:
    env = _validation_env()

    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    assert env["NO_COLOR"] == "1"
    assert env["FORCE_COLOR"] == "0"
    assert env["TERM"] == "dumb"
    assert str(ROOT) in env["PYTHONPATH"]
    assert str(ROOT / "backend") in env["PYTHONPATH"]


def test_final_validation_env_preserves_existing_pythonpath(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "existing-path")

    env = _validation_env()
    entries = env["PYTHONPATH"].split(os.pathsep)

    assert str(ROOT) in entries
    assert str(ROOT / "backend") in entries
    assert "existing-path" in entries


def test_final_validation_run_step_passes_utf8_env_to_subprocess() -> None:
    step = ValidationStep(
        id="synthetic_utf8_env",
        description="Synthetic UTF-8 subprocess env check.",
        command=(
            sys.executable,
            "-c",
            (
                "import os; "
                "print(os.environ.get('PYTHONIOENCODING')); "
                "print(os.environ.get('PYTHONUTF8')); "
                "print(os.environ.get('NO_COLOR')); "
                "print(os.environ.get('FORCE_COLOR')); "
                "print(os.environ.get('TERM'))"
            ),
        ),
    )

    result = run_step(step)

    assert result["ok"] is True
    assert "utf-8" in str(result["stdout"])
    assert "1" in str(result["stdout"])
    assert "0" in str(result["stdout"])
    assert "dumb" in str(result["stdout"])


def test_final_validation_strips_ansi_sequences_from_report_output() -> None:
    assert _strip_ansi("\x1b[32mPASS\x1b[0m") == "PASS"
    assert _strip_ansi("ok \x1b[1;32mPASS\x1b[0m") == "ok PASS"

    step = ValidationStep(
        id="synthetic_ansi_output",
        description="Synthetic ANSI output check.",
        command=(
            sys.executable,
            "-c",
            "print('\\x1b[31mSome chunks are larger than\\x1b[0m')",
        ),
        failure_patterns=("Some chunks are larger than",),
    )

    result = run_step(step)

    assert result["ok"] is False
    assert result["output_failures"] == ["Some chunks are larger than"]
    assert "\x1b[" not in str(result["stdout"])
    assert "Some chunks are larger than" in str(result["stdout"])


def test_final_validation_failure_patterns_scan_full_output_before_truncation() -> None:
    step = ValidationStep(
        id="synthetic_output_pattern",
        description="Synthetic pattern check.",
        command=(
            sys.executable,
            "-c",
            "print('PATTERN_AT_START:' + 'x' * 200)",
        ),
        failure_patterns=("PATTERN_AT_START",),
    )

    result = run_step(step, output_char_limit=8)

    assert result["ok"] is False
    assert result["output_failures"] == ["PATTERN_AT_START"]
    assert result["stdout_truncated"] is True
    assert "PATTERN_AT_START" not in str(result["stdout"])


def test_validation_doc_references_final_acceptance_entry() -> None:
    content = VALIDATION_DOC.read_text(encoding="utf-8")

    required_snippets = [
        "## Final Acceptance Entry",
        "deploy/run_final_validation.py --profile quick",
        "deploy/run_final_validation.py --profile quick --parallel-workers 4",
        "deploy/run_final_validation.py --profile full --include-frontend-build",
        "deploy/run_final_validation.py --profile quick --verbose-output",
        "deploy/run_final_validation.py --profile full --include-frontend-build --max-output-chars 12000",
        "deploy/run_storage_integration_check.py --compact",
        "summary",
        "selected=",
        "executed=",
        "STORAGE_INTEGRATION_TEST",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_validation_doc_locks_real_ops_evidence_closure_contract() -> None:
    content = VALIDATION_DOC.read_text(encoding="utf-8")

    required_snippets = [
        "### Evidence Closure Verification",
        "deploy/run_real_ops_evidence.py --json",
        "deploy/run_real_ops_evidence.py --json --skip-probes",
        "deploy/run_real_ops_evidence.py --json --report-path runtime/ops-readiness/real-ops/real-ops-evidence-plan.json",
        "deploy/run_real_ops_evidence.py --json --strict-plan --report-path runtime/ops-readiness/real-ops/real-ops-evidence-plan.json",
        "deploy/run_real_ops_evidence.py --json --execute",
        "deploy/run_real_ops_evidence.py --json --execute --strict-plan --strict-verifier --report-path runtime/ops-readiness/real-ops/real-ops-evidence-report.json",
        "--execute",
        "--strict-plan",
        "--strict-verifier",
        "--report-path",
        "--archive-dir",
        "--history-path",
        "--skip-probes",
        "real_environment",
        "dry-run plan",
        "may still persist the plan and report artifacts",
        "without it the runner must remain inert",
        "returns non-zero",
        "blocker",
        "unknown readiness",
        "empty selection",
        "mode",
        "execute",
        "strict_plan",
        "summary",
        "plan",
        "results",
        "verifier",
        "deploy/verify_ops_evidence.py --json --strict",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []
