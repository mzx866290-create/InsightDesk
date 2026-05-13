"""Prompt and assistant preset persistence adapters.

These tiny adapters keep chat-store CRUD wiring out of ``api_server.py`` while
still resolving functions dynamically for tests and runtime monkeypatching.
"""

from __future__ import annotations

from typing import Any, Optional


def list_assistant_presets() -> list[dict[str, Any]]:
    from backend import chat_store

    return chat_store.get_all_assistant_presets()


def create_assistant_preset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from backend import chat_store

    return chat_store.create_assistant_preset(*args, **kwargs)


def update_assistant_preset(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    from backend import chat_store

    return chat_store.update_assistant_preset(*args, **kwargs)


def delete_assistant_preset(preset_id: str) -> bool:
    from backend import chat_store

    return chat_store.delete_assistant_preset(preset_id)


def activate_assistant_preset(preset_id: str) -> dict[str, Any] | None:
    from backend import chat_store

    return chat_store.activate_assistant_preset(preset_id)


def list_system_prompts() -> list[dict[str, Any]]:
    from backend import chat_store

    return chat_store.get_all_system_prompts()


def create_system_prompt(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from backend import chat_store

    return chat_store.create_system_prompt(*args, **kwargs)


def update_system_prompt(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    from backend import chat_store

    return chat_store.update_system_prompt(*args, **kwargs)


def delete_system_prompt(prompt_id: str) -> bool:
    from backend import chat_store

    return chat_store.delete_system_prompt(prompt_id)


def activate_system_prompt(prompt_id: str) -> dict[str, Any] | None:
    from backend import chat_store

    return chat_store.activate_system_prompt(prompt_id)


def resolve_active_prompt_runtime(
    knowledge_base_enabled: bool,
) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    from backend.chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt() or {}

    system_prompt_content_raw = active_prompt.get("content")
    system_prompt_content = (
        str(system_prompt_content_raw).strip()
        if isinstance(system_prompt_content_raw, str)
        else ""
    ) or None

    vector_store_path = str(active_prompt.get("vector_store_id") or "").strip() or None
    if not knowledge_base_enabled:
        vector_store_path = None

    dashboard_template_raw = active_prompt.get("dashboard_template", {})
    dashboard_template = (
        dict(dashboard_template_raw) if isinstance(dashboard_template_raw, dict) else {}
    )

    return system_prompt_content, vector_store_path, dashboard_template
