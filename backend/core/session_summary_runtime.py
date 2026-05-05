"""Session phase summary runtime helpers."""

from __future__ import annotations

from typing import Any, Optional

from backend.schemas.api_models import ModelConfig


def _clip_text(ctx, text: Any, limit: int) -> str:
    normalized = ctx.re.sub("\\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 3)].rstrip() + "..."


def _summary_llm_enabled(ctx) -> bool:
    return ctx.summary_llm_enabled()


def _summary_llm_timeout_seconds(ctx) -> float:
    return ctx.summary_llm_timeout_seconds(12.0)


def _normalize_llm_text_content(ctx, content: Any) -> str:
    return ctx.normalize_llm_text_content(content)


def _resolve_summary_model_config(
    ctx, session_id: str, preferred_model_config: Optional[dict[str, Any]] = None
) -> Optional[ModelConfig]:
    from chat_store import get_session_panels

    if preferred_model_config:
        try:
            return ctx._normalize_model_config(
                ctx.ModelConfig(**preferred_model_config)
            )
        except Exception:
            ctx.logger.warning(
                "Invalid preferred model config for summary session_id=%s", session_id
            )
    panels = get_session_panels(session_id)
    if not panels:
        return None
    selected = next((item for item in panels if item.get("is_primary")), panels[0])
    model_config = dict(selected.get("model_config") or {})
    if not str(model_config.get("panel_id") or "").strip():
        model_config["panel_id"] = str(selected.get("panel_id") or "summary")
    try:
        return ctx._normalize_model_config(ctx.ModelConfig(**model_config))
    except Exception:
        ctx.logger.warning(
            "Cannot resolve summary model config from session panels session_id=%s",
            session_id,
        )
        return None


def _build_phase_summary_llm_prompt(
    ctx, turns: list[dict[str, Any]], *, total_turns: int
) -> str:
    return ctx.build_phase_summary_llm_prompt(turns, total_turns=total_turns)


async def _try_llm_phase_summary_content(
    ctx,
    session_id: str,
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    if not ctx._summary_llm_enabled():
        return None
    model_config = ctx._resolve_summary_model_config(
        session_id, preferred_model_config=preferred_model_config
    )
    if model_config is None:
        return None
    from backend.services.agent_core import get_llm

    try:
        resolved_api_key = ctx._resolve_model_api_key(model_config)
        llm = get_llm(
            provider=model_config.connection_type or model_config.provider,
            model_name=model_config.model,
            base_url=model_config.base_url,
            api_key=resolved_api_key or None,
            temperature=min(max(model_config.temperature, 0.0), 0.4),
        )
        prompt = ctx._build_phase_summary_llm_prompt(turns, total_turns=total_turns)
        timeout_seconds = ctx._summary_llm_timeout_seconds()
        response = await ctx.asyncio.wait_for(
            llm.ainvoke(prompt), timeout=timeout_seconds
        )
        content = ctx._normalize_llm_text_content(
            getattr(response, "content", response)
        )
        content = ctx._clip_text(
            content, max(120, ctx.SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS)
        )
        if not content:
            return None
        return content
    except Exception:
        ctx.logger.warning(
            "LLM summary generation failed, fallback to rule summary session_id=%s",
            session_id,
            exc_info=True,
        )
        return None


def _summary_turns(ctx, message_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return ctx.summary_turns(message_records, clip_text=ctx._clip_text)


def _build_phase_summary_content(
    ctx, turns: list[dict[str, Any]], *, total_turns: int
) -> str:
    return ctx.build_phase_summary_content(
        turns,
        total_turns=total_turns,
        clip_text=ctx._clip_text,
        max_chars=ctx.SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS,
    )


def _sqlite_history_db_path(history: Any) -> str | None:
    from backend.core.storage_runtime import DATABASE_PROVIDER_POSTGRES, database_provider

    if database_provider() == DATABASE_PROVIDER_POSTGRES:
        return None
    db_path = str(getattr(history, "db_path", "") or "").strip()
    return db_path or None


async def _generate_session_phase_summary_memory(
    ctx,
    session_id: str,
    *,
    trigger: str,
    force: bool = False,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    from chat_store import (
        list_session_memory,
        pin_session_memory,
    )
    from backend.stores.factory import create_chat_message_history

    history = create_chat_message_history(session_id=session_id)
    history_db_path = _sqlite_history_db_path(history)
    turns = ctx._summary_turns(history.get_all_message_records())
    total_turns = len(turns)
    min_turns = max(2, ctx.SESSION_MEMORY_AUTO_SUMMARY_MIN_TURNS)
    if not force and total_turns < min_turns:
        raise ValueError(
            f"Need at least {min_turns} conversation turns before generating a phase summary memory."
        )
    summaries = (
        list_session_memory(
            session_id, kind="summary", newest_first=True, db_path=history_db_path
        )
        if history_db_path
        else list_session_memory(session_id, kind="summary", newest_first=True)
    )
    latest_auto = ctx.latest_auto_summary(summaries)
    covered_turns = ctx.covered_turns_from_summary(latest_auto)
    new_turns = max(0, total_turns - covered_turns)
    min_new_turns = max(1, ctx.SESSION_MEMORY_AUTO_SUMMARY_MIN_NEW_TURNS)
    if latest_auto and (not force) and (new_turns < min_new_turns):
        return {
            "created": False,
            "memory": latest_auto,
            "reason": "up_to_date",
            "stats": {
                "total_turns": total_turns,
                "new_turns": new_turns,
                "required_new_turns": min_new_turns,
            },
        }
    window_size = max(2, ctx.SESSION_MEMORY_AUTO_SUMMARY_WINDOW_SIZE)
    window_turns = turns[-window_size:]
    content = ctx._build_phase_summary_content(window_turns, total_turns=total_turns)
    generator = "rules"
    llm_content = await ctx._try_llm_phase_summary_content(
        session_id,
        window_turns,
        total_turns=total_turns,
        preferred_model_config=preferred_model_config,
    )
    if llm_content:
        content = llm_content
        generator = "llm"
    meta = ctx.summarize_window_meta(
        total_turns=total_turns,
        trigger=trigger,
        generator=generator,
        window_turns=window_turns,
    )
    result = (
        pin_session_memory(
            session_id,
            content=content,
            kind="summary",
            meta=meta,
            db_path=history_db_path,
        )
        if history_db_path
        else pin_session_memory(session_id, content=content, kind="summary", meta=meta)
    )
    if not result:
        return None
    return {
        **result,
        "reason": "created" if result.get("created") else "deduped",
        "stats": {
            "total_turns": total_turns,
            "new_turns": new_turns,
            "required_new_turns": min_new_turns,
        },
    }


async def _auto_generate_phase_summary_memory(
    ctx,
    session_id: str,
    *,
    trigger: str,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> None:
    try:
        result = await ctx._generate_session_phase_summary_memory(
            session_id,
            trigger=trigger,
            force=False,
            preferred_model_config=preferred_model_config,
        )
        if result and result.get("created"):
            ctx.logger.info("Auto summary memory created session_id=%s", session_id)
    except ValueError:
        return
    except Exception:
        ctx.logger.exception(
            "Auto summary memory generation failed session_id=%s", session_id
        )
