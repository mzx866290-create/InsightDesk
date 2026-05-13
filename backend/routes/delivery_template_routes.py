from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


class InstallDeliveryTemplateManifestRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)


def build_delivery_template_router(
    *,
    delivery_template_catalog_response_model: type,
    list_delivery_template_catalog: Callable[[], dict[str, Any]],
    install_delivery_template_manifest_payload: Callable[[dict[str, Any]], dict[str, Any]],
    uninstall_delivery_template_manifest_payload: Callable[[str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    audit_security_event: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/api/delivery-templates/catalog",
        response_model=delivery_template_catalog_response_model,
    )
    async def get_delivery_template_catalog(request: Request):
        require_remote_viewer(request)
        payload = list_delivery_template_catalog()
        summary = payload.get("summary", {})
        audit_security_event(
            "get_delivery_template_catalog",
            request,
            details=(
                f"total={summary.get('total', 0)} "
                f"manifest={summary.get('manifest', 0)}"
            ),
        )
        return payload

    @router.post("/api/delivery-templates/install")
    async def install_delivery_template_manifest(
        request: Request,
        payload: InstallDeliveryTemplateManifestRequest,
    ):
        require_remote_admin(request)
        try:
            result = install_delivery_template_manifest_payload(payload.manifest)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        installed = result.get("installed", {})
        audit_security_event(
            "install_delivery_template_manifest",
            request,
            details=(
                f"id={installed.get('id', '')} "
                f"total={result.get('summary', {}).get('total', 0)}"
            ),
        )
        return result

    @router.delete("/api/delivery-templates/{template_id}")
    async def uninstall_delivery_template_manifest(request: Request, template_id: str):
        require_remote_admin(request)
        try:
            result = uninstall_delivery_template_manifest_payload(template_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        uninstalled = result.get("uninstalled", {})
        audit_security_event(
            "uninstall_delivery_template_manifest",
            request,
            details=(
                f"id={uninstalled.get('id', template_id)} "
                f"total={result.get('summary', {}).get('total', 0)}"
            ),
        )
        return result

    return router
