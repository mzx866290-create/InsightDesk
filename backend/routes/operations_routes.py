from __future__ import annotations

import os
import time
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.core.runtime_metrics import (
    aggregate_runtime_metrics_snapshots,
    build_runtime_metrics_exporter_contract,
    runtime_llm_metrics_payload,
    runtime_operations_summary_payload,
    runtime_prometheus_metrics_text,
)
from backend.core.tracing import (
    DEFAULT_TRACE_SERVICE_NAME,
    build_otel_exporter_contract,
    build_trace_dashboard_payload,
    build_trace_export_payload,
    get_recent_trace_events,
    ingest_external_trace_events,
    reset_trace_events,
)
from backend.agent.agents.integrator.audit import (
    cleanup_integrator_outbound_audit_payload,
    integrator_outbound_audit_payload,
)
from backend.helpers.integration_connector_helpers import (
    integrator_connectors_payload,
    integrator_schedules_payload,
    probe_integrator_connector_payload,
    rotate_integrator_connector_credentials_payload,
    save_integrator_connectors_payload,
    save_integrator_schedules_payload,
    test_integrator_connector_payload,
    tick_integrator_schedules_payload,
    trigger_integrator_schedule_payload,
)
from backend.agent_mcp_helpers import (
    current_mcp_server_config_payload,
    save_mcp_server_config_payload,
)


class SaveConfigRequest(BaseModel):
    tavily_api_key: str | None = None
    embedding_model: str | None = None


class UpsertCloudModelApiKeyRequest(BaseModel):
    api_key: str
    api_key_ref: str | None = None


class UpsertIntegratorConnectorsRequest(BaseModel):
    connectors: list[dict[str, Any]] = Field(default_factory=list)


class UpsertMcpServerConfigRequest(BaseModel):
    servers: dict[str, dict[str, Any]] = Field(default_factory=dict)


class TestIntegratorConnectorRequest(BaseModel):
    connector: dict[str, Any] | None = None


class UpsertIntegratorSchedulesRequest(BaseModel):
    schedules: list[dict[str, Any]] = Field(default_factory=list)


class IngestTraceEventsRequest(BaseModel):
    source: str | None = None
    process_id: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


