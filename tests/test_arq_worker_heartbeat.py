import asyncio
import importlib
import sys
import types

import pytest

from backend.tasks.registry import (
    DEFAULT_ARQ_QUEUE_WARNING_LENGTH,
    DEFAULT_ARQ_PENDING_STALE_SECONDS,
    DEFAULT_ARQ_RUNNING_STALE_SECONDS,
    DEFAULT_ARQ_RETRY_ATTEMPTS,
    DEFAULT_ARQ_RETRY_BACKOFF_SECONDS,
    DEFAULT_ARQ_WORKER_HEARTBEAT_KEY,
    DEFAULT_ARQ_WORKER_HEARTBEAT_SECONDS,
    DEFAULT_ARQ_WORKER_DRAIN_SECONDS,
    arq_pending_stale_seconds_from_env,
    arq_queue_health_payload,
    arq_queue_warning_length_from_env,
    arq_retry_attempts_from_env,
    arq_retry_backoff_seconds_from_env,
    arq_retry_config_from_env,
    arq_retry_defer_seconds_from_env,
    arq_retry_runtime_settings_from_env,
    arq_running_stale_seconds_from_env,
    arq_runtime_config_payload,
    arq_should_retry_failed_task,
    arq_should_start_task_record,
    arq_task_stale_thresholds_from_env,
    arq_worker_drain_config_from_env,
    arq_worker_drain_seconds_from_env,
    arq_worker_drain_settings_from_env,
    arq_worker_heartbeat_key_from_env,
    arq_worker_heartbeat_seconds_from_env,
    arq_worker_heartbeat_settings_from_env,
    arq_worker_heartbeat_ttl_seconds,
    arq_worker_runtime_settings_from_env,
    build_arq_worker_heartbeat_key,
)
from backend.stores.task_store import TaskRecord, TaskStatus


def test_arq_worker_heartbeat_uses_generated_defaults(monkeypatch):
    monkeypatch.delenv("ARQ_WORKER_HEARTBEAT_KEY", raising=False)
    monkeypatch.delenv("ARQ_WORKER_HEARTBEAT_SECONDS", raising=False)

    assert DEFAULT_ARQ_WORKER_HEARTBEAT_KEY == "insightdesk:tasks:worker:heartbeat"
    assert DEFAULT_ARQ_WORKER_HEARTBEAT_SECONDS == 30
    assert build_arq_worker_heartbeat_key("custom:tasks") == "custom:tasks:worker:heartbeat"
    assert arq_worker_heartbeat_key_from_env() == "insightdesk:tasks:worker:heartbeat"
    assert arq_worker_heartbeat_seconds_from_env() == 30
    assert arq_worker_heartbeat_ttl_seconds(30) == 31
    assert arq_worker_heartbeat_settings_from_env() == {
        "health_check_interval": 30,
        "health_check_key": "insightdesk:tasks:worker:heartbeat",
    }


def test_arq_worker_heartbeat_env_overrides_key_and_interval(monkeypatch):
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_KEY", "ops:worker:heartbeat")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "45")

    assert arq_worker_heartbeat_key_from_env(queue_name="ignored:queue") == "ops:worker:heartbeat"
    assert arq_worker_heartbeat_seconds_from_env() == 45
    assert arq_worker_heartbeat_ttl_seconds(45) == 46
    assert arq_worker_heartbeat_settings_from_env(queue_name="ignored:queue") == {
        "health_check_interval": 45,
        "health_check_key": "ops:worker:heartbeat",
    }


def test_arq_worker_heartbeat_can_disable_custom_settings(monkeypatch):
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "0")
    monkeypatch.delenv("ARQ_WORKER_HEARTBEAT_KEY", raising=False)
    assert arq_worker_heartbeat_settings_from_env() == {}
    assert arq_worker_heartbeat_ttl_seconds(0) == 0

    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "30")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_KEY", "disabled")
    assert arq_worker_heartbeat_key_from_env() == ""
    assert arq_worker_heartbeat_settings_from_env() == {}


