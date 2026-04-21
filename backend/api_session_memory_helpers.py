import json
import os
import re
from typing import Any


def summary_llm_enabled() -> bool:
    raw = os.getenv("SESSION_MEMORY_SUMMARY_USE_LLM")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def summary_llm_timeout_seconds(default: float = 12.0) -> float:
    raw = str(os.getenv("SESSION_MEMORY_SUMMARY_LLM_TIMEOUT_SECONDS", str(default))).strip()
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return default


def normalize_llm_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def build_phase_summary_llm_prompt(
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
) -> str:
    serialized_turns: list[str] = []
    for index, turn in enumerate(turns, start=1):
        role = "USER" if turn["type"] == "human" else "ASSISTANT"
        serialized_turns.append(f"{index}. {role}: {turn['content']}")

    return (
        "You are writing one long-term memory item for an ongoing chat session.\n"
        "Produce a phase summary based only on the conversation snippets.\n\n"
        "Output requirements:\n"
        "- Language: Chinese.\n"
        "- 2-4 lines plain text.\n"
        "- Keep facts only. No speculation.\n"
        "- Must include: current objective, stable constraints/decisions, and next step.\n"
        "- Keep it concise and reusable for future turns.\n\n"
        f"Session total human/assistant turns: {total_turns}\n"
        f"Current window turns: {len(turns)}\n\n"
        "Conversation snippets:\n"
        + "\n".join(serialized_turns)
    )


def summary_turns(
    message_records: list[dict[str, Any]],
    *,
    clip_text: Any,
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for record in message_records:
        turn_type = str(record.get("type") or "").strip().lower()
        if turn_type not in {"human", "ai"}:
            continue
        content = clip_text(record.get("content") or "", 220)
        if not content:
            continue
        turns.append(
            {
                "id": int(record.get("id") or 0),
                "type": turn_type,
                "content": content,
            }
        )
    return turns


def build_phase_summary_content(
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
    clip_text: Any,
    max_chars: int,
) -> str:
    if not turns:
        raise ValueError("No conversation turns are available for summary memory.")

    user_points = [turn["content"] for turn in turns if turn["type"] == "human"][-3:]
    ai_points = [turn["content"] for turn in turns if turn["type"] == "ai"][-3:]

    lines = [
        (
            "Phase summary (auto): latest "
            f"{len(turns)} turns, covering {total_turns} human/assistant turns in this session."
        )
    ]
    if user_points:
        lines.append("User focus: " + " | ".join(user_points))
    if ai_points:
        lines.append("Assistant progress: " + " | ".join(ai_points))

    summary = "\n".join(lines).strip()
    return clip_text(summary, max(120, max_chars))


def latest_auto_summary(summaries: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in summaries
            if str((item.get("meta") or {}).get("source") or "").strip().lower() == "auto"
        ),
        None,
    )


def covered_turns_from_summary(summary: dict[str, Any] | None) -> int:
    if not summary:
        return 0
    try:
        return int((summary.get("meta") or {}).get("message_coverage") or 0)
    except (TypeError, ValueError):
        return 0


def summarize_window_meta(
    *,
    total_turns: int,
    trigger: str,
    generator: str,
    window_turns: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source": "auto",
        "trigger": trigger,
        "generator": generator,
        "message_coverage": total_turns,
        "window_size": len(window_turns),
        "window_start_id": int(window_turns[0]["id"] or 0),
        "window_end_id": int(window_turns[-1]["id"] or 0),
        "version": "v1",
    }
