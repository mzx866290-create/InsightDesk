"""Integrator connector configuration helpers."""

from __future__ import annotations

import json
import ipaddress
import socket
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.agent.agents.integrator.audit import (
    persist_integrator_outbound_audit_record,
)
from backend.agent.agents.integrator.connectors import (
    SUPPORTED_CONNECTOR_TYPES,
    ConnectorSpec,
    normalize_connector_type,
)
from backend.agent.agents.integrator.connectors.base import redact_settings
from backend.agent.agents.integrator.execution import (
    NoRedirectUrlLibWebhookClient,
    WebhookClient,
    WebhookExecutionResponse,
    build_webhook_outbound_audit_record,
    collect_webhook_secret_values,
    endpoint_info,
    post_webhook_with_retry,
    redact_secret_values,
    resolve_webhook_headers,
    resolve_webhook_hmac_headers,
    resolve_webhook_url,
    summarize_webhook_response,
    validate_webhook_url,
)

INTEGRATOR_CONNECTORS_CONFIG_KEY = "integrator_connectors"
INTEGRATOR_SCHEDULES_CONFIG_KEY = "integrator_schedules"
_REDACTED = "***redacted***"
_DEFAULT_SCHEDULE_INTERVAL_MINUTES = 60
_MIN_SCHEDULE_INTERVAL_MINUTES = 5
_MAX_SCHEDULE_INTERVAL_MINUTES = 60 * 24 * 30
_DEFAULT_SCHEDULE_TIMEZONE = "UTC"
_DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS = 3.0
_MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS = 0.1
_MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS = 10.0
_CRON_LOOKAHEAD_MINUTES = 366 * 24 * 60 * 5
_CRON_FIELD_RANGES = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day_of_month", 1, 31),
    ("month", 1, 12),
    ("day_of_week", 0, 7),
)
_CRON_MONTH_ALIASES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_CRON_WEEKDAY_ALIASES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}
_CRON_MACROS = {
    "@HOURLY": "0 * * * *",
    "@DAILY": "0 0 * * *",
    "@MIDNIGHT": "0 0 * * *",
    "@WEEKLY": "0 0 * * 0",
    "@MONTHLY": "0 0 1 * *",
    "@YEARLY": "0 0 1 1 *",
    "@ANNUALLY": "0 0 1 1 *",
}
_BLOCKED_EXTERNAL_PROBE_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-authorization",
    "te",
    "transfer-encoding",
    "upgrade",
}


def integrator_connectors_payload(config_store: Any) -> dict[str, Any]:
    connectors = load_integrator_connectors(config_store)
    public_connectors = [connector_to_public_config(connector) for connector in connectors]
    return {
        "connectors": public_connectors,
        "total": len(public_connectors),
        "supported_types": list(SUPPORTED_CONNECTOR_TYPES),
        "persistence": {
            "enabled": True,
            "config_key": INTEGRATOR_CONNECTORS_CONFIG_KEY,
            "sensitive_fields_redacted": True,
        },
    }


def save_integrator_connectors_payload(
    config_store: Any,
    raw_connectors: list[Any],
) -> dict[str, Any]:
    if not isinstance(raw_connectors, list):
        raise ValueError("connectors must be a list")

    previous_by_id = {
        connector.id: connector for connector in load_integrator_connectors(config_store)
    }
    connectors = [
        normalize_integrator_connector(
            item,
            previous=previous_by_id.get(str((item or {}).get("id") or "").strip())
            if isinstance(item, Mapping)
            else None,
        )
        for item in raw_connectors
    ]

    serialized = [connector_to_config(connector) for connector in connectors]
    if serialized:
        config_store.set(
            INTEGRATOR_CONNECTORS_CONFIG_KEY,
            json.dumps(serialized, ensure_ascii=False, sort_keys=True),
        )
    else:
        config_store.delete(INTEGRATOR_CONNECTORS_CONFIG_KEY)
    return integrator_connectors_payload(config_store)


def load_integrator_connectors(config_store: Any) -> tuple[ConnectorSpec, ...]:
    raw_value = str(
        config_store.get_value(INTEGRATOR_CONNECTORS_CONFIG_KEY, "") or ""
    ).strip()
    if not raw_value:
        return ()
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("stored integrator connector config is not valid JSON") from exc
    if not isinstance(decoded, list):
        raise ValueError("stored integrator connector config must be a list")
    return tuple(normalize_integrator_connector(item) for item in decoded)


def normalize_integrator_connector(
    raw_connector: Any,
    *,
    previous: ConnectorSpec | None = None,
) -> ConnectorSpec:
    if isinstance(raw_connector, ConnectorSpec):
        connector = raw_connector
    elif isinstance(raw_connector, Mapping):
        connector = ConnectorSpec.from_mapping(dict(raw_connector))
    else:
        raise ValueError("connector entries must be objects")

    connector_type = normalize_connector_type(connector.type)
    if connector_type not in SUPPORTED_CONNECTOR_TYPES:
        raise ValueError(f"unsupported connector type: {connector.type}")
    if not str(connector.id or "").strip():
        raise ValueError("connector id is required")

    connector.id = str(connector.id).strip()
    connector.type = connector_type
    connector.name = str(connector.name or "").strip()
    connector.description = str(connector.description or "").strip()
    connector.settings = _merge_redacted_settings(
        dict(connector.settings or {}),
        dict(previous.settings or {}) if previous is not None else {},
    )
    return connector


