from fastapi.testclient import TestClient

import backend.api_server as api_server


def test_health_endpoint_returns_request_trace_headers():
    client = TestClient(api_server.app)

    response = client.get("/api/health", headers={"X-Request-ID": "req-health-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-health-123"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0

