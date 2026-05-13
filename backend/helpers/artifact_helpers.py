from __future__ import annotations

from typing import Any, Callable


def artifact_payload(
    artifact: Any,
    *,
    artifact_export_formats: Callable[[Any], list[str]],
) -> dict[str, Any]:
    payload = artifact.model_dump(mode="json")
    payload["available_formats"] = artifact_export_formats(artifact)
    return payload