def connector_to_config(connector: ConnectorSpec) -> dict[str, Any]:
    payload = {
        "type": connector.normalized_type,
        "name": connector.name,
        "description": connector.description,
        "enabled": bool(connector.enabled),
        "approved": bool(connector.approved),
        "settings": dict(connector.settings or {}),
    }
    if connector.id and connector.id not in {connector.name, connector.normalized_type}:
        payload["id"] = connector.id
    if not payload["name"]:
        payload.pop("name")
    if not payload["description"]:
        payload.pop("description")
    return payload


def connector_to_public_config(connector: ConnectorSpec) -> dict[str, Any]:
    payload = connector_to_config(connector)
    payload["settings"] = redact_settings(dict(connector.settings or {}))
    return payload


def test_integrator_connector_payload(raw_connector: Any) -> dict[str, Any]:
    connector = normalize_integrator_connector(raw_connector)
    checks = _build_connector_checks(connector)
    blocking_failures = [
        check for check in checks if check["severity"] == "error" and not check["ok"]
    ]
    warnings = [
        check for check in checks if check["severity"] == "warning" and not check["ok"]
    ]
    status = "ready" if not blocking_failures and not warnings else "warning"
    if blocking_failures:
        status = "blocked"
    return {
        "ok": not blocking_failures,
        "status": status,
        "dry_run": True,
        "executed": False,
        "connector": connector_to_public_config(connector),
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "failed_count": sum(1 for check in checks if not check["ok"]),
            "blocking_failure_count": len(blocking_failures),
            "warning_count": len(warnings),
        },
    }


def rotate_integrator_connector_credentials_payload(
    config_store: Any,
    connector_id: str,
    raw_patch: Any,
) -> dict[str, Any]:
    if not isinstance(raw_patch, Mapping):
        raise ValueError("credential rotation payload must be an object")

    disallowed_fields = sorted(
        str(key)
        for key in raw_patch
        if str(key) not in {"settings", "credentials"}
    )
    if disallowed_fields:
        raise ValueError(
            "credential rotation only accepts settings or credentials patches: "
            + ", ".join(disallowed_fields)
        )

    settings_patch = raw_patch.get("settings") or {}
    credentials_patch = raw_patch.get("credentials") or {}
    if not isinstance(settings_patch, Mapping):
        raise ValueError("settings patch must be an object")
    if not isinstance(credentials_patch, Mapping):
        raise ValueError("credentials patch must be an object")
    if not settings_patch and not credentials_patch:
        raise ValueError("credential rotation patch cannot be empty")

    patch = _deep_merge_settings_patch(dict(settings_patch), dict(credentials_patch))
    connectors = list(load_integrator_connectors(config_store))
    target_index, target = _find_connector_by_id(connectors, connector_id)
    merged_settings, summary = _merge_credential_rotation_settings(
        dict(target.settings or {}),
        patch,
    )

    connectors[target_index] = ConnectorSpec(
        id=target.id,
        type=target.normalized_type,
        name=target.name,
        description=target.description,
        enabled=target.enabled,
        approved=target.approved,
        settings=merged_settings,
    )
    serialized = [connector_to_config(connector) for connector in connectors]
    config_store.set(
        INTEGRATOR_CONNECTORS_CONFIG_KEY,
        json.dumps(serialized, ensure_ascii=False, sort_keys=True),
    )
    public_connector = connector_to_public_config(connectors[target_index])
    return {
        "ok": True,
        "status": "rotated",
        "connector": public_connector,
        "rotated_fields": summary["rotated_fields"],
        "preserved_fields": summary["preserved_fields"],
        "summary": {
            "connector_id": public_connector.get("id") or connector_id,
            "rotated_count": len(summary["rotated_fields"]),
            "preserved_count": len(summary["preserved_fields"]),
            "sensitive_fields_redacted": True,
        },
    }


async def probe_integrator_connector_payload(
    config_store: Any,
    connector_id: str,
    raw_options: Any | None = None,
    *,
    webhook_client: WebhookClient | None = None,
) -> dict[str, Any]:
    connectors = list(load_integrator_connectors(config_store))
    _target_index, target = _find_connector_by_id(connectors, connector_id)
    options = _normalize_probe_options(raw_options)
    mode = options["mode"]
    result = test_integrator_connector_payload(connector_to_config(target))
    result["connector"] = connector_to_public_config(target)
    result["summary"]["connector_id"] = result["connector"].get("id") or connector_id
    result["summary"]["sensitive_fields_redacted"] = True
    if mode == "static":
        result["dry_run"] = True
        result["executed"] = False
        result["probe"] = {
            "mode": "static",
            "outbound_request_sent": False,
        }
        result["summary"]["probe_mode"] = "static"
        return result

    external_result = await _external_probe_integrator_connector_payload(
        target,
        base_result=result,
        timeout_seconds=options["timeout_seconds"],
        webhook_client=webhook_client,
    )
    external_result["summary"]["probe_mode"] = "external"
    return external_result


