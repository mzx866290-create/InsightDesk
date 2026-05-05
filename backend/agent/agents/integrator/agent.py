"""Integrator Agent MVP for dry-run external system handoff."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.agent.agents.integrator.connectors import (
    SUPPORTED_CONNECTOR_TYPES,
    ConnectorSpec,
    describe_connector,
    normalize_connector_type,
)
from backend.agent.agents.integrator.execution import (
    UrlLibWebhookClient,
    WebhookClient,
    WebhookExecutionResponse,
    build_webhook_execution_artifact,
    build_webhook_outbound_audit_artifact,
    collect_webhook_secret_values,
    endpoint_info,
    post_webhook_with_retry,
    resolve_webhook_hmac_headers,
    redact_secret_values,
    resolve_webhook_headers,
    resolve_webhook_retry_attempts,
    resolve_webhook_retry_backoff_seconds,
    resolve_webhook_timeout_seconds,
    resolve_webhook_url,
    validate_webhook_url,
)
from backend.agent.agents.integrator.push import build_push_dry_run_artifact
from backend.agent.agents.integrator.sync import build_sync_dry_run_artifact
from backend.agent.protocols import AgentResult, AgentTask
from backend.agent.agents.integrator.audit import (
    persist_integrator_outbound_audit_record,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IntegratorAgentConfig:
    connectors: tuple[ConnectorSpec | dict[str, Any], ...] | list[ConnectorSpec | dict[str, Any]] = ()
    default_action: str = "push"
    default_sync_direction: str = "outbound"
    execute: bool = False
    webhook_timeout_seconds: float = 10.0
    webhook_retry_attempts: int = 1
    webhook_retry_backoff_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class IntegratorAgent:
    """Produces dry-run artifacts for webhook/email/Feishu/DingTalk integrations."""

    name = "integrator"
    description = "Integrator Agent for external system dry-run push and sync handoff."
    capabilities = [
        "integration",
        "integrator",
        "external_integration",
        "integration_push",
        "integration_sync",
        "push",
        "sync",
        "webhook",
        "email",
        "feishu",
        "dingtalk",
    ]

    def __init__(
        self,
        *,
        config: IntegratorAgentConfig | None = None,
        webhook_client: WebhookClient | None = None,
    ) -> None:
        self.config = config or IntegratorAgentConfig()
        self.connectors = self._normalize_connectors(self.config.connectors)
        self.webhook_client = webhook_client or UrlLibWebhookClient()

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        action = self._resolve_action(task, context)
        request = self._request_text(task)
        execution_requested = self._execution_requested(task, context)
        connector = self._select_connector(task, context)
        if connector is None:
            return self._error_result(
                task,
                context,
                error="No enabled connector configured for Integrator Agent.",
                dry_run=not execution_requested,
                execution_requested=execution_requested,
                action=action,
            )

        connector_description = describe_connector(connector)
        payload = self._resolve_payload(task, context)
        if execution_requested:
            return await self._execute_webhook(
                task=task,
                context=context,
                action=action,
                request=request,
                connector=connector,
                connector_description=connector_description,
                payload=payload,
            )

        if action == "sync":
            artifact = build_sync_dry_run_artifact(
                task_id=str(task.get("id") or ""),
                connector=connector_description,
                payload=payload,
                request=request,
                sync_direction=self._resolve_sync_direction(task, context),
            )
        else:
            artifact = build_push_dry_run_artifact(
                task_id=str(task.get("id") or ""),
                connector=connector_description,
                payload=payload,
                request=request,
            )

        output = self._render_success_output(action, connector_description, artifact["content"])
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": output,
            "artifacts": [artifact],
            "sources": [],
            "metadata": {
                **self.config.metadata,
                "context_keys": sorted(context.keys()),
                "dry_run": True,
                "action": action,
                "connector_id": connector.id,
                "connector_type": connector.normalized_type,
                "configured_connector_count": len(self.connectors),
            },
        }

    async def _execute_webhook(
        self,
        *,
        task: AgentTask,
        context: dict[str, Any],
        action: str,
        request: str,
        connector: ConnectorSpec,
        connector_description: dict[str, Any],
        payload: Any,
    ) -> AgentResult:
        if connector.normalized_type != "webhook":
            return self._error_result(
                task,
                context,
                error="Real integration execution currently supports webhook connectors only.",
                dry_run=False,
                execution_requested=True,
                action=action,
            )
        approval_gate = self._connector_execution_gate(connector)
        if not approval_gate["allowed"]:
            return self._error_result(
                task,
                context,
                error="Connector is not approved for real webhook execution.",
                dry_run=False,
                execution_requested=True,
                action=action,
                approval_gate=approval_gate,
            )

        webhook_url = resolve_webhook_url(connector.settings)
        validation_error = validate_webhook_url(webhook_url)
        if validation_error:
            return self._error_result(
                task,
                context,
                error=validation_error,
                dry_run=False,
                execution_requested=True,
                action=action,
            )

        endpoint = endpoint_info(webhook_url)
        headers = resolve_webhook_headers(connector.settings)
        hmac_headers, hmac_summary, hmac_error = resolve_webhook_hmac_headers(connector.settings, payload)
        if hmac_error:
            return self._error_result(
                task,
                context,
                error=hmac_error,
                dry_run=False,
                execution_requested=True,
                action=action,
            )
        headers = {**headers, **hmac_headers}
        timeout_seconds, timeout_error = resolve_webhook_timeout_seconds(
            connector.settings,
            default_seconds=self.config.webhook_timeout_seconds,
        )
        if timeout_error:
            return self._error_result(
                task,
                context,
                error=timeout_error,
                dry_run=False,
                execution_requested=True,
                action=action,
            )
        retry_attempts = resolve_webhook_retry_attempts(
            connector.settings,
            default_attempts=self.config.webhook_retry_attempts,
        )
        retry_backoff_seconds = resolve_webhook_retry_backoff_seconds(
            connector.settings,
            default_seconds=self.config.webhook_retry_backoff_seconds,
        )
        secret_values = collect_webhook_secret_values(connector.settings)
        response, retry_summary = await post_webhook_with_retry(
            self.webhook_client,
            webhook_url,
            payload,
            headers=headers,
            timeout_seconds=timeout_seconds,
            max_attempts=retry_attempts,
            backoff_seconds=retry_backoff_seconds,
        )

        connector_for_artifact = {**connector_description, "dry_run_only": False}
        artifact = build_webhook_execution_artifact(
            task_id=str(task.get("id") or ""),
            action=action,
            connector=connector_for_artifact,
            endpoint=endpoint,
            payload=payload,
            request=request,
            response=response,
            retry_summary=retry_summary,
            signing_summary=hmac_summary,
            secret_values=secret_values,
        )
        audit_artifact = build_webhook_outbound_audit_artifact(
            task_id=str(task.get("id") or ""),
            action=action,
            connector=connector_for_artifact,
            endpoint=endpoint,
            payload=payload,
            response=response,
            retry_summary=retry_summary,
            signing_summary=hmac_summary,
            secret_values=secret_values,
        )
        audit_record = audit_artifact["content"]
        try:
            persist_integrator_outbound_audit_record(audit_record)
        except Exception:
            logger.exception(
                "Failed to persist integrator webhook outbound audit task_id=%s connector_id=%s",
                str(task.get("id") or ""),
                connector.id,
            )
        logger.info(
            "integrator.webhook_outbound",
            extra={
                "integrator_outbound_audit": audit_record,
                "task_id": str(task.get("id") or ""),
                "connector_id": connector.id,
                "endpoint_fingerprint": endpoint.get("fingerprint", ""),
            },
        )
        status = "completed" if response.ok else "failed"
        result: AgentResult = {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": status,
            "output": self._render_execution_output(action, connector_for_artifact, artifact["content"]),
            "artifacts": [artifact, audit_artifact],
            "sources": [],
            "metadata": {
                **self.config.metadata,
                "context_keys": sorted(context.keys()),
                "dry_run": False,
                "execution_requested": True,
                "action": action,
                "connector_id": connector.id,
                "connector_type": connector.normalized_type,
                "configured_connector_count": len(self.connectors),
                "endpoint_host": endpoint.get("host", ""),
                "endpoint_fingerprint": endpoint.get("fingerprint", ""),
                "execution_status": artifact["content"]["status"],
                "http_status_code": response.status_code,
                "webhook_timeout_seconds": timeout_seconds,
                "webhook_attempts": retry_summary["attempted"],
                "webhook_retry_max_attempts": retry_summary["max_attempts"],
                "webhook_retry_exhausted": retry_summary["exhausted"],
                "webhook_hmac_enabled": bool(hmac_summary.get("enabled")),
                "outbound_audit_event": audit_record["event"],
                "outbound_audit_status": audit_record["status"],
                "outbound_audit_endpoint_fingerprint": endpoint.get("fingerprint", ""),
            },
        }
        if not response.ok:
            result["error"] = self._execution_error_message(response, secret_values=secret_values)
        return result

    @staticmethod
    def _normalize_connectors(
        connectors: tuple[ConnectorSpec | dict[str, Any], ...] | list[ConnectorSpec | dict[str, Any]],
    ) -> tuple[ConnectorSpec, ...]:
        normalized: list[ConnectorSpec] = []
        for raw_connector in connectors:
            connector = (
                raw_connector
                if isinstance(raw_connector, ConnectorSpec)
                else ConnectorSpec.from_mapping(raw_connector)
            )
            connector_type = normalize_connector_type(connector.type)
            if connector_type not in SUPPORTED_CONNECTOR_TYPES:
                raise ValueError(f"Unsupported connector type: {connector.type}")
            if not connector.id:
                connector.id = connector_type
            connector.type = connector_type
            normalized.append(connector)
        return tuple(normalized)

    def _select_connector(self, task: AgentTask, context: dict[str, Any]) -> ConnectorSpec | None:
        selector = self._connector_selector(task, context)
        enabled_connectors = [connector for connector in self.connectors if connector.enabled]
        if not enabled_connectors:
            return None
        if not selector:
            return enabled_connectors[0]
        for connector in enabled_connectors:
            if connector.matches(selector):
                return connector
        return None

    @staticmethod
    def _connector_selector(task: AgentTask, context: dict[str, Any]) -> str:
        task_metadata = task.get("metadata") or {}
        raw_input = task.get("input")
        candidates: list[Any] = [
            task_metadata.get("connector_id"),
            task_metadata.get("connector"),
            task_metadata.get("connector_type"),
            task_metadata.get("channel"),
            task_metadata.get("target"),
        ]
        if isinstance(raw_input, dict):
            candidates.extend(
                [
                    raw_input.get("connector_id"),
                    raw_input.get("connector"),
                    raw_input.get("connector_type"),
                    raw_input.get("channel"),
                    raw_input.get("target"),
                ]
            )
        candidates.extend(
            [
                context.get("connector_id"),
                context.get("connector"),
                context.get("connector_type"),
                context.get("channel"),
                context.get("target"),
            ]
        )
        for value in candidates:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _execution_requested(self, task: AgentTask, context: dict[str, Any]) -> bool:
        task_metadata = task.get("metadata") or {}
        raw_input = task.get("input")
        candidates: list[Any] = [
            self.config.execute,
            task_metadata.get("execute"),
            task_metadata.get("execute_webhook"),
            task_metadata.get("real_execution"),
            task_metadata.get("integration_execute"),
            context.get("execute"),
            context.get("execute_webhook"),
            context.get("real_execution"),
            context.get("integration_execute"),
        ]
        if isinstance(raw_input, dict):
            candidates.extend(
                [
                    raw_input.get("execute"),
                    raw_input.get("execute_webhook"),
                    raw_input.get("real_execution"),
                    raw_input.get("integration_execute"),
                ]
            )
        return any(self._truthy(value) for value in candidates)

    @classmethod
    def _connector_allows_execution(cls, connector: ConnectorSpec) -> bool:
        return bool(cls._connector_execution_gate(connector)["allowed"])

    @classmethod
    def _connector_execution_gate(cls, connector: ConnectorSpec) -> dict[str, Any]:
        approved_sources: list[str] = []
        if connector.approved:
            approved_sources.append("connector.approved")
        if cls._truthy(connector.settings.get("approved")):
            approved_sources.append("settings.approved")
        if cls._truthy(connector.settings.get("execution_approved")):
            approved_sources.append("settings.execution_approved")

        configured = bool(resolve_webhook_url(connector.settings))
        allowed = connector.enabled and bool(approved_sources)
        reason = "allowed"
        if not connector.enabled:
            reason = "connector_disabled"
        elif not approved_sources:
            reason = "approval_required"

        return {
            "allowed": allowed,
            "status": "allowed" if allowed else "blocked",
            "reason": reason,
            "requires_approval": True,
            "connector_id": connector.id,
            "connector_type": connector.normalized_type,
            "connector_enabled": connector.enabled,
            "connector_configured": configured,
            "connector_approved": bool(approved_sources),
            "approval_sources": approved_sources,
        }

    @staticmethod
    def _truthy(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "approved"}

    def _resolve_action(self, task: AgentTask, context: dict[str, Any]) -> str:
        raw_input = task.get("input")
        task_metadata = task.get("metadata") or {}
        candidates: list[Any] = [
            task_metadata.get("action"),
            task_metadata.get("operation"),
            context.get("action"),
            context.get("operation"),
        ]
        if isinstance(raw_input, dict):
            candidates.extend([raw_input.get("action"), raw_input.get("operation")])
        candidates.extend([task.get("type"), self.config.default_action])

        for value in candidates:
            text = str(value or "").strip().lower()
            if not text:
                continue
            if "sync" in text or "同步" in text:
                return "sync"
            if "push" in text or "publish" in text or "send" in text or "推送" in text:
                return "push"
        return "push"

    def _resolve_sync_direction(self, task: AgentTask, context: dict[str, Any]) -> str:
        raw_input = task.get("input")
        task_metadata = task.get("metadata") or {}
        candidates: list[Any] = [
            task_metadata.get("sync_direction"),
            task_metadata.get("direction"),
            context.get("sync_direction"),
            context.get("direction"),
        ]
        if isinstance(raw_input, dict):
            candidates.extend([raw_input.get("sync_direction"), raw_input.get("direction")])
        for value in candidates:
            text = str(value or "").strip().lower()
            if text:
                return text
        return str(self.config.default_sync_direction or "outbound").strip().lower()

    @staticmethod
    def _request_text(task: AgentTask) -> str:
        raw_input = task.get("input")
        if isinstance(raw_input, str) and raw_input.strip():
            return raw_input.strip()
        if isinstance(raw_input, dict):
            for key in ("request", "query", "prompt", "message"):
                value = raw_input.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return str(task.get("description") or "").strip()

    def _resolve_payload(self, task: AgentTask, context: dict[str, Any]) -> Any:
        task_metadata = task.get("metadata") or {}
        raw_input = task.get("input")
        if isinstance(raw_input, dict) and "payload" in raw_input:
            return raw_input["payload"]
        if "payload" in task_metadata:
            return task_metadata["payload"]
        if "integration_payload" in context:
            return context["integration_payload"]
        if "payload" in context:
            return context["payload"]
        upstream_payload = self._upstream_payload(context)
        if upstream_payload:
            return {"upstream_results": upstream_payload}
        if isinstance(raw_input, dict):
            return {key: value for key, value in raw_input.items() if key not in self._control_keys()}
        return raw_input or task.get("description") or ""

    @staticmethod
    def _upstream_payload(context: dict[str, Any]) -> list[dict[str, Any]]:
        results = context.get("_agent_results")
        if not isinstance(results, dict):
            return []
        payload: list[dict[str, Any]] = []
        for step_id, result in results.items():
            if not isinstance(result, dict):
                continue
            payload.append(
                {
                    "step_id": str(step_id),
                    "agent": str(result.get("agent") or ""),
                    "status": str(result.get("status") or ""),
                    "output": str(result.get("output") or ""),
                    "artifacts": result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
                }
            )
        return payload

    @staticmethod
    def _control_keys() -> set[str]:
        return {
            "action",
            "operation",
            "connector",
            "connector_id",
            "connector_type",
            "channel",
            "target",
            "sync_direction",
            "direction",
            "execute",
            "execute_webhook",
            "real_execution",
            "integration_execute",
        }

    def _error_result(
        self,
        task: AgentTask,
        context: dict[str, Any],
        *,
        error: str,
        dry_run: bool = True,
        execution_requested: bool = False,
        action: str | None = None,
        approval_gate: dict[str, Any] | None = None,
    ) -> AgentResult:
        artifact = {
            "type": "integration_error",
            "title": "Integration connector error",
            "content": {
                "dry_run": dry_run,
                "execution_requested": execution_requested,
                "error": error,
                "requested_connector": self._connector_selector(task, context),
                "configured_connectors": [
                    {
                        "id": connector.id,
                        "type": connector.normalized_type,
                        "enabled": connector.enabled,
                        "approved": connector.approved,
                    }
                    for connector in self.connectors
                ],
            },
        }
        if action:
            artifact["content"]["action"] = action
        if approval_gate is not None:
            artifact["content"]["approval_gate"] = approval_gate
        metadata: dict[str, Any] = {
            **self.config.metadata,
            "context_keys": sorted(context.keys()),
            "dry_run": dry_run,
            "execution_requested": execution_requested,
            "configured_connector_count": len(self.connectors),
        }
        if approval_gate is not None:
            metadata["approval_gate"] = approval_gate
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "failed",
            "output": f"Integrator Agent failed: {error}",
            "artifacts": [artifact],
            "sources": [],
            "error": error,
            "metadata": metadata,
        }

    @staticmethod
    def _render_success_output(
        action: str,
        connector: dict[str, Any],
        artifact_content: dict[str, Any],
    ) -> str:
        summary = artifact_content.get("payload_summary", {})
        connector_name = str(connector.get("name") or connector.get("id") or "")
        connector_type = str(connector.get("type") or "")
        summary_text = ", ".join(f"{key}={value}" for key, value in summary.items())
        return "\n".join(
            [
                "Integrator Agent Dry-run",
                "",
                f"- Action: {action}",
                f"- Connector: {connector_name} ({connector_type})",
                "- Real outbound: disabled",
                f"- Payload summary: {summary_text}",
            ]
        )

    @staticmethod
    def _render_execution_output(
        action: str,
        connector: dict[str, Any],
        artifact_content: dict[str, Any],
    ) -> str:
        response = artifact_content.get("response", {})
        endpoint = artifact_content.get("endpoint", {})
        connector_name = str(connector.get("name") or connector.get("id") or "")
        connector_type = str(connector.get("type") or "")
        status_code = response.get("status_code", 0)
        response_text = f"HTTP {status_code}" if status_code else str(response.get("error") or "no status")
        lines = [
            "Integrator Agent Execution",
            "",
            f"- Action: {action}",
            f"- Connector: {connector_name} ({connector_type})",
            f"- Status: {artifact_content.get('status')}",
            f"- Endpoint: {endpoint.get('host', '')} [{endpoint.get('fingerprint', '')}]",
            f"- Response: {response_text}",
        ]
        retry = artifact_content.get("retry")
        if isinstance(retry, dict):
            lines.append(f"- Attempts: {retry.get('attempted', 0)}/{retry.get('max_attempts', 1)}")
        return "\n".join(lines)

    @staticmethod
    def _execution_error_message(
        response: WebhookExecutionResponse,
        *,
        secret_values: tuple[str, ...] = (),
    ) -> str:
        if response.error:
            return f"Webhook POST failed: {redact_secret_values(response.error, secret_values)}"
        if response.status_code:
            return f"Webhook POST failed with status {response.status_code}"
        return "Webhook POST failed without a response status."


__all__ = ["IntegratorAgent", "IntegratorAgentConfig", "ConnectorSpec"]
