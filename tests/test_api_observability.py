from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.core.tracing import reset_trace_events, trace_span


def test_health_endpoint_returns_request_trace_headers():
    client = TestClient(api_server.app)

    response = client.get("/api/health", headers={"X-Request-ID": "req-health-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-health-123"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_kubernetes_probe_endpoints_return_lightweight_json():
    client = TestClient(api_server.app)

    health_response = client.get("/healthz")
    ready_response = client.get("/readyz")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert "timestamp" in health_response.json()

    assert ready_response.status_code == 200
    ready_payload = ready_response.json()
    assert ready_payload["status"] == "ok"
    assert ready_payload["checks"] == {
        "config": "ok",
        "runtime": "ok",
    }
    assert "timestamp" in ready_payload


def test_operations_runtime_includes_operations_summary():
    client = TestClient(api_server.app)

    response = client.get("/api/operations/runtime")

    assert response.status_code == 200
    payload = response.json()
    summary = payload["operations_summary"]
    task_summary = payload["task_summary"]
    assert summary["health_status"] in {"ok", "warning"}
    assert summary["active_tasks"] == task_summary["pending"] + task_summary["running"]
    assert summary["alert_count"] == len(summary["alerts"])
    assert summary["error_rate"] >= 0
    assert summary["requests_per_minute"] >= 0
    assert summary["llm_error_rate"] >= 0


def test_operations_metrics_exposes_operations_summary_samples():
    client = TestClient(api_server.app)

    response = client.get("/api/operations/metrics")

    assert response.status_code == 200
    body = response.text
    assert "insightdesk_operations_health_status" in body
    assert "insightdesk_operations_error_rate" in body
    assert "insightdesk_operations_requests_per_minute" in body
    assert "insightdesk_operations_active_tasks" in body
    assert "insightdesk_operations_llm_error_rate" in body
    assert "insightdesk_operations_alerts" in body


def test_operations_trace_endpoints_return_and_clear_recent_spans():
    reset_trace_events()
    with trace_span("test.api.trace", {"component": "observability"}):
        pass

    client = TestClient(api_server.app)
    response = client.get("/api/operations/traces", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["returned"] >= 2
    assert payload["summary"]["limit"] == 10
    assert any(item["name"] == "test.api.trace" for item in payload["events"])
    assert payload["export"]["format"] == "otlp-json-preview"
    assert payload["export"]["summary"]["span_count"] >= 1
    assert payload["summary"]["otel_exporter"]["network_send"] is False
    assert "initialization" in payload["summary"]["otel_exporter"]
    assert payload["export_preview"]["span_count"] >= 1
    assert payload["dashboard_cards"]
    assert payload["panel_templates"][0]["id"] == "trace_export_preview"

    clear_response = client.delete("/api/operations/traces")
    assert clear_response.status_code == 200
    assert clear_response.json() == {"ok": True, "cleared": True}

    empty_response = client.get("/api/operations/traces")
    assert empty_response.status_code == 200
    assert empty_response.json()["summary"]["returned"] == 0


def test_operations_trace_ingest_merges_external_process_events():
    reset_trace_events()
    client = TestClient(api_server.app)

    ingest_response = client.post(
        "/api/operations/traces/ingest",
        json={
            "source": "worker-1",
            "process_id": "pid-worker",
            "events": [
                {
                    "event": "end",
                    "name": "worker.job",
                    "trace_id": "trace-worker",
                    "span_id": "span-worker",
                    "timestamp": 1700000000,
                    "duration_ms": 25,
                    "attributes": {"queue": "default"},
                }
            ],
        },
    )
    trace_response = client.get("/api/operations/traces", params={"limit": 10})

    assert ingest_response.status_code == 200
    assert ingest_response.json()["accepted"] == 1
    payload = trace_response.json()
    assert payload["summary"]["source_nodes"]["worker-1"] == 1
    assert payload["summary"]["process_nodes"]["pid-worker"] == 1
    assert payload["events"][0]["source"] == "worker-1"
    assert payload["export_preview"]["source_nodes"]["worker-1"] == 1


def test_operations_observability_snapshot_returns_dashboard_templates():
    reset_trace_events()
    with trace_span("test.api.snapshot", {"component": "observability"}):
        pass

    client = TestClient(api_server.app)
    response = client.get("/api/operations/observability", params={"trace_limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert "runtime" in payload
    assert payload["traces"]["summary"]["returned"] >= 2
    assert payload["traces"]["export_preview"]["span_count"] >= 1
    assert payload["metrics_aggregation"]["summary"]["node_count"] == 1
    assert payload["exporters"]["traces"]["network_send"] is False
    assert "initialization" in payload["exporters"]["traces"]
    assert payload["exporters"]["metrics"]["network_send"] is False
    assert payload["dashboard_cards"]
    assert payload["panel_templates"][0]["id"] == "trace_export_preview"


def test_operations_trace_endpoint_filters_recent_spans():
    reset_trace_events()
    with trace_span("test.api.alpha", {"component": "observability"}, trace_id="trace-alpha"):
        pass
    with trace_span("test.api.beta", {"component": "observability"}, trace_id="trace-beta"):
        pass

    client = TestClient(api_server.app)
    response = client.get(
        "/api/operations/traces",
        params={
            "limit": 10,
            "event": "end",
            "name": "test.api.beta",
            "trace_id": "trace-beta",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["returned"] == 1
    assert payload["summary"]["limit"] == 10
    assert payload["summary"]["filters"] == {
        "event": "end",
        "name": "test.api.beta",
        "trace_id": "trace-beta",
    }
    assert payload["events"][0]["event"] == "end"
    assert payload["events"][0]["name"] == "test.api.beta"
    assert payload["events"][0]["trace_id"] == "trace-beta"
