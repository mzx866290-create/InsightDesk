from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request

from backend.schemas.api_models import (
    AssistantPresetListResponse,
    AssistantPresetRequest,
    AssistantPresetResponse,
)


def _model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def build_assistant_preset_router(
    *,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    list_assistant_presets: Callable[[], list[dict[str, Any]]],
    create_assistant_preset: Callable[..., dict[str, Any]],
    update_assistant_preset: Callable[..., dict[str, Any] | None],
    delete_assistant_preset: Callable[[str], bool],
    activate_assistant_preset: Callable[[str], bool],
    clear_agent_cache: Callable[[], Awaitable[None]],
    audit_security_event: Callable[..., Any],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/assistant-presets", response_model=AssistantPresetListResponse)
    async def list_presets(request: Request):
        require_remote_viewer(request)
        presets = list_assistant_presets()
        audit_security_event(
            "list_assistant_presets",
            request,
            details=f"preset_count={len(presets)}",
        )
        return {"presets": presets}

    @router.post("/api/assistant-presets", response_model=AssistantPresetResponse)
    async def create_preset(request: Request, payload: AssistantPresetRequest):
        require_remote_editor(request)
        try:
            preset = create_assistant_preset(
                payload.name,
                avatar=payload.avatar,
                system_prompt_id=payload.system_prompt_id,
                default_model_config=_model_payload(payload.default_model_config),
                tool_config=_model_payload(payload.tool_config),
                starters=payload.starters,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await clear_agent_cache()
        return preset

    @router.put(
        "/api/assistant-presets/{preset_id}",
        response_model=AssistantPresetResponse,
    )
    async def update_preset(
        preset_id: str,
        request: Request,
        payload: AssistantPresetRequest,
    ):
        require_remote_editor(request)
        try:
            preset = update_assistant_preset(
                preset_id,
                payload.name,
                avatar=payload.avatar,
                system_prompt_id=payload.system_prompt_id,
                default_model_config=_model_payload(payload.default_model_config),
                tool_config=_model_payload(payload.tool_config),
                starters=payload.starters,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not preset:
            raise HTTPException(status_code=404, detail="未找到助手预设")
        await clear_agent_cache()
        return preset

    @router.delete("/api/assistant-presets/{preset_id}")
    async def delete_preset(preset_id: str, request: Request):
        require_remote_editor(request)
        ok = delete_assistant_preset(preset_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail="未找到助手预设，或该预设是最后一个可用预设",
            )
        await clear_agent_cache()
        return {"ok": True}

    @router.post("/api/assistant-presets/{preset_id}/activate")
    async def activate_preset(preset_id: str, request: Request):
        require_remote_editor(request)
        ok = activate_assistant_preset(preset_id)
        if not ok:
            logger.info("Assistant preset activation failed: %s", preset_id)
            raise HTTPException(status_code=404, detail="未找到助手预设")
        await clear_agent_cache()
        return {"ok": True}

    return router
