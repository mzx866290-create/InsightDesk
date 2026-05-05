from threading import Lock

from backend.core.runtime_metrics import (
    aggregate_runtime_metrics_snapshots,
    new_llm_metrics_state,
    new_runtime_metrics_state,
    record_llm_call,
    record_runtime_request,
    runtime_llm_metrics_payload,
    runtime_operations_summary_payload,
    runtime_prometheus_metrics_text,
    runtime_request_metrics_payload,
)


def test_runtime_prometheus_metrics_includes_task_snapshot_and_backend():
    metrics_state = new_runtime_metrics_state()
    lock = Lock()
    record_runtime_request(
        metrics_state,
        lock,
        status_code=202,
        timestamp=1234.5,
    )
    request_metrics = runtime_request_metrics_payload(metrics_state, lock)

    body = runtime_prometheus_metrics_text(
        request_metrics=request_metrics,
        task_summary={
            "in_memory_total": 4,
            "pending": 1,
            "running": 1,
            "waiting_approval": 1,
            "completed": 1,
            "failed": 0,
            "latest_task_updated_at": 1300.25,
            "health": {
                "summary": {
                    "warning_count": 2,
                    "warning_codes": ["task_pending_stale", "arq_queue_backlog"],
                }
            },
        },
        uptime_seconds=12.5,
        task_backend='sqlite"local',
    )

    assert "insightdesk_http_recent_errors 0" in body
    assert "insightdesk_http_last_request_timestamp_seconds 1234.5" in body
    assert 'insightdesk_task_queue_backend{backend="sqlite\\"local"} 1' in body
    assert 'insightdesk_tasks_by_status{status="waiting_approval"} 1' in body
    assert "insightdesk_tasks_latest_updated_timestamp_seconds 1300.25" in body
    assert 'insightdesk_task_queue_health{code="task_pending_stale"} 1' in body
    assert 'insightdesk_task_queue_health{code="arq_queue_backlog"} 1' in body


def test_runtime_llm_metrics_payload_groups_by_model():
    metrics_state = new_llm_metrics_state()
    lock = Lock()

    record_llm_call(
        provider="openrouter",
        model="qwen",
        status="success",
        latency_seconds=1.25,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        timestamp=2000,
        metrics=metrics_state,
        lock=lock,
    )
    record_llm_call(
        provider="openrouter",
        model="qwen",
        status="timeout",
        latency_seconds=0.5,
        timestamp=2001,
        metrics=metrics_state,
        lock=lock,
    )

    payload = runtime_llm_metrics_payload(metrics_state, lock)

    assert payload["total_calls"] == 2
    assert payload["total_errors"] == 1
    assert payload["total_timeouts"] == 1
    assert payload["total_latency_seconds"] == 1.75
    assert payload["total_tokens"] == 30
    assert payload["last_call_at"] == 2001
    assert payload["last_error_at"] == 2001
    assert payload["by_model"] == [
        {
            "provider": "openrouter",
            "model": "qwen",
            "total_calls": 2,
            "total_errors": 1,
            "total_timeouts": 1,
            "total_latency_seconds": 1.75,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }
    ]


def test_runtime_operations_summary_reports_rates_and_alerts():
    summary = runtime_operations_summary_payload(
        request_metrics={
            "total_requests": 100,
            "total_errors": 8,
            "by_status_class": {},
        },
        task_summary={"pending": 2, "running": 1},
        uptime_seconds=120,
        llm_metrics={"total_calls": 10, "total_errors": 1},
    )

    assert summary["health_status"] == "warning"
    assert summary["error_rate"] == 0.08
    assert summary["requests_per_minute"] == 50.0
    assert summary["active_tasks"] == 3
    assert summary["llm_error_rate"] == 0.1
    assert summary["alert_count"] == 3
    assert [alert["code"] for alert in summary["alerts"]] == [
        "runtime_http_error_rate",
        "runtime_llm_error_rate",
        "runtime_tasks_active",
    ]


def test_runtime_operations_summary_reports_task_health_alerts():
    summary = runtime_operations_summary_payload(
        request_metrics={
            "total_requests": 10,
            "total_errors": 0,
            "by_status_class": {},
        },
        task_summary={
            "pending": 0,
            "running": 0,
            "health": {
                "summary": {
                    "warning_count": 1,
                    "warning_codes": ["arq_worker_heartbeat_missing"],
                }
            },
        },
        uptime_seconds=60,
    )

    assert summary["health_status"] == "warning"
    assert summary["alert_count"] == 1
    assert summary["alerts"][0]["code"] == "runtime_task_queue_health"


def test_runtime_prometheus_metrics_includes_llm_snapshot():
    metrics_state = new_runtime_metrics_state()
    lock = Lock()
    request_metrics = runtime_request_metrics_payload(metrics_state, lock)
    llm_state = new_llm_metrics_state()
    llm_lock = Lock()
    record_llm_call(
        provider='openrouter"test',
        model="qwen",
        status="success",
        latency_seconds=0.25,
        prompt_tokens=4,
        completion_tokens=6,
        total_tokens=10,
        metrics=llm_state,
        lock=llm_lock,
    )

    body = runtime_prometheus_metrics_text(
        request_metrics=request_metrics,
        task_summary={"in_memory_total": 0},
        uptime_seconds=1,
        llm_metrics=runtime_llm_metrics_payload(llm_state, llm_lock),
        operations_summary={
            "health_status": "ok",
            "error_rate": 0.0,
            "requests_per_minute": 12.5,
            "active_tasks": 2,
            "llm_error_rate": 0.25,
            "alert_count": 0,
        },
    )

    assert "insightdesk_llm_calls_total 1" in body
    assert "insightdesk_llm_tokens_total 10" in body
    assert 'insightdesk_llm_calls_by_model_total{model="qwen",provider="openrouter\\"test"} 1' in body
    assert 'insightdesk_llm_tokens_by_model_total{model="qwen",provider="openrouter\\"test"} 10' in body
    assert 'insightdesk_operations_health_status{status="ok"} 1' in body
    assert "insightdesk_operations_requests_per_minute 12.5" in body
    assert "insightdesk_operations_active_tasks 2" in body
    assert "insightdesk_operations_llm_error_rate 0.25" in body


def test_aggregate_runtime_metrics_snapshots_keeps_process_nodes():
    payload = aggregate_runtime_metrics_snapshots(
        [
            {
                "source": "api-1",
                "process_id": "pid-api",
                "request_metrics": {
                    "total_requests": 10,
                    "total_errors": 1,
                    "by_status_class": {"2xx": 9, "5xx": 1},
                    "last_request_at": 100,
                    "last_error_at": 99,
                },
            },
            {
                "source": "worker-1",
                "process_id": "pid-worker",
                "total_requests": 5,
                "total_errors": 0,
                "by_status_class": {"2xx": 5},
                "last_request_at": 110,
            },
        ]
    )

    assert payload["summary"]["node_count"] == 2
    assert payload["summary"]["total_requests"] == 15
    assert payload["summary"]["total_errors"] == 1
    assert payload["summary"]["error_rate"] == 0.066667
    assert payload["summary"]["by_status_class"]["2xx"] == 14
    assert payload["summary"]["by_status_class"]["5xx"] == 1
    assert payload["summary"]["last_request_at"] == 110
    assert payload["summary"]["last_error_at"] == 99
    assert payload["nodes"][1]["source"] == "worker-1"
    assert payload["nodes"][1]["process_id"] == "pid-worker"
