"""Regression tests for reverse-proxy local detection, ACL fail-closed writes,
and webhook outbound scope guards."""

from __future__ import annotations

import pytest
from fastapi import Request

from backend.agent.agents.integrator.execution import validate_webhook_outbound_scope
from backend.core import request_runtime
from backend.routes.resource_access_helpers import require_resource_access


def _make_request(
    client: tuple[str, int] | None,
    *,
    forwarded_for: str = "",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("utf-8")))
    return Request(
        scope={
            "type": "http",
            "client": client,
            "headers": headers,
            "method": "POST",
            "path": "/api/chat/single",
        }
    )


class _AccessStore:
    def __init__(self, *, grants: list[tuple[str, str, str]] | None = None):
        self.grants = list(grants or [])

    def list_grants(self, *, resource_type: str, resource_id: str, limit: int):
        return [
            record
            for record in self.grants
            if record[0] == resource_type and record[1] == resource_id
        ][:limit]

    def resolve_user_access(self, **kwargs):
        from backend.stores.identity_store import (
            IDENTITY_ROLE_RANKS,
            normalize_identity_role,
        )

        user_id = str(kwargs.get("user_id") or "")
        minimum_role = normalize_identity_role(
            str(kwargs.get("minimum_role") or "viewer")
        )
        best_role = ""
        best_rank = 0
        for resource_type, resource_id, role, subject in self.grants:
            if subject == user_id:
                rank = IDENTITY_ROLE_RANKS[normalize_identity_role(role)]
                if rank > best_rank:
                    best_role = role
                    best_rank = rank
        from backend.stores.resource_access_store import ResourceAccessRecord

        return ResourceAccessRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            role=best_role,
            allowed=best_rank >= IDENTITY_ROLE_RANKS[minimum_role],
            source="user_grant" if best_role else "none",
        )

    def upsert_grant(self, **_kwargs):
        raise NotImplementedError


class _IdentityStore:
    def list_memberships(self, **kwargs):
        return []


def test_direct_loopback_request_is_local(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
    request = _make_request(("127.0.0.1", 4321))
    assert request_runtime.request_is_local_origin(request) is True


def test_forwarded_header_without_declared_proxy_is_not_local(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
    request = _make_request(("127.0.0.1", 4321), forwarded_for="203.0.113.9")
    assert request_runtime.request_is_local_origin(request) is False
    assert request_runtime.request_client_ip(request) == "127.0.0.1"


def test_trusted_proxy_chain_reveals_remote_client(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    request = _make_request(("127.0.0.1", 4321), forwarded_for="203.0.113.9")
    assert request_runtime.request_is_local_origin(request) is False
    assert request_runtime.request_client_ip(request) == "203.0.113.9"


def test_trusted_local_chain_remains_local(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    request = _make_request(("127.0.0.1", 4321), forwarded_for="127.0.0.1")
    assert request_runtime.request_is_local_origin(request) is True


def test_missing_client_is_unix_socket_local():
    request = _make_request(None)
    assert request_runtime.request_is_local_origin(request) is True


@pytest.mark.parametrize(
    ("auth", "minimum_role", "expected_denied"),
    [
        ({"user_id": "viewer", "role": "viewer"}, "editor", True),
        ({"user_id": "editor", "role": "editor"}, "editor", False),
        ({"user_id": "viewer", "role": "viewer"}, "viewer", False),
        ({"user_id": "admin", "role": "admin"}, "editor", False),
    ],
)
def test_legacy_resource_without_acl_gates_on_global_role(
    auth, minimum_role, expected_denied
):
    access_store = _AccessStore()

    def require_remote_role(request):
        return auth

    if expected_denied:
        with pytest.raises(Exception) as exc_info:
            require_resource_access(
                object(),
                resource_type="session",
                resource_id="legacy-session",
                minimum_role=minimum_role,
                require_remote_role=require_remote_role,
                access_store=access_store,
                identity_store=_IdentityStore(),
            )
        assert exc_info.value.status_code == 403
    else:
        result = require_resource_access(
            object(),
            resource_type="session",
            resource_id="legacy-session",
            minimum_role=minimum_role,
            require_remote_role=require_remote_role,
            access_store=access_store,
            identity_store=_IdentityStore(),
        )
        assert result == auth


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/hook",
        "http://10.0.0.5/hook",
        "http://192.168.1.10/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/hook",
        "http://localhost/hook",
        "https://hook.local/notify",
        "https://secret.internal/notify",
        "http://metadata/notify",
        "http://user:pass@example.com/hook",
    ],
)
def test_webhook_outbound_scope_rejects_private_targets(url):
    assert validate_webhook_outbound_scope(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.example.com/ops",
        "http://93.184.216.34:8080/hook",
        "https://hooks.example.test/ops",
    ],
)
def test_webhook_outbound_scope_allows_public_targets(url):
    assert validate_webhook_outbound_scope(url) == ""
