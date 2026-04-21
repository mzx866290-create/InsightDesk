from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Callable

import httpx
from fastapi import APIRouter, Request


def build_chat_router(
    *,
    prepare_chat_route_runtime: Callable[..., Any],
    sse_streaming_response: Callable[..., Any],
    stream_parallel_sse: Callable[..., Any],
    stream_single_sse: Callable[..., Any],
    build_parallel_agent_streams: Callable[..., Any],
    build_single_agent_stream: Callable[..., Any],
    list_mcp_server_catalog: Callable[[], list[Any]],
    default_mcp_server_names: Callable[[], list[str]],
    resolve_active_prompt_runtime: Callable[..., Any],
    validate_chat_payload: Callable[..., None],
    prepare_chat_files: Callable[..., Any],
    build_user_input: Callable[..., Any],
    base_model_payload: Callable[..., dict[str, Any]],
    normalize_model_config: Callable[..., Any],
    model_config_payload: Callable[..., dict[str, Any]],
    invoke_agent_stream: Callable[..., AsyncGenerator[str, None]],
    clear_agent_cache: Callable[..., Any],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    audit_security_event: Callable[..., Any],
    chat_request_model: type,
    single_chat_request_model: type,
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    async def health():
        import time
        return {"status": "ok", "timestamp": time.time()}

    @router.get("/api/connectors/mcp")
    async def list_mcp_connectors():
        return {
            "connectors": list_mcp_server_catalog(),
            "default_enabled": default_mcp_server_names(),
        }

    @router.get("/api/models/ollama")
    async def get_ollama_models(base_url: str = "http://localhost:11434"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return {"models": [m["name"] for m in models]}
        except httpx.HTTPError as e:
            logger.warning("Cannot reach Ollama: %s", e)
            return {"models": [], "error": str(e)}

    @router.post("/api/agents/reset")
    async def reset_agents(request: Request):
        require_remote_admin(request)
        await clear_agent_cache()
        audit_security_event("reset_agents", request)
        return {"ok": True, "message": "智能体缓存已清除"}

    @router.post("/api/chat/parallel")
    async def chat_parallel(request: chat_request_model, http_request: Request):
        from fastapi import HTTPException
        from chat_store import replace_session_panels

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
        from chat_store import upsert_session_panel

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
