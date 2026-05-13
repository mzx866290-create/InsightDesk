import json
import sqlite3
import calendar
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

import backend.api_server as api_server
from backend.core import env_runtime
import backend.agent.agents.integrator.audit as outbound_audit_helpers
import backend.helpers.integration_connector_helpers as connector_helpers
from backend.agent_mcp_helpers import MCP_SERVER_METADATA
from backend.routes.operations_routes import build_operations_router
from backend.agent.agents.integrator.audit import (
    persist_integrator_outbound_audit_record,
)
from backend.agent.agents.integrator.execution import (
    NoRedirectUrlLibWebhookClient,
    WebhookExecutionResponse,
)
from backend.stores.integrator_outbound_audit_store import (
    SQLiteIntegratorOutboundAuditStore,
)


INTEGRATOR_CONNECTORS_CONFIG_KEY = "integrator_connectors"
INTEGRATOR_SCHEDULES_CONFIG_KEY = "integrator_schedules"


def _test_store(tmp_path, monkeypatch):
    db_path = tmp_path / "config.db"
    monkeypatch.setenv(
        "APP_CONFIG_MASTER_KEY_PATH",
        str(tmp_path / ".app_config.key"),
    )
    store = api_server.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    return store, db_path


def _connector_payload():
    return {
        "connectors": [
            {
                "type": "webhook",
                "name": "Ops Webhook",
                "enabled": True,
                "approved": False,
                "settings": {
                    "url": "https://hooks.example.test/ops",
                    "token": "ops-webhook-token",
                    "channel": "ops-alerts",
                    "nested": {
                        "client_secret": "nested-client-secret",
                        "safe_label": "incident-review",
                    },
                },
            },
            {
                "type": "email",
                "name": "Finance Email",
                "enabled": False,
                "approved": True,
                "settings": {
                    "to": ["finance@example.test"],
                    "subject_prefix": "[Finance]",
                },
            },
        ]
    }


def _schedule_payload():
    return {
        "schedules": [
            {
                "id": "nightly-ops-sync",
                "name": "Nightly Ops Sync",
                "description": "Push nightly operations summary",
                "enabled": True,
                "connector_id": "ops-webhook",
                "action": "sync",
                "interval_minutes": 1440,
                "payload": {
                    "topic": "ops",
                    "url": "https://hooks.example.test/ops",
                    "token": "schedule-token",
                    "nested": {"client_secret": "schedule-client-secret"},
                },
                "context": {
                    "owner": "ops",
                    "authorization": "Bearer schedule-auth-secret",
                },
            }
        ]
    }


def _utc_timestamp(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int = 0,
) -> float:
    return float(calendar.timegm((year, month, day, hour, minute, second)))


def _outbound_audit_store(tmp_path, monkeypatch):
    store = SQLiteIntegratorOutboundAuditStore(
        db_path=str(tmp_path / "integrator-outbound-audit.db"),
        history_limit=100,
    )
    monkeypatch.setattr(outbound_audit_helpers, "_default_store", store)
    return store


def _append_outbound_audit(store, *, task_id: str, status: str = "succeeded"):
    return persist_integrator_outbound_audit_record(
        {
            "event": "integrator.webhook.outbound",
            "task_id": task_id,
            "action": "push",
            "dry_run": False,
            "executed": True,
            "status": status,
            "created_at": "2026-04-30T00:00:00Z",
            "connector": {
                "id": "ops-webhook",
                "type": "webhook",
                "name": "Ops Webhook",
                "approved": True,
                "token": "raw-connector-token",
            },
            "endpoint": {
                "host": "hooks.example.test",
                "fingerprint": f"fp-{task_id}",
                "url": "https://hooks.example.test/ops?token=raw-url-token",
            },
            "payload_summary": {
                "type": "dict",
                "keys": ["message"],
                "preview": "callback=https://hooks.example.test/cb secret=raw-payload-secret",
            },
            "response": {
                "ok": status == "succeeded",
                "status_code": 200 if status == "succeeded" else 500,
                "body_preview": "token=raw-response-token authorization=Bearer raw-auth-secret",
            },
        },
        store=store,
    )


class _RuntimeOperationsResponse(BaseModel):
    pass


async def _noop_async(*_args, **_kwargs):
    return None


def _operations_client_with_enqueue(store, enqueue_task, scheduler_config=None):
    tasks: dict[str, object] = {}
    tasks_lock = object()
    app = FastAPI()
    app.include_router(
        build_operations_router(
            runtime_operations_response_model=_RuntimeOperationsResponse,
            require_remote_viewer=lambda _request: {},
            require_remote_admin=lambda _request: {},
            runtime_request_metrics_payload=lambda: {},
            runtime_task_summary_payload=lambda: {},
            runtime_operations_payload=lambda: {},
            get_runtime_started_at=lambda: 0.0,
            sync_runtime_secret_from_store=lambda _env_name, _config_key: "",
            validate_tavily_api_key=_noop_async,
            get_app_config_store=lambda: store,
            upsert_cloud_model_api_key=lambda api_key_ref, _api_key: api_key_ref or "key-ref",
            delete_cloud_model_api_key=lambda _api_key_ref: False,
            clear_agent_cache=_noop_async,
            audit_security_event=lambda *_args, **_kwargs: None,
            tasks=lambda: tasks,
            tasks_lock=tasks_lock,
            prune_task_records_locked=lambda *_args, **_kwargs: None,
            persist_task_record=lambda *_args, **_kwargs: None,
            prune_persisted_tasks=lambda: None,
            run_task=_noop_async,
            enqueue_task=enqueue_task,
            spawn_background_task=lambda _coro: None,
            logger=object(),
            task_backend="memory",
            enqueue_external_task=_noop_async,
            integrator_scheduler_config=scheduler_config,
        )
    )
    return TestClient(app), tasks, tasks_lock


