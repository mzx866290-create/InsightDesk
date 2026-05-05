"""Compatibility proxy for ``backend.artifact_service``."""

from importlib import import_module
from types import ModuleType
from typing import Any

_LEGACY_MODULE_NAME = "backend.artifact_service"


def _legacy_module() -> ModuleType:
    return import_module(_LEGACY_MODULE_NAME)


def __getattr__(name: str) -> Any:
    return getattr(_legacy_module(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_legacy_module())))


__all__ = [
    name
    for name in dir(_legacy_module())
    if not (name.startswith("__") and name.endswith("__"))
]
