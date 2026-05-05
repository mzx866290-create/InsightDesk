"""Share link helper utilities."""

import base64
import hashlib

from fastapi import Request


def share_signature(payload: str, secret: str) -> str:
    digest = hashlib.sha256(f"{payload}:{secret}".encode("utf-8")).hexdigest()
    return digest[:24]


def encode_share_token(resource_type: str, resource_id: str, secret: str) -> str:
    payload = f"{resource_type}:{resource_id}"
    signed_payload = f"{payload}:{share_signature(payload, secret)}"
    token = base64.urlsafe_b64encode(signed_payload.encode("utf-8")).decode("ascii")
    return token.rstrip("=")


def decode_share_token(token: str, secret: str) -> tuple[str, str]:
    normalized = str(token or "").strip()
    if not normalized:
        raise ValueError("Empty share token")

    padding = "=" * (-len(normalized) % 4)
    try:
        decoded = base64.urlsafe_b64decode((normalized + padding).encode("ascii")).decode(
            "utf-8"
        )
    except Exception as exc:
        raise ValueError("Invalid share token") from exc

    parts = decoded.split(":", 2)
    if len(parts) != 3:
        raise ValueError("Invalid share token")

    resource_type, resource_id, signature = parts
    payload = f"{resource_type}:{resource_id}"
    if signature != share_signature(payload, secret):
        raise ValueError("Invalid share token")
    if resource_type not in {"session", "deck"}:
        raise ValueError("Unsupported shared resource")
    return resource_type, resource_id


def build_share_url(request: Request, share_token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/shared/{share_token}"


__all__ = [
    "share_signature",
    "encode_share_token",
    "decode_share_token",
    "build_share_url",
]
