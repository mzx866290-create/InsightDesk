"""Compatibility re-export for the split :mod:`backend.agent` package.

New code should import from ``backend.agent`` or its focused submodules. This
module intentionally keeps the legacy ``backend.agent_core`` path working.
"""

import sys
from types import ModuleType

import backend.agent as _agent_pkg

__all__ = list(_agent_pkg.__all__)

_SPLIT_MODULE_NAMES = (
    "backend.agent.runtime_support",
    "backend.agent.tools",
    "backend.agent.runtime_tools",
    "backend.agent.fallbacks",
    "backend.agent.langgraph",
    "backend.agent.langgraph_helpers",
    "backend.agent.builder",
    "backend.agent.builder_wrappers",
    "backend.agent.builder_context",
    "backend.agent.builder_history",
    "backend.agent.builder_streaming",
    "backend.agent.dashboard",
    "backend.agent.dashboard_payload",
    "backend.agent.dashboard_attachments",
    "backend.agent.runtime_intent",
    "backend.agent.runtime_plain_chat",
)

_LEGACY_PATCH_NAMES = {"build_agent", "build_runtime_tools"}
_PATCH_TARGET_MODULE_NAMES = {
    "build_agent": ("backend.agent.builder",),
    "build_runtime_tools": (
        "backend.agent.runtime_tools",
        "backend.agent.langgraph",
        "backend.agent.builder",
    ),
}


class _AgentCoreCompatModule(ModuleType):
    """Mirror legacy monkeypatches to the split implementation modules."""

    def __getattr__(self, name):
        return getattr(_agent_pkg, name)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        module_names = _PATCH_TARGET_MODULE_NAMES.get(name, _SPLIT_MODULE_NAMES)
        for module_name in module_names:
            try:
                module = __import__(module_name, fromlist=["_"])
            except Exception:
                continue
            if hasattr(module, name) or name in _LEGACY_PATCH_NAMES:
                setattr(module, name, value)
        chat_store = sys.modules.get("backend.chat_store")
        if chat_store is None and name == "SQLiteChatMessageHistory":
            try:
                chat_store = __import__("backend.chat_store", fromlist=["_"])
            except Exception:
                chat_store = None
        if chat_store is not None and hasattr(chat_store, name):
            setattr(chat_store, name, value)


sys.modules[__name__].__class__ = _AgentCoreCompatModule
