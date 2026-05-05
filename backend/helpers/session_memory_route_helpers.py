from typing import Any


def session_memory_payload(
    *,
    session_id: str,
    session: dict[str, Any] | None,
    memories: list[dict[str, Any]],
) -> dict[str, Any]:
    if not session:
        raise KeyError("Session not found")
    return {
        "session_id": session_id,
        "memories": memories,
    }


def pin_session_memory_payload(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        raise KeyError("Session not found")
    return {
        "ok": True,
        "created": bool(result.get("created")),
        "memory": result.get("memory", {}),
    }


def session_memory_updates(
    request: Any,
    *,
    field_set: set[str],
) -> dict[str, Any]:
    if "content" not in field_set and "kind" not in field_set:
        raise ValueError("At least one memory field is required")

    updates: dict[str, Any] = {}
    if "content" in field_set:
        if request.content is None:
            raise ValueError("content must be a non-empty string")
        updates["content"] = request.content
    if "kind" in field_set:
        if request.kind is None:
            raise ValueError("kind must be a valid memory kind")
        updates["kind"] = request.kind
    return updates


def update_session_memory_payload(memory: dict[str, Any] | None) -> dict[str, Any]:
    if not memory:
        raise KeyError("Session memory not found")
    return {
        "ok": True,
        "memory": memory,
    }


def summarize_session_memory_payload(
    *,
    session: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not session or not result:
        raise KeyError("Session not found")
    return {
        "ok": True,
        **result,
    }


def delete_session_memory_payload(deleted: bool) -> dict[str, Any]:
    if not deleted:
        raise KeyError("Session memory not found")
    return {"ok": True}
