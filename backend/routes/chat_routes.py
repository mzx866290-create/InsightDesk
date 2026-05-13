"""Chat route definitions."""

import logging
from typing import Any, AsyncGenerator, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.agent.providers.ollama import list_ollama_models
from backend.routes.resource_access_helpers import require_resource_access


class MCPConnectorApprovalRequest(BaseModel):
    name: str = Field(..., min_length=1)


def build_chat_router(
    *,
    prepare_chat_route_runtime: Callable[..., Any],
    sse_streaming_response: Callable[..., Any],
    stream_parallel_sse: Callable[..., Any],
    stream_single_sse: Callable[..., Any],
    build_parallel_agent_streams: Callable[..., Any],
    build_single_agent_stream: Callable[..., Any],
    list_mcp_server_catalog: Callable[[], list[Any]],
    list_mcp_server_runtime_health: Callable[[], Awaitable[dict[str, Any]]],
    get_mcp_runtime_health_history: Callable[[int], dict[str, Any]],
    default_mcp_server_names: Callable[[], list[str]],
    current_mcp_approvals_payload: Callable[[], dict[str, Any]],
    approve_runtime_mcp_connector: Callable[[str], dict[str, Any]],
    revoke_runtime_mcp_connector: Callable[[str], dict[str, Any]],
    resolve_active_prompt_runtime: Callable[..., Any],
    validate_chat_payload: Callable[..., None],
    prepare_chat_files: Callable[..., Any],
    build_user_input: Callable[..., Any],
    base_model_payload: Callable[..., dict[str, Any]],
    normalize_model_config: Callable[..., Any],
    model_config_payload: Callable[..., dict[str, Any]],
    invoke_agent_stream: Callable[..., AsyncGenerator[str, None]],
    clear_agent_cache: Callable[..., Any],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    access_store: Any | Callable[[], Any],
    identity_store: Any | Callable[[], Any],
    audit_security_event: Callable[..., Any],
    chat_request_model: type,
    single_chat_request_model: type,
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    def health_timestamp() -> float:
        import time

        return time.time()

    def readiness_checks() -> dict[str, str]:
        runtime_ready = all(
            callable(check)
            for check in (
                prepare_chat_route_runtime,
                sse_streaming_response,
                stream_parallel_sse,
                stream_single_sse,
                build_parallel_agent_streams,
                build_single_agent_stream,
                invoke_agent_stream,
            )
        )
        return {
            "config": "ok",
            "runtime": "ok" if runtime_ready else "unavailable",
        }

    def probe_response(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
        return JSONResponse(content=payload, status_code=status_code)

    def require_chat_session_access(
        request: Request, session_id: str
    ) -> dict[str, Any]:
        return require_resource_access(
            request,
            resource_type="session",
            resource_id=session_id,
            minimum_role="editor",
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
            audit_security_event=audit_security_event,
        )

    @router.get("/api/health")
    async def health():
        return probe_response({"status": "ok", "timestamp": health_timestamp()})

    @router.get("/healthz")
    async def healthz():
        return probe_response({"status": "ok", "timestamp": health_timestamp()})

    @router.get("/readyz")
    async def readyz():
        # Keep readiness local-only so probes stay fast and deterministic.
        checks = readiness_checks()
        ready = all(status == "ok" for status in checks.values())
        return probe_response(
            {
                "status": "ok" if ready else "not_ready",
                "timestamp": health_timestamp(),
                "checks": checks,
            },
            status_code=200 if ready else 503,
        )

    @router.get("/api/connectors/mcp")
    async def list_mcp_connectors():
        return {
            "connectors": list_mcp_server_catalog(),
            "default_enabled": default_mcp_server_names(),
        }

    @router.get("/api/connectors/mcp/approvals")
    async def list_mcp_connector_approvals(request: Request):
        require_remote_viewer(request)
        payload = current_mcp_approvals_payload()
        audit_security_event(
            "list_mcp_connector_approvals",
            request,
            details=f"total={payload.get('total', 0)}",
        )
        return payload

    @router.post("/api/connectors/mcp/approvals")
    async def approve_mcp_connector(
        request: Request, payload: MCPConnectorApprovalRequest
    ):
        require_remote_admin(request)
        try:
            result = approve_runtime_mcp_connector(payload.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        connector = result.get("connector", {})
        audit_security_event(
            "approve_mcp_connector",
            request,
            details=(
                f"name={connector.get('name', '')} "
                f"changed={connector.get('changed', False)}"
            ),
        )
        return result

    @router.delete("/api/connectors/mcp/approvals/{connector_name}")
    async def revoke_mcp_connector_approval(request: Request, connector_name: str):
        require_remote_admin(request)
        try:
            result = revoke_runtime_mcp_connector(connector_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        connector = result.get("connector", {})
        audit_security_event(
            "revoke_mcp_connector_approval",
            request,
            details=(
                f"name={connector.get('name', '')} "
                f"removed={connector.get('removed', False)}"
            ),
        )
        return result

    @router.get("/api/connectors/mcp/runtime-health")
    async def get_mcp_runtime_health(request: Request):
        require_remote_admin(request)
        payload = await list_mcp_server_runtime_health()
        audit_security_event(
            "get_mcp_runtime_health",
            request,
            details=(
                f"status={payload.get('status')} "
                f"servers={payload.get('summary', {}).get('total', 0)}"
            ),
        )
        return payload

    @router.get("/api/connectors/mcp/runtime-health/history")
    async def list_mcp_runtime_health_history(request: Request, limit: int = 10):
        require_remote_admin(request)
        payload = get_mcp_runtime_health_history(limit)
        audit_security_event(
            "list_mcp_runtime_health_history",
            request,
            details=f"count={len(payload.get('history', []))}",
        )
        return payload

    @router.get("/api/models/ollama")
    async def get_ollama_models(base_url: str = "http://localhost:11434"):
        return await list_ollama_models(base_url, route_logger=logger)

    @router.post("/api/agents/reset")
    async def reset_agents(request: Request):
        require_remote_admin(request)
        await clear_agent_cache()
        audit_security_event("reset_agents", request)
        return {"ok": True, "message": "智能体缓存已清除"}

    @router.post("/api/chat/parallel")
    async def chat_parallel(request: chat_request_model, http_request: Request):
        from fastapi import HTTPException
        from backend.chat_store import replace_session_panels

        require_chat_session_access(http_request, request.session_id)
        runtime = prepare_chat_route_runtime(
            request,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
            validate_chat_payload=validate_chat_payload,
            prepare_chat_files=prepare_chat_files,
            build_user_input=build_user_input,
            base_model_payload=base_model_payload,
        )

        if not request.models:
            raise HTTPException(status_code=400, detail="至少需要选择一个模型")

        normalized_models = [normalize_model_config(mc) for mc in request.models]
        replace_session_panels(
            request.session_id,
            [model_config_payload(mc) for mc in normalized_models],
        )

        async def event_generator() -> AsyncGenerator[str, None]:
            generators = build_parallel_agent_streams(
                normalized_models,
                runtime=runtime,
                request=request,
                invoke_agent_stream=invoke_agent_stream,
            )
            async for item in stream_parallel_sse(
                generators,
                is_disconnected=http_request.is_disconnected,
                logger=logger,
            ):
                yield item

        return sse_streaming_response(event_generator())

    @router.post("/api/chat/single")
    async def chat_single(request: single_chat_request_model, http_request: Request):
        from backend.chat_store import upsert_session_panel

        require_chat_session_access(http_request, request.session_id)
        runtime = prepare_chat_route_runtime(
            request,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
            validate_chat_payload=validate_chat_payload,
            prepare_chat_files=prepare_chat_files,
            build_user_input=build_user_input,
            base_model_payload=base_model_payload,
        )
        normalized_panel_config = normalize_model_config(request.panel_config)
        upsert_session_panel(
            request.session_id,
            model_config_payload(normalized_panel_config),
        )

        async def event_generator() -> AsyncGenerator[str, None]:
            async for chunk in stream_single_sse(
                build_single_agent_stream(
                    normalized_panel_config,
                    runtime=runtime,
                    request=request,
                    invoke_agent_stream=invoke_agent_stream,
                ),
                is_disconnected=http_request.is_disconnected,
            ):
                yield chunk

        return sse_streaming_response(event_generator())

    return router
