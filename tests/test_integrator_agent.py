import asyncio
import hashlib
import hmac
import json
import logging

from backend.agent.agents.integrator import ConnectorSpec, IntegratorAgent, IntegratorAgentConfig
from backend.agent.agents.integrator.execution import WebhookExecutionResponse, encode_webhook_json_payload
from backend.agent.registry import create_default_agent_registry


class FakeWebhookClient:
    def __init__(self, response) -> None:
        self.responses = list(response) if isinstance(response, (list, tuple)) else [response]
        self.calls = []

    async def post_json(self, url, payload, *, headers=None, timeout_seconds=10.0):
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": dict(headers or {}),
                "timeout_seconds": timeout_seconds,
            }
        )
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


def _agent() -> IntegratorAgent:
    return IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="ops-email",
                    type="email",
                    name="Ops Email",
                    settings={"to": ["ops@example.test"]},
                ),
                ConnectorSpec(
                    id="sales-hook",
                    type="webhook",
                    name="Sales Webhook",
                    settings={"url": "https://example.test/hooks/sales", "token": "secret-token"},
                ),
                ConnectorSpec(
                    id="feishu-card",
                    type="feishu",
                    name="Feishu Card",
                    settings={"app_id": "cli_xxx", "app_secret": "secret"},
                ),
            ]
        )
    )


def test_integrator_agent_can_handle_integration_tasks():
    agent = IntegratorAgent()

    assert agent.can_handle("integration")
    assert agent.can_handle("integration_push")
    assert agent.can_handle("webhook")
    assert agent.can_handle("sync")
    assert not agent.can_handle("research")


def test_default_registry_registers_integrator_agent():
    registry = create_default_agent_registry()

    agent = registry.find_for_task("integration")

    assert agent is not None
    assert agent.name == "integrator"


def test_integrator_selects_requested_connector_by_type_and_redacts_secrets():
    result = asyncio.run(
        _agent().execute(
            {
                "id": "integrate-1",
                "type": "integration_push",
                "description": "Push summary",
                "input": {"payload": {"title": "Q2 Summary"}, "connector_type": "webhook"},
            },
            {},
        )
    )

    artifact = result["artifacts"][0]
    connector = artifact["content"]["connector"]

    assert result["status"] == "completed"
    assert result["metadata"]["connector_id"] == "sales-hook"
    assert connector["type"] == "webhook"
    assert connector["settings"]["url"] == "***redacted***"
    assert connector["settings"]["token"] == "***redacted***"


def test_integrator_outputs_push_dry_run_artifact():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(config=_agent().config, webhook_client=fake_client)

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-2",
                "type": "integration_push",
                "description": "Push report to email",
                "input": {
                    "connector_id": "ops-email",
                    "payload": {"subject": "Weekly report", "body": "Done"},
                },
            },
            {},
        )
    )

    artifact = result["artifacts"][0]
    content = artifact["content"]

    assert artifact["type"] == "integration_dry_run"
    assert artifact["title"] == "Integration push dry-run"
    assert content["action"] == "push"
    assert content["dry_run"] is True
    assert content["would_send"] is True
    assert content["connector"]["id"] == "ops-email"
    assert content["payload_summary"]["keys"] == ["body", "subject"]
    assert "- Real outbound: disabled" in result["output"]
    assert fake_client.calls == []


def test_integrator_outputs_sync_dry_run_artifact():
    result = asyncio.run(
        _agent().execute(
            {
                "id": "integrate-3",
                "type": "integration_sync",
                "description": "Sync task status",
                "input": {
                    "connector": "feishu-card",
                    "direction": "outbound",
                    "payload": [{"task": "review", "status": "completed"}],
                },
            },
            {},
        )
    )

    content = result["artifacts"][0]["content"]

    assert result["status"] == "completed"
    assert content["action"] == "sync"
    assert content["dry_run"] is True
    assert content["would_sync"] is True
    assert content["direction"] == "outbound"
    assert content["connector"]["type"] == "feishu"
    assert content["payload_summary"] == {"kind": "array", "item_count": 1}


