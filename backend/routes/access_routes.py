import logging
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request


def _record_payload(record: Any) -> dict[str, Any]:
    if hasattr(record, "__dict__"):
        return dict(record.__dict__)
    return dict(record)


def _is_owner(record: Any) -> bool:
    return str(getattr(record, "role", "") or "").strip().lower() == "owner"


def _owner_count(store: Any, *, resource_type: str, resource_id: str) -> int:
    return sum(
        1
        for grant in store.list_grants(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=500,
        )
        if _is_owner(grant)
    )


def build_access_router(
    *,
    resource_grant_response_model: type,
    resource_grant_list_response_model: type,
    resource_access_response_model: type,
    role_permission_matrix_response_model: type,
    upsert_resource_grant_request_model: type,
    delete_resource_grant_request_model: type,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    access_store: Callable[[], Any],
    identity_store: Callable[[], Any],
    role_permission_matrix_payload: Callable[[], dict[str, Any]],
    audit_security_event: Callable[..., Any],
    now: Callable[[], float],
    logger: logging.Logger,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/api/access/resource-grants",
        response_model=resource_grant_list_response_model,
    )
    async def list_resource_grants(
        request: Request,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        role: str = "",
        subject_type: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        require_remote_viewer(request)
        try:
            store = access_store()
            grants = store.list_grants(
                resource_type=resource_type,
                resource_id=resource_id,
                org_id=org_id,
                user_id=user_id,
                role=role,
                subject_type=subject_type,
                limit=limit,
                offset=offset,
            )
            total = store.count_grants(
                resource_type=resource_type,
                resource_id=resource_id,
                org_id=org_id,
                user_id=user_id,
                role=role,
                subject_type=subject_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "list_resource_grants",
            request,
            details=(
                f"returned={len(grants)} total={total} "
                f"resource_type={resource_type} resource_id={resource_id} "
                f"role={role} subject_type={subject_type} offset={offset} limit={limit}"
            ),
        )
        return {
            "grants": [_record_payload(grant) for grant in grants],
            "total": total,
            "limit": max(1, min(int(limit or 100), 500)),
            "offset": max(0, int(offset or 0)),
            "returned": len(grants),
        }

    @router.get(
        "/api/access/role-matrix",
        response_model=role_permission_matrix_response_model,
    )
    async def get_access_role_matrix(request: Request):
        require_remote_viewer(request)
        payload = role_permission_matrix_payload()
        audit_security_event(
            "get_access_role_matrix",
            request,
            details=(
                f"roles={','.join(payload['roles'])} "
                f"operations={len(payload['operations'])}"
            ),
        )
        return payload

    @router.get(
        "/api/access/resources/{resource_type}/{resource_id}/me",
        response_model=resource_access_response_model,
    )
    async def get_my_resource_access(
        request: Request,
        resource_type: str,
        resource_id: str,
        minimum_role: str = "viewer",
    ):
        auth = require_remote_viewer(request)
        if auth.get("bypass_enabled"):
            return {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": str(auth.get("user_id") or "local"),
                "role": "admin",
                "allowed": True,
                "source": "local_bypass",
            }
        record = access_store().resolve_user_access(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=str(auth.get("user_id") or ""),
            identity_store=identity_store(),
            minimum_role=minimum_role,
        )
        audit_security_event(
            "get_resource_access",
            request,
            details=(
                f"resource_type={record.resource_type} resource_id={record.resource_id} "
                f"allowed={record.allowed} source={record.source}"
            ),
        )
        return _record_payload(record)

    @router.post(
        "/api/access/resource-grants",
        response_model=resource_grant_response_model,
    )
    async def upsert_resource_grant(
        request: Request, body: upsert_resource_grant_request_model
    ):
        require_remote_admin(request)
        store = access_store()
        try:
            existing = store.get_grant(
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                org_id=body.org_id,
                user_id=body.user_id,
            )
            if (
                existing is not None
                and _is_owner(existing)
                and str(body.role or "").strip().lower() != "owner"
                and _owner_count(
                    store,
                    resource_type=body.resource_type,
                    resource_id=body.resource_id,
                ) <= 1
            ):
                audit_security_event(
                    "upsert_resource_grant",
                    request,
                    result="rejected",
                    details=(
                        f"reason=last_owner_downgrade_blocked "
                        f"resource_type={body.resource_type} resource_id={body.resource_id} "
                        f"org_id={body.org_id} user_id={body.user_id}"
                    ),
                )
                raise HTTPException(
                    status_code=409,
                    detail="Cannot downgrade the last owner grant for a resource.",
                )
            record = store.upsert_grant(
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                org_id=body.org_id,
                user_id=body.user_id,
                role=body.role,
                now=now(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "upsert_resource_grant",
            request,
            details=(
                f"resource_type={record.resource_type} resource_id={record.resource_id} "
                f"org_id={record.org_id} user_id={record.user_id} role={record.role}"
            ),
        )
        return _record_payload(record)

    @router.delete("/api/access/resource-grants")
    async def delete_resource_grant(
        request: Request, body: delete_resource_grant_request_model
    ):
        require_remote_admin(request)
        store = access_store()
        try:
            existing = store.get_grant(
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                org_id=body.org_id,
                user_id=body.user_id,
            )
            if (
                existing is not None
                and _is_owner(existing)
                and _owner_count(
                    store,
                    resource_type=body.resource_type,
                    resource_id=body.resource_id,
                ) <= 1
            ):
                audit_security_event(
                    "delete_resource_grant",
                    request,
                    result="rejected",
                    details=(
                        f"reason=last_owner_delete_blocked "
                        f"resource_type={body.resource_type} resource_id={body.resource_id} "
                        f"org_id={body.org_id} user_id={body.user_id}"
                    ),
                )
                raise HTTPException(
                    status_code=409,
                    detail="Cannot delete the last owner grant for a resource.",
                )
            deleted = store.delete_grant(
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                org_id=body.org_id,
                user_id=body.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_security_event(
            "delete_resource_grant",
            request,
            result="ok" if deleted else "not_found",
            details=(
                f"resource_type={body.resource_type} resource_id={body.resource_id} "
                f"org_id={body.org_id} user_id={body.user_id}"
            ),
        )
        return {"ok": deleted}

    return router