async def _external_probe_integrator_connector_payload(
    connector: ConnectorSpec,
    *,
    base_result: dict[str, Any],
    timeout_seconds: float,
    webhook_client: WebhookClient | None,
) -> dict[str, Any]:
    result = dict(base_result)
    checks = list(result.get("checks") or [])
    result["dry_run"] = False
    result["executed"] = False
    result["probe"] = {
        "mode": "external",
        "outbound_request_sent": False,
        "timeout_seconds": timeout_seconds,
        "target_policy": {
            "allowed_schemes": ["https"],
            "public_network_only": True,
        },
    }

    external_checks = _build_external_probe_checks(
        connector,
        timeout_seconds=timeout_seconds,
    )
    checks.extend(external_checks)
    result["checks"] = checks
    blocking_failures = [
        check for check in checks if check["severity"] == "error" and not check["ok"]
    ]
    warnings = [
        check for check in checks if check["severity"] == "warning" and not check["ok"]
    ]
    if blocking_failures:
        result["ok"] = False
        result["status"] = "blocked"
        result["summary"] = _probe_summary(result, blocking_failures, warnings)
        return result

    webhook_url = resolve_webhook_url(connector.settings)
    endpoint = endpoint_info(webhook_url)
    result["probe"]["endpoint"] = endpoint
    secret_values = collect_webhook_secret_values(connector.settings)
    payload = _external_probe_request_payload(connector)
    headers, signing_summary, signing_error = resolve_webhook_hmac_headers(
        connector.settings,
        payload,
    )
    if signing_error:
        checks.append(
            _check(
                "external_probe_signing",
                False,
                "Webhook signing configuration is valid.",
                failed_message=signing_error,
            )
        )
        result["ok"] = False
        result["status"] = "blocked"
        result["summary"] = _probe_summary(result, [checks[-1]], warnings)
        return result

    headers = {
        **_safe_external_probe_headers(resolve_webhook_headers(connector.settings)),
        **headers,
    }
    response, retry_summary = await post_webhook_with_retry(
        webhook_client or NoRedirectUrlLibWebhookClient(),
        webhook_url,
        payload,
        headers=headers,
        timeout_seconds=timeout_seconds,
        max_attempts=1,
        backoff_seconds=0.0,
    )
    result["executed"] = True
    result["probe"]["outbound_request_sent"] = True
    result["probe"]["response"] = summarize_webhook_response(
        response,
        secret_values=secret_values,
    )
    result["probe"]["retry"] = retry_summary
    if signing_summary:
        result["probe"]["signing"] = signing_summary

    checks.append(
        _check(
            "external_probe_response",
            response.ok,
            "External probe received a successful response.",
            failed_message=_external_probe_response_failure_message(
                response,
                secret_values=secret_values,
            ),
        )
    )
    blocking_failures = [
        check for check in checks if check["severity"] == "error" and not check["ok"]
    ]
    result["ok"] = not blocking_failures
    result["status"] = "ready" if result["ok"] and not warnings else "warning"
    if blocking_failures:
        result["status"] = "blocked"
    result["summary"] = _probe_summary(result, blocking_failures, warnings)
    _persist_external_probe_audit(
        connector,
        endpoint=endpoint,
        payload=payload,
        response=response,
        retry_summary=retry_summary,
        signing_summary=signing_summary,
        secret_values=secret_values,
    )
    return result


def integrator_schedules_payload(config_store: Any) -> dict[str, Any]:
    schedules = load_integrator_schedules(config_store)
    public_schedules = [schedule_to_public_config(schedule) for schedule in schedules]
    return {
        "schedules": public_schedules,
        "total": len(public_schedules),
        "persistence": {
            "enabled": True,
            "config_key": INTEGRATOR_SCHEDULES_CONFIG_KEY,
            "sensitive_fields_redacted": True,
        },
        "scheduler": {
            "mode": "configured",
            "automatic_dispatch": False,
            "manual_trigger_supported": True,
        },
    }