def test_arq_worker_heartbeat_rejects_invalid_interval(monkeypatch):
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "-1")
    with pytest.raises(ValueError, match="ARQ_WORKER_HEARTBEAT_SECONDS"):
        arq_worker_heartbeat_seconds_from_env()

    with pytest.raises(ValueError, match="heartbeat_seconds"):
        arq_worker_heartbeat_ttl_seconds(-1)


def test_arq_task_stale_thresholds_use_defaults_overrides_and_disabled(monkeypatch):
    monkeypatch.delenv("ARQ_PENDING_STALE_SECONDS", raising=False)
    monkeypatch.delenv("ARQ_RUNNING_STALE_SECONDS", raising=False)

    assert DEFAULT_ARQ_PENDING_STALE_SECONDS == 600
    assert DEFAULT_ARQ_RUNNING_STALE_SECONDS == 1800
    assert arq_pending_stale_seconds_from_env() == 600
    assert arq_running_stale_seconds_from_env() == 1800
    assert arq_task_stale_thresholds_from_env() == {
        "pending_stale_seconds": 600,
        "running_stale_seconds": 1800,
    }

    monkeypatch.setenv("ARQ_PENDING_STALE_SECONDS", "120")
    monkeypatch.setenv("ARQ_RUNNING_STALE_SECONDS", "240")
    assert arq_task_stale_thresholds_from_env() == {
        "pending_stale_seconds": 120,
        "running_stale_seconds": 240,
    }

    monkeypatch.setenv("ARQ_PENDING_STALE_SECONDS", "disabled")
    monkeypatch.setenv("ARQ_RUNNING_STALE_SECONDS", "0")
    assert arq_task_stale_thresholds_from_env() == {
        "pending_stale_seconds": 0,
        "running_stale_seconds": 0,
    }


def test_arq_task_stale_thresholds_reject_invalid_values(monkeypatch):
    monkeypatch.setenv("ARQ_PENDING_STALE_SECONDS", "-1")
    with pytest.raises(ValueError, match="ARQ_PENDING_STALE_SECONDS"):
        arq_pending_stale_seconds_from_env()

    monkeypatch.setenv("ARQ_RUNNING_STALE_SECONDS", "abc")
    with pytest.raises(ValueError, match="ARQ_RUNNING_STALE_SECONDS"):
        arq_running_stale_seconds_from_env()


def test_arq_queue_warning_length_uses_default_override_and_disabled(monkeypatch):
    monkeypatch.delenv("ARQ_QUEUE_WARNING_LENGTH", raising=False)
    assert DEFAULT_ARQ_QUEUE_WARNING_LENGTH == 100
    assert arq_queue_warning_length_from_env() == 100

    monkeypatch.setenv("ARQ_QUEUE_WARNING_LENGTH", "25")
    assert arq_queue_warning_length_from_env() == 25

    monkeypatch.setenv("ARQ_QUEUE_WARNING_LENGTH", "disabled")
    assert arq_queue_warning_length_from_env() == 0


def test_arq_queue_warning_length_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("ARQ_QUEUE_WARNING_LENGTH", "-1")
    with pytest.raises(ValueError, match="ARQ_QUEUE_WARNING_LENGTH"):
        arq_queue_warning_length_from_env()