def test_integrator_returns_error_when_connector_is_not_configured():
    result = asyncio.run(
        IntegratorAgent().execute(
            {
                "id": "integrate-4",
                "type": "integration_push",
                "description": "Push report",
                "input": {"connector": "webhook", "payload": {"ok": True}},
            },
            {},
        )
    )

    error_artifact = result["artifacts"][0]

    assert result["status"] == "failed"
    assert "No enabled connector configured" in result["error"]
    assert error_artifact["type"] == "integration_error"
    assert error_artifact["content"]["requested_connector"] == "webhook"


def test_integrator_executes_real_webhook_when_explicitly_requested():
    fake_client = FakeWebhookClient(
        WebhookExecutionResponse(
            status_code=202,
            body='{"accepted":true}',
            headers={"Content-Type": "application/json"},
            elapsed_ms=7,
        )
    )
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="sales-hook",
                    type="webhook",
                    name="Sales Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/sales",
                        "headers": {"X-Connector": "sales"},
                    },
                )
            ]
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-5",
                "type": "integration_push",
                "description": "Push report to webhook",
                "input": {
                    "execute": True,
                    "connector": "sales-hook",
                    "payload": {"title": "Q2 Summary"},
                },
            },
            {},
        )
    )

    artifact = result["artifacts"][0]
    content = artifact["content"]

    assert result["status"] == "completed"
    assert result["metadata"]["dry_run"] is False
    assert result["metadata"]["execution_status"] == "succeeded"
    assert artifact["type"] == "integration_execution"
    assert content["dry_run"] is False
    assert content["status"] == "succeeded"
    assert content["endpoint"]["host"] == "hooks.example.test"
    assert len(content["endpoint"]["fingerprint"]) == 16
    assert content["response"]["status_code"] == 202
    assert content["response"]["ok"] is True
    assert content["retry"]["attempted"] == 1
    assert content["retry"]["max_attempts"] == 1
    assert result["metadata"]["webhook_attempts"] == 1
    assert fake_client.calls == [
        {
            "url": "https://hooks.example.test/sales",
            "payload": {"title": "Q2 Summary"},
            "headers": {"X-Connector": "sales"},
            "timeout_seconds": 10.0,
        }
    ]


def test_integrator_blocks_real_webhook_when_connector_is_not_approved():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="unapproved-hook",
                    type="webhook",
                    name="Unapproved Webhook",
                    settings={"url": "https://hooks.example.test/unapproved"},
                )
            ]
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-unapproved",
                "type": "integration_push",
                "description": "Push unapproved webhook",
                "input": {
                    "execute": True,
                    "connector": "unapproved-hook",
                    "payload": {"title": "Do not send"},
                },
            },
            {},
        )
    )

    artifact = result["artifacts"][0]

    assert result["status"] == "failed"
    assert result["metadata"]["dry_run"] is False
    assert result["metadata"]["execution_requested"] is True
    assert "approved" in result["error"]
    assert artifact["type"] == "integration_error"
    assert artifact["content"]["dry_run"] is False
    assert artifact["content"]["execution_requested"] is True
    assert artifact["content"]["approval_gate"] == {
        "allowed": False,
        "status": "blocked",
        "reason": "approval_required",
        "requires_approval": True,
        "connector_id": "unapproved-hook",
        "connector_type": "webhook",
        "connector_enabled": True,
        "connector_configured": True,
        "connector_approved": False,
        "approval_sources": [],
    }
    assert result["metadata"]["approval_gate"] == artifact["content"]["approval_gate"]
    assert artifact["content"]["configured_connectors"] == [
        {
            "id": "unapproved-hook",
            "type": "webhook",
            "enabled": True,
            "approved": False,
        }
    ]
    assert fake_client.calls == []


