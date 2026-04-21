from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request


def build_security_router(
    *,
    security_status_response_model: type,
    auth_whoami_response_model: type,
    auth_token_catalog_response_model: type,
    security_audit_event_list_response_model: type,
    security_audit_cleanup_response_model: type,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    security_status_payload: Callable[[], dict[str, Any]],
    auth_whoami_payload: Callable[[dict[str, Any]], dict[str, Any]],
    auth_token_catalog_payload: Callable[[], dict[str, Any]],
    security_audit_events_payload: Callable[..., dict[str, Any]],
    cleanup_security_audit_events: Callable[..., dict[str, Any]],
    audit_security_event: Callable[..., Any],
    get_security_audit_store_count: Callable[[], int],
    get_memory_security_audit_event_count: Callable[[], int],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/security/status", response_model=security_status_response_model)
    async def get_security_status(request: Request):
        require_remote_viewer(request)
        payload = security_status_payload()
        audit_security_event(
            "get_security_status",
            request,
            details=(
                f"remote_clients={payload['allow_remote_clients']} "
                f"admin_ready={payload['remote_admin_ready']} "
                f"share_ready={payload['remote_share_ready']}"
            ),
        )
        return payload

    @router.get("/api/auth/whoami", response_model=auth_whoami_response_model)
    async def get_auth_whoami(request: Request):
        auth = require_remote_viewer(request)
        payload = auth_whoami_payload(auth)
        audit_security_event(
            "get_auth_whoami",
            request,
            details=(
                f"role={payload['role']} "
                f"capability_count={len(payload['capabilities'])}"
            ),
        )
        return payload

    @router.get("/api/auth/tokens", response_model=auth_token_catalog_response_model)
    async def get_auth_tokens(request: Request):
        require_remote_admin(request)
        payload = auth_token_catalog_payload()
        audit_security_event(
            "get_auth_tokens",
            request,
            details=(
                f"total={payload['total']} "
                f"roles={','.join(payload['configured_roles']) or '<none>'}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-events",
        response_model=security_audit_event_list_response_model,
    )
    async def get_security_audit_events(
        request: Request,
        limit: int = 50,
        action: str = "",
        result: str = "",
    ):
        require_remote_admin(request)
        payload = security_audit_events_payload(
            limit=limit,
            action=action,
            result=result,
        )
        audit_security_event(
            "get_security_audit_events",
            request,
            details=(
                f"limit={payload['limit']} "
                f"action={action or '<all>'} "
                f"result={result or '<all>'} "
                f"total={payload['total']}"
            ),
        )
        return payload

    @router.post(
        "/api/security/audit-events/cleanup",
        response_model=security_audit_cleanup_response_model,
    )
    async def cleanup_security_audit_events_route(
        request: Request,
        keep_latest: int = 0,
    ):
        require_remote_admin(request)
        payload = cleanup_security_audit_events(keep_latest=keep_latest)
        audit_security_event(
            "cleanup_security_audit_events",
            request,
            details=(
                f"keep_latest={payload['keep_latest']} "
                f"deleted={payload['deleted_count']} "
                f"memory_deleted={payload['memory_deleted_count']}"
            ),
        )
        try:
            payload["remaining_count"] = get_security_audit_store_count()
        except Exception:
            logger.exception("Failed to refresh security audit count after cleanup")
        payload["memory_remaining_count"] = get_memory_security_audit_event_count()
        payload["includes_cleanup_event"] = True
        return payload

    return router