def test_arq_retry_and_drain_config_use_defaults_overrides_and_disabled(monkeypatch):
    monkeypatch.delenv("ARQ_RETRY_ATTEMPTS", raising=False)
    monkeypatch.delenv("ARQ_RETRY_BACKOFF_SECONDS", raising=False)
    monkeypatch.delenv("ARQ_WORKER_DRAIN_SECONDS", raising=False)

    assert DEFAULT_ARQ_RETRY_ATTEMPTS == 3
    assert DEFAULT_ARQ_RETRY_BACKOFF_SECONDS == 15
    assert DEFAULT_ARQ_WORKER_DRAIN_SECONDS == 30
    assert arq_retry_attempts_from_env() == 3
    assert arq_retry_backoff_seconds_from_env() == 15
    assert arq_retry_config_from_env() == {
        "enabled": True,
        "attempts": 3,
        "max_retries": 2,
        "backoff_seconds": 15,
        "strategy": "fixed",
    }
    assert arq_retry_runtime_settings_from_env() == {
        "max_tries": 3,
        "retry_jobs": True,
    }
    assert arq_retry_defer_seconds_from_env() == 15
    assert arq_worker_drain_seconds_from_env() == 30
    assert arq_worker_drain_config_from_env() == {
        "enabled": True,
        "graceful_shutdown": True,
        "drain_seconds": 30,
        "job_completion_wait_seconds": 30,
    }
    assert arq_worker_drain_settings_from_env() == {"job_completion_wait": 30}

    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("ARQ_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("ARQ_WORKER_DRAIN_SECONDS", "disabled")
    assert arq_retry_config_from_env() == {
        "enabled": False,
        "attempts": 1,
        "max_retries": 0,
        "backoff_seconds": 0,
        "strategy": "none",
    }
    assert arq_retry_runtime_settings_from_env() == {
        "max_tries": 1,
        "retry_jobs": False,
    }
    assert arq_retry_defer_seconds_from_env() == 0
    assert arq_worker_drain_config_from_env()["enabled"] is False
    assert arq_worker_drain_settings_from_env() == {"job_completion_wait": 0}


def test_arq_retry_policy_decides_failed_record_retries(monkeypatch):
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "3")
    monkeypatch.setenv("ARQ_RETRY_BACKOFF_SECONDS", "10")

    assert arq_should_retry_failed_task(status=TaskStatus.FAILED, job_try=1) is True
    assert arq_should_retry_failed_task(status=TaskStatus.FAILED, job_try=2) is True
    assert arq_should_retry_failed_task(status=TaskStatus.FAILED, job_try=3) is False
    assert arq_should_retry_failed_task(status=TaskStatus.COMPLETED, job_try=1) is False

    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "1")
    assert arq_should_retry_failed_task(status=TaskStatus.FAILED, job_try=1) is False


def test_arq_worker_start_policy_skips_duplicate_or_terminal_deliveries(monkeypatch):
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "3")

    assert arq_should_start_task_record(status=TaskStatus.PENDING, job_try=1) is True
    assert arq_should_start_task_record(status=TaskStatus.RUNNING, job_try=1) is False
    assert arq_should_start_task_record(status=TaskStatus.COMPLETED, job_try=1) is False
    assert arq_should_start_task_record(status=TaskStatus.WAITING_APPROVAL, job_try=1) is False
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=1) is False
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=2) is True
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=3) is True
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=4) is False

    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "1")
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=2) is False


def test_arq_retry_and_drain_config_reject_invalid_values(monkeypatch):
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "-1")
    with pytest.raises(ValueError, match="ARQ_RETRY_ATTEMPTS"):
        arq_retry_attempts_from_env()

    monkeypatch.setenv("ARQ_RETRY_BACKOFF_SECONDS", "-1")
    with pytest.raises(ValueError, match="ARQ_RETRY_BACKOFF_SECONDS"):
        arq_retry_backoff_seconds_from_env()

    monkeypatch.setenv("ARQ_WORKER_DRAIN_SECONDS", "-1")
    with pytest.raises(ValueError, match="ARQ_WORKER_DRAIN_SECONDS"):
        arq_worker_drain_seconds_from_env()


def test_arq_runtime_config_payload_exposes_retry_heartbeat_and_drain(monkeypatch):
    monkeypatch.setenv("ARQ_QUEUE_NAME", "ops:tasks")
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "4")
    monkeypatch.setenv("ARQ_RETRY_BACKOFF_SECONDS", "20")
    monkeypatch.setenv("ARQ_WORKER_DRAIN_SECONDS", "45")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "10")
    monkeypatch.delenv("ARQ_WORKER_HEARTBEAT_KEY", raising=False)

    payload = arq_runtime_config_payload()

    assert payload["backend"] == "arq"
    assert payload["queue_name"] == "ops:tasks"
    assert payload["retry"] == {
        "enabled": True,
        "attempts": 4,
        "max_retries": 3,
        "backoff_seconds": 20,
        "strategy": "fixed",
    }
    assert payload["worker"]["heartbeat"] == {
        "enabled": True,
        "key": "ops:tasks:worker:heartbeat",
        "interval_seconds": 10,
        "expected_ttl_seconds": 11,
    }
    assert payload["worker"]["drain"]["job_completion_wait_seconds"] == 45