def test_integrator_emits_secret_safe_outbound_audit_artifact_and_log(caplog):
    secret = "webhook-signing-secret"
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202, body="accepted"))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="audit-hook",
                    type="webhook",
                    name="Audit Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/audit",
                        "hmac_secret": secret,
                    },
                )
            ]
        ),
        webhook_client=fake_client,
    )

    with caplog.at_level(logging.INFO, logger="backend.agent.agents.integrator.agent"):
        result = asyncio.run(
            agent.execute(
                {
                    "id": "integrate-audit",
                    "type": "integration_push",
                    "description": "Push report to webhook",
                    "input": {
                        "execute": True,
                        "connector": "audit-hook",
                        "payload": {"title": "Q2 Summary"},
                    },
                },
                {},
            )
        )

    audit_artifact = result["artifacts"][1]
    audit = audit_artifact["content"]
    rendered_audit = json.dumps(audit, ensure_ascii=False)

    assert audit_artifact["type"] == "integration_outbound_audit"
    assert audit["event"] == "integrator.webhook.outbound"
    assert audit["task_id"] == "integrate-audit"
    assert audit["status"] == "succeeded"
    assert audit["connector"]["id"] == "audit-hook"
    assert audit["endpoint"]["host"] == "hooks.example.test"
    assert audit["payload_summary"]["keys"] == ["title"]
    assert audit["response"]["status_code"] == 202
    assert result["metadata"]["outbound_audit_event"] == "integrator.webhook.outbound"
    assert result["metadata"]["outbound_audit_status"] == "succeeded"
    assert result["metadata"]["outbound_audit_endpoint_fingerprint"] == audit["endpoint"]["fingerprint"]
    assert secret not in rendered_audit
    assert any(
        record.getMessage() == "integrator.webhook_outbound"
        and getattr(record, "integrator_outbound_audit", {}).get("task_id") == "integrate-audit"
        for record in caplog.records
    )


def test_integrator_signs_real_webhook_payload_with_hmac_secret():
    secret = "webhook-signing-secret"
    payload = {"title": "Q2 Summary", "count": 2}
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="signed-hook",
                    type="webhook",
                    name="Signed Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/signed",
                        "headers": {"X-Connector": "signed"},
                        "hmac_secret": secret,
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-signed",
                "type": "integration_push",
                "description": "Push signed webhook",
                "input": {
                    "execute": True,
                    "connector": "signed-hook",
                    "payload": payload,
                },
            },
            {},
        )
    )

    body = encode_webhook_json_payload(payload)
    expected_signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    content = result["artifacts"][0]["content"]

    assert result["status"] == "completed"
    assert result["metadata"]["webhook_hmac_enabled"] is True
    assert fake_client.calls[0]["headers"]["X-Connector"] == "signed"
    assert fake_client.calls[0]["headers"]["X-Integrator-Signature"] == f"sha256={expected_signature}"
    assert content["signing"] == {
        "enabled": True,
        "algorithm": "sha256",
        "header": "X-Integrator-Signature",
        "body_sha256": hashlib.sha256(body).hexdigest()[:16],
    }
    assert secret not in json.dumps(result, ensure_ascii=False)


def test_integrator_dry_run_does_not_sign_or_call_webhook():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="signed-dry-run-hook",
                    type="webhook",
                    name="Signed Dry-run Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/signed-dry-run",
                        "hmac_secret": "dry-run-secret",
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-signed-dry-run",
                "type": "integration_push",
                "description": "Dry-run signed webhook",
                "input": {
                    "connector": "signed-dry-run-hook",
                    "payload": {"title": "Still dry-run"},
                },
            },
            {},
        )
    )

    content = result["artifacts"][0]["content"]

    assert result["status"] == "completed"
    assert result["metadata"]["dry_run"] is True
    assert "signing" not in content
    assert fake_client.calls == []


