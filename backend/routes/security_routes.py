from __future__ import annotations

import hashlib
import logging
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class SaveSsoConfigRequest(BaseModel):
    provider: str | None = None
    issuer_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    clear_client_secret: bool = False
    allowed_domains: str | None = None
    scopes: str | None = None
    default_role: str | None = None
    session_ttl_seconds: int | None = Field(default=None, ge=300, le=604800)


def _fingerprint(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return "empty"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _count_external_groups(payload: dict[str, Any]) -> int:
    external = payload.get("external")
    if not isinstance(external, dict):
        return 0
    groups = external.get("groups")
    return len(groups) if isinstance(groups, list) else 0


def _sso_login_audit_details(payload: dict[str, Any], response_mode: str) -> str:
    scopes = payload.get("scopes")
    scope_list = [str(item) for item in scopes] if isinstance(scopes, list) else []
    return (
        f"redirect_uri={payload.get('redirect_uri') or ''} "
        f"scopes={','.join(scope_list)} "
        f"response_mode={response_mode or '<default>'} "
        f"state_fp={_fingerprint(payload.get('state'))} "
        f"nonce_fp={_fingerprint(payload.get('nonce'))}"
    )


def _sso_callback_audit_details(payload: dict[str, Any]) -> str:
    memberships = payload.get("memberships")
    membership_count = len(memberships) if isinstance(memberships, list) else 0
    external = payload.get("external") if isinstance(payload.get("external"), dict) else {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    return (
        f"provider={external.get('provider') or ''} "
        f"user_id={user.get('user_id') or ''} "
        f"role={payload.get('role') or ''} "
        f"memberships={membership_count} "
        f"groups={_count_external_groups(payload)} "
        f"token_type={payload.get('token_type') or '<none>'} "
        f"expires_in={payload.get('expires_in')} "
        f"app_session_expires_at={payload.get('app_session_expires_at') or 0} "
        f"app_session_token_fp={_fingerprint(payload.get('app_session_token'))}"
    )


def build_security_router(
    *,
    security_status_response_model: type,
    auth_whoami_response_model: type,
    auth_token_catalog_response_model: type,
    sso_config_response_model: type,
    sso_login_response_model: type,
    sso_callback_response_model: type,
    security_audit_event_list_response_model: type,
    security_audit_cleanup_response_model: type,
    security_audit_action_catalog_response_model: type,
    security_audit_summary_response_model: type,
    security_audit_siem_export_response_model: type,
    security_audit_aggregate_report_response_model: type,
    security_audit_archive_policy_response_model: type,
    security_audit_legal_hold_response_model: type,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    security_status_payload: Callable[[], dict[str, Any]],
    auth_whoami_payload: Callable[[dict[str, Any]], dict[str, Any]],
    auth_token_catalog_payload: Callable[[], dict[str, Any]],
    sso_config_payload: Callable[[], dict[str, Any]],
    save_sso_config_payload: Callable[[SaveSsoConfigRequest], dict[str, Any]],
    sso_login_payload: Callable[..., dict[str, Any]],
    sso_callback_payload: Callable[..., Awaitable[dict[str, Any]]],
    security_audit_events_payload: Callable[..., dict[str, Any]],
    security_audit_action_catalog_payload: Callable[..., dict[str, Any]],
    security_audit_summary_payload: Callable[..., dict[str, Any]],
    security_audit_siem_export_payload: Callable[..., dict[str, Any]],
    security_audit_aggregate_report_payload: Callable[..., dict[str, Any]],
    security_audit_archive_policy_payload: Callable[..., dict[str, Any]],
    security_audit_legal_hold_payload: Callable[..., dict[str, Any]],
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

    @router.get("/api/auth/sso/config", response_model=sso_config_response_model)
    async def get_auth_sso_config(request: Request):
        require_remote_viewer(request)
        payload = sso_config_payload()
        audit_security_event(
            "get_auth_sso_config",
            request,
            details=(
                f"provider={payload['provider']} "
                f"enabled={payload['enabled']} ready={payload['ready']}"
            ),
        )
        return payload

    @router.put("/api/auth/sso/config", response_model=sso_config_response_model)
    async def save_auth_sso_config(request: Request, payload: SaveSsoConfigRequest):
        require_remote_admin(request)
        updated = save_sso_config_payload(payload)
        audit_security_event(
            "update_auth_sso_config",
            request,
            details=(
                f"provider={updated['provider']} "
                f"enabled={updated['enabled']} ready={updated['ready']} "
                f"client_secret_set={updated['client_secret_configured']}"
            ),
        )
        return updated

    @router.get("/api/auth/sso/login", response_model=sso_login_response_model)
    async def start_auth_sso_login(request: Request, response_mode: str = ""):
        try:
            payload = sso_login_payload(request, response_mode=response_mode)
        except ValueError as exc:
            audit_security_event(
                "start_auth_sso_login",
                request,
                result="blocked",
                details=str(exc),
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit_security_event(
            "start_auth_sso_login",
            request,
            details=_sso_login_audit_details(payload, response_mode),
        )
        return payload

    @router.get("/api/auth/sso/callback", response_model=sso_callback_response_model)
    async def complete_auth_sso_callback(
        request: Request,
        code: str = "",
        state: str = "",
        error: str = "",
        error_description: str = "",
        response_mode: str = "",
    ):
        if error:
            audit_security_event(
                "complete_auth_sso_callback",
                request,
                result="rejected",
                details=f"error={error} description={error_description}",
            )
            raise HTTPException(
                status_code=400,
                detail=error_description or error,
            )
        try:
            payload = await sso_callback_payload(
                request,
                code=code,
                state=state,
            )
        except ValueError as exc:
            audit_security_event(
                "complete_auth_sso_callback",
                request,
                result="rejected",
                details=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            audit_security_event(
                "complete_auth_sso_callback",
                request,
                result="blocked",
                details=str(exc),
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit_security_event(
            "complete_auth_sso_callback",
            request,
            details=_sso_callback_audit_details(payload),
        )
        if str(response_mode or "").strip().lower() == "fragment":
            token = str(payload["app_session_token"])
            html = (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>SSO Login Complete</title></head><body>"
                "<script>"
                f"sessionStorage.setItem('api_token', {token!r});"
                f"sessionStorage.setItem('admin_api_token', {token!r});"
                "window.location.replace('/');"
                "</script>"
                "</body></html>"
            )
            return HTMLResponse(html)
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
        category: str = "",
        user_id: str = "",
        since: str = "",
        until: str = "",
    ):
        require_remote_admin(request)
        payload = security_audit_events_payload(
            limit=limit,
            action=action,
            result=result,
            category=category,
            user_id=user_id,
            since=since,
            until=until,
        )
        audit_security_event(
            "get_security_audit_events",
            request,
            details=(
                f"limit={payload['limit']} "
                f"action={action or '<all>'} "
                f"result={result or '<all>'} "
                f"category={category or '<all>'} "
                f"user_id={user_id or '<all>'} "
                f"since={payload['filters']['since']} "
                f"until={payload['filters']['until']} "
                f"total={payload['total']}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-actions",
        response_model=security_audit_action_catalog_response_model,
    )
    async def get_security_audit_actions(
        request: Request,
        category: str = "",
    ):
        require_remote_admin(request)
        payload = security_audit_action_catalog_payload(category=category)
        audit_security_event(
            "get_security_audit_actions",
            request,
            details=(
                f"category={category or '<all>'} "
                f"total={payload['total']}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-summary",
        response_model=security_audit_summary_response_model,
    )
    async def get_security_audit_summary(
        request: Request,
        category: str = "",
        limit: int = 0,
    ):
        require_remote_admin(request)
        payload = security_audit_summary_payload(category=category, limit=limit)
        audit_security_event(
            "get_security_audit_summary",
            request,
            details=(
                f"category={category or '<all>'} "
                f"limit={payload['window_limit']} "
                f"total={payload['total']}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-siem-export",
        response_model=security_audit_siem_export_response_model,
    )
    async def export_security_audit_siem(
        request: Request,
        format: str = "json",
        limit: int = 100,
        action: str = "",
        result: str = "",
        category: str = "",
        user_id: str = "",
        since: str = "",
        until: str = "",
    ):
        require_remote_admin(request)
        payload = security_audit_siem_export_payload(
            format=format,
            limit=limit,
            action=action,
            result=result,
            category=category,
            user_id=user_id,
            since=since,
            until=until,
        )
        audit_security_event(
            "export_security_audit_siem",
            request,
            details=(
                f"format={payload['format']} "
                f"limit={payload['limit']} "
                f"total={payload['total']}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-aggregate-report",
        response_model=security_audit_aggregate_report_response_model,
    )
    async def get_security_audit_aggregate_report(
        request: Request,
        limit: int = 0,
        action: str = "",
        result: str = "",
        category: str = "",
        user_id: str = "",
        since: str = "",
        until: str = "",
    ):
        require_remote_admin(request)
        payload = security_audit_aggregate_report_payload(
            limit=limit,
            action=action,
            result=result,
            category=category,
            user_id=user_id,
            since=since,
            until=until,
        )
        audit_security_event(
            "get_security_audit_aggregate_report",
            request,
            details=(
                f"limit={payload['window_limit']} "
                f"total={payload['total']} "
                f"rows={len(payload['rows'])}"
            ),
        )
        return payload

    @router.get(
        "/api/security/audit-archive-policy",
        response_model=security_audit_archive_policy_response_model,
    )
    async def get_security_audit_archive_policy(
        request: Request,
        mode: str = "preview",
        retention_days: int = 365,
        limit: int = 100,
        legal_hold: bool = False,
    ):
        require_remote_admin(request)
        payload = security_audit_archive_policy_payload(
            mode=mode,
            retention_days=retention_days,
            limit=limit,
            legal_hold=legal_hold,
        )
        audit_security_event(
            "get_security_audit_archive_policy",
            request,
            details=(
                f"mode={payload['mode']} "
                f"retention_days={payload['retention_days']} "
                f"candidates={payload['archive_candidate_count']} "
                f"legal_hold={payload['legal_hold_count']}"
            ),
        )
        return payload

    @router.post(
        "/api/security/audit-events/legal-hold",
        response_model=security_audit_legal_hold_response_model,
    )
    async def set_security_audit_legal_hold(
        request: Request,
        request_id: str,
        legal_hold: bool = True,
    ):
        require_remote_admin(request)
        payload = security_audit_legal_hold_payload(
            request_id=request_id,
            legal_hold=legal_hold,
        )
        audit_security_event(
            "set_security_audit_legal_hold",
            request,
            result="ok" if payload["updated_count"] else "not_found",
            details=(
                f"request_id={payload['request_id']} "
                f"legal_hold={payload['legal_hold']} "
                f"updated={payload['updated_count']}"
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
        dry_run: bool = False,
    ):
        require_remote_admin(request)
        payload = cleanup_security_audit_events(
            keep_latest=keep_latest,
            dry_run=dry_run,
        )
        audit_security_event(
            "cleanup_security_audit_events",
            request,
            details=(
                f"keep_latest={payload['keep_latest']} "
                f"dry_run={payload['dry_run']} "
                f"would_delete={payload['would_delete_count']} "
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