async def enqueue_integrator_schedule_workflow(
    result: dict[str, Any],
    *,
    tasks: dict[str, Any] | Callable[[], dict[str, Any]] | None = None,
    tasks_lock: Any | None = None,
    prune_task_records_locked: Callable[..., None] | None = None,
    persist_task_record: Callable[..., None] | None = None,
    prune_persisted_tasks: Callable[[], None] | None = None,
    run_task: Callable[..., Awaitable[None]] | None = None,
    enqueue_task: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    spawn_background_task: Callable[[Awaitable[None]], Any] | None = None,
    logger: Any | None = None,
    task_backend: str | Callable[[], str] = "memory",
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    missing_task_helpers = [
        name
        for name, value in {
            "tasks_lock": tasks_lock,
            "prune_task_records_locked": prune_task_records_locked,
            "persist_task_record": persist_task_record,
            "prune_persisted_tasks": prune_persisted_tasks,
            "run_task": run_task,
            "enqueue_task": enqueue_task,
            "spawn_background_task": spawn_background_task,
        }.items()
        if value is None
    ]
    if missing_task_helpers:
        raise RuntimeError(
            "Task runtime is not available for integrator schedule trigger: "
            + ", ".join(missing_task_helpers)
        )

    resolved_tasks = tasks() if callable(tasks) else tasks or {}
    resolved_task_backend = str(task_backend() if callable(task_backend) else task_backend)
    task_spec = result.get("would_create_task", {})
    params = task_spec.get("params") if isinstance(task_spec, dict) else {}
    if not isinstance(params, dict):
        params = {}
    task_payload = await enqueue_task(
        resolved_tasks,
        tasks_lock,
        task_type="multi_agent_workflow",
        params=params,
        session_id=None,
        prune_in_memory=prune_task_records_locked,
        persist_record=persist_task_record,
        prune_persisted=prune_persisted_tasks,
        run_task=run_task,
        spawn_background_task=spawn_background_task,
        logger=logger,
        task_backend=resolved_task_backend,
        enqueue_external_task=enqueue_external_task,
    )
    result["dry_run"] = False
    result["executed"] = True
    result["task"] = task_payload
    return result


async def run_integrator_scheduler_tick(
    config_store: Any,
    *,
    tick_lock: Any | None = None,
    now: float | None = None,
    tasks: dict[str, Any] | Callable[[], dict[str, Any]] | None = None,
    tasks_lock: Any | None = None,
    prune_task_records_locked: Callable[..., None] | None = None,
    persist_task_record: Callable[..., None] | None = None,
    prune_persisted_tasks: Callable[[], None] | None = None,
    run_task: Callable[..., Awaitable[None]] | None = None,
    enqueue_task: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    spawn_background_task: Callable[[Awaitable[None]], Any] | None = None,
    logger: Any | None = None,
    task_backend: str | Callable[[], str] = "memory",
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    if tick_lock is not None and tick_lock.locked():
        return {
            "ok": True,
            "status": "skipped",
            "skipped_reason": "tick_already_running",
            "dry_run": False,
            "executed": False,
            "checked": 0,
            "due_count": 0,
            "due": [],
            "skipped": {"disabled": 0, "not_due": 0},
        }

    acquired_lock = False
    if tick_lock is not None:
        await tick_lock.acquire()
        acquired_lock = True
    try:
        result = tick_integrator_schedules_payload(
            config_store,
            dry_run=False,
            now=now,
        )
        result["due"] = [
            await enqueue_integrator_schedule_workflow(
                dict(item),
                tasks=tasks,
                tasks_lock=tasks_lock,
                prune_task_records_locked=prune_task_records_locked,
                persist_task_record=persist_task_record,
                prune_persisted_tasks=prune_persisted_tasks,
                run_task=run_task,
                enqueue_task=enqueue_task,
                spawn_background_task=spawn_background_task,
                logger=logger,
                task_backend=task_backend,
                enqueue_external_task=enqueue_external_task,
            )
            for item in result.get("due", [])
            if isinstance(item, dict)
        ]
        result["dry_run"] = False
        result["executed"] = bool(result["due"])
        return result
    finally:
        if acquired_lock:
            tick_lock.release()


def build_operations_router(
    *,
    runtime_operations_response_model: type,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    runtime_request_metrics_payload: Callable[[], dict[str, Any]],
    runtime_task_summary_payload: Callable[[], Awaitable[dict[str, Any]]],
    runtime_operations_payload: Callable[[], Awaitable[dict[str, Any]]],
    get_runtime_started_at: Callable[[], float],
    sync_runtime_secret_from_store: Callable[[str, str], str],
    validate_tavily_api_key: Callable[[str], Awaitable[None]],
    get_app_config_store: Callable[[], Any],
    upsert_cloud_model_api_key: Callable[[str | None, str], str],
    delete_cloud_model_api_key: Callable[[str], bool],
    clear_agent_cache: Callable[[], Awaitable[Any]],
    audit_security_event: Callable[..., Any],
    tasks: dict[str, Any] | Callable[[], dict[str, Any]] | None = None,
    tasks_lock: Any | None = None,
    prune_task_records_locked: Callable[..., None] | None = None,
    persist_task_record: Callable[..., None] | None = None,
    prune_persisted_tasks: Callable[[], None] | None = None,
    run_task: Callable[..., Awaitable[None]] | None = None,
    enqueue_task: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    spawn_background_task: Callable[[Awaitable[None]], Any] | None = None,
    logger: Any | None = None,
    task_backend: str | Callable[[], str] = "memory",
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None = None,
    integrator_scheduler_tick_lock: Any | None = None,
    integrator_scheduler_config: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter()

    def parse_request_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    def trace_service_name() -> str:
        return (
            os.getenv("OTEL_SERVICE_NAME")
            or os.getenv("SERVICE_NAME")
            or DEFAULT_TRACE_SERVICE_NAME
        )

    def build_trace_observability_payload(
        events: list[dict[str, Any]],
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        export_payload = build_trace_export_payload(
            events,
            service_name=trace_service_name(),
        )
        dashboard_payload = build_trace_dashboard_payload(events, export_payload)
        return {
            "events": events,
            "summary": {
                "returned": len(events),
                "limit": limit,
                "error_events": sum(1 for item in events if item.get("event") == "error"),
                "filters": filters or {},
                "source_nodes": export_payload["summary"]["source_nodes"],
            "process_nodes": export_payload["summary"]["process_nodes"],
            "otel_exporter": export_payload["summary"]["otel_exporter"],
            },
            "export": export_payload,
            **dashboard_payload,
        }

    @router.get("/api/operations/metrics")
    async def get_prometheus_metrics(request: Request):
        """Prometheus exposition format metrics endpoint."""
        require_remote_viewer(request)
        metrics = runtime_request_metrics_payload()
        task_summary = await runtime_task_summary_payload()
        uptime = round(max(0.0, time.time() - get_runtime_started_at()), 3)
        llm_metrics = runtime_llm_metrics_payload()
        operations_summary = runtime_operations_summary_payload(
            request_metrics=metrics,
            task_summary=task_summary,
            uptime_seconds=uptime,
            llm_metrics=llm_metrics,
        )
        content = runtime_prometheus_metrics_text(
            request_metrics=metrics,
            task_summary=task_summary,
            uptime_seconds=uptime,
            task_backend=os.getenv("TASK_QUEUE_BACKEND")
            or os.getenv("DATABASE_PROVIDER")
            or "sqlite",
            llm_metrics=llm_metrics,
            operations_summary=operations_summary,
        )
        return Response(
            content=content,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @router.get(
        "/api/operations/runtime",
        response_model=runtime_operations_response_model,
    )
    async def get_runtime_operations(request: Request):
        require_remote_viewer(request)
        payload = await runtime_operations_payload()
        audit_security_event(
            "get_runtime_operations",
            request,
            details=(
                f"requests={payload['request_metrics']['total_requests']} "
                f"errors={payload['request_metrics']['total_errors']} "
                f"running_tasks={payload['task_summary']['running']}"
            ),
        )
        return payload

    @router.get("/api/operations/traces")
    async def get_runtime_traces(
        request: Request,
        limit: int = 100,
        event: str | None = None,
        name: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ):
        require_remote_admin(request)
        safe_limit = min(500, max(1, int(limit or 100)))
        events = get_recent_trace_events(
            limit=safe_limit,
            event=event,
            name=name,
            trace_id=trace_id,
            span_id=span_id,
        )
        filters = {
            key: value
            for key, value in {
                "event": event,
                "name": name,
                "trace_id": trace_id,
                "span_id": span_id,
            }.items()
            if value
        }
        payload = build_trace_observability_payload(
            events,
            limit=safe_limit,
            filters=filters,
        )
        audit_security_event(
            "get_runtime_traces",
            request,
            details=(
                f"returned={payload['summary']['returned']} "
                f"limit={safe_limit} filters={filters}"
            ),
        )
        return payload

    @router.post("/api/operations/traces/ingest")
    async def ingest_runtime_traces(
        request: Request,
        payload: IngestTraceEventsRequest,
    ):
        require_remote_admin(request)
        payload_data = (
            payload.model_dump()
            if hasattr(payload, "model_dump")
            else payload.dict()
        )
        result = ingest_external_trace_events(payload_data)
        audit_security_event(
            "ingest_runtime_traces",
            request,
            details=(
                f"accepted={result['accepted']} rejected={result['rejected']} "
                f"source={result['source']} process_id={result['process_id']}"
            ),
        )
        return {"ok": True, **result}

    @router.get("/api/operations/observability")
    async def get_observability_snapshot(request: Request, trace_limit: int = 50):
        require_remote_admin(request)
        safe_trace_limit = min(200, max(1, int(trace_limit or 50)))
        runtime_payload = await runtime_operations_payload()
        trace_events = get_recent_trace_events(limit=safe_trace_limit)
        trace_payload = build_trace_observability_payload(
            trace_events,
            limit=safe_trace_limit,
        )
        metrics_aggregation = aggregate_runtime_metrics_snapshots(
            [
                {
                    "source": "local",
                    "process_id": str(os.getpid()),
                    "request_metrics": runtime_payload.get("request_metrics", {}),
                }
            ]
        )
        audit_security_event(
            "get_observability_snapshot",
            request,
            details=(
                f"trace_events={trace_payload['summary']['returned']} "
                f"metric_nodes={metrics_aggregation['summary']['node_count']}"
            ),
        )
        return {
            "runtime": runtime_payload,
            "traces": {
                "summary": trace_payload["summary"],
                "export_preview": trace_payload["export_preview"],
            },
            "metrics_aggregation": metrics_aggregation,
            "exporters": {
                "traces": build_otel_exporter_contract(),
                "metrics": build_runtime_metrics_exporter_contract(),
            },
            "dashboard_cards": trace_payload["dashboard_cards"],
            "panel_templates": trace_payload["panel_templates"],
        }

    @router.delete("/api/operations/traces")
    async def clear_runtime_traces(request: Request):
        require_remote_admin(request)
        reset_trace_events()
        audit_security_event("clear_runtime_traces", request)
        return {"ok": True, "cleared": True}

    @router.get("/api/config")
    async def get_config(request: Request):
        require_remote_admin(request)
        tavily_key = sync_runtime_secret_from_store("TAVILY_API_KEY", "tavily_api_key")
        payload = {
            "tavily_api_key_set": bool(tavily_key),
            "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
            "ollama_model": os.environ.get("OLLAMA_MODEL", "qwen3.5-2B:latest"),
            "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            "openrouter_model": os.environ.get("OPENROUTER_MODEL", ""),
            "openrouter_base_url": os.environ.get(
                "OPENROUTER_BASE_URL",
                "https://openrouter.ai/api/v1",
            ),
        }
        audit_security_event("get_config", request)
        return payload

    @router.post("/api/config")
    async def save_config(request: Request, payload: SaveConfigRequest):
        require_remote_admin(request)
        if payload.tavily_api_key is not None:
            normalized_tavily_key = str(payload.tavily_api_key or "").strip()
            if normalized_tavily_key:
                await validate_tavily_api_key(normalized_tavily_key)
                get_app_config_store().set("tavily_api_key", normalized_tavily_key)
                os.environ["TAVILY_API_KEY"] = normalized_tavily_key
            else:
                get_app_config_store().delete("tavily_api_key")
                os.environ.pop("TAVILY_API_KEY", None)

        audit_security_event(
            "save_config",
            request,
            details=f"tavily_api_key_set={payload.tavily_api_key is not None}",
        )
        return {"ok": True, "tavily_api_key_set": bool(os.environ.get("TAVILY_API_KEY"))}

    @router.post("/api/config/cloud-model-api-key")
    async def save_cloud_model_api_key(
        request: Request,
        payload: UpsertCloudModelApiKeyRequest,
    ):
        require_remote_admin(request)
        api_key_ref = upsert_cloud_model_api_key(payload.api_key_ref, payload.api_key)
        audit_security_event(
            "save_cloud_model_api_key",
            request,
            details=f"api_key_ref={api_key_ref}",
        )
        return {"ok": True, "api_key_ref": api_key_ref, "api_key_set": True}

    @router.delete("/api/config/cloud-model-api-key/{api_key_ref}")
    async def remove_cloud_model_api_key(api_key_ref: str, request: Request):
        require_remote_admin(request)
        deleted = delete_cloud_model_api_key(api_key_ref)
        audit_security_event(
            "delete_cloud_model_api_key",
            request,
            details=f"api_key_ref={api_key_ref} deleted={deleted}",
        )
        return {"ok": True, "deleted": deleted}

    @router.get("/api/connectors/mcp/config")
    async def get_mcp_server_config(request: Request):
        require_remote_viewer(request)
        payload = current_mcp_server_config_payload()
        audit_security_event(
            "get_mcp_server_config",
            request,
            details=f"source={payload.get('source')} total={payload.get('total', 0)}",
        )
        return payload

    @router.put("/api/connectors/mcp/config")
    async def save_mcp_server_config(
        request: Request,
        payload: UpsertMcpServerConfigRequest,
    ):
        require_remote_admin(request)
        try:
            result = save_mcp_server_config_payload({"servers": payload.servers})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        audit_security_event(
            "save_mcp_server_config",
            request,
            details=f"total={result.get('total', 0)}",
        )
        return result

    @router.get("/api/integrations/connectors")
    async def list_integrator_connectors(request: Request):
        require_remote_admin(request)
        try:
            payload = integrator_connectors_payload(get_app_config_store())
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        audit_security_event(
            "list_integrator_connectors",
            request,
            details=f"total={payload.get('total', 0)}",
        )
        return payload

    @router.put("/api/integrations/connectors")
    async def save_integrator_connectors(
        request: Request,
        payload: UpsertIntegratorConnectorsRequest,
    ):
        require_remote_admin(request)
        try:
            result = save_integrator_connectors_payload(
                get_app_config_store(),
                payload.connectors,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        audit_security_event(
            "save_integrator_connectors",
            request,
            details=f"total={result.get('total', 0)}",
        )
        return result

    @router.post("/api/integrations/connectors/test")
    async def test_integrator_connector(
        request: Request,
        payload: dict[str, Any],
    ):
        require_remote_admin(request)
        connector_payload = (
            payload.get("connector")
            if isinstance(payload.get("connector"), dict)
            else payload
        )
        try:
            result = test_integrator_connector_payload(connector_payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        connector = result.get("connector", {})
        audit_security_event(
            "test_integrator_connector",
            request,
            details=(
                f"type={connector.get('type', '')} "
                f"status={result.get('status', '')} "
                f"ok={result.get('ok', False)}"
            ),
        )
        return result

    @router.post("/api/integrations/connectors/{connector_id}/credentials/rotate")
    async def rotate_integrator_connector_credentials(
        connector_id: str,
        request: Request,
        payload: dict[str, Any],
    ):
        require_remote_admin(request)
        try:
            result = rotate_integrator_connector_credentials_payload(
                get_app_config_store(),
                connector_id,
                payload,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        audit_security_event(
            "rotate_integrator_connector_credentials",
            request,
            details=(
                f"connector_id={connector_id} "
                f"rotated={len(result.get('rotated_fields', []))} "
                f"preserved={len(result.get('preserved_fields', []))}"
            ),
        )
        return result

    @router.post("/api/integrations/connectors/{connector_id}/probe")
    async def probe_integrator_connector(
        connector_id: str,
        request: Request,
        payload: dict[str, Any] | None = None,
    ):
        require_remote_admin(request)
        body = payload if isinstance(payload, dict) else {}
        try:
            result = await probe_integrator_connector_payload(
                get_app_config_store(),
                connector_id,
                body,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        connector = result.get("connector", {})
        audit_security_event(
            "probe_integrator_connector",
            request,
            details=(
                f"connector_id={connector_id} "
                f"probe_mode={result.get('probe', {}).get('mode', '')} "
                f"outbound_request_sent={result.get('probe', {}).get('outbound_request_sent', False)} "
                f"type={connector.get('type', '')} "
                f"status={result.get('status', '')} "
                f"ok={result.get('ok', False)}"
            ),
        )
        return result

    @router.get("/api/integrations/schedules")
    async def list_integrator_schedules(request: Request):
        require_remote_admin(request)
        try:
            payload = integrator_schedules_payload(get_app_config_store())
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if integrator_scheduler_config is not None:
            scheduler_config = integrator_scheduler_config()
            scheduler = payload.setdefault("scheduler", {})
            scheduler["mode"] = (
                "background" if scheduler_config.get("enabled") else "configured"
            )
            scheduler["automatic_dispatch"] = bool(scheduler_config.get("enabled"))
            scheduler["interval_seconds"] = int(
                scheduler_config.get("interval_seconds") or 60
            )
        audit_security_event(
            "list_integrator_schedules",
            request,
            details=f"total={payload.get('total', 0)}",
        )
        return payload

    @router.put("/api/integrations/schedules")
    async def save_integrator_schedules(
        request: Request,
        payload: UpsertIntegratorSchedulesRequest,
    ):
        require_remote_admin(request)
        try:
            result = save_integrator_schedules_payload(
                get_app_config_store(),
                payload.schedules,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "save_integrator_schedules",
            request,
            details=f"total={result.get('total', 0)}",
        )
        return result

    @router.post("/api/integrations/schedules/tick")
    async def tick_integrator_schedules(
        request: Request,
        payload: dict[str, Any] | None = None,
    ):
        require_remote_admin(request)
        body = payload if isinstance(payload, dict) else {}
        dry_run = parse_request_bool(body.get("dry_run"), True)
        raw_now = body.get("now")
        try:
            tick_now = float(raw_now) if raw_now is not None else None
            if dry_run:
                result = tick_integrator_schedules_payload(
                    get_app_config_store(),
                    dry_run=True,
                    now=tick_now,
                )
            else:
                result = await run_integrator_scheduler_tick(
                    get_app_config_store(),
                    tick_lock=integrator_scheduler_tick_lock,
                    now=tick_now,
                    tasks=tasks,
                    tasks_lock=tasks_lock,
                    prune_task_records_locked=prune_task_records_locked,
                    persist_task_record=persist_task_record,
                    prune_persisted_tasks=prune_persisted_tasks,
                    run_task=run_task,
                    enqueue_task=enqueue_task,
                    spawn_background_task=spawn_background_task,
                    logger=logger,
                    task_backend=task_backend,
                    enqueue_external_task=enqueue_external_task,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit_security_event(
            "tick_integrator_schedules",
            request,
            details=(
                f"due_count={result.get('due_count', 0)} "
                f"dry_run={dry_run}"
            ),
        )
        return result

    @router.post("/api/integrations/schedules/{schedule_id}/trigger")
    async def trigger_integrator_schedule(
        schedule_id: str,
        request: Request,
        payload: dict[str, Any] | None = None,
    ):
        require_remote_admin(request)
        body = payload if isinstance(payload, dict) else {}
        dry_run = parse_request_bool(body.get("dry_run"), True)
        try:
            result = trigger_integrator_schedule_payload(
                get_app_config_store(),
                schedule_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule was not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        schedule = result.get("schedule", {})
        if not dry_run:
            try:
                result = await enqueue_integrator_schedule_workflow(
                    result,
                    tasks=tasks,
                    tasks_lock=tasks_lock,
                    prune_task_records_locked=prune_task_records_locked,
                    persist_task_record=persist_task_record,
                    prune_persisted_tasks=prune_persisted_tasks,
                    run_task=run_task,
                    enqueue_task=enqueue_task,
                    spawn_background_task=spawn_background_task,
                    logger=logger,
                    task_backend=task_backend,
                    enqueue_external_task=enqueue_external_task,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit_security_event(
            "trigger_integrator_schedule",
            request,
            details=(
                f"schedule_id={schedule.get('id', '')} "
                f"connector_id={schedule.get('connector_id', '')} "
                f"dry_run={dry_run}"
            ),
        )
        return result

    @router.get("/api/integrations/audit")
    async def list_integrator_audit(request: Request, limit: int = 20):
        require_remote_admin(request)
        payload = integrator_outbound_audit_payload(limit=limit)
        audit_security_event(
            "list_integrator_audit",
            request,
            details=f"total={payload.get('total', 0)} limit={payload.get('limit', 0)}",
        )
        return payload

    @router.get("/api/integrations/outbound-audit")
    async def list_integrator_outbound_audit(
        request: Request,
        limit: int = 50,
    ):
        require_remote_admin(request)
        payload = integrator_outbound_audit_payload(limit=limit)
        audit_security_event(
            "list_integrator_outbound_audit",
            request,
            details=f"limit={payload['limit']} total={payload['total']}",
        )
        return payload

    @router.post("/api/integrations/outbound-audit/cleanup")
    async def cleanup_integrator_outbound_audit(
        request: Request,
        keep_latest: int = 0,
        dry_run: bool = False,
    ):
        require_remote_admin(request)
        payload = cleanup_integrator_outbound_audit_payload(
            keep_latest=keep_latest,
            dry_run=dry_run,
        )
        audit_security_event(
            "cleanup_integrator_outbound_audit",
            request,
            details=(
                f"keep_latest={payload['keep_latest']} "
                f"dry_run={payload['dry_run']} "
                f"would_delete={payload['would_delete_count']} "
                f"deleted={payload['deleted_count']}"
            ),
        )
        return payload

    return router
