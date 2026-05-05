import re
from typing import Any

from backend.agent.llm import _stringify_user_input


def _normalized_intent_text(user_input: Any) -> str:
    return re.sub(r"\s+", "", _stringify_user_input(user_input or "")).lower()


def _looks_like_reasoning_only_output(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return True
    return lowered.startswith("<think>") or lowered.startswith("thinking process:")
