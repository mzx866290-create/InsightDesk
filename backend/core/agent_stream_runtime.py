"""Agent cache/build/stream runtime for the chat endpoints.

Implementation moved out of backend.api_server; the api_server module keeps
thin wrappers that pass a lazily-built context whose attributes are read
dynamically from the api_server namespace, preserving monkeypatch semantics
for tests and the router context.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from backend.agent_mcp_helpers import normalize_mcp_server_names
from backend.core import kb_runtime, model_config_runtime, session_summary_runtime
from backend.helpers.agent_stream_helpers import (
    dashboard_prompt_excerpt,
    fail_dashboard_task,
    fallback_generate_with_llm,
    finalize_dashboard_task,
    resolve_non_stream_agent_result,
    stream_agent_item,
    task_created_event,
)
from backend.helpers.chat_input_helpers import stringify_user_input as _stringify_user_input_impl
from backend.helpers.chat_stream_helpers import (
    answer_chunks,
    build_agent_config_payload,
    done_event as _done_event,
    panel_event as _panel_event,
)
from backend.helpers.http_runtime_helpers import classify_runtime_error
from backend.helpers.misc_helpers import (
    dashboard_feature_enabled,
    is_max_iterations_output,
)
from backend.helpers.security_helpers import content_hash, hash_secret
from backend.helpers.task_helpers import (
    contains_dashboard_card as _contains_dashboard_card,
    should_start_dashboard_task as _should_start_dashboard_task,
    summarize_dashboard_task_error as _summarize_dashboard_task_error,
    summarize_dashboard_task_result as _summarize_dashboard_task_result,
)
from backend.schemas.api_models import ModelConfig
from backend.stores import TaskRecord

logger = logging.getLogger(__name__)

AGENT_STREAM_RUNTIME_CONTEXT_ATTRIBUTES = (
    "_agent_cache",
    "_agent_cache_lock",
    "_app_config_store",
    "_create_inline_task_record",
    "_get_or_build_agent",
    "_session_summary_runtime_context",
    "_set_inline_task_state",
    "PROJECT_ROOT",
)


class AgentStreamRuntimeContext:
    def __init__(self, source: Any, allowed_attributes: tuple[str, ...]) -> None:
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_allowed", frozenset(allowed_attributes))

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed:
            raise AttributeError(f"Agent stream runtime context has no dependency {name!r}")
        return getattr(self._source, name)


def build_agent_stream_runtime_context(source: Any) -> AgentStreamRuntimeContext:
    missing = [
        attribute
        for attribute in AGENT_STREAM_RUNTIME_CONTEXT_ATTRIBUTES
        if not hasattr(source, attribute)
    ]
    if missing:
        raise AttributeError(
            "Agent stream runtime context missing required attributes: "
            + ", ".join(missing)
        )
    return AgentStreamRuntimeContext(source, AGENT_STREAM_RUNTIME_CONTEXT_ATTRIBUTES)


async def clear_agent_cache(ctx: AgentStreamRuntimeContext) -> None:
    async with ctx._agent_cache_lock:
        cleared_count = len(ctx._agent_cache)
        ctx._agent_cache.clear()
    if cleared_count:
        logger.info("Cleared %d cached agent(s)", cleared_count)


async def get_or_build_agent(
    ctx: AgentStreamRuntimeContext,
    mc: ModelConfig,
    system_prompt: str | None = None,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    vector_store_path: str | None = None,
    dashboard_template: dict[str, Any] | None = None,
    enabled_mcp_servers: list[str] | None = None,
):
    """????????? Agent?"""
    from backend.services.agent_core import build_agent

    mc = model_config_runtime.normalize_model_config(mc)
    resolved_api_key = model_config_runtime.resolve_model_api_key(
        ctx._app_config_store,
        logger,
        mc,
    )
    api_key_hash = hash_secret(resolved_api_key)
    cache_key = content_hash(
        {
            "connection_type": mc.connection_type or mc.provider,
            "provider": mc.provider,
            "model": mc.model,
            "base_url": mc.base_url,
            "api_key_hash": api_key_hash,
            "temperature": mc.temperature,
            "agent_mode": mc.agent_mode,
            "web_search_enabled": web_search_enabled,
            "knowledge_base_enabled": knowledge_base_enabled,
            "vector_store_path": str(
                kb_runtime.resolve_project_subdir(
                    vector_store_path,
                    project_root=ctx.PROJECT_ROOT,
                )
            )
            if vector_store_path
            else "",
            "system_prompt": system_prompt or "",
            "dashboard_template": dashboard_template or {},
            "enabled_mcp_servers": normalize_mcp_server_names(enabled_mcp_servers),
        }
    )
    async with ctx._agent_cache_lock:
        if cache_key not in ctx._agent_cache:
            logger.info("Building new agent: %s", cache_key[:12])
            ctx._agent_cache[cache_key] = await build_agent(
                provider=mc.provider,
                model_name=mc.model,
                base_url=mc.base_url,
                api_key=resolved_api_key or None,
                temperature=mc.temperature,
                agent_mode=mc.agent_mode,
                system_prompt=system_prompt,
                web_search_enabled=web_search_enabled,
                knowledge_base_enabled=knowledge_base_enabled,
                vector_store_path=vector_store_path,
                dashboard_template=dashboard_template,
                enabled_mcp_servers=normalize_mcp_server_names(enabled_mcp_servers),
            )
        return ctx._agent_cache[cache_key]


async def invoke_agent_stream(
    ctx: AgentStreamRuntimeContext,
    panel_id: str,
    mc: ModelConfig,
    message: Any,
    session_id: str,
    web_search_enabled: bool,
    knowledge_base_enabled: bool,
    system_prompt: str | None = None,
    vector_store_path: str | None = None,
    dashboard_template: dict[str, Any] | None = None,
    enabled_mcp_servers: list[str] | None = None,
    persist_history: bool = True,
    persist_user_history: bool = True,
    persist_ai_history: bool = True,
    replace_ai_history: bool = False,
    exclude_ai_answer_group_id: str = "",
    answer_group_id: str = "",
    raw_user_message: str = "",
    raw_images: list[dict[str, Any]] | None = None,
    raw_files: list[dict[str, Any]] | None = None,
    omit_history: bool = False,
    auto_summary_trigger: bool = False,
) -> AsyncGenerator[str, None]:
    """???? Agent???????? SSE ???"""
    try:
        mc = model_config_runtime.normalize_model_config(mc)
        agent = await ctx._get_or_build_agent(
            mc,
            system_prompt=system_prompt,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
            vector_store_path=vector_store_path,
            dashboard_template=dashboard_template,
            enabled_mcp_servers=normalize_mcp_server_names(enabled_mcp_servers),
        )
        answer_parts: list[str] = []
        dashboard_task_record: TaskRecord | None = None

        dashboard_requested = _should_start_dashboard_task(
            raw_user_message or message,
            knowledge_base_enabled=knowledge_base_enabled,
            logger=logger,
        ) and dashboard_feature_enabled(dashboard_template)
        if dashboard_requested:
            prompt_excerpt = dashboard_prompt_excerpt(raw_user_message)
            dashboard_task_record = await ctx._create_inline_task_record(
                "generate_dashboard",
                {
                    "panel_id": panel_id,
                    "prompt_excerpt": prompt_excerpt,
                },
                session_id=session_id,
                progress=20,
            )
            yield task_created_event(panel_id, dashboard_task_record)

        config_payload = build_agent_config_payload(
            session_id=session_id,
            persist_history=persist_history,
            persist_user_history=persist_user_history,
            persist_ai_history=persist_ai_history,
            replace_ai_history=replace_ai_history,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            panel_id=panel_id,
            model_id=mc.model,
            answer_group_id=answer_group_id,
            raw_user_message=raw_user_message,
            raw_images=raw_images or [],
            raw_files=raw_files or [],
            omit_history=omit_history,
            task_id=dashboard_task_record.task_id if dashboard_task_record else "",
            task_type=dashboard_task_record.task_type if dashboard_task_record else "",
        )

        if hasattr(agent, "astream_answer"):
            async for item in agent.astream_answer(
                message,
                config=config_payload,
            ):
                event, chunk = stream_agent_item(panel_id, item)
                if chunk:
                    answer_parts.append(chunk)
                yield event
        else:
            from backend.services.agent_core import get_llm

            result = await agent.ainvoke(
                {"input": message},
                config=config_payload,
            )
            if is_max_iterations_output(result.get("output", str(result))):
                logger.warning(
                    "panel_id=%s max iterations reached, attempting fallback", panel_id
                )
            outcome = await resolve_non_stream_agent_result(
                panel_id,
                result,
                mc=mc,
                message=message,
                is_max_iterations_output=is_max_iterations_output,
                stringify_user_input=_stringify_user_input_impl,
                fallback_generate=lambda fallback_mc, user_input, tool_outputs: (
                    fallback_generate_with_llm(
                        fallback_mc,
                        user_input,
                        tool_outputs,
                        app_config_store=ctx._app_config_store,
                        logger=logger,
                        create_llm=get_llm,
                    )
                ),
            )
            for event in outcome.events:
                yield event
            if outcome.should_stop:
                if dashboard_task_record is not None and outcome.dashboard_error:
                    await fail_dashboard_task(
                        dashboard_task_record,
                        error=outcome.dashboard_error,
                        set_inline_task_state=ctx._set_inline_task_state,
                    )
                return

            answer = outcome.answer
            sources = outcome.sources

            answer_parts.clear()
            answer_parts.append(answer)

            # Emit sources before answer chunks
            if sources:
                yield _panel_event(panel_id, "sources", sources=sources)

            # Emit the resolved answer in small chunks to match streaming output.
            for chunk in answer_chunks(answer, chunk_size=20):
                yield _panel_event(panel_id, "chunk", content=chunk)
                await asyncio.sleep(0.01)
            if result.get("token_usage"):
                yield _panel_event(
                    panel_id,
                    "token_usage",
                    token_usage=dict(result.get("token_usage") or {}),
                )

        # 完成信号
        if dashboard_task_record is not None:
            final_answer = "".join(answer_parts)
            await finalize_dashboard_task(
                dashboard_task_record,
                final_answer,
                contains_dashboard_card=_contains_dashboard_card,
                summarize_dashboard_task_result=_summarize_dashboard_task_result,
                summarize_dashboard_task_error=_summarize_dashboard_task_error,
                set_inline_task_state=ctx._set_inline_task_state,
            )

        if auto_summary_trigger and persist_ai_history:
            asyncio.create_task(
                session_summary_runtime._auto_generate_phase_summary_memory(
                    ctx._session_summary_runtime_context(),
                    session_id,
                    trigger=f"chat_stream:{panel_id}",
                    preferred_model_config=model_config_runtime.model_config_payload(mc),
                )
            )

        yield _done_event(panel_id)

    except Exception as e:
        logger.exception("Agent invocation failed panel_id=%s", panel_id)
        if "dashboard_task_record" in locals() and dashboard_task_record is not None:
            await fail_dashboard_task(
                dashboard_task_record,
                error=str(e),
                set_inline_task_state=ctx._set_inline_task_state,
            )
        err = classify_runtime_error(e)
        yield _panel_event(
            panel_id,
            "error",
            content=err["message"],
            error_code=err["code"],
            suggestion=err["suggestion"],
        )
