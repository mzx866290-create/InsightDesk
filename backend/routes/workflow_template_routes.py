"""CRUD routes for reusable multi-agent workflow templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.helpers.workflow_template_helpers import (
    delete_workflow_template,
    list_workflow_templates,
    save_workflow_template,
)

router = APIRouter()


class WorkflowTemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    plan: list[dict]


@router.get("/api/workflow-templates")
async def list_templates() -> dict:
    return {"templates": list_workflow_templates()}


@router.post("/api/workflow-templates")
async def create_template(request: WorkflowTemplateCreateRequest) -> dict:
    try:
        record = save_workflow_template(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"template": record}


@router.delete("/api/workflow-templates/{template_id}")
async def delete_template(template_id: str) -> dict:
    deleted = delete_workflow_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到工作流模板")
    return {"ok": True}