def test_get_integrator_connectors_returns_redacted_persisted_config(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.get("/api/integrations/connectors")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connectors"][0]["type"] == "webhook"
    assert payload["connectors"][0]["name"] == "Ops Webhook"
    assert payload["connectors"][0]["enabled"] is True
    assert payload["connectors"][0]["approved"] is False
    assert payload["connectors"][0]["settings"] == {
        "url": "***redacted***",
        "token": "***redacted***",
        "channel": "ops-alerts",
        "nested": {
            "client_secret": "***redacted***",
            "safe_label": "incident-review",
        },
    }
    assert payload["connectors"][1]["settings"]["to"] == ["finance@example.test"]

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_payload
    assert "ops-webhook-token" not in rendered_payload
    assert "nested-client-secret" not in rendered_payload


def test_put_integrator_connectors_persists_and_returns_redacted_config(
    monkeypatch,
    tmp_path,
):
    store, db_path = _test_store(tmp_path, monkeypatch)
    payload = _connector_payload()
    client = TestClient(api_server.app)

    response = client.put("/api/integrations/connectors", json=payload)

    assert response.status_code == 200
    rendered_response = json.dumps(response.json(), ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_response
    assert "ops-webhook-token" not in rendered_response
    assert "nested-client-secret" not in rendered_response
    assert response.json()["connectors"][0]["settings"]["url"] == "***redacted***"
    assert response.json()["connectors"][0]["settings"]["token"] == "***redacted***"
    assert (
        response.json()["connectors"][0]["settings"]["nested"]["client_secret"]
        == "***redacted***"
    )
    assert response.json()["connectors"][0]["settings"]["channel"] == "ops-alerts"

    persisted = json.loads(store.get_value(INTEGRATOR_CONNECTORS_CONFIG_KEY))
    assert persisted == payload["connectors"]

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (INTEGRATOR_CONNECTORS_CONFIG_KEY,),
        ).fetchone()

    assert row is not None
    raw_stored_value = str(row[0])
    assert raw_stored_value.startswith("enc:v1:")
    assert "https://hooks.example.test/ops" not in raw_stored_value
    assert "ops-webhook-token" not in raw_stored_value
    assert "nested-client-secret" not in raw_stored_value

    follow_up = client.get("/api/integrations/connectors")
    assert follow_up.status_code == 200
    assert follow_up.json() == response.json()


def test_put_integrator_connectors_rejects_non_list_connectors(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)

    response = client.put(
        "/api/integrations/connectors",
        json={"connectors": {"type": "webhook", "name": "Invalid"}},
    )

    assert response.status_code == 422


def test_post_integrator_connector_test_dry_run_returns_redacted_contract(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    connector = _connector_payload()["connectors"][0]

    response = client.post("/api/integrations/connectors/test", json=connector)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] in {"ready", "warning"}
    assert payload["dry_run"] is True
    assert payload["executed"] is False
    assert isinstance(payload["checks"], list)
    assert payload["checks"]
    assert payload["connector"]["type"] == "webhook"
    assert payload["connector"]["name"] == "Ops Webhook"
    assert payload["connector"]["enabled"] is True
    assert payload["connector"]["approved"] is False
    assert payload["connector"]["settings"] == {
        "url": "***redacted***",
        "token": "***redacted***",
        "channel": "ops-alerts",
        "nested": {
            "client_secret": "***redacted***",
            "safe_label": "incident-review",
        },
    }

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_payload
    assert "ops-webhook-token" not in rendered_payload
    assert "nested-client-secret" not in rendered_payload


def test_post_integrator_connector_test_rejects_invalid_json(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/test",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code in {400, 422}


def test_post_integrator_connector_test_rejects_unsupported_type(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/test",
        json={
            "type": "pagerduty",
            "name": "Unsupported Connector",
            "settings": {"token": "pagerduty-token"},
        },
    )

    assert response.status_code in {400, 422}
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "pagerduty-token" not in rendered_payload


def test_rotate_integrator_connector_credentials_persists_encrypted_and_redacted(
    monkeypatch,
    tmp_path,
):
    store, db_path = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/credentials/rotate",
        json={
            "settings": {
                "token": "rotated-webhook-token",
                "nested": {"client_secret": "rotated-client-secret"},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rotated"
    assert payload["connector"]["settings"]["token"] == "***redacted***"
    assert payload["connector"]["settings"]["nested"]["client_secret"] == "***redacted***"
    assert payload["connector"]["settings"]["channel"] == "ops-alerts"
    assert payload["rotated_fields"] == ["nested.client_secret", "token"]
    assert payload["preserved_fields"] == []
    assert payload["summary"]["rotated_count"] == 2
    assert payload["summary"]["sensitive_fields_redacted"] is True

    persisted = json.loads(store.get_value(INTEGRATOR_CONNECTORS_CONFIG_KEY))
    assert persisted[0]["settings"]["token"] == "rotated-webhook-token"
    assert persisted[0]["settings"]["nested"]["client_secret"] == "rotated-client-secret"
    assert persisted[0]["settings"]["nested"]["safe_label"] == "incident-review"

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (INTEGRATOR_CONNECTORS_CONFIG_KEY,),
        ).fetchone()

    assert row is not None
    raw_stored_value = str(row[0])
    assert raw_stored_value.startswith("enc:v1:")
    rendered_response = json.dumps(payload, ensure_ascii=False)
    assert "rotated-webhook-token" not in rendered_response
    assert "rotated-client-secret" not in rendered_response
    assert "rotated-webhook-token" not in raw_stored_value
    assert "rotated-client-secret" not in raw_stored_value


def test_rotate_integrator_connector_credentials_preserves_redacted_values(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/credentials/rotate",
        json={
            "credentials": {
                "token": "***redacted***",
                "nested": {
                    "client_secret": "***redacted***",
                    "safe_label": "post-rotation-review",
                },
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rotated_fields"] == ["nested.safe_label"]
    assert payload["preserved_fields"] == ["nested.client_secret", "token"]
    persisted = json.loads(store.get_value(INTEGRATOR_CONNECTORS_CONFIG_KEY))
    assert persisted[0]["settings"]["token"] == "ops-webhook-token"
    assert persisted[0]["settings"]["nested"]["client_secret"] == "nested-client-secret"
    assert persisted[0]["settings"]["nested"]["safe_label"] == "post-rotation-review"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "ops-webhook-token" not in rendered_payload
    assert "nested-client-secret" not in rendered_payload


def test_rotate_integrator_connector_credentials_rejects_unknown_connector(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/missing/credentials/rotate",
        json={"settings": {"token": "new-token"}},
    )

    assert response.status_code == 404
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "new-token" not in rendered_payload


def test_rotate_integrator_connector_credentials_rejects_structural_fields(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/credentials/rotate",
        json={
            "type": "email",
            "settings": {"token": "new-token"},
        },
    )

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "new-token" not in rendered_payload


def test_probe_integrator_connector_returns_static_dry_run_without_leaking_secrets(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    client = TestClient(api_server.app)

    response = client.post("/api/integrations/connectors/Ops%20Webhook/probe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["executed"] is False
    assert payload["probe"]["mode"] == "static"
    assert payload["probe"]["outbound_request_sent"] is False
    assert payload["summary"]["probe_mode"] == "static"
    assert payload["connector"]["settings"]["url"] == "***redacted***"
    assert payload["connector"]["settings"]["token"] == "***redacted***"
    assert payload["summary"]["sensitive_fields_redacted"] is True
    assert isinstance(payload["checks"], list)
    assert payload["checks"]

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_payload
    assert "ops-webhook-token" not in rendered_payload
    assert "nested-client-secret" not in rendered_payload


def test_probe_integrator_connector_external_mode_executes_with_mocked_client_and_audit(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    audit_store = _outbound_audit_store(tmp_path, monkeypatch)
    connectors = _connector_payload()["connectors"]
    connectors[0]["approved"] = True
    store.set(INTEGRATOR_CONNECTORS_CONFIG_KEY, json.dumps(connectors))
    monkeypatch.setattr(
        connector_helpers.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (connector_helpers.socket.AF_INET, connector_helpers.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    calls: list[dict[str, object]] = []

    class FakeWebhookClient:
        async def post_json(self, url, payload, *, headers=None, timeout_seconds=10.0):
            calls.append(
                {
                    "url": url,
                    "payload": payload,
                    "headers": dict(headers or {}),
                    "timeout_seconds": timeout_seconds,
                }
            )
            return WebhookExecutionResponse(
                status_code=204,
                body=(
                    "ok token=ops-webhook-token "
                    "secret=nested-client-secret "
                    "callback=https://hooks.example.test/ops"
                ),
                elapsed_ms=7,
            )

    monkeypatch.setattr(connector_helpers, "NoRedirectUrlLibWebhookClient", FakeWebhookClient)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/probe",
        json={"mode": "external", "timeout_seconds": 1.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dry_run"] is False
    assert payload["executed"] is True
    assert payload["probe"]["mode"] == "external"
    assert payload["probe"]["outbound_request_sent"] is True
    assert payload["probe"]["timeout_seconds"] == 1.5
    assert payload["probe"]["endpoint"]["host"] == "hooks.example.test"
    assert payload["probe"]["response"]["status_code"] == 204
    assert payload["summary"]["probe_mode"] == "external"
    assert payload["summary"]["sensitive_fields_redacted"] is True
    assert len(calls) == 1
    assert calls[0]["url"] == "https://hooks.example.test/ops"
    assert calls[0]["timeout_seconds"] == 1.5
    assert calls[0]["payload"]["event"] == "integrator.connector.probe"
    assert calls[0]["payload"]["mode"] == "external"

    audit_payload = outbound_audit_helpers.integrator_outbound_audit_payload(
        store=audit_store,
    )
    assert audit_payload["total"] == 1
    audit_event = audit_payload["events"][0]
    assert audit_event["event"] == "integrator.connector.probe"
    assert audit_event["action"] == "probe"
    assert audit_event["probe"]["mode"] == "external"
    assert audit_event["endpoint"]["host"] == "hooks.example.test"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    rendered_audit = json.dumps(audit_payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_payload
    assert "https://hooks.example.test/ops" not in rendered_audit
    assert "ops-webhook-token" not in rendered_payload
    assert "ops-webhook-token" not in rendered_audit
    assert "nested-client-secret" not in rendered_payload
    assert "nested-client-secret" not in rendered_audit


def test_no_redirect_url_lib_webhook_client_returns_redirect_without_following():
    hits: list[tuple[str, str]] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(("POST", self.path))
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://{self.headers['Host']}/redirect-target?token=redirect-token",
            )
            self.end_headers()
            self.wfile.write(b"redirecting token=redirect-token")

        def do_GET(self):
            hits.append(("GET", self.path))
            self.send_response(204)
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        response = asyncio.run(
            NoRedirectUrlLibWebhookClient().post_json(
                f"http://{host}:{port}/probe",
                {"event": "integrator.connector.probe"},
                timeout_seconds=1.0,
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.ok is False
    assert response.status_code == 302
    assert "redirect-token" in response.body
    assert hits == [("POST", "/probe")]


def test_probe_integrator_connector_external_mode_blocks_redirect_response(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    audit_store = _outbound_audit_store(tmp_path, monkeypatch)
    connectors = _connector_payload()["connectors"]
    connectors[0]["approved"] = True
    store.set(INTEGRATOR_CONNECTORS_CONFIG_KEY, json.dumps(connectors))
    monkeypatch.setattr(
        connector_helpers.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (connector_helpers.socket.AF_INET, connector_helpers.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    calls: list[str] = []

    class RedirectWebhookClient:
        async def post_json(self, url, _payload, *, headers=None, timeout_seconds=10.0):
            calls.append(url)
            return WebhookExecutionResponse(
                status_code=302,
                body=(
                    "redirect token=ops-webhook-token "
                    "secret=nested-client-secret"
                ),
                headers={
                    "Location": "https://169.254.169.254/latest?token=ops-webhook-token",
                },
                elapsed_ms=4,
            )

    monkeypatch.setattr(
        connector_helpers,
        "NoRedirectUrlLibWebhookClient",
        RedirectWebhookClient,
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/probe",
        json={"mode": "external", "timeout_seconds": 1.0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["dry_run"] is False
    assert payload["executed"] is True
    assert payload["probe"]["outbound_request_sent"] is True
    assert payload["probe"]["response"]["ok"] is False
    assert payload["probe"]["response"]["status_code"] == 302
    assert calls == ["https://hooks.example.test/ops"]
    assert any(
        check["name"] == "external_probe_response" and check["ok"] is False
        for check in payload["checks"]
    )
    assert payload["summary"]["blocking_failure_count"] >= 1

    audit_payload = outbound_audit_helpers.integrator_outbound_audit_payload(
        store=audit_store,
    )
    assert audit_payload["events"][0]["status"] == "failed"
    assert audit_payload["events"][0]["response"]["status_code"] == 302

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    rendered_audit = json.dumps(audit_payload, ensure_ascii=False)
    assert "ops-webhook-token" not in rendered_payload
    assert "ops-webhook-token" not in rendered_audit
    assert "nested-client-secret" not in rendered_payload
    assert "nested-client-secret" not in rendered_audit


def test_probe_integrator_connector_external_mode_blocks_unapproved_connector(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(_connector_payload()["connectors"]),
    )
    monkeypatch.setattr(
        connector_helpers.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (connector_helpers.socket.AF_INET, connector_helpers.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    calls: list[object] = []

    class FakeWebhookClient:
        async def post_json(self, *_args, **_kwargs):
            calls.append(_args)
            return WebhookExecutionResponse(status_code=204)

    monkeypatch.setattr(connector_helpers, "NoRedirectUrlLibWebhookClient", FakeWebhookClient)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/probe",
        json={"mode": "external"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["dry_run"] is False
    assert payload["executed"] is False
    assert payload["probe"]["mode"] == "external"
    assert payload["probe"]["outbound_request_sent"] is False
    assert any(
        check["name"] == "external_probe_approved" and check["ok"] is False
        for check in payload["checks"]
    )
    assert calls == []

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_payload
    assert "ops-webhook-token" not in rendered_payload


def test_probe_integrator_connector_external_mode_blocks_non_public_targets(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    connectors = _connector_payload()["connectors"]
    connectors[0]["approved"] = True
    connectors[0]["settings"]["url"] = "https://localhost/ops?token=ops-webhook-token"
    store.set(INTEGRATOR_CONNECTORS_CONFIG_KEY, json.dumps(connectors))
    calls: list[object] = []

    class FakeWebhookClient:
        async def post_json(self, *_args, **_kwargs):
            calls.append(_args)
            return WebhookExecutionResponse(status_code=204)

    monkeypatch.setattr(connector_helpers, "NoRedirectUrlLibWebhookClient", FakeWebhookClient)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/integrations/connectors/Ops%20Webhook/probe",
        json={"mode": "external"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["executed"] is False
    assert payload["probe"]["outbound_request_sent"] is False
    assert any(
        check["name"] == "external_probe_target" and check["ok"] is False
        for check in payload["checks"]
    )
    assert calls == []

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "localhost/ops" not in rendered_payload
    assert "ops-webhook-token" not in rendered_payload


def test_integrator_schedules_persist_encrypted_and_return_redacted_config(
    monkeypatch,
    tmp_path,
):
    store, db_path = _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)

    response = client.put("/api/integrations/schedules", json=_schedule_payload())

    assert response.status_code == 200
    payload = response.json()
    schedule = payload["schedules"][0]
    assert schedule["id"] == "nightly-ops-sync"
    assert schedule["connector_id"] == "ops-webhook"
    assert schedule["action"] == "sync"
    assert schedule["timezone"] == "UTC"
    assert schedule["interval_minutes"] == 1440
    assert schedule["payload"]["topic"] == "ops"
    assert schedule["payload"]["url"] == "***redacted***"
    assert schedule["payload"]["token"] == "***redacted***"
    assert schedule["payload"]["nested"]["client_secret"] == "***redacted***"
    assert schedule["context"]["authorization"] == "***redacted***"
    assert payload["scheduler"]["automatic_dispatch"] is False

    rendered_response = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test/ops" not in rendered_response
    assert "schedule-token" not in rendered_response
    assert "schedule-client-secret" not in rendered_response
    assert "schedule-auth-secret" not in rendered_response

    persisted = json.loads(store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY))
    assert persisted[0]["payload"]["token"] == "schedule-token"

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (INTEGRATOR_SCHEDULES_CONFIG_KEY,),
        ).fetchone()
    assert row is not None
    raw_stored_value = str(row[0])
    assert raw_stored_value.startswith("enc:v1:")
    assert "schedule-token" not in raw_stored_value
    assert "schedule-client-secret" not in raw_stored_value

    follow_up = client.get("/api/integrations/schedules")
    assert follow_up.status_code == 200
    assert follow_up.json()["schedules"][0]["payload"]["token"] == "***redacted***"


def test_integrator_schedules_preserve_redacted_settings_when_saved_by_schedule_id(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    save_response = client.put("/api/integrations/schedules", json=_schedule_payload())
    assert save_response.status_code == 200
    public_schedule = dict(save_response.json()["schedules"][0])
    public_schedule.pop("id", None)
    public_schedule.pop("context", None)
    public_schedule["name"] = "Nightly Ops Sync Updated"

    update_response = client.put(
        "/api/integrations/schedules",
        json={"schedules": [public_schedule]},
    )

    assert update_response.status_code == 200
    persisted = json.loads(store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY))
    assert persisted[0]["name"] == "Nightly Ops Sync Updated"
    assert persisted[0]["payload"]["token"] == "schedule-token"
    assert persisted[0]["payload"]["nested"]["client_secret"] == "schedule-client-secret"
    assert persisted[0]["context"]["authorization"] == "Bearer schedule-auth-secret"


def test_integrator_schedule_valid_cron_sets_next_run_at_and_redacts_response(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    now = _utc_timestamp(2026, 1, 1, 0, 5)
    expected_next = _utc_timestamp(2026, 1, 1, 0, 15)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "*/15 0-23/2 1,2 1-12 0-7"
    schedule_payload["schedules"][0]["interval_minutes"] = 1440

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 200
    schedule = response.json()["schedules"][0]
    assert schedule["cron"] == "*/15 0-23/2 1,2 1-12 0-7"
    assert schedule["next_run_at"] == expected_next

    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload
    assert "Bearer schedule-auth-secret" not in rendered_payload


def test_integrator_schedule_cron_aliases_are_case_insensitive_and_support_ranges(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    now = _utc_timestamp(2026, 1, 6, 9, 31)
    expected_next = _utc_timestamp(2026, 1, 7, 9, 30)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "30 9 * jan-mar mon-fri/2"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 200
    schedule = response.json()["schedules"][0]
    assert schedule["cron"] == "30 9 * jan-mar mon-fri/2"
    assert schedule["timezone"] == "UTC"
    assert schedule["next_run_at"] == expected_next


def test_integrator_schedule_cron_sunday_alias_matches_zero_and_seven(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    now = _utc_timestamp(2026, 1, 3, 23, 59)
    expected_next = _utc_timestamp(2026, 1, 4, 0, 0)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "0 0 * * SUN,7"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 200
    assert response.json()["schedules"][0]["next_run_at"] == expected_next


def test_integrator_schedule_cron_timezone_uses_local_time_for_next_run_at(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    now = _utc_timestamp(2026, 1, 1, 0, 0)
    expected_next = _utc_timestamp(2026, 1, 1, 0, 30)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "30 8 * * *"
    schedule_payload["schedules"][0]["timezone"] = "Asia/Shanghai"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 200
    schedule = response.json()["schedules"][0]
    assert schedule["timezone"] == "Asia/Shanghai"
    assert schedule["next_run_at"] == expected_next


def test_integrator_schedule_cron_macros_and_question_mark_are_supported(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    now = _utc_timestamp(2026, 1, 1, 0, 5)
    expected_next = _utc_timestamp(2026, 1, 1, 1, 0)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "@hourly"
    schedule_payload["schedules"].append(
        {
            **schedule_payload["schedules"][0],
            "id": "weekday-question-mark",
            "schedule_id": "weekday-question-mark",
            "name": "Weekday Question Mark",
            "cron": "30 9 ? JAN MON-FRI",
        }
    )

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 200
    schedules = response.json()["schedules"]
    assert schedules[0]["cron"] == "@hourly"
    assert schedules[0]["next_run_at"] == expected_next
    assert schedules[1]["cron"] == "30 9 ? JAN MON-FRI"
    assert schedules[1]["next_run_at"] == _utc_timestamp(2026, 1, 1, 9, 30)


def test_integrator_schedule_cron_question_mark_is_rejected_outside_day_fields(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "? * * * *"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "cron ? is only supported for day_of_month or day_of_week" in rendered_payload
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload


def test_integrator_schedule_cron_question_mark_must_be_entire_day_field(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "30 9 ?,1 * *"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "cron ? must be the entire day_of_month or day_of_week field" in rendered_payload
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload


def test_integrator_schedule_cron_skips_repeated_dst_local_minute_after_trigger(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    save_now = _utc_timestamp(2026, 11, 1, 5, 0)
    first_local_run = _utc_timestamp(2026, 11, 1, 5, 30)
    repeated_local_run = _utc_timestamp(2026, 11, 1, 6, 30)
    expected_next_day = _utc_timestamp(2026, 11, 2, 6, 30)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: save_now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "30 1 * * *"
    schedule_payload["schedules"][0]["timezone"] = "America/New_York"
    save_response = client.put("/api/integrations/schedules", json=schedule_payload)
    assert save_response.status_code == 200
    assert save_response.json()["schedules"][0]["next_run_at"] == first_local_run

    monkeypatch.setattr(connector_helpers.time, "time", lambda: first_local_run)
    response = client.post("/api/integrations/schedules/nightly-ops-sync/trigger")

    assert response.status_code == 200
    schedule = response.json()["schedule"]
    assert schedule["last_triggered_at"] == first_local_run
    assert schedule["next_run_at"] == expected_next_day
    assert schedule["next_run_at"] != repeated_local_run


def test_integrator_schedule_rejects_invalid_timezone_without_leaking_secrets(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "0 9 * * MON"
    schedule_payload["schedules"][0]["timezone"] = "Mars/Olympus"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "schedule timezone must be a valid IANA timezone" in rendered_payload
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload
    assert "Bearer schedule-auth-secret" not in rendered_payload


def test_integrator_schedule_trigger_advances_next_run_at_with_cron(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    save_now = _utc_timestamp(2026, 1, 1, 0, 5)
    trigger_now = _utc_timestamp(2026, 1, 1, 0, 15)
    expected_next = _utc_timestamp(2026, 1, 1, 0, 30)
    monkeypatch.setattr(connector_helpers.time, "time", lambda: save_now)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "*/15 * * * *"
    save_response = client.put("/api/integrations/schedules", json=schedule_payload)
    assert save_response.status_code == 200
    monkeypatch.setattr(connector_helpers.time, "time", lambda: trigger_now)

    response = client.post("/api/integrations/schedules/nightly-ops-sync/trigger")

    assert response.status_code == 200
    schedule = response.json()["schedule"]
    assert schedule["last_triggered_at"] == trigger_now
    assert schedule["last_run_at"] == trigger_now
    assert schedule["next_run_at"] == expected_next
    assert schedule["trigger_count"] == 1

    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload


def test_integrator_schedule_rejects_invalid_cron_without_leaking_secrets(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "60 * * * *"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "cron minute value must be between 0 and 59" in rendered_payload
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload
    assert "Bearer schedule-auth-secret" not in rendered_payload


def test_integrator_schedule_rejects_cron_step_larger_than_field_range(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["cron"] = "*/61 * * * *"

    response = client.put("/api/integrations/schedules", json=schedule_payload)

    assert response.status_code == 400
    rendered_payload = json.dumps(response.json(), ensure_ascii=False)
    assert "cron minute step is larger than its value range" in rendered_payload
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload


def test_integrator_schedule_trigger_records_dry_run_workflow_payload(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    save_response = client.put("/api/integrations/schedules", json=_schedule_payload())
    assert save_response.status_code == 200

    response = client.post("/api/integrations/schedules/nightly-ops-sync/trigger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["executed"] is False
    assert payload["schedule"]["id"] == "nightly-ops-sync"
    assert payload["schedule"]["trigger_count"] == 1
    assert payload["schedule"]["last_triggered_at"] > 0
    assert payload["would_create_task"]["task_type"] == "multi_agent_workflow"
    task_params = payload["would_create_task"]["params"]
    assert task_params["plan"][0]["agent"] == "integrator"
    assert task_params["plan"][0]["input"]["connector"] == "ops-webhook"
    assert task_params["plan"][0]["input"]["action"] == "sync"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload

    missing = client.post("/api/integrations/schedules/missing-schedule/trigger")
    assert missing.status_code == 404


def test_integrator_schedule_trigger_enqueues_workflow_when_dry_run_false(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    queued: dict[str, object] = {}
    tasks: dict[str, object] = {}

    async def fake_enqueue_task(tasks_arg, tasks_lock_arg, **kwargs):
        queued["tasks"] = tasks_arg
        queued["tasks_lock"] = tasks_lock_arg
        queued["kwargs"] = kwargs
        return {
            "task_id": "task-scheduled-sync",
            "status": "pending",
            "task_type": kwargs["task_type"],
            "params": kwargs["params"],
            "session_id": None,
            "created_at": 123.0,
        }

    client, tasks, tasks_lock = _operations_client_with_enqueue(store, fake_enqueue_task)
    save_response = client.put("/api/integrations/schedules", json=_schedule_payload())
    assert save_response.status_code == 200

    response = client.post(
        "/api/integrations/schedules/nightly-ops-sync/trigger",
        json={"dry_run": "false"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is False
    assert payload["executed"] is True
    assert payload["task"]["task_id"] == "task-scheduled-sync"
    assert payload["task"]["task_type"] == "multi_agent_workflow"
    assert queued["tasks"] is tasks
    assert queued["tasks_lock"] is tasks_lock
    queued_kwargs = queued["kwargs"]
    assert queued_kwargs["task_type"] == "multi_agent_workflow"
    assert queued_kwargs["params"]["plan"][0]["agent"] == "integrator"
    assert queued_kwargs["params"]["plan"][0]["input"]["connector"] == "ops-webhook"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    rendered_queued = json.dumps(queued_kwargs, ensure_ascii=False, default=str)
    assert "schedule-token" not in rendered_payload
    assert "schedule-token" not in rendered_queued
    assert "schedule-client-secret" not in rendered_payload
    assert "schedule-client-secret" not in rendered_queued


def test_integrator_schedule_tick_dry_run_returns_due_without_mutation(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["next_run_at"] = 100
    schedule_payload["schedules"][0]["interval_minutes"] = 5
    save_response = client.put("/api/integrations/schedules", json=schedule_payload)
    assert save_response.status_code == 200

    response = client.post("/api/integrations/schedules/tick", json={"now": 200})

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["executed"] is False
    assert payload["checked"] == 1
    assert payload["due_count"] == 1
    assert payload["skipped"] == {"disabled": 0, "not_due": 0}
    due = payload["due"][0]
    assert due["schedule_id"] == "nightly-ops-sync"
    assert due["schedule"]["trigger_count"] == 0
    assert due["would_create_task"]["task_type"] == "multi_agent_workflow"
    assert due["would_create_task"]["params"]["plan"][0]["agent"] == "integrator"

    persisted = json.loads(store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY))
    assert persisted[0]["trigger_count"] == 0
    assert persisted[0]["next_run_at"] == 100

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "schedule-token" not in rendered_payload
    assert "schedule-client-secret" not in rendered_payload
    assert "Bearer schedule-auth-secret" not in rendered_payload


def test_integrator_schedule_tick_enqueues_due_workflows_when_dry_run_false(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    queued: list[dict[str, object]] = []

    async def fake_enqueue_task(_tasks_arg, _tasks_lock_arg, **kwargs):
        queued.append(kwargs)
        return {
            "task_id": f"task-scheduled-sync-{len(queued)}",
            "status": "pending",
            "task_type": kwargs["task_type"],
            "params": kwargs["params"],
            "session_id": None,
            "created_at": 200.0,
        }

    client, _tasks, _tasks_lock = _operations_client_with_enqueue(store, fake_enqueue_task)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["next_run_at"] = 100
    schedule_payload["schedules"][0]["interval_minutes"] = 5
    save_response = client.put("/api/integrations/schedules", json=schedule_payload)
    assert save_response.status_code == 200

    response = client.post(
        "/api/integrations/schedules/tick",
        json={"dry_run": False, "now": 200},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is False
    assert payload["executed"] is True
    assert payload["due_count"] == 1
    assert payload["due"][0]["executed"] is True
    assert payload["due"][0]["task"]["task_id"] == "task-scheduled-sync-1"
    assert len(queued) == 1
    assert queued[0]["task_type"] == "multi_agent_workflow"
    assert queued[0]["params"]["plan"][0]["input"]["connector"] == "ops-webhook"

    schedule = payload["due"][0]["schedule"]
    assert schedule["trigger_count"] == 1
    assert schedule["last_triggered_at"] == 200
    assert schedule["last_run_at"] == 200
    assert schedule["next_run_at"] == 500

    persisted = json.loads(store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY))
    assert persisted[0]["trigger_count"] == 1
    assert persisted[0]["last_triggered_at"] == 200
    assert persisted[0]["last_run_at"] == 200
    assert persisted[0]["next_run_at"] == 500

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    rendered_queued = json.dumps(queued, ensure_ascii=False, default=str)
    assert "schedule-token" not in rendered_payload
    assert "schedule-token" not in rendered_queued
    assert "schedule-client-secret" not in rendered_payload
    assert "schedule-client-secret" not in rendered_queued
    assert "Bearer schedule-auth-secret" not in rendered_payload
    assert "Bearer schedule-auth-secret" not in rendered_queued


def test_integrator_schedule_tick_skips_disabled_and_not_due_schedules(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    client = TestClient(api_server.app)
    base_schedule = json.loads(json.dumps(_schedule_payload()["schedules"][0]))
    disabled_schedule = dict(base_schedule)
    disabled_schedule.update(
        {
            "id": "disabled-sync",
            "name": "Disabled Sync",
            "enabled": False,
            "next_run_at": 100,
        }
    )
    not_due_schedule = dict(base_schedule)
    not_due_schedule.update(
        {
            "id": "future-sync",
            "name": "Future Sync",
            "enabled": True,
            "next_run_at": 1000,
        }
    )
    save_response = client.put(
        "/api/integrations/schedules",
        json={"schedules": [disabled_schedule, not_due_schedule]},
    )
    assert save_response.status_code == 200

    response = client.post("/api/integrations/schedules/tick", json={"now": 200})

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["executed"] is False
    assert payload["checked"] == 2
    assert payload["due_count"] == 0
    assert payload["due"] == []
    assert payload["skipped"] == {"disabled": 1, "not_due": 1}


def test_integrator_scheduler_env_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("INTEGRATOR_SCHEDULER_ENABLED", raising=False)
    monkeypatch.delenv("INTEGRATOR_SCHEDULER_INTERVAL_SECONDS", raising=False)

    config = env_runtime.integrator_scheduler_config(runtime_logger=api_server.logger)

    assert config["enabled"] is False
    assert config["enabled_source"] == "default"
    assert config["interval_seconds"] == 60
    assert config["interval_source"] == "default"


def test_integrator_scheduler_env_parses_enabled_and_interval(monkeypatch):
    monkeypatch.setenv("INTEGRATOR_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("INTEGRATOR_SCHEDULER_INTERVAL_SECONDS", "2")

    config = env_runtime.integrator_scheduler_config(runtime_logger=api_server.logger)

    assert config["enabled"] is True
    assert config["enabled_source"] == "env"
    assert config["interval_seconds"] == 2
    assert config["interval_source"] == "env"


def test_integrator_schedules_reflect_scheduler_config_in_response(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    client, _tasks, _tasks_lock = _operations_client_with_enqueue(
        store,
        _noop_async,
        scheduler_config=lambda: {
            "enabled": True,
            "interval_seconds": 30,
        },
    )

    response = client.get("/api/integrations/schedules")

    assert response.status_code == 200
    scheduler = response.json()["scheduler"]
    assert scheduler["mode"] == "background"
    assert scheduler["automatic_dispatch"] is True
    assert scheduler["interval_seconds"] == 30


def test_integrator_scheduler_tick_once_enqueues_due_workflow(
    monkeypatch,
    tmp_path,
):
    store, _ = _test_store(tmp_path, monkeypatch)
    queued: list[dict[str, object]] = []

    async def fake_enqueue_task(_tasks_arg, _tasks_lock_arg, **kwargs):
        queued.append(kwargs)
        return {
            "task_id": f"task-background-scheduled-sync-{len(queued)}",
            "status": "pending",
            "task_type": kwargs["task_type"],
            "params": kwargs["params"],
            "session_id": None,
            "created_at": 200.0,
        }

    monkeypatch.setattr(api_server, "enqueue_task", fake_enqueue_task)
    schedule_payload = _schedule_payload()
    schedule_payload["schedules"][0]["next_run_at"] = 100
    schedule_payload["schedules"][0]["interval_minutes"] = 5
    connector_helpers.save_integrator_schedules_payload(
        store,
        schedule_payload["schedules"],
    )

    result = asyncio.run(api_server._run_integrator_scheduler_tick_once(now=200))

    assert result["dry_run"] is False
    assert result["executed"] is True
    assert result["due_count"] == 1
    assert result["due"][0]["task"]["task_id"] == "task-background-scheduled-sync-1"
    assert len(queued) == 1
    assert queued[0]["task_type"] == "multi_agent_workflow"
    assert queued[0]["params"]["plan"][0]["agent"] == "integrator"

    persisted = json.loads(store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY))
    assert persisted[0]["trigger_count"] == 1
    assert persisted[0]["last_run_at"] == 200
    assert persisted[0]["next_run_at"] == 500

    rendered_result = json.dumps(result, ensure_ascii=False)
    rendered_queued = json.dumps(queued, ensure_ascii=False, default=str)
    assert "schedule-token" not in rendered_result
    assert "schedule-token" not in rendered_queued
    assert "schedule-client-secret" not in rendered_result
    assert "schedule-client-secret" not in rendered_queued


def test_get_integrator_outbound_audit_returns_limited_redacted_events(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    store = _outbound_audit_store(tmp_path, monkeypatch)
    _append_outbound_audit(store, task_id="task-old")
    _append_outbound_audit(store, task_id="task-new", status="failed")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/integrations/outbound-audit",
        params={"limit": "1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 1
    assert payload["total"] == 2
    assert len(payload["events"]) == 1
    assert payload["events"][0]["task_id"] == "task-new"
    assert payload["events"][0]["status"] == "failed"
    assert payload["retention"]["sensitive_fields_redacted"] is True

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test" not in rendered_payload
    assert "raw-url-token" not in rendered_payload
    assert "raw-connector-token" not in rendered_payload
    assert "raw-payload-secret" not in rendered_payload
    assert "raw-response-token" not in rendered_payload
    assert "raw-auth-secret" not in rendered_payload
    assert "***redacted***" in rendered_payload


def test_mcp_connector_config_api_returns_ui_marketplace_hot_update_contract(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    config_path = tmp_path / "mcp.json"
    monkeypatch.setenv("MCP_SERVER_CONFIG_PATH", str(config_path))
    client = TestClient(api_server.app)

    response = client.put(
        "/api/connectors/mcp/config",
        json={
            "servers": {
                "crm-sync": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["crm.py"],
                    "env": {"CRM_TOKEN": "secret-token"},
                    "metadata": {
                        "label": "CRM Sync",
                        "category": "crm",
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                }
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hot_update"]["applied"] is True
    assert payload["hot_update"]["restart_required"] is False
    assert payload["connectors"][0]["name"] == "crm-sync"
    assert payload["connectors"][0]["label"] == "CRM Sync"
    by_name = {item["name"]: item for item in payload["connectors"]}
    assert payload["marketplace"]["summary"]["total"] == len(MCP_SERVER_METADATA) + 1
    assert by_name["fetch"]["source"] == "template"
    assert by_name["fetch"]["configured"] is False
    assert payload["servers"]["crm-sync"]["env"]["CRM_TOKEN"] == "***redacted***"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "secret-token" not in rendered_payload

    follow_up = client.get("/api/connectors/mcp/config")
    assert follow_up.status_code == 200
    assert follow_up.json()["hot_update"]["applied"] is False


def test_integrator_outbound_audit_cleanup_dry_run_and_retention(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    store = _outbound_audit_store(tmp_path, monkeypatch)
    _append_outbound_audit(store, task_id="task-1")
    _append_outbound_audit(store, task_id="task-2")
    _append_outbound_audit(store, task_id="task-3")
    client = TestClient(api_server.app)

    dry_run_response = client.post(
        "/api/integrations/outbound-audit/cleanup",
        params={"keep_latest": "1", "dry_run": "true"},
    )

    assert dry_run_response.status_code == 200
    dry_run_payload = dry_run_response.json()
    assert dry_run_payload["dry_run"] is True
    assert dry_run_payload["would_delete_count"] == 2
    assert dry_run_payload["deleted_count"] == 0
    assert dry_run_payload["remaining_count"] == 3

    cleanup_response = client.post(
        "/api/integrations/outbound-audit/cleanup",
        params={"keep_latest": "1"},
    )

    assert cleanup_response.status_code == 200
    cleanup_payload = cleanup_response.json()
    assert cleanup_payload["dry_run"] is False
    assert cleanup_payload["would_delete_count"] == 2
    assert cleanup_payload["deleted_count"] == 2
    assert cleanup_payload["remaining_count"] == 1

    list_response = client.get("/api/integrations/outbound-audit")
    assert list_response.status_code == 200
    assert [event["task_id"] for event in list_response.json()["events"]] == ["task-3"]


def test_get_integrator_audit_lists_redacted_outbound_events(
    monkeypatch,
    tmp_path,
):
    _test_store(tmp_path, monkeypatch)
    store = _outbound_audit_store(tmp_path, monkeypatch)
    _append_outbound_audit(store, task_id="task-integrator-audit")
    client = TestClient(api_server.app)

    response = client.get("/api/integrations/audit?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 5
    assert payload["retention"]["sensitive_fields_redacted"] is True
    event = payload["events"][0]
    assert event["event"] == "integrator.webhook.outbound"
    assert event["connector"]["name"] == "Ops Webhook"
    assert event["endpoint"]["host"] == "hooks.example.test"
    assert event["endpoint"]["fingerprint"] == "fp-task-integrator-audit"
    assert event["endpoint"]["url"] == "***redacted***"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "https://hooks.example.test" not in rendered_payload
    assert "raw-url-token" not in rendered_payload
    assert "raw-response-token" not in rendered_payload