def test_integrator_blocks_unsupported_webhook_hmac_algorithm_before_outbound_call():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            connectors=[
                ConnectorSpec(
                    id="bad-signing-hook",
                    type="webhook",
                    name="Bad Signing Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/bad-signing",
                        "hmac_secret": "secret",
                        "hmac_algorithm": "md5",
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-bad-signing",
                "type": "integration_push",
                "description": "Push bad signed webhook",
                "input": {
                    "execute": True,
                    "connector": "bad-signing-hook",
                    "payload": {"ok": True},
                },
            },
            {},
        )
    )

    assert result["status"] == "failed"
    assert result["metadata"]["dry_run"] is False
    assert result["error"] == "Unsupported webhook HMAC algorithm: md5."
    assert result["artifacts"][0]["type"] == "integration_error"
    assert fake_client.calls == []


def test_integrator_uses_valid_connector_webhook_timeout_override():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            webhook_timeout_seconds=10.0,
            connectors=[
                ConnectorSpec(
                    id="timeout-hook",
                    type="webhook",
                    name="Timeout Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/timeout",
                        "timeout_seconds": 2.5,
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-timeout",
                "type": "integration_push",
                "description": "Push report with timeout override",
                "input": {
                    "execute": True,
                    "connector": "timeout-hook",
                    "payload": {"title": "Timeout override"},
                },
            },
            {},
        )
    )

    assert result["status"] == "completed"
    assert result["metadata"]["webhook_timeout_seconds"] == 2.5
    assert fake_client.calls[0]["timeout_seconds"] == 2.5


def test_integrator_blocks_invalid_webhook_timeout_before_outbound_call():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            execute=True,
            connectors=[
                ConnectorSpec(
                    id="invalid-timeout-hook",
                    type="webhook",
                    name="Invalid Timeout Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/invalid-timeout",
                        "webhook_timeout_seconds": 0,
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-invalid-timeout",
                "type": "integration_push",
                "description": "Push report with invalid timeout",
                "input": {"connector": "invalid-timeout-hook", "payload": {"ok": True}},
            },
            {},
        )
    )

    artifact = result["artifacts"][0]

    assert result["status"] == "failed"
    assert result["metadata"]["dry_run"] is False
    assert result["error"] == "Webhook timeout_seconds must be at least 0.1 seconds."
    assert artifact["type"] == "integration_error"
    assert artifact["content"]["execution_requested"] is True
    assert fake_client.calls == []


def test_integrator_retries_transient_webhook_failure_until_success():
    fake_client = FakeWebhookClient(
        [
            WebhookExecutionResponse(status_code=503, body="temporary outage", elapsed_ms=2),
            WebhookExecutionResponse(status_code=202, body='{"accepted":true}', elapsed_ms=4),
        ]
    )
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            webhook_retry_attempts=3,
            connectors=[
                ConnectorSpec(
                    id="retry-hook",
                    type="webhook",
                    name="Retry Webhook",
                    approved=True,
                    settings={"url": "https://hooks.example.test/retry"},
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-retry-success",
                "type": "integration_push",
                "description": "Push report to retrying webhook",
                "input": {
                    "execute": True,
                    "connector": "retry-hook",
                    "payload": {"title": "Retry me"},
                },
            },
            {},
        )
    )

    content = result["artifacts"][0]["content"]
    retry = content["retry"]

    assert result["status"] == "completed"
    assert content["status"] == "succeeded"
    assert retry["attempted"] == 2
    assert retry["max_attempts"] == 3
    assert retry["exhausted"] is False
    assert [attempt["status_code"] for attempt in retry["attempts"]] == [503, 202]
    assert retry["attempts"][0]["will_retry"] is True
    assert retry["attempts"][1]["will_retry"] is False
    assert result["metadata"]["webhook_attempts"] == 2
    assert "- Attempts: 2/3" in result["output"]
    assert len(fake_client.calls) == 2