def test_arq_worker_runtime_settings_expose_startup_semantics(monkeypatch):
    monkeypatch.setenv("ARQ_WORKER_MAX_JOBS", "6")
    monkeypatch.setenv("ARQ_KEEP_RESULT_SECONDS", "120")
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "4")
    monkeypatch.setenv("ARQ_WORKER_DRAIN_SECONDS", "18")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "9")
    monkeypatch.delenv("ARQ_WORKER_HEARTBEAT_KEY", raising=False)

    assert arq_worker_runtime_settings_from_env(queue_name="ops:tasks") == {
        "max_jobs": 6,
        "keep_result": 120,
        "max_tries": 4,
        "retry_jobs": True,
        "job_completion_wait": 18,
        "health_check_interval": 9,
        "health_check_key": "ops:tasks:worker:heartbeat",
    }


def test_arq_queue_health_payload_reads_queue_length_and_heartbeat():
    class FakeRedis:
        async def zcard(self, key):
            assert key == "ops:tasks"
            return 42

        async def exists(self, key):
            assert key == "ops:tasks:worker:heartbeat"
            return 1

        async def ttl(self, key):
            assert key == "ops:tasks:worker:heartbeat"
            return 9

    payload = asyncio.run(
        arq_queue_health_payload(
            redis=FakeRedis(),
            queue_name="ops:tasks",
            warning_length=100,
            heartbeat_key="ops:tasks:worker:heartbeat",
            heartbeat_seconds=12,
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue_name"] == "ops:tasks"
    assert payload["length"] == 42
    assert payload["warning_count"] == 0
    assert payload["heartbeat"] == {
        "enabled": True,
        "key": "ops:tasks:worker:heartbeat",
        "ttl_seconds": 9,
        "present": True,
        "expected_ttl_seconds": 13,
    }


def test_arq_queue_health_payload_warns_for_backlog_and_missing_heartbeat():
    class FakeRedis:
        def zcard(self, key):
            return 101

        def exists(self, key):
            return 0

        def ttl(self, key):
            return -2

    payload = asyncio.run(
        arq_queue_health_payload(
            redis=FakeRedis(),
            queue_name="ops:tasks",
            warning_length=100,
            heartbeat_key="ops:tasks:worker:heartbeat",
            heartbeat_seconds=30,
        )
    )

    assert payload["status"] == "warning"
    assert payload["length"] == 101
    assert payload["warning_count"] == 2
    assert payload["warnings"] == [
        "arq_queue_backlog",
        "arq_worker_heartbeat_missing",
    ]
    assert payload["heartbeat"]["present"] is False


def test_worker_settings_exposes_arq_health_check_settings(monkeypatch):
    fake_arq = types.ModuleType("arq")
    fake_connections = types.ModuleType("arq.connections")

    class FakeRedisSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        @classmethod
        def from_dsn(cls, dsn):
            return cls(dsn=dsn)

        @classmethod
        def from_dsn(cls, dsn):
            return cls(dsn=dsn)

    fake_connections.RedisSettings = FakeRedisSettings
    fake_arq.connections = fake_connections
    monkeypatch.setitem(sys.modules, "arq", fake_arq)
    monkeypatch.setitem(sys.modules, "arq.connections", fake_connections)
    monkeypatch.setenv("ARQ_QUEUE_NAME", "ops:tasks")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_KEY", "ops:tasks:heartbeat")
    monkeypatch.setenv("ARQ_WORKER_HEARTBEAT_SECONDS", "12")
    monkeypatch.setenv("ARQ_PENDING_STALE_SECONDS", "90")
    monkeypatch.setenv("ARQ_RUNNING_STALE_SECONDS", "900")
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("ARQ_WORKER_DRAIN_SECONDS", "21")

    previous_worker_module = sys.modules.pop("backend.tasks.worker", None)
    try:
        worker = importlib.import_module("backend.tasks.worker")
        assert worker.WorkerSettings.queue_name == "ops:tasks"
        assert worker.WorkerSettings.max_tries == 5
        assert worker.WorkerSettings.retry_jobs is True
        assert worker.WorkerSettings.job_completion_wait == 21
        assert worker.WorkerSettings.health_check_key == "ops:tasks:heartbeat"
        assert worker.WorkerSettings.health_check_interval == 12
        assert worker.WorkerSettings.task_pending_stale_seconds == 90
        assert worker.WorkerSettings.task_running_stale_seconds == 900
    finally:
        sys.modules.pop("backend.tasks.worker", None)
        if previous_worker_module is not None:
            sys.modules["backend.tasks.worker"] = previous_worker_module


def test_run_task_by_id_requeues_failed_record_with_fixed_backoff(monkeypatch):
    fake_arq = types.ModuleType("arq")
    fake_connections = types.ModuleType("arq.connections")

    class FakeRetry(Exception):
        def __init__(self, defer=None):
            super().__init__(f"retry:{defer}")
            self.defer = defer

    class FakeRedisSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_arq.Retry = FakeRetry
    fake_connections.RedisSettings = FakeRedisSettings
    fake_arq.connections = fake_connections
    monkeypatch.setitem(sys.modules, "arq", fake_arq)
    monkeypatch.setitem(sys.modules, "arq.connections", fake_connections)
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "3")
    monkeypatch.setenv("ARQ_RETRY_BACKOFF_SECONDS", "17")

    record = TaskRecord(
        task_id="task-1",
        task_type="web_research",
        status=TaskStatus.PENDING,
        params={},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )

    class FakeTaskStore:
        def get(self, task_id):
            assert task_id == "task-1"
            return record

    fake_api_server = types.ModuleType("backend.api_server")
    fake_api_server._get_task_store = lambda: FakeTaskStore()

    async def fake_run_task(task_record):
        task_record.status = TaskStatus.FAILED

    fake_api_server._run_task = fake_run_task
    previous_api_server_module = sys.modules.get("backend.api_server")
    monkeypatch.setitem(sys.modules, "backend.api_server", fake_api_server)

    previous_worker_module = sys.modules.pop("backend.tasks.worker", None)
    try:
        worker = importlib.import_module("backend.tasks.worker")
        with pytest.raises(FakeRetry) as exc_info:
            asyncio.run(worker.run_task_by_id({"job_try": 1}, "task-1"))
        assert exc_info.value.defer == 17
    finally:
        sys.modules.pop("backend.tasks.worker", None)
        if previous_worker_module is not None:
            sys.modules["backend.tasks.worker"] = previous_worker_module
        sys.modules.pop("backend.api_server", None)
        if previous_api_server_module is not None:
            sys.modules["backend.api_server"] = previous_api_server_module


def test_run_task_by_id_skips_completed_duplicate_delivery(monkeypatch):
    fake_arq = types.ModuleType("arq")
    fake_connections = types.ModuleType("arq.connections")

    class FakeRedisSettings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_connections.RedisSettings = FakeRedisSettings
    fake_arq.connections = fake_connections
    monkeypatch.setitem(sys.modules, "arq", fake_arq)
    monkeypatch.setitem(sys.modules, "arq.connections", fake_connections)

    record = TaskRecord(
        task_id="task-1",
        task_type="web_research",
        status=TaskStatus.COMPLETED,
        params={},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    run_calls: list[str] = []

    class FakeTaskStore:
        def get(self, task_id):
            assert task_id == "task-1"
            return record

    fake_api_server = types.ModuleType("backend.api_server")
    fake_api_server._get_task_store = lambda: FakeTaskStore()

    async def fake_run_task(task_record):
        run_calls.append(task_record.task_id)

    fake_api_server._run_task = fake_run_task
    previous_api_server_module = sys.modules.get("backend.api_server")
    monkeypatch.setitem(sys.modules, "backend.api_server", fake_api_server)

    previous_worker_module = sys.modules.pop("backend.tasks.worker", None)
    try:
        worker = importlib.import_module("backend.tasks.worker")
        asyncio.run(worker.run_task_by_id({"job_try": 1}, "task-1"))
        assert run_calls == []
    finally:
        sys.modules.pop("backend.tasks.worker", None)
        if previous_worker_module is not None:
            sys.modules["backend.tasks.worker"] = previous_worker_module
        sys.modules.pop("backend.api_server", None)
        if previous_api_server_module is not None:
            sys.modules["backend.api_server"] = previous_api_server_module
