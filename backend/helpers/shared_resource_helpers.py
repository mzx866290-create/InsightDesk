from typing import Any, Callable


def open_shared_resource_payload(
    share_token: str,
    request: Any,
    *,
    secret: str,
    decode_share_token: Callable[[str, str], tuple[str, str]],
    build_share_url: Callable[[Any, str], str],
    build_session_messages_payload: Callable[[str], dict[str, Any]],
    render_shared_session_html: Callable[[dict[str, Any], str], str],
    get_deck: Callable[[str], Any],
    render_shared_deck_html: Callable[[Any, str], str],
) -> dict[str, str]:
    resource_type, resource_id = decode_share_token(share_token, secret)
    share_url = build_share_url(request, share_token)

    if resource_type == "session":
        try:
            payload = build_session_messages_payload(resource_id)
        except KeyError as exc:
            raise KeyError("未找到会话") from exc
        return {
            "content": render_shared_session_html(payload, share_url),
            "media_type": "text/html; charset=utf-8",
        }

    if resource_type == "deck":
        try:
            deck = get_deck(resource_id)
        except KeyError as exc:
            raise KeyError("未找到演示稿") from exc
        return {
            "content": render_shared_deck_html(deck, share_url),
            "media_type": "text/html; charset=utf-8",
        }

    raise ValueError("不支持的共享资源类型")