def test_integrator_config_execute_reports_webhook_failure():
    fake_client = FakeWebhookClient(
        WebhookExecutionResponse(
            status_code=503,
            body="service unavailable",
            headers={"Content-Type": "text/plain"},
            elapsed_ms=3,
        )
    )
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            execute=True,
            connectors=[
                {
                    "id": "ops-hook",
                    "type": "webhook",
                    "enabled": True,
                    "approved": True,
                    "settings": {"webhook_url": "https://hooks.example.test/ops"},
                }
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-6",
                "type": "integration_push",
                "description": "Push failing webhook",
                "input": {"payload": {"ok": False}, "connector": "ops-hook"},
            },
            {},
        )
    )

    artifact = result["artifacts"][0]
    content = artifact["content"]

    assert result["status"] == "failed"
    assert result["error"] == "Webhook POST failed with status 503"
    assert artifact["type"] == "integration_execution"
    assert content["status"] == "failed"
    assert content["response"]["ok"] is False
    assert content["response"]["status_code"] == 503
    assert content["response"]["body_preview"] == "service unavailable"
    assert content["retry"]["attempted"] == 1
    assert result["metadata"]["webhook_retry_exhausted"] is True
    assert fake_client.calls[0]["url"] == "https://hooks.example.test/ops"


def test_integrator_retry_failure_summary_does_not_leak_secret_values():
    secret = "super-secret-token"
    fake_client = FakeWebhookClient(
        [
            WebhookExecutionResponse(
                status_code=503,
                body=f"temporary failure for {secret}",
                headers={"Content-Type": "text/plain"},
                elapsed_ms=2,
            ),
            WebhookExecutionResponse(
                status_code=503,
                body=f"still failing for Bearer {secret}",
                headers={"Content-Type": "text/plain"},
                elapsed_ms=3,
            ),
        ]
    )
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            webhook_retry_attempts=2,
            connectors=[
                ConnectorSpec(
                    id="secure-hook",
                    type="webhook",
                    name="Secure Webhook",
                    approved=True,
                    settings={
                        "url": "https://hooks.example.test/secure",
                        "token": secret,
                        "headers": {"Authorization": f"Bearer {secret}"},
                    },
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-retry-failure",
                "type": "integration_push",
                "description": "Push report to failing webhook",
                "input": {
                    "execute": True,
                    "connector": "secure-hook",
                    "payload": {"title": "No secrets here"},
                },
            },
            {},
        )
    )

    content = result["artifacts"][0]["content"]
    rendered_result = json.dumps(result, ensure_ascii=False)

    assert result["status"] == "failed"
    assert content["status"] == "failed"
    assert content["retry"]["attempted"] == 2
    assert content["retry"]["exhausted"] is True
    assert content["retry"]["attempts"] == [
        {"attempt": 1, "ok": False, "status_code": 503, "will_retry": True, "elapsed_ms": 2},
        {"attempt": 2, "ok": False, "status_code": 503, "will_retry": False, "elapsed_ms": 3},
    ]
    assert content["response"]["body_preview"] == "still failing for ***redacted***"
    assert content["connector"]["settings"]["token"] == "***redacted***"
    assert content["connector"]["settings"]["headers"]["Authorization"] == "***redacted***"
    assert secret not in rendered_result
    assert f"Bearer {secret}" not in rendered_result


def test_integrator_blocks_real_webhook_when_connector_is_disabled():
    fake_client = FakeWebhookClient(WebhookExecutionResponse(status_code=202))
    agent = IntegratorAgent(
        config=IntegratorAgentConfig(
            execute=True,
            connectors=[
                ConnectorSpec(
                    id="disabled-hook",
                    type="webhook",
                    enabled=False,
                    approved=True,
                    settings={"url": "https://hooks.example.test/disabled"},
                )
            ],
        ),
        webhook_client=fake_client,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "integrate-7",
                "type": "integration_push",
                "description": "Push disabled webhook",
                "input": {"payload": {"ok": True}, "connector": "disabled-hook"},
            },
            {},
        )
    )

    artifact = result["artifacts"][0]

    assert result["status"] == "failed"
    assert result["metadata"]["dry_run"] is False
    assert "No enabled connector configured" in result["error"]
    assert artifact["type"] == "integration_error"
    assert artifact["content"]["dry_run"] is False
    assert artifact["content"]["execution_requested"] is True
    assert fake_client.calls == []
