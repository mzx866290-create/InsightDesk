from __future__ import annotations

import os
import time
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel


class SaveConfigRequest(BaseModel):
    tavily_api_key: str | None = None
    embedding_model: str | None = None


class UpsertCloudModelApiKeyRequest(BaseModel):
    api_key: str
    api_key_ref: str | None = None


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
    audit_security_event: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/operations/metrics")
    async def get_prometheus_metrics(request: Request):
        """Prometheus exposition format metrics endpoint."""
        require_remote_viewer(request)
        metrics = runtime_request_metrics_payload()
        task_summary = await runtime_task_summary_payload()
        uptime = round(max(0.0, time.time() - get_runtime_started_at()), 3)
        lines: list[str] = [
            "# HELP insightdesk_uptime_seconds 服务运行时长（秒）",
            "# TYPE insightdesk_uptime_seconds gauge",
            f"insightdesk_uptime_seconds {uptime}",
            "",
            "# HELP insightdesk_http_requests_total HTTP 请求总数",
            "# TYPE insightdesk_http_requests_total counter",
            f"insightdesk_http_requests_total {metrics['total_requests']}",
            "",
            "# HELP insightdesk_http_errors_total HTTP 错误总数",
            "# TYPE insightdesk_http_errors_total counter",
            f"insightdesk_http_errors_total {metrics['total_errors']}",
            "",
            "# HELP insightdesk_http_requests_by_status HTTP 请求按状态码分类",
            "# TYPE insightdesk_http_requests_by_status counter",
        ]
        for status_class, count in sorted(metrics["by_status_class"].items()):
            lines.append(
                f'insightdesk_http_requests_by_status{{status="{status_class}"}} {count}'
            )
        lines.extend(
            [
                "",
                "# HELP insightdesk_tasks_total 内存任务池任务总数",
                "# TYPE insightdesk_tasks_total gauge",
                f"insightdesk_tasks_total {task_summary['in_memory_total']}",
                "",
                "# HELP insightdesk_tasks_by_status 按状态分类的任务数",
                "# TYPE insightdesk_tasks_by_status gauge",
                f'insightdesk_tasks_by_status{{status="pending"}} {task_summary["pending"]}',
                f'insightdesk_tasks_by_status{{status="running"}} {task_summary["running"]}',
                f'insightdesk_tasks_by_status{{status="completed"}} {task_summary["completed"]}',
                f'insightdesk_tasks_by_status{{status="failed"}} {task_summary["failed"]}',
                "",
            ]
        )
        return Response(
            content="\n".join(lines) + "\n",
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

    return router
