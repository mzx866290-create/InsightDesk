"""Route-level helpers for share-link endpoints."""

from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import Response


SHARE_LINK_NOT_FOUND_DETAIL = "Share link was not found."
SHARE_LINK_INVALID_OR_EXPIRED_DETAIL = "Share link is invalid or expired."
SHARE_LINK_RESOURCE_MISMATCH_DETAIL = "Share link resource does not match the token."


def list_share_links_payload(
    *,
    request: Any,
    resource_type: str = "",
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    share_link_store: Any,
    share_link_audit_payload: Callable[[Any], dict[str, Any]],
    audit_security_event: Callable[..., Any],
) -> dict[str, Any]:
    records = share_link_store.list_links(
        resource_type=resource_type,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    payload_records = [share_link_audit_payload(record) for record in records]
    payload = {
        "share_links": payload_records,
        "total": len(payload_records),
        "active_count": sum(1 for item in payload_records if item["is_active"]),
    }
    audit_security_event(
        "list_share_links",
        request,
        details=(
            f"resource_type={resource_type or '<all>'} "
            f"active_only={active_only} total={payload['total']}"
        ),
    )
    return payload


def revoke_share_link_result(
    *,
    share_token: str,
    request: Any,
    share_link_store: Any,
    token_fingerprint: Callable[[str], str],
    audit_security_event: Callable[..., Any],
    revoke_share_link_response_model: type,
) -> Any:
    if not share_link_store.revoke(share_token):
        raise HTTPException(status_code=404, detail=SHARE_LINK_NOT_FOUND_DETAIL)
    audit_security_event(
        "revoke_share_link",
        request,
        details=f"share_token_fp={token_fingerprint(share_token)}",
    )
    return revoke_share_link_response_model(ok=True)


def open_shared_resource_response(
    *,
    share_token: str,
    request: Any,
    share_secret: str,
    share_link_store: Any,
    decode_share_token: Callable[[str, str], tuple[str, str]],
    build_share_url: Callable[..., str],
    build_session_messages_payload: Callable[..., dict[str, Any]],
    render_shared_session_html: Callable[..., Any],
    get_deck: Callable[[str], Any],
    render_shared_deck_html: Callable[..., Any],
    request_client_ip: Callable[[Any], str],
    request_user_agent: Callable[[Any], str],
    audit_security_event: Callable[..., Any],
    token_fingerprint: Callable[[str], str],
    open_shared_resource_payload: Callable[..., dict[str, Any]],
) -> Response:
    try:
        link_record = share_link_store.get_active(share_token)
        if link_record is None:
            raise ValueError(SHARE_LINK_INVALID_OR_EXPIRED_DETAIL)

        decoded_type, decoded_id = decode_share_token(share_token, share_secret)
        if (
            link_record.resource_type != decoded_type
            or link_record.resource_id != decoded_id
        ):
            raise ValueError(SHARE_LINK_RESOURCE_MISMATCH_DETAIL)

        shared_payload = open_shared_resource_payload(
            share_token,
            request,
            secret=share_secret,
            decode_share_token=decode_share_token,
            build_share_url=build_share_url,
            build_session_messages_payload=build_session_messages_payload,
            render_shared_session_html=render_shared_session_html,
            get_deck=get_deck,
            render_shared_deck_html=render_shared_deck_html,
        )
        share_link_store.record_access(
            share_token,
            accessed_ip=request_client_ip(request),
            accessed_user_agent=request_user_agent(request),
        )
        audit_security_event(
            "open_shared_resource",
            request,
            details=(
                f"resource_type={decoded_type} "
                f"share_token_fp={token_fingerprint(share_token)}"
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        detail = str(exc.args[0]) if exc.args else "Not found"
        raise HTTPException(status_code=404, detail=detail) from exc

    return Response(
        content=shared_payload["content"],
        media_type=shared_payload["media_type"],
    )


__all__ = [
    "SHARE_LINK_INVALID_OR_EXPIRED_DETAIL",
    "SHARE_LINK_NOT_FOUND_DETAIL",
    "SHARE_LINK_RESOURCE_MISMATCH_DETAIL",
    "list_share_links_payload",
    "open_shared_resource_response",
    "revoke_share_link_result",
]
