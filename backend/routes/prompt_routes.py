from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


class CreatePromptRequest(BaseModel):
    name: str
    content: str
    vector_store_id: str | None = None
    dashboard_template: dict[str, Any] = Field(default_factory=dict)


class UpdatePromptRequest(BaseModel):
    name: str
    content: str
    vector_store_id: str | None = None
    dashboard_template: dict[str, Any] = Field(default_factory=dict)


def build_prompt_router(
    *,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    list_system_prompts: Callable[[], list[dict[str, Any]]],
    create_system_prompt: Callable[..., dict[str, Any]],
    update_system_prompt: Callable[..., dict[str, Any] | None],
    delete_system_prompt: Callable[[str], bool],
    activate_system_prompt: Callable[[str], bool],
    clear_agent_cache: Callable[[], Awaitable[None]],
    build_doc_pipeline: Callable[[str], Any],
    audit_security_event: Callable[..., Any],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/prompts")
    async def list_prompts(request: Request):
        require_remote_viewer(request)
        payload = {"prompts": list_system_prompts()}
        audit_security_event(
            "list_prompts",
            request,
            details=f"prompt_count={len(payload['prompts'])}",
        )
        return payload

    @router.post("/api/prompts")
    async def create_prompt(request: Request, payload: CreatePromptRequest):
        require_remote_editor(request)
        return create_system_prompt(
            payload.name,
            payload.content,
            vector_store_id=payload.vector_store_id or "",
            dashboard_template=payload.dashboard_template or {},
        )

    @router.put("/api/prompts/{prompt_id}")
    async def update_prompt(
        prompt_id: str,
        request: Request,
        payload: UpdatePromptRequest,
    ):
        require_remote_editor(request)
        prompt = update_system_prompt(
            prompt_id,
            payload.name,
            payload.content,
            vector_store_id=payload.vector_store_id or "",
            dashboard_template=payload.dashboard_template or {},
        )
        if not prompt:
            raise HTTPException(status_code=404, detail="未找到提示词")
        await clear_agent_cache()
        return prompt

    @router.delete("/api/prompts/{prompt_id}")
    async def delete_prompt(prompt_id: str, request: Request):
        require_remote_editor(request)
        ok = delete_system_prompt(prompt_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail="未找到提示词，或该提示词是最后一个默认项",
            )
        await clear_agent_cache()
        return {"ok": True}

    @router.post("/api/prompts/{prompt_id}/activate")
    async def activate_prompt(prompt_id: str, request: Request):
        require_remote_editor(request)
        ok = activate_system_prompt(prompt_id)
        if not ok:
            raise HTTPException(status_code=404, detail="未找到提示词")

        await clear_agent_cache()

        prompts = list_system_prompts()
        target = next((prompt for prompt in prompts if prompt["id"] == prompt_id), None)
        kb_status = "none"
        if target and target.get("vector_store_id"):
            try:
                loaded = build_doc_pipeline(target["vector_store_id"]).load_store()
                kb_status = "loaded" if loaded else "error"
            except Exception as exc:
                logger.warning("Failed to load KB for prompt %s: %s", prompt_id, exc)
                kb_status = "error"
        return {"ok": True, "kb_status": kb_status}

    return router
