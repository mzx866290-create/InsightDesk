import logging
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request


def _record_payload(record: Any) -> dict[str, Any]:
    if hasattr(record, "__dict__"):
        return dict(record.__dict__)
    return dict(record)


def build_identity_router(
    *,
    identity_catalog_response_model: type,
    organization_response_model: type,
    user_response_model: type,
    membership_response_model: type,
    sync_external_identity_response_model: type,
    upsert_organization_request_model: type,
    upsert_user_request_model: type,
    set_membership_request_model: type,
    sync_external_identity_request_model: type,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    identity_store: Callable[[], Any],
    sync_external_identity_payload: Callable[[Any], dict[str, Any]],
    audit_security_event: Callable[..., Any],
    now: Callable[[], float],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/identity", response_model=identity_catalog_response_model)
    async def get_identity_catalog(request: Request, limit: int = 100):
        require_remote_viewer(request)
        store = identity_store()
        payload = {
            "organizations": [
                _record_payload(item) for item in store.list_orgs(limit=limit)
            ],
            "users": [_record_payload(item) for item in store.list_users(limit=limit)],
            "memberships": [
                _record_payload(item) for item in store.list_memberships(limit=limit)
            ],
        }
        audit_security_event(
            "get_identity_catalog",
            request,
            details=(
                f"orgs={len(payload['organizations'])} "
                f"users={len(payload['users'])} "
                f"memberships={len(payload['memberships'])}"
            ),
        )
        return payload

    @router.post("/api/identity/orgs", response_model=organization_response_model)
    async def upsert_organization(
        request: Request, body: upsert_organization_request_model
    ):
        require_remote_admin(request)
        try:
            record = identity_store().upsert_org(
                org_id=body.org_id,
                name=body.name,
                description=body.description,
                now=now(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "upsert_identity_org",
            request,
            details=f"org_id={record.org_id}",
        )
        return _record_payload(record)

    @router.post("/api/identity/users", response_model=user_response_model)
    async def upsert_user(request: Request, body: upsert_user_request_model):
        require_remote_admin(request)
        try:
            record = identity_store().upsert_user(
                user_id=body.user_id,
                display_name=body.display_name,
                email=body.email,
                now=now(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "upsert_identity_user",
            request,
            details=f"user_id={record.user_id}",
        )
        return _record_payload(record)

    @router.post(
        "/api/identity/sso/sync",
        response_model=sync_external_identity_response_model,
    )
    async def sync_external_identity(
        request: Request,
        body: sync_external_identity_request_model,
    ):
        require_remote_admin(request)
        try:
            payload = sync_external_identity_payload(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "sync_external_identity",
            request,
            details=(
                f"provider={payload['external']['provider']} "
                f"user_id={payload['user']['user_id']} "
                f"memberships={len(payload['memberships'])}"
            ),
        )
        return payload

    @router.post("/api/identity/memberships", response_model=membership_response_model)
    async def set_membership(request: Request, body: set_membership_request_model):
        require_remote_admin(request)
        try:
            record = identity_store().set_membership(
                org_id=body.org_id,
                user_id=body.user_id,
                role=body.role,
                now=now(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "set_identity_membership",
            request,
            details=f"org_id={record.org_id} user_id={record.user_id} role={record.role}",
        )
        return _record_payload(record)

    return router
