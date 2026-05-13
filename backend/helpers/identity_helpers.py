from __future__ import annotations

from typing import Any, Callable

from backend.stores.identity_store import normalize_identity_role


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = [value]
    items: list[str] = []
    for item in raw_items:
        normalized = str(item or "").strip()
        if normalized:
            items.append(normalized)
    return items


def _normalize_domain_list(domains: list[str] | str) -> list[str]:
    return [item.lower() for item in _string_list(domains)]


def map_external_identity_claims(
    claims: dict[str, Any],
    *,
    provider: str = "oidc",
    allowed_domains: list[str] | str = (),
) -> dict[str, Any]:
    """Map verified external identity claims to the local identity shape.

    This helper intentionally does not verify OIDC tokens. It should only be
    called after a trusted auth layer has already validated the external claims.
    """
    normalized_claims = dict(claims or {})
    normalized_provider = str(provider or "oidc").strip().lower() or "oidc"
    subject = str(normalized_claims.get("sub") or "").strip()
    if not subject:
        raise ValueError("external claim sub is required")

    email = str(normalized_claims.get("email") or "").strip().lower()
    domains = _normalize_domain_list(allowed_domains)
    if domains:
        if "@" not in email:
            raise ValueError("email is required when allowed domains are configured")
        domain = email.rsplit("@", 1)[-1].lower()
        if domain not in domains:
            raise ValueError("external identity email domain is not allowed")

    display_name = (
        str(normalized_claims.get("name") or "").strip()
        or str(normalized_claims.get("preferred_username") or "").strip()
        or email
        or subject
    )
    return {
        "provider": normalized_provider,
        "external_subject": subject,
        "user_id": f"{normalized_provider}:{subject}",
        "email": email,
        "display_name": display_name,
        "groups": _string_list(normalized_claims.get("groups")),
    }


def sync_external_identity(
    *,
    identity_store: Any,
    claims: dict[str, Any],
    provider: str,
    allowed_domains: list[str] | str,
    default_org_id: str = "",
    default_role: str = "viewer",
    group_org_map: dict[str, str] | None = None,
    group_role_map: dict[str, str] | None = None,
    now: Callable[[], float],
) -> dict[str, Any]:
    mapped = map_external_identity_claims(
        claims,
        provider=provider,
        allowed_domains=allowed_domains,
    )
    user = identity_store.upsert_user(
        user_id=mapped["user_id"],
        display_name=mapped["display_name"],
        email=mapped["email"],
        now=now(),
    )

    memberships = []
    normalized_default_org_id = str(default_org_id or "").strip()
    normalized_default_role = normalize_identity_role(default_role)
    if normalized_default_org_id:
        memberships.append(
            identity_store.set_membership(
                org_id=normalized_default_org_id,
                user_id=user.user_id,
                role=normalized_default_role,
                now=now(),
            )
        )

    resolved_group_org_map = dict(group_org_map or {})
    resolved_group_role_map = dict(group_role_map or {})
    for group in mapped["groups"]:
        org_id = str(resolved_group_org_map.get(group) or "").strip()
        if not org_id:
            continue
        role = normalize_identity_role(
            resolved_group_role_map.get(group) or normalized_default_role
        )
        membership = identity_store.set_membership(
            org_id=org_id,
            user_id=user.user_id,
            role=role,
            now=now(),
        )
        if not any(item.org_id == membership.org_id for item in memberships):
            memberships.append(membership)

    return {
        "user": dict(user.__dict__),
        "memberships": [dict(item.__dict__) for item in memberships],
        "external": {
            "provider": mapped["provider"],
            "external_subject": mapped["external_subject"],
            "groups": mapped["groups"],
        },
    }


def sync_external_identity_payload(
    body: Any,
    *,
    identity_store: Any,
    effective_config_value: Callable[[str], str],
    now: Callable[[], float],
) -> dict[str, Any]:
    allowed_domains = getattr(body, "allowed_domains", None) or [
        item.strip()
        for item in str(effective_config_value("allowed_domains") or "").split(",")
        if item.strip()
    ]
    return sync_external_identity(
        identity_store=identity_store,
        claims=getattr(body, "claims", {}),
        provider=getattr(body, "provider", None)
        or effective_config_value("provider")
        or "oidc",
        allowed_domains=allowed_domains,
        default_org_id=getattr(body, "default_org_id", ""),
        default_role=getattr(body, "default_role", "viewer"),
        group_org_map=getattr(body, "group_org_map", None),
        group_role_map=dict(getattr(body, "group_role_map", {}) or {}),
        now=now,
    )


__all__ = [
    "map_external_identity_claims",
    "sync_external_identity",
    "sync_external_identity_payload",
]
