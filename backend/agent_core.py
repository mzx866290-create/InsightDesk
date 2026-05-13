"""Compatibility re-export for the split :mod:`backend.agent` package."""
import sys
from types import ModuleType

import backend.agent as _agent_pkg

__all__ = sorted([*_agent_pkg.__all__, "DocPipeline"])

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

_LEGACY_PATCH_NAMES = {
    "AgentExecutor",
    "DocPipeline",
    "build_agent",
    "build_runtime_tools",
    "create_tool_calling_agent",
}
_PATCH_TARGET_MODULE_NAMES = {
    "AgentExecutor": ("backend.agent.builder",),
    "build_agent": ("backend.agent.builder",),
    "build_runtime_tools": (
        "backend.agent.runtime_tools",
        "backend.agent.langgraph",
        "backend.agent.builder",
    ),
    "create_tool_calling_agent": ("backend.agent.builder",),
    "DocPipeline": ("backend.doc_pipeline",),
}


class _AgentCoreCompatModule(ModuleType):
    """Mirror legacy monkeypatches to the split implementation modules."""

    def __getattr__(self, name):
        if name == "DocPipeline":
            from backend.doc_pipeline import DocPipeline

            return DocPipeline
        if name in {"AgentExecutor", "create_tool_calling_agent"}:
            from langchain_classic import agents as agents_module

            return getattr(agents_module, name)
        try:
            return getattr(_agent_pkg, name)
        except AttributeError as exc:
            runtime_support = __import__("backend.agent.runtime_support", fromlist=["_"])
            try:
                return getattr(runtime_support, name)
            except AttributeError:
                raise exc

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
