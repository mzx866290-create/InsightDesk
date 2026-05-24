"""SSO and OIDC runtime helpers.

The API server keeps thin compatibility wrappers for these helpers. This module
holds the implementation so security/auth state is easier to reason about and
test without growing ``api_server.py`` further.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

import httpx
from fastapi import Request

from backend.helpers.identity_helpers import (
    sync_external_identity_payload as build_sync_external_identity_payload,
)
from backend.helpers.security_helpers import (
    build_sso_login_payload,
    normalize_auth_role,
    pkce_code_challenge,
    sso_callback_url_for_mode,
    sso_session_token_hash,
)
from backend.schemas.api_models import SyncExternalIdentityRequest


SSO_RUNTIME_CONTEXT_ATTRIBUTES = (
    "AUTH_ROLE_RANKS",
    "DEFAULT_AUTH_ROLE",
    "OIDC_ALLOWED_DOMAINS",
    "OIDC_AUTHORIZATION_ENDPOINT",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_ISSUER_URL",
    "OIDC_JWKS_URL",
    "OIDC_SCOPES",
    "OIDC_TOKEN_ENDPOINT",
    "SSO_DEFAULT_ROLE",
    "SSO_LOGIN_STATE_TTL_SECONDS",
    "SSO_PROVIDER",
    "SSO_SESSION_TTL_SECONDS",
    "_INITIAL_SSO_CONFIG_VALUES",
    "_SSO_CONFIG_FIELDS",
    "_app_config_store",
    "_effective_sso_config_value",
    "_effective_sso_session_ttl_seconds",
    "_exchange_oidc_code",
    "_get_sso_session_store",
    "_identity_store",
    "_issue_sso_session_token",
    "_prune_sso_login_states",
    "_prune_sso_sessions",
    "_sso_callback_url",
    "_sso_login_states",
    "_sso_login_states_lock",
    "_sso_sessions",
    "_sso_sessions_lock",
    "_verify_oidc_id_token",
    "logger",
)


class SsoRuntimeContext:
    """Whitelist-backed dynamic proxy for SSO runtime dependencies."""

    __slots__ = ("_allowed_attributes", "_source")

    def __init__(
        self,
        source: Any,
        allowed_attributes: tuple[str, ...] = SSO_RUNTIME_CONTEXT_ATTRIBUTES,
    ) -> None:
        self._source = source
        self._allowed_attributes = frozenset(allowed_attributes)

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed_attributes:
            raise AttributeError(f"SSO runtime context has no dependency {name!r}")
        return getattr(self._source, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_allowed_attributes", "_source"}:
            object.__setattr__(self, name, value)
            return
        if name not in self._allowed_attributes:
            raise AttributeError(f"SSO runtime context has no dependency {name!r}")
        setattr(self._source, name, value)


def build_sso_runtime_context(source: Any) -> SsoRuntimeContext:
    missing = [
        attribute
        for attribute in SSO_RUNTIME_CONTEXT_ATTRIBUTES
        if not hasattr(source, attribute)
    ]
    if missing:
        raise AttributeError(
            "SSO runtime context missing required attributes: " + ", ".join(missing)
        )
    return SsoRuntimeContext(source)


def stored_sso_config_value(ctx: Any, field: str) -> str | None:
    spec = ctx._SSO_CONFIG_FIELDS.get(field)
    if spec is None:
        return None
    _, _, config_key, _ = spec
    try:
        record = ctx._app_config_store.get(config_key)
    except Exception:
        ctx.logger.exception("Failed to read persisted SSO config field=%s", field)
        return None
    return record.value if record is not None else None


def effective_sso_config_value(ctx: Any, field: str) -> str:
    spec = ctx._SSO_CONFIG_FIELDS[field]
    attr_name, _, _, default = spec
    current_value = str(getattr(ctx, attr_name, default) or "").strip()
    initial_value = ctx._INITIAL_SSO_CONFIG_VALUES.get(
        attr_name,
        str(default),
    ).strip()
    if current_value != initial_value:
        return current_value
    stored_value = stored_sso_config_value(ctx, field)
    if stored_value is not None:
        return str(stored_value or "").strip()
    return current_value


def effective_sso_session_ttl_seconds(ctx: Any) -> int:
    raw_value = ctx._effective_sso_config_value("session_ttl_seconds")
    try:
        return max(300, int(raw_value or str(8 * 60 * 60)))
    except (TypeError, ValueError):
        return 8 * 60 * 60


def set_sso_config_field(ctx: Any, field: str, value: str) -> None:
    attr_name, env_name, config_key, _ = ctx._SSO_CONFIG_FIELDS[field]
    if value:
        ctx._app_config_store.set(config_key, value)
        os.environ[env_name] = value
    else:
        ctx._app_config_store.delete(config_key)
        os.environ.pop(env_name, None)
    if attr_name == "SSO_SESSION_TTL_SECONDS":
        setattr(ctx, attr_name, int(value or str(8 * 60 * 60)))
    else:
        setattr(ctx, attr_name, value)


def sso_callback_url(request: Request) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/auth/sso/callback"


def prune_sso_login_states(ctx: Any, now: float | None = None) -> None:
    current_time = time.time() if now is None else float(now)
    expired_before = current_time - float(ctx.SSO_LOGIN_STATE_TTL_SECONDS)
    with ctx._sso_login_states_lock:
        expired = [
            state
            for state, record in ctx._sso_login_states.items()
            if float(record.get("created_at", 0.0) or 0.0) <= expired_before
        ]
        for state in expired:
            ctx._sso_login_states.pop(state, None)


def prune_sso_sessions(ctx: Any, now: float | None = None) -> None:
    current_time = time.time() if now is None else float(now)
    try:
        ctx._get_sso_session_store().prune(now=current_time)
    except Exception:
        ctx.logger.exception("Failed to prune persisted SSO sessions")
    with ctx._sso_sessions_lock:
        expired = [
            token
            for token, record in ctx._sso_sessions.items()
            if float(record.get("expires_at", 0.0) or 0.0) <= current_time
        ]
        for token in expired:
            ctx._sso_sessions.pop(token, None)


def issue_sso_session_token(ctx: Any, *, user_id: str, role: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("user_id is required")
    normalized_role = normalize_auth_role(
        role,
        role_ranks=ctx.AUTH_ROLE_RANKS,
        default=ctx.DEFAULT_AUTH_ROLE,
    )
    token = f"sso_{secrets.token_urlsafe(32)}"
    created_at = time.time()
    expires_at = created_at + float(ctx._effective_sso_session_ttl_seconds())
    ctx._prune_sso_sessions()
    session_record = {
        "user_id": normalized_user_id,
        "role": normalized_role,
        "auth_source": "sso_oidc",
        "expires_at": expires_at,
        "created_at": created_at,
    }
    try:
        ctx._get_sso_session_store().save(
            token_hash=sso_session_token_hash(token),
            user_id=normalized_user_id,
            role=normalized_role,
            auth_source="sso_oidc",
            created_at=created_at,
            expires_at=expires_at,
        )
    except Exception as exc:
        raise RuntimeError("Failed to persist SSO session") from exc
    with ctx._sso_sessions_lock:
        ctx._sso_sessions[token] = session_record
    return {
        "token": token,
        "expires_at": expires_at,
        "role": normalized_role,
    }


def resolve_sso_session_token(ctx: Any, token: str) -> dict[str, str] | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None
    ctx._prune_sso_sessions()
    token_hash = sso_session_token_hash(normalized_token)
    try:
        persisted = ctx._get_sso_session_store().get_active(token_hash)
    except Exception:
        ctx.logger.exception("Failed to resolve persisted SSO session")
        persisted = None
    if persisted is not None:
        return {
            "user_id": str(persisted.user_id or "").strip(),
            "role": str(persisted.role or ctx.DEFAULT_AUTH_ROLE).strip(),
            "auth_source": str(persisted.auth_source or "sso_oidc").strip(),
        }
    with ctx._sso_sessions_lock:
        record = ctx._sso_sessions.get(normalized_token)
        if record is None:
            return None
        return {
            "user_id": str(record.get("user_id") or "").strip(),
            "role": str(record.get("role") or ctx.DEFAULT_AUTH_ROLE).strip(),
            "auth_source": str(record.get("auth_source") or "sso_oidc").strip(),
        }


def sso_login_payload(
    ctx: Any,
    request: Request,
    response_mode: str = "",
) -> dict[str, Any]:
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(48)
    payload = build_sso_login_payload(
        provider=ctx._effective_sso_config_value("provider"),
        authorization_endpoint=ctx._effective_sso_config_value(
            "authorization_endpoint"
        ),
        client_id=ctx._effective_sso_config_value("client_id"),
        redirect_uri=sso_callback_url_for_mode(
            ctx._sso_callback_url(request),
            response_mode,
        ),
        state=state,
        nonce=nonce,
        code_challenge=pkce_code_challenge(code_verifier),
        scopes=ctx._effective_sso_config_value("scopes"),
    )
    ctx._prune_sso_login_states()
    with ctx._sso_login_states_lock:
        ctx._sso_login_states[state] = {
            "created_at": time.time(),
            "nonce": nonce,
            "code_verifier": code_verifier,
            "redirect_uri": payload["redirect_uri"],
        }
    return payload


async def exchange_oidc_code(
    ctx: Any,
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("authorization code is required")
    if ctx._effective_sso_config_value("provider").lower() != "oidc":
        raise ValueError("SSO_PROVIDER must be oidc")
    token_endpoint = ctx._effective_sso_config_value("token_endpoint")
    if not token_endpoint:
        raise RuntimeError("OIDC_TOKEN_ENDPOINT is required")
    data = {
        "grant_type": "authorization_code",
        "code": normalized_code,
        "redirect_uri": str(redirect_uri or "").strip(),
        "client_id": ctx._effective_sso_config_value("client_id"),
        "code_verifier": str(code_verifier or "").strip(),
    }
    client_secret = ctx._effective_sso_config_value("client_secret")
    if client_secret:
        data["client_secret"] = client_secret
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                token_endpoint,
                data=data,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("OIDC token exchange failed") from exc
    if response.status_code >= 400:
        raise RuntimeError("OIDC token exchange failed")
    try:
        raw_payload = response.json()
    except ValueError as exc:
        raise RuntimeError("OIDC token response is not JSON") from exc
    if not isinstance(raw_payload, dict):
        raise RuntimeError("OIDC token response is not a JSON object")
    payload = {str(key): value for key, value in raw_payload.items()}
    if not str(payload.get("id_token") or "").strip():
        raise RuntimeError("OIDC token response missing id_token")
    return payload


def verify_oidc_id_token(ctx: Any, id_token: str, *, nonce: str) -> dict[str, Any]:
    normalized_id_token = str(id_token or "").strip()
    if not normalized_id_token:
        raise ValueError("id_token is required")
    jwks_url = ctx._effective_sso_config_value("jwks_url")
    if not jwks_url:
        raise RuntimeError("OIDC_JWKS_URL is required")
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise RuntimeError("PyJWT[crypto] is required for OIDC ID token verification") from exc
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(
            normalized_id_token
        )
        claims = jwt.decode(
            normalized_id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=ctx._effective_sso_config_value("client_id"),
            issuer=ctx._effective_sso_config_value("issuer_url"),
        )
    except Exception as exc:
        raise ValueError("OIDC ID token verification failed") from exc
    expected_nonce = str(nonce or "").strip()
    if expected_nonce and str(claims.get("nonce") or "").strip() != expected_nonce:
        raise ValueError("OIDC nonce mismatch")
    return dict(claims)


async def sso_callback_payload(
    ctx: Any,
    request: Request,
    *,
    code: str,
    state: str,
) -> dict[str, Any]:
    normalized_state = str(state or "").strip()
    if not normalized_state:
        raise ValueError("state is required")
    ctx._prune_sso_login_states()
    with ctx._sso_login_states_lock:
        state_record = ctx._sso_login_states.pop(normalized_state, None)
    if state_record is None:
        raise ValueError("Invalid or expired SSO state")

    token_payload = await ctx._exchange_oidc_code(
        code=code,
        redirect_uri=str(state_record.get("redirect_uri") or ctx._sso_callback_url(request)),
        code_verifier=str(state_record.get("code_verifier") or ""),
    )
    claims = ctx._verify_oidc_id_token(
        str(token_payload.get("id_token") or ""),
        nonce=str(state_record.get("nonce") or ""),
    )
    sync_request = SyncExternalIdentityRequest(
        claims=claims,
        provider=ctx._effective_sso_config_value("provider") or "oidc",
    )
    payload = build_sync_external_identity_payload(
        sync_request,
        identity_store=ctx._identity_store,
        effective_config_value=ctx._effective_sso_config_value,
        now=time.time,
    )
    payload["auth_source"] = "oidc"
    payload["token_type"] = str(token_payload.get("token_type") or "")
    expires_in = token_payload.get("expires_in")
    payload["expires_in"] = int(expires_in) if expires_in is not None else None
    session = ctx._issue_sso_session_token(
        user_id=str(payload["user"]["user_id"] or ""),
        role=ctx._effective_sso_config_value("default_role"),
    )
    payload["app_session_token"] = session["token"]
    payload["app_session_expires_at"] = session["expires_at"]
    payload["role"] = session["role"]
    return payload


__all__ = [
    "SSO_RUNTIME_CONTEXT_ATTRIBUTES",
    "SsoRuntimeContext",
    "build_sso_runtime_context",
    "effective_sso_config_value",
    "effective_sso_session_ttl_seconds",
    "exchange_oidc_code",
    "issue_sso_session_token",
    "prune_sso_login_states",
    "prune_sso_sessions",
    "resolve_sso_session_token",
    "set_sso_config_field",
    "sso_callback_payload",
    "sso_callback_url",
    "sso_login_payload",
    "stored_sso_config_value",
    "verify_oidc_id_token",
]
