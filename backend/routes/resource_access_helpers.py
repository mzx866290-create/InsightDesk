"""Shared resource access helpers for route modules."""

from __future__ import annotations

from typing import Any, Callable, Iterable, TypeVar

from fastapi import HTTPException, Request

T = TypeVar("T")


def _audit_resource_event(
    audit_security_event: Callable[..., Any] | None,
    request: Request | None,
    action: str,
    *,
    result: str = "ok",
    details: str = "",
) -> None:
    if audit_security_event is None or request is None:
        return
    audit_security_event(action, request, result=result, details=details)


def _resolve_store(store: Any | Callable[[], Any]) -> Any:
    return store() if callable(store) else store


def _resource_has_acl(
    *,
    access_store: Any | Callable[[], Any],
    resource_type: str,
    resource_id: str,
) -> bool:
    store = _resolve_store(access_store)
    grants = store.list_grants(
        resource_type=resource_type,
        resource_id=resource_id,
        limit=1,
    )
    return bool(grants)


def require_resource_access(
    request: Request,
    *,
    resource_type: str,
    resource_id: str,
    minimum_role: str,
    require_remote_role: Callable[[Request], dict[str, Any]],
    access_store: Any | Callable[[], Any],
    identity_store: Any | Callable[[], Any],
    audit_security_event: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Require access only when a resource has explicit ACL grants.

    This keeps legacy local/single-user resources readable until they are given
    explicit grants, while newly created resources can be locked down by writing
    an owner grant at creation time.
    """
    auth = require_remote_role(request)
    if auth.get("bypass_enabled"):
        return auth
    normalized_resource_id = str(resource_id or "").strip()
    if not normalized_resource_id:
        raise HTTPException(status_code=400, detail="resource_id is required")
    store = _resolve_store(access_store)
    if not _resource_has_acl(
        access_store=store,
        resource_type=resource_type,
        resource_id=normalized_resource_id,
    ):
        return auth
    access = store.resolve_user_access(
        resource_type=resource_type,
        resource_id=normalized_resource_id,
        user_id=str(auth.get("user_id") or ""),
        identity_store=_resolve_store(identity_store),
        minimum_role=minimum_role,
    )
    if not access.allowed:
        _audit_resource_event(
            audit_security_event,
            request,
            "resource_access_denied",
            result="rejected",
            details=(
                f"resource_type={resource_type} resource_id={normalized_resource_id} "
                f"user_id={str(auth.get('user_id') or '')} required_role={minimum_role} "
                f"effective_role={access.role or '<none>'} source={access.source}"
            ),
        )
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient resource role: {minimum_role} required.",
        )
    return auth


def grant_resource_owner(
    request: Request,
    *,
    resource_type: str,
    resource_id: str,
    require_remote_role: Callable[[Request], dict[str, Any]],
    access_store: Any | Callable[[], Any],
    now: Callable[[], float],
    audit_security_event: Callable[..., Any] | None = None,
) -> None:
    auth = require_remote_role(request)
    if auth.get("bypass_enabled"):
        return
    user_id = str(auth.get("user_id") or "").strip()
    if not user_id:
        return
    _resolve_store(access_store).upsert_grant(
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        role="owner",
        now=now(),
    )
    _audit_resource_event(
        audit_security_event,
        request,
        "resource_owner_granted",
        details=(
            f"resource_type={resource_type} resource_id={resource_id} "
            f"user_id={user_id} role=owner"
        ),
    )


def inherit_resource_grants(
    *,
    source_resource_type: str,
    source_resource_id: str,
    target_resource_type: str,
    target_resource_id: str,
    access_store: Any | Callable[[], Any],
    now: Callable[[], float],
    audit_security_event: Callable[..., Any] | None = None,
    request: Request | None = None,
) -> int:
    """Copy explicit ACL grants from one resource to a derived resource."""
    normalized_source_id = str(source_resource_id or "").strip()
    normalized_target_id = str(target_resource_id or "").strip()
    if not normalized_source_id or not normalized_target_id:
        return 0
    store = _resolve_store(access_store)
    copied = 0
    for grant in store.list_grants(
        resource_type=source_resource_type,
        resource_id=normalized_source_id,
        limit=500,
    ):
        store.upsert_grant(
            resource_type=target_resource_type,
            resource_id=normalized_target_id,
            org_id=str(getattr(grant, "org_id", "") or ""),
            user_id=str(getattr(grant, "user_id", "") or ""),
            role=str(getattr(grant, "role", "viewer") or "viewer"),
            now=now(),
        )
        copied += 1
    if copied:
        _audit_resource_event(
            audit_security_event,
            request,
            "resource_grants_inherited",
            details=(
                f"source_type={source_resource_type} source_id={normalized_source_id} "
                f"target_type={target_resource_type} target_id={normalized_target_id} copied={copied}"
            ),
        )
    return copied


def filter_visible_resources(
    request: Request,
    resources: Iterable[T],
    *,
    resource_type: str,
    resource_id_getter: Callable[[T], str],
    require_remote_role: Callable[[Request], dict[str, Any]],
    access_store: Any | Callable[[], Any],
    identity_store: Any | Callable[[], Any],
) -> list[T]:
    auth = require_remote_role(request)
    if auth.get("bypass_enabled"):
        return list(resources)
    store = _resolve_store(access_store)
    resolved_identity_store = _resolve_store(identity_store)
    user_id = str(auth.get("user_id") or "").strip()
    visible: list[T] = []
    for resource in resources:
        resource_id = str(resource_id_getter(resource) or "").strip()
        if not resource_id:
            continue
        if not _resource_has_acl(
            access_store=store,
            resource_type=resource_type,
            resource_id=resource_id,
        ):
            visible.append(resource)
            continue
        access = store.resolve_user_access(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            identity_store=resolved_identity_store,
            minimum_role="viewer",
        )
        if access.allowed:
            visible.append(resource)
    return visible
