from __future__ import annotations

from typing import Any


def request_field_set(model: Any) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields or set())


def is_max_iterations_output(text: str) -> bool:
    lower = str(text or "").lower()
    return (
        "agent stopped due to max iterations" in lower
        or "agent stopped due to iteration limit" in lower
        or (lower.startswith("agent stopped") and "iteration" in lower)
    )


def dashboard_feature_enabled(dashboard_template: Any) -> bool:
    if not isinstance(dashboard_template, dict):
        return True
    return dashboard_template.get("enabled") is not False


__all__ = [
    "dashboard_feature_enabled",
    "is_max_iterations_output",
    "request_field_set",
]