def save_integrator_schedules_payload(
    config_store: Any,
    raw_schedules: list[Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_schedules, list):
        raise ValueError("schedules must be a list")

    previous_by_id = {
        schedule["id"]: schedule for schedule in load_integrator_schedules(config_store)
    }
    timestamp = float(now if now is not None else time.time())
    schedules = [
        normalize_integrator_schedule(
            item,
            previous=previous_by_id.get(_schedule_identity(item))
            if isinstance(item, Mapping)
            else None,
            now=timestamp,
        )
        for item in raw_schedules
    ]

    serialized = [schedule_to_config(schedule) for schedule in schedules]
    if serialized:
        config_store.set(
            INTEGRATOR_SCHEDULES_CONFIG_KEY,
            json.dumps(serialized, ensure_ascii=False, sort_keys=True),
        )
    else:
        config_store.delete(INTEGRATOR_SCHEDULES_CONFIG_KEY)
    return integrator_schedules_payload(config_store)


def load_integrator_schedules(config_store: Any) -> tuple[dict[str, Any], ...]:
    raw_value = str(
        config_store.get_value(INTEGRATOR_SCHEDULES_CONFIG_KEY, "") or ""
    ).strip()
    if not raw_value:
        return ()
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("stored integrator schedule config is not valid JSON") from exc
    if not isinstance(decoded, list):
        raise ValueError("stored integrator schedule config must be a list")
    return tuple(normalize_integrator_schedule(item) for item in decoded)


def normalize_integrator_schedule(
    raw_schedule: Any,
    *,
    previous: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_schedule, Mapping):
        raise ValueError("schedule entries must be objects")

    schedule = dict(raw_schedule)
    schedule_id = str(
        schedule.get("id") or schedule.get("schedule_id") or schedule.get("name") or ""
    ).strip()
    if not schedule_id:
        raise ValueError("schedule id is required")
    connector_id = str(schedule.get("connector_id") or schedule.get("connector") or "").strip()
    if not connector_id:
        raise ValueError("schedule connector_id is required")

    interval_minutes = _safe_interval_minutes(schedule.get("interval_minutes"))
    cron = str(schedule.get("cron") or schedule.get("cron_expression") or "").strip()
    timezone_name = _normalize_schedule_timezone(schedule.get("timezone"))
    if cron:
        _parse_cron_expression(cron)
    timestamp = float(now if now is not None else time.time())
    previous_next_run_at = _safe_float(
        schedule.get("next_run_at")
        if schedule.get("next_run_at") is not None
        else (previous or {}).get("next_run_at")
    )
    if cron and now is not None:
        next_run_at = _next_cron_run_at(timestamp, cron, timezone_name)
    elif cron:
        next_run_at = previous_next_run_at or _next_cron_run_at(
            timestamp,
            cron,
            timezone_name,
        )
    else:
        next_run_at = previous_next_run_at or _next_run_at(timestamp, interval_minutes)
    last_triggered_at = _safe_float(
        schedule.get("last_triggered_at")
        if schedule.get("last_triggered_at") is not None
        else schedule.get("last_run_at")
        if schedule.get("last_run_at") is not None
        else (previous or {}).get("last_triggered_at")
    )

    raw_payload = (
        schedule.get("payload")
        if isinstance(schedule.get("payload"), Mapping)
        else schedule.get("settings")
        if isinstance(schedule.get("settings"), Mapping)
        else {}
    )
    previous_payload = (
        previous.get("payload")
        if isinstance((previous or {}).get("payload"), Mapping)
        else previous.get("settings")
        if isinstance((previous or {}).get("settings"), Mapping)
        else {}
    ) if previous is not None else {}
    payload = _merge_redacted_settings(dict(raw_payload), dict(previous_payload))
    has_context = "context" in schedule
    raw_context = schedule.get("context") if isinstance(schedule.get("context"), Mapping) else {}
    previous_context = (
        previous.get("context")
        if isinstance((previous or {}).get("context"), Mapping)
        else {}
    ) if previous is not None else {}
    context = (
        _merge_redacted_settings(dict(raw_context), dict(previous_context))
        if has_context
        else dict(previous_context)
    )
    return {
        "id": schedule_id,
        "schedule_id": schedule_id,
        "name": str(schedule.get("name") or schedule_id).strip(),
        "description": str(schedule.get("description") or "").strip(),
        "enabled": bool(schedule.get("enabled", True)),
        "connector_id": connector_id,
        "action": _normalize_schedule_action(schedule.get("action")),
        "cron": cron,
        "timezone": timezone_name,
        "interval_minutes": interval_minutes,
        "next_run_at": next_run_at,
        "last_triggered_at": last_triggered_at,
        "last_run_at": last_triggered_at,
        "trigger_count": max(0, int(schedule.get("trigger_count") or (previous or {}).get("trigger_count") or 0)),
        "payload": dict(payload),
        "settings": dict(payload),
        "context": dict(context),
    }


def schedule_to_config(schedule: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "id": str(schedule.get("id") or "").strip(),
        "schedule_id": str(schedule.get("id") or schedule.get("schedule_id") or "").strip(),
        "name": str(schedule.get("name") or "").strip(),
        "description": str(schedule.get("description") or "").strip(),
        "enabled": bool(schedule.get("enabled", True)),
        "connector_id": str(schedule.get("connector_id") or "").strip(),
        "action": _normalize_schedule_action(schedule.get("action")),
        "cron": str(schedule.get("cron") or "").strip(),
        "timezone": _normalize_schedule_timezone(schedule.get("timezone")),
        "interval_minutes": _safe_interval_minutes(schedule.get("interval_minutes")),
        "next_run_at": _safe_float(schedule.get("next_run_at")),
        "last_triggered_at": _safe_float(schedule.get("last_triggered_at")),
        "last_run_at": _safe_float(schedule.get("last_run_at") or schedule.get("last_triggered_at")),
        "trigger_count": max(0, int(schedule.get("trigger_count") or 0)),
        "payload": dict(schedule.get("payload") or {})
        if isinstance(schedule.get("payload"), Mapping)
        else {},
        "settings": dict(schedule.get("settings") or schedule.get("payload") or {})
        if isinstance(schedule.get("settings") or schedule.get("payload"), Mapping)
        else {},
        "context": dict(schedule.get("context") or {})
        if isinstance(schedule.get("context"), Mapping)
        else {},
    }
    if not payload["description"]:
        payload.pop("description")
    if payload["last_triggered_at"] <= 0:
        payload.pop("last_triggered_at")
    if payload["last_run_at"] <= 0:
        payload.pop("last_run_at")
    return payload


def schedule_to_public_config(schedule: Mapping[str, Any]) -> dict[str, Any]:
    payload = schedule_to_config(schedule)
    payload["payload"] = redact_settings(dict(payload.get("payload") or {}))
    payload["settings"] = redact_settings(dict(payload.get("settings") or {}))
    payload["context"] = redact_settings(dict(payload.get("context") or {}))
    return payload


def trigger_integrator_schedule_payload(
    config_store: Any,
    schedule_id: str,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    normalized_id = str(schedule_id or "").strip()
    if not normalized_id:
        raise ValueError("schedule id is required")

    timestamp = float(now if now is not None else time.time())
    schedules = list(load_integrator_schedules(config_store))
    selected_index = next(
        (index for index, schedule in enumerate(schedules) if schedule["id"] == normalized_id),
        -1,
    )
    if selected_index < 0:
        raise KeyError(normalized_id)

    schedule = dict(schedules[selected_index])
    schedule["last_triggered_at"] = timestamp
    schedule["last_run_at"] = timestamp
    schedule["trigger_count"] = max(0, int(schedule.get("trigger_count") or 0)) + 1
    schedule["next_run_at"] = _next_schedule_run_at(timestamp, schedule)
    schedules[selected_index] = schedule
    config_store.set(
        INTEGRATOR_SCHEDULES_CONFIG_KEY,
        json.dumps([schedule_to_config(item) for item in schedules], ensure_ascii=False, sort_keys=True),
    )

    task_params = _schedule_task_params(schedule)
    return {
        "ok": True,
        "status": "triggered",
        "schedule_id": normalized_id,
        "triggered_at": timestamp,
        "dry_run": True,
        "executed": False,
        "schedule": schedule_to_public_config(schedule),
        "would_create_task": {
            "task_type": "multi_agent_workflow",
            "params": task_params,
        },
        "message": "Schedule trigger recorded; automatic dispatch is not enabled in this runtime.",
    }


def tick_integrator_schedules_payload(
    config_store: Any,
    *,
    dry_run: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    timestamp = float(now if now is not None else time.time())
    schedules = list(load_integrator_schedules(config_store))
    due_items: list[dict[str, Any]] = []
    skipped_disabled = 0
    skipped_not_due = 0

    for schedule in schedules:
        if not bool(schedule.get("enabled", True)):
            skipped_disabled += 1
            continue
        next_run_at = _safe_float(schedule.get("next_run_at"))
        if next_run_at > timestamp:
            skipped_not_due += 1
            continue

        if dry_run:
            public_schedule = schedule_to_public_config(schedule)
            due_items.append(
                {
                    "schedule_id": str(schedule.get("id") or "").strip(),
                    "schedule": public_schedule,
                    "would_create_task": {
                        "task_type": "multi_agent_workflow",
                        "params": _schedule_task_params(schedule),
                    },
                }
            )
            continue

        # Reuse the single-schedule trigger path so state transitions stay identical.
        due_items.append(
            trigger_integrator_schedule_payload(
                config_store,
                str(schedule.get("id") or "").strip(),
                now=timestamp,
            )
        )

    return {
        "ok": True,
        "status": "ok",
        "dry_run": bool(dry_run),
        "executed": False,
        "checked": len(schedules),
        "due_count": len(due_items),
        "due": due_items,
        "skipped": {
            "disabled": skipped_disabled,
            "not_due": skipped_not_due,
        },
        "now": timestamp,
    }


def _normalize_probe_options(raw_options: Any | None) -> dict[str, Any]:
    if raw_options is None:
        raw_options = {}
    if not isinstance(raw_options, Mapping):
        raise ValueError("probe options must be an object")
    nested_probe = raw_options.get("probe")
    options = dict(nested_probe) if isinstance(nested_probe, Mapping) else dict(raw_options)
    raw_mode = options.get("mode")
    if raw_mode is None and bool(options.get("external")):
        raw_mode = "external"
    mode = str(raw_mode or "static").strip().lower()
    if mode not in {"static", "external"}:
        raise ValueError("probe mode must be static or external")
    return {
        "mode": mode,
        "timeout_seconds": _external_probe_timeout_seconds(
            options.get("timeout_seconds"),
        ) if mode == "external" else _DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS,
    }


def _external_probe_timeout_seconds(value: Any) -> float:
    if value is None:
        return _DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("external probe timeout_seconds must be a number") from exc
    if timeout_seconds < _MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS:
        raise ValueError("external probe timeout_seconds must be at least 0.1 seconds")
    if timeout_seconds > _MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS:
        raise ValueError("external probe timeout_seconds must be at most 10 seconds")
    return timeout_seconds


def _build_external_probe_checks(
    connector: ConnectorSpec,
    *,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    webhook_url = resolve_webhook_url(connector.settings)
    url_error = validate_webhook_url(webhook_url)
    target_error = "" if url_error else _validate_external_probe_target(webhook_url)
    return [
        _check(
            "external_probe_opt_in",
            True,
            "External probe was explicitly requested.",
        ),
        _check(
            "external_probe_supported",
            connector.normalized_type == "webhook",
            "Connector type supports controlled external probes.",
            failed_message="Controlled external probes are only supported for webhook connectors.",
        ),
        _check(
            "external_probe_enabled",
            connector.enabled,
            "Connector is enabled for external probing.",
            failed_message="Connector must be enabled before an external probe can run.",
        ),
        _check(
            "external_probe_approved",
            connector.approved,
            "Connector is approved for external probing.",
            failed_message="Connector must be approved before an external probe can run.",
        ),
        _check(
            "external_probe_timeout",
            _MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS <= timeout_seconds <= _MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS,
            "External probe timeout is within the controlled range.",
            failed_message="External probe timeout is outside the controlled range.",
        ),
        _check(
            "external_probe_target",
            not url_error and not target_error,
            "External probe target passed protocol and public-network restrictions.",
            failed_message=url_error or target_error,
        ),
    ]


def _validate_external_probe_target(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        return "External probe target must use https."
    if parsed.username or parsed.password:
        return "External probe target must not include user info."
    if parsed.fragment:
        return "External probe target must not include a fragment."
    host = parsed.hostname or ""
    if not host:
        return "External probe target must include a host."
    if host.lower() in {"localhost"} or host.lower().endswith(".localhost"):
        return "External probe target must use a public host."
    addresses_error = _validate_external_probe_addresses(host, parsed.port or 443)
    if addresses_error:
        return addresses_error
    return ""


def _validate_external_probe_addresses(host: str, port: int) -> str:
    try:
        literal_ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        return "" if literal_ip.is_global else "External probe target must resolve to public IP addresses."

    try:
        address_info = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        return "External probe target host could not be resolved."
    addresses = {
        item[4][0]
        for item in address_info
        if len(item) >= 5 and item[4] and item[4][0]
    }
    if not addresses:
        return "External probe target host could not be resolved."
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(str(address).strip("[]"))
        except ValueError:
            return "External probe target resolved to an invalid address."
        if not parsed_address.is_global:
            return "External probe target must resolve to public IP addresses."
    return ""


def _safe_external_probe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    safe_headers: dict[str, str] = {}
    for key, value in headers.items():
        key_text = str(key or "").strip()
        value_text = str(value)
        normalized_key = key_text.lower()
        if (
            not key_text
            or normalized_key in _BLOCKED_EXTERNAL_PROBE_HEADERS
            or "\r" in key_text
            or "\n" in key_text
            or "\r" in value_text
            or "\n" in value_text
        ):
            continue
        safe_headers[key_text] = value_text
    return safe_headers


def _external_probe_request_payload(connector: ConnectorSpec) -> dict[str, Any]:
    return {
        "event": "integrator.connector.probe",
        "connector_id": connector.id,
        "connector_type": connector.normalized_type,
        "mode": "external",
        "timestamp": int(time.time()),
    }


def _external_probe_response_failure_message(
    response: WebhookExecutionResponse,
    *,
    secret_values: tuple[str, ...],
) -> str:
    if response.error:
        return redact_secret_values(
            f"External probe failed: {response.error}",
            secret_values,
        )
    return f"External probe returned HTTP {response.status_code}."


def _persist_external_probe_audit(
    connector: ConnectorSpec,
    *,
    endpoint: dict[str, Any],
    payload: dict[str, Any],
    response: WebhookExecutionResponse,
    retry_summary: Mapping[str, Any],
    signing_summary: Mapping[str, Any],
    secret_values: tuple[str, ...],
) -> None:
    record = build_webhook_outbound_audit_record(
        task_id=f"probe:{connector.id}",
        action="probe",
        connector=connector_to_config(connector),
        endpoint=endpoint,
        payload=payload,
        response=response,
        retry_summary=retry_summary,
        signing_summary=signing_summary,
        secret_values=secret_values,
    )
    record["event"] = "integrator.connector.probe"
    record["probe"] = {
        "mode": "external",
        "outbound_request_sent": True,
    }
    persist_integrator_outbound_audit_record(record)


def _probe_summary(
    result: Mapping[str, Any],
    blocking_failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = result.get("checks") if isinstance(result.get("checks"), list) else []
    summary = dict(result.get("summary") or {})
    summary.update(
        {
            "check_count": len(checks),
            "failed_count": sum(1 for check in checks if not check.get("ok")),
            "blocking_failure_count": len(blocking_failures),
            "warning_count": len(warnings),
            "sensitive_fields_redacted": True,
        }
    )
    return summary


def _build_connector_checks(connector: ConnectorSpec) -> list[dict[str, Any]]:
    checks = [
        _check("type_supported", True, "Connector type is supported."),
        _check(
            "enabled",
            connector.enabled,
            "Connector is enabled.",
            failed_message="Connector is disabled.",
            severity="warning",
        ),
        _check(
            "approved",
            connector.approved,
            "Connector is approved for real execution.",
            failed_message="Connector is not approved for real execution.",
            severity="warning",
        ),
    ]
    if connector.normalized_type == "webhook":
        webhook_url = resolve_webhook_url(connector.settings)
        validation_error = validate_webhook_url(webhook_url)
        checks.append(
            _check(
                "webhook_url",
                not validation_error,
                "Webhook URL is configured and valid.",
                failed_message=validation_error or "Webhook URL is invalid.",
            )
        )
        checks.append(
            _check(
                "real_outbound",
                True,
                "Dry-run only; no outbound request was sent.",
            )
        )
    elif connector.normalized_type == "email":
        recipients = connector.settings.get("to") or connector.settings.get("recipients")
        recipient_count = len(recipients) if isinstance(recipients, list) else int(bool(recipients))
        checks.append(
            _check(
                "email_recipients",
                recipient_count > 0,
                "Email recipients are configured.",
                failed_message="Email connector requires at least one recipient.",
            )
        )
    elif connector.normalized_type in {"feishu", "dingtalk"}:
        configured = any(
            str(connector.settings.get(key) or "").strip()
            for key in ("webhook_url", "url", "app_id", "robot_code")
        )
        checks.append(
            _check(
                "chatops_endpoint",
                configured,
                "ChatOps endpoint or app identity is configured.",
                failed_message="ChatOps connector requires an endpoint or app identity.",
            )
        )
    return checks


def _schedule_task_params(schedule: Mapping[str, Any]) -> dict[str, Any]:
    connector_id = str(schedule.get("connector_id") or "").strip()
    action = _normalize_schedule_action(schedule.get("action"))
    return {
        "user_request": (
            f"Run scheduled Integrator {action} for connector {connector_id}."
        ),
        "context": {
            "schedule_id": str(schedule.get("id") or "").strip(),
            "connector": connector_id,
            "action": action,
            "payload": schedule_to_public_config(schedule).get("payload", {}),
        },
        "plan": [
            {
                "id": "integrator_scheduled_sync",
                "agent": "integrator",
                "task_type": "integration_sync" if action == "sync" else "integration_push",
                "description": "Run scheduled Integrator handoff",
                "input": {
                    "connector": connector_id,
                    "action": action,
                    "payload": schedule_to_public_config(schedule).get("payload", {}),
                },
            }
        ],
    }


def _schedule_identity(schedule: Mapping[str, Any]) -> str:
    return str(schedule.get("id") or schedule.get("schedule_id") or "").strip()


def _normalize_schedule_action(value: Any) -> str:
    normalized = str(value or "sync").strip().lower()
    return normalized if normalized in {"sync", "push"} else "sync"


def _safe_interval_minutes(value: Any) -> int:
    try:
        interval = int(value or _DEFAULT_SCHEDULE_INTERVAL_MINUTES)
    except (TypeError, ValueError):
        interval = _DEFAULT_SCHEDULE_INTERVAL_MINUTES
    return max(_MIN_SCHEDULE_INTERVAL_MINUTES, min(_MAX_SCHEDULE_INTERVAL_MINUTES, interval))


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _next_run_at(now: float, interval_minutes: int) -> float:
    return float(now) + (_safe_interval_minutes(interval_minutes) * 60)


def _next_schedule_run_at(now: float, schedule: Mapping[str, Any]) -> float:
    cron = str(schedule.get("cron") or "").strip()
    if cron:
        return _next_cron_run_at(
            now,
            cron,
            _normalize_schedule_timezone(schedule.get("timezone")),
            skip_local_slot_at=_safe_float(schedule.get("last_triggered_at")),
        )
    return _next_run_at(now, _safe_interval_minutes(schedule.get("interval_minutes")))


def _normalize_schedule_timezone(value: Any) -> str:
    timezone_name = str(value or _DEFAULT_SCHEDULE_TIMEZONE).strip()
    if not timezone_name:
        timezone_name = _DEFAULT_SCHEDULE_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(
            "schedule timezone must be a valid IANA timezone"
        ) from exc
    return timezone_name


def _parse_cron_expression(expression: str) -> tuple[tuple[set[int], bool], ...]:
    fields = _expand_cron_expression(expression).split()
    if len(fields) != 5:
        raise ValueError("cron must contain 5 fields")
    return tuple(
        _parse_cron_field(value, field_name, minimum, maximum)
        for value, (field_name, minimum, maximum) in zip(fields, _CRON_FIELD_RANGES)
    )


def _expand_cron_expression(expression: str) -> str:
    value = str(expression or "").strip()
    if not value:
        return value
    if value.startswith("@"):
        expanded = _CRON_MACROS.get(value.upper())
        if not expanded:
            raise ValueError(
                "cron macro must be one of @hourly, @daily, @weekly, @monthly, @yearly, @annually, or @midnight"
            )
        return expanded
    return value


def _parse_cron_field(
    raw_value: str,
    field_name: str,
    minimum: int,
    maximum: int,
) -> tuple[set[int], bool]:
    raw_text = str(raw_value or "").strip()
    if raw_text == "?":
        if field_name not in {"day_of_month", "day_of_week"}:
            raise ValueError("cron ? is only supported for day_of_month or day_of_week")
        return set(range(minimum, maximum + 1)), True
    if "?" in raw_text:
        raise ValueError("cron ? must be the entire day_of_month or day_of_week field")

    values: set[int] = set()
    wildcard = True
    for part in raw_text.split(","):
        token = part.strip()
        if not token:
            raise ValueError(f"cron {field_name} contains an empty segment")
        token_values, token_wildcard = _parse_cron_token(
            token,
            field_name,
            minimum,
            maximum,
        )
        values.update(token_values)
        wildcard = wildcard and token_wildcard
    if not values:
        raise ValueError(f"cron {field_name} has no allowed values")
    if field_name == "day_of_week" and 7 in values:
        values.add(0)
        values.discard(7)
    return values, wildcard


def _parse_cron_token(
    token: str,
    field_name: str,
    minimum: int,
    maximum: int,
) -> tuple[set[int], bool]:
    base = token
    step = 1
    if "/" in token:
        base, raw_step = token.split("/", 1)
        if not raw_step.isdigit():
            raise ValueError(f"cron {field_name} step must be a positive integer")
        step = int(raw_step)
        if step <= 0:
            raise ValueError(f"cron {field_name} step must be greater than 0")
        if step > (maximum - minimum + 1):
            raise ValueError(f"cron {field_name} step is larger than its value range")

    if base == "*":
        start, end = minimum, maximum
        wildcard = True
    elif "-" in base:
        raw_start, raw_end = base.split("-", 1)
        start = _parse_cron_value(raw_start, field_name, minimum, maximum)
        end = _parse_cron_value(raw_end, field_name, minimum, maximum)
        if start > end:
            raise ValueError(f"cron {field_name} range start must be <= end")
        wildcard = False
    elif base:
        if "/" in token:
            raise ValueError(f"cron {field_name} step requires * or a range")
        start = end = _parse_cron_value(base, field_name, minimum, maximum)
        wildcard = False
    else:
        raise ValueError(f"cron {field_name} contains an unsupported token")

    return set(range(start, end + 1, step)), wildcard


def _parse_cron_value(
    raw_value: str,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    normalized = str(raw_value or "").strip().upper()
    alias = _cron_alias_value(normalized, field_name)
    if alias is not None:
        return alias
    if not normalized.isdigit():
        raise ValueError(f"cron {field_name} value must be an integer")
    value = int(normalized)
    if value < minimum or value > maximum:
        raise ValueError(
            f"cron {field_name} value must be between {minimum} and {maximum}"
        )
    return value


def _cron_alias_value(raw_value: str, field_name: str) -> int | None:
    if field_name == "month":
        return _CRON_MONTH_ALIASES.get(raw_value)
    if field_name == "day_of_week":
        return _CRON_WEEKDAY_ALIASES.get(raw_value)
    return None


def _next_cron_run_at(
    now: float,
    expression: str,
    timezone_name: str = _DEFAULT_SCHEDULE_TIMEZONE,
    *,
    skip_local_slot_at: float | None = None,
) -> float:
    minute, hour, day_of_month, month, day_of_week = _parse_cron_expression(expression)
    timezone_info = ZoneInfo(_normalize_schedule_timezone(timezone_name))
    skipped_local_slot = _cron_local_slot_key(skip_local_slot_at, timezone_info)
    start = (int(float(now)) // 60) * 60 + 60
    for offset_minutes in range(_CRON_LOOKAHEAD_MINUTES):
        candidate = start + (offset_minutes * 60)
        current = datetime.fromtimestamp(candidate, timezone_info)
        cron_day_of_week = (current.weekday() + 1) % 7
        if current.minute not in minute[0]:
            continue
        if current.hour not in hour[0]:
            continue
        if current.month not in month[0]:
            continue
        if not _cron_day_matches(
            current.day,
            cron_day_of_week,
            day_of_month,
            day_of_week,
        ):
            continue
        if skipped_local_slot and _cron_local_slot_key(candidate, timezone_info) == skipped_local_slot:
            continue
        return float(candidate)
    raise ValueError("cron has no matching run in the next 5 years")


def _cron_local_slot_key(
    timestamp: float | None,
    timezone_info: ZoneInfo,
) -> tuple[int, int, int, int, int] | None:
    if not timestamp:
        return None
    current = datetime.fromtimestamp(float(timestamp), timezone_info)
    return (current.year, current.month, current.day, current.hour, current.minute)


def _cron_day_matches(
    day_of_month: int,
    day_of_week: int,
    configured_day_of_month: tuple[set[int], bool],
    configured_day_of_week: tuple[set[int], bool],
) -> bool:
    month_days, month_wildcard = configured_day_of_month
    week_days, week_wildcard = configured_day_of_week
    month_matches = day_of_month in month_days
    week_matches = day_of_week in week_days
    if month_wildcard and week_wildcard:
        return True
    if month_wildcard:
        return week_matches
    if week_wildcard:
        return month_matches
    return month_matches or week_matches


def _check(
    name: str,
    ok: bool,
    message: str,
    *,
    failed_message: str | None = None,
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "severity": "info" if ok else severity,
        "message": message if ok else failed_message or message,
    }


def _find_connector_by_id(
    connectors: list[ConnectorSpec],
    connector_id: str,
) -> tuple[int, ConnectorSpec]:
    selector = str(connector_id or "").strip()
    if not selector:
        raise LookupError("connector not found")
    for index, connector in enumerate(connectors):
        if connector.matches(selector):
            return index, connector
    raise LookupError("connector not found")


def _deep_merge_settings_patch(
    base: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        key_text = str(key)
        previous_value = merged.get(key_text)
        if isinstance(previous_value, dict) and isinstance(value, dict):
            merged[key_text] = _deep_merge_settings_patch(previous_value, value)
        else:
            merged[key_text] = value
    return merged


def _merge_credential_rotation_settings(
    previous: dict[str, Any],
    patch: dict[str, Any],
    *,
    prefix: str = "",
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    merged = dict(previous)
    rotated_fields: list[str] = []
    preserved_fields: list[str] = []
    for key, value in patch.items():
        key_text = str(key)
        field_path = f"{prefix}.{key_text}" if prefix else key_text
        previous_value = previous.get(key_text)
        if value == _REDACTED and previous_value is not None:
            merged[key_text] = previous_value
            preserved_fields.append(field_path)
        elif isinstance(value, dict) and isinstance(previous_value, dict):
            nested_value, nested_summary = _merge_credential_rotation_settings(
                previous_value,
                value,
                prefix=field_path,
            )
            merged[key_text] = nested_value
            rotated_fields.extend(nested_summary["rotated_fields"])
            preserved_fields.extend(nested_summary["preserved_fields"])
        else:
            merged[key_text] = value
            rotated_fields.append(field_path)
    return merged, {
        "rotated_fields": sorted(rotated_fields),
        "preserved_fields": sorted(preserved_fields),
    }


def _merge_redacted_settings(
    incoming: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in incoming.items():
        key_text = str(key)
        previous_value = previous.get(key_text)
        if value == _REDACTED and previous_value is not None:
            merged[key_text] = previous_value
        elif isinstance(value, dict) and isinstance(previous_value, dict):
            merged[key_text] = _merge_redacted_settings(value, previous_value)
        else:
            merged[key_text] = value
    return merged


__all__ = [
    "INTEGRATOR_CONNECTORS_CONFIG_KEY",
    "INTEGRATOR_SCHEDULES_CONFIG_KEY",
    "connector_to_config",
    "connector_to_public_config",
    "integrator_connectors_payload",
    "integrator_schedules_payload",
    "load_integrator_connectors",
    "load_integrator_schedules",
    "normalize_integrator_connector",
    "normalize_integrator_schedule",
    "probe_integrator_connector_payload",
    "rotate_integrator_connector_credentials_payload",
    "save_integrator_connectors_payload",
    "save_integrator_schedules_payload",
    "schedule_to_config",
    "schedule_to_public_config",
    "test_integrator_connector_payload",
    "tick_integrator_schedules_payload",
    "trigger_integrator_schedule_payload",
]
