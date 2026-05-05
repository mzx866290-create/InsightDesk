from __future__ import annotations

import json
from pathlib import Path

from deploy import (
    run_arq_drain_drill,
    run_arq_e2e_smoke,
    run_arq_long_running_validation,
)


ROOT = Path(__file__).resolve().parents[1]
ROOT_COMPOSE_FILE = ROOT / "docker-compose.yml"
COMPOSE_FILE = ROOT / "deploy" / "compose.arq-worker.yml"
ARQ_WORKER_DOCKERFILE = ROOT / "deploy" / "Dockerfile.arq-worker"
PROBE_FILE = ROOT / "deploy" / "arq_e2e_probe.py"
SMOKE_FILE = ROOT / "deploy" / "run_arq_e2e_smoke.py"
DRAIN_FILE = ROOT / "deploy" / "run_arq_drain_drill.py"
LONG_RUNNING_FILE = ROOT / "deploy" / "run_arq_long_running_validation.py"
RUNBOOK_FILE = ROOT / "docs" / "ARQ_WORKER_OPERATIONS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_standalone_arq_worker_compose_locks_runtime_contract() -> None:
    content = _read(COMPOSE_FILE)

    required_snippets = [
        "TASK_BACKEND: arq",
        'TASK_STORE_FAIL_INCOMPLETE_ON_START: "false"',
        "ARQ_QUEUE_NAME: ${ARQ_QUEUE_NAME:-insightdesk:tasks}",
        "ARQ_WORKER_DRAIN_SECONDS: ${ARQ_WORKER_DRAIN_SECONDS:-30}",
        "ARQ_WORKER_HEARTBEAT_KEY: ${ARQ_WORKER_HEARTBEAT_KEY:-insightdesk:tasks:worker:heartbeat}",
        "ARQ_WORKER_HEARTBEAT_SECONDS: ${ARQ_WORKER_HEARTBEAT_SECONDS:-30}",
        "ARQ_WORKER_MAX_JOBS: ${ARQ_WORKER_MAX_JOBS:-4}",
        "ARQ_KEEP_RESULT_SECONDS: ${ARQ_KEEP_RESULT_SECONDS:-3600}",
        "ARQ_RETRY_ATTEMPTS: ${ARQ_RETRY_ATTEMPTS:-3}",
        "ARQ_RETRY_BACKOFF_SECONDS: ${ARQ_RETRY_BACKOFF_SECONDS:-15}",
        "ARQ_QUEUE_WARNING_LENGTH: ${ARQ_QUEUE_WARNING_LENGTH:-100}",
        "dockerfile: deploy/Dockerfile.arq-worker",
        "arq backend.tasks.worker.WorkerSettings",
        "healthcheck:",
        "redis-cli",
        "stop_signal: SIGTERM",
        "stop_grace_period: ${ARQ_WORKER_STOP_GRACE_PERIOD:-45s}",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []

    dockerfile = _read(ARQ_WORKER_DOCKERFILE)
    dockerfile_required = [
        "FROM python:3.12-slim",
        "pip install \"arq>=0.26.0\"",
        "COPY backend ./backend",
        "COPY deploy ./deploy",
        'CMD ["arq", "backend.tasks.worker.WorkerSettings"]',
    ]
    dockerfile_missing = [
        snippet for snippet in dockerfile_required if snippet not in dockerfile
    ]
    assert dockerfile_missing == []


def test_root_arq_worker_compose_preserves_pending_tasks_on_start() -> None:
    content = _read(ROOT_COMPOSE_FILE)

    required_snippets = [
        "worker:",
        "TASK_BACKEND: arq",
        'TASK_STORE_FAIL_INCOMPLETE_ON_START: "false"',
        "arq backend.tasks.worker.WorkerSettings",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_arq_e2e_probe_script_locks_task_probe_contract() -> None:
    content = _read(PROBE_FILE)

    required_snippets = [
        "--mode",
        "enqueue",
        "wait",
        "probe_step_seconds",
        "SQLiteTaskStore",
        "fail_incomplete_on_start=False",
        "enqueue_arq_task",
        "arq_queue_name_from_env",
        "TASK_STORE_FAIL_INCOMPLETE_ON_START",
        "TaskStatus.PENDING",
        "TaskStatus.COMPLETED",
        "task completed",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_arq_drain_drill_script_locks_worker_drain_contract() -> None:
    content = _read(DRAIN_FILE)

    required_snippets = [
        '"docker", "compose"',
        "compose.arq-worker.yml",
        "stop",
        "arq-worker",
        "/app/deploy/arq_e2e_probe.py",
        "--mode",
        "enqueue",
        "wait",
        "--mode enqueue",
        "--mode wait",
        "TASK_ID=",
        "ARQ_WORKER_DRAIN_SECONDS",
        "TASK_STORE_FAIL_INCOMPLETE_ON_START",
        "--json",
        "--report-path",
        "--archive-dir",
        "--history-path",
        "--manifest-path",
        "manifest_path",
        "--docker-start-hint",
        "--skip-if-unavailable",
        "docker_daemon_unavailable",
        "DOCKER_DESKTOP_START_COMMANDS",
        "arq_drain_drill",
        "skipped_no_real_environment",
        "schema_version",
        "archive_ready",
        "archive_path",
        "task_reached_terminal_state",
        "cleanup_completed",
        "closure_decision",
        "drain_closed",
        "drain_incomplete",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_arq_drain_drill_closure_summary_marks_complete_report() -> None:
    report = {
        "id": "arq_drain_drill",
        "ok": True,
        "task_id": "task-1",
        "drain_seconds": 15,
        "blockers": [],
        "steps": [
            {"name": "compose_up", "ok": True},
            {"name": "enqueue_probe", "ok": True},
            {"name": "stop_worker", "ok": True},
            {"name": "wait_for_terminal_task", "ok": True},
        ],
        "closure": {
            "enqueued": True,
            "worker_stopped": True,
            "task_reached_terminal_state": True,
            "cleanup_completed": True,
        },
    }

    run_arq_drain_drill._apply_closure_summary(report)

    assert report["closure"]["complete"] is True
    assert report["closure"]["decision"] == "drain_closed"
    assert report["closure"]["missing"] == []
    assert report["closure"]["evidence"]["task_id"] == "task-1"
    assert report["closure"]["evidence"]["failed_steps"] == []


def test_arq_drain_drill_closure_summary_names_missing_steps() -> None:
    report = {
        "id": "arq_drain_drill",
        "ok": False,
        "task_id": "task-2",
        "drain_seconds": 15,
        "blockers": ["docker_daemon_unavailable"],
        "steps": [{"name": "compose_up", "ok": False}],
        "closure": {
            "enqueued": False,
            "worker_stopped": False,
            "task_reached_terminal_state": False,
            "cleanup_completed": False,
        },
    }

    run_arq_drain_drill._apply_closure_summary(report)

    assert report["closure"]["complete"] is False
    assert report["closure"]["decision"] == "drain_incomplete"
    assert report["closure"]["missing"] == [
        "enqueued",
        "worker_stopped",
        "task_reached_terminal_state",
        "cleanup_completed",
    ]
    assert report["closure"]["evidence"]["failed_steps"] == ["compose_up"]
    assert report["closure"]["evidence"]["blockers"] == ["docker_daemon_unavailable"]


def test_arq_long_running_validation_is_env_gated() -> None:
    content = _read(LONG_RUNNING_FILE)

    required_snippets = [
        "ARQ_LONG_RUNNING_TEST",
        "run_long_running_validation",
        "compose.arq-worker.yml",
        "/app/deploy/arq_e2e_probe.py",
        "--duration-seconds",
        "--max-iterations",
        "--json",
        "--report-path",
        "--archive-dir",
        "--history-path",
        "--manifest-path",
        "manifest_path",
        "--docker-start-hint",
        "--skip-if-unavailable",
        "docker_daemon_unavailable",
        "skipped_no_real_environment",
        "long_running_validation_passed",
        "long_running_validation_failed",
        "completed_iterations",
        "schema_version",
        "archive_ready",
        "TASK_STORE_FAIL_INCOMPLETE_ON_START=false",
        "TASK_BACKEND=arq",
        "docker engine is not available",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_arq_e2e_smoke_script_runs_worker_stack_and_probe() -> None:
    content = _read(SMOKE_FILE)

    required_snippets = [
        '"docker", "compose"',
        "compose.arq-worker.yml",
        "redis",
        "arq-worker",
        "/app/deploy/arq_e2e_probe.py",
        "TASK_STORE_FAIL_INCOMPLETE_ON_START",
        "false",
        "--report-path",
        "--archive-dir",
        "--history-path",
        "--manifest-path",
        "manifest_path",
        "--docker-start-hint",
        "--skip-if-unavailable",
        "docker_daemon_unavailable",
        "skipped_no_real_environment",
        "smoke_passed",
        "smoke_failed",
        "schema_version",
        "archive_ready",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_arq_scripts_write_evidence_manifest_entries(tmp_path: Path) -> None:
    manifest_path = tmp_path / "evidence-manifest.json"

    smoke_report = {
        "id": "arq_long_running_smoke",
        "ok": True,
        "skipped": False,
        "exit_code": 0,
        "started_at": 1.0,
        "finished_at": 2.0,
        "blockers": [],
    }
    run_arq_e2e_smoke._emit_report(
        smoke_report,
        json_output=False,
        report_path=str(tmp_path / "smoke.json"),
        archive_dir=str(tmp_path / "archive"),
        history_path=str(tmp_path / "history.json"),
        manifest_path=str(manifest_path),
    )

    long_report = {
        "id": "arq_long_running_validation",
        "ok": True,
        "skipped": False,
        "exit_code": 0,
        "started_at": 3.0,
        "finished_at": 4.0,
        "duration_seconds": 10,
        "max_iterations": 1,
        "iterations": [{"index": 1, "ok": True}],
        "blockers": [],
    }
    run_arq_long_running_validation._emit_report(
        long_report,
        json_output=False,
        report_path=str(tmp_path / "long.json"),
        archive_dir=str(tmp_path / "archive"),
        history_path=str(tmp_path / "history.json"),
        manifest_path=str(manifest_path),
    )

    drain_report = {
        "id": "arq_drain_drill",
        "ok": False,
        "skipped": True,
        "exit_code": 0,
        "started_at": 5.0,
        "finished_at": 6.0,
        "task_id": "",
        "drain_seconds": 15,
        "steps": [],
        "blockers": ["docker_daemon_unavailable"],
        "closure": {
            "enqueued": False,
            "worker_stopped": False,
            "task_reached_terminal_state": False,
            "cleanup_completed": False,
        },
    }
    run_arq_drain_drill._emit_report(
        drain_report,
        json_output=False,
        report_path=str(tmp_path / "drain.json"),
        archive_dir=str(tmp_path / "archive"),
        history_path=str(tmp_path / "history.json"),
        manifest_path=str(manifest_path),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["updated_at"], str)
    assert set(manifest["reports"]) >= {
        "arq_long_running_smoke",
        "arq_long_running_validation",
        "arq_drain_drill",
    }
    for report_id, report in (
        ("arq_long_running_smoke", smoke_report),
        ("arq_long_running_validation", long_report),
        ("arq_drain_drill", drain_report),
    ):
        entry = manifest["reports"][report_id]
        assert entry["id"] == report_id
        assert entry["ok"] is bool(report["ok"])
        assert entry["skipped"] is bool(report["skipped"])
        assert entry["decision"]
        assert entry["status"] == entry["decision"]
        assert entry["report_path"]
        assert entry["archive_path"]
        assert entry["history_path"]
        assert entry["blockers"] == report["blockers"]
        assert entry["finished_at"] == report["finished_at"]
        assert report["evidence"]["manifest_path"] == str(manifest_path)


def test_arq_worker_runbook_documents_drain_and_health_drill() -> None:
    content = _read(RUNBOOK_FILE)

    required_snippets = [
        "TASK_BACKEND=arq",
        "ARQ_QUEUE_NAME=insightdesk:tasks",
        "ARQ_WORKER_DRAIN_SECONDS=30",
        "ARQ_WORKER_HEARTBEAT_SECONDS=30",
        "docker compose -f deploy/compose.arq-worker.yml up --build -d redis arq-worker",
        "curl \"http://localhost:8000/api/tasks?limit=20\"",
        "health.runtime.backend",
        "health.queue.heartbeat.present",
        "Graceful Shutdown Drill",
        "python deploy/run_arq_drain_drill.py --timeout-seconds 120",
        "python deploy/run_arq_drain_drill.py --timeout-seconds 120 --json --report-path runtime/ops-readiness/arq/arq-drain-drill.json",
        "python deploy/run_arq_long_running_validation.py --duration-seconds 900 --json --report-path runtime/ops-readiness/arq/arq-long-running-validation.json",
        "python deploy/run_arq_e2e_smoke.py --timeout-seconds 90 --json --report-path runtime/ops-readiness/arq/arq-long-running-smoke.json",
        "ARQ_LONG_RUNNING_TEST=1",
        "Docker daemon must be running",
        "docker_daemon_unavailable",
        "summary.arq_report_paths",
        "docker compose -f deploy/compose.arq-worker.yml stop arq-worker",
        "Do not change `ARQ_QUEUE_NAME` during a drain.",
        "Default Backend Switch Contract",
        "TASK_BACKEND_SWITCH_READY=1",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []
