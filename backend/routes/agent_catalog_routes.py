from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


class InstallAgentPluginManifestRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)


def build_agent_catalog_router(
    *,
    agent_catalog_response_model: type,
    list_agent_catalog: Callable[[], dict[str, Any]],
    install_agent_plugin_manifest_payload: Callable[[dict[str, Any]], dict[str, Any]],
    uninstall_agent_plugin_manifest_payload: Callable[[str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    audit_security_event: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/agents/catalog", response_model=agent_catalog_response_model)
    async def get_agent_catalog(request: Request):
        require_remote_viewer(request)
        payload = list_agent_catalog()
        audit_security_event(
            "get_agent_catalog",
            request,
            details=(
                f"total={payload.get('summary', {}).get('total', 0)} "
                f"plugin={payload.get('summary', {}).get('plugin', 0)}"
            ),
        )
        return payload

    @router.post("/api/agents/plugins/install")
    async def install_agent_plugin_manifest(
        request: Request,
        payload: InstallAgentPluginManifestRequest,
    ):
        require_remote_admin(request)
        try:
            result = install_agent_plugin_manifest_payload(payload.manifest)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        installed = result.get("installed", {})
        audit_security_event(
            "install_agent_plugin_manifest",
            request,
            details=(
                f"name={installed.get('name', '')} "
                f"total={result.get('summary', {}).get('total', 0)}"
            ),
        )
        return result

    @router.delete("/api/agents/plugins/{name}")
    async def uninstall_agent_plugin_manifest(request: Request, name: str):
        require_remote_admin(request)
        try:
            result = uninstall_agent_plugin_manifest_payload(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        uninstalled = result.get("uninstalled", {})
        audit_security_event(
            "uninstall_agent_plugin_manifest",
            request,
            details=(
                f"name={uninstalled.get('name', name)} "
                f"total={result.get('summary', {}).get('total', 0)}"
            ),
        )
        return result

    return router
