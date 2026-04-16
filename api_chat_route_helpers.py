import uuid
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi.responses import StreamingResponse


SSE_RESPONSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


@dataclass(frozen=True)
class ChatRouteRuntime:
    answer_group_id: str
    dashboard_template: dict[str, Any] | None
    prepared_files: list[dict[str, Any]]
    raw_images: list[dict[str, Any]]
    system_prompt_content: str | None
    user_input: Any
    vector_store_path: str | None


def prepare_chat_route_runtime(
    request: Any,
    *,
    resolve_active_prompt_runtime: Callable[[bool], tuple[str | None, str | None, dict[str, Any] | None]],
    validate_chat_payload: Callable[[str, list[Any], list[Any]], None],
    prepare_chat_files: Callable[[list[Any]], tuple[list[dict[str, Any]], str]],
    build_user_input: Callable[[str, list[Any], str], Any],
    base_model_payload: Callable[[Any], dict[str, Any]],
    answer_group_id_factory: Callable[[], Any] = uuid.uuid4,
) -> ChatRouteRuntime:
    (
        system_prompt_content,
        vector_store_path,
        dashboard_template,
    ) = resolve_active_prompt_runtime(bool(getattr(request, "knowledge_base_enabled", False)))

    message = str(getattr(request, "message", "") or "")
    images = list(getattr(request, "images", []) or [])
    files = list(getattr(request, "files", []) or [])

    validate_chat_payload(message, images, files)
    prepared_files, attachment_context = prepare_chat_files(files)
    user_input = build_user_input(message, images, attachment_context)
    raw_images = [base_model_payload(image) for image in images]
    answer_group_id = str(getattr(request, "answer_group_id", "") or answer_group_id_factory())

    return ChatRouteRuntime(
        answer_group_id=answer_group_id,
        dashboard_template=dashboard_template,
        prepared_files=prepared_files,
        raw_images=raw_images,
        system_prompt_content=system_prompt_content,
        user_input=user_input,
        vector_store_path=vector_store_path,
    )


def build_parallel_agent_streams(
    normalized_models: list[Any],
    *,
    runtime: ChatRouteRuntime,
    request: Any,
    invoke_agent_stream: Callable[..., AsyncIterable[str]],
) -> list[AsyncIterable[str]]:
    primary_panel_id = normalized_models[0].panel_id
    return [
        invoke_agent_stream(
            mc.panel_id,
            mc,
            runtime.user_input,
            request.session_id,
            request.web_search_enabled,
            request.knowledge_base_enabled,
            system_prompt=runtime.system_prompt_content,
            vector_store_path=runtime.vector_store_path,
            dashboard_template=runtime.dashboard_template,
            enabled_mcp_servers=list(getattr(request, "enabled_mcp_servers", []) or []),
            persist_history=mc.panel_id == primary_panel_id,
            persist_user_history=mc.panel_id == primary_panel_id,
            persist_ai_history=True,
            answer_group_id=runtime.answer_group_id,
            raw_user_message=request.message,
            raw_images=runtime.raw_images,
            raw_files=runtime.prepared_files,
            auto_summary_trigger=mc.panel_id == primary_panel_id,
        )
        for mc in normalized_models
    ]


def build_single_agent_stream(
    normalized_panel_config: Any,
    *,
    runtime: ChatRouteRuntime,
    request: Any,
    invoke_agent_stream: Callable[..., AsyncIterable[str]],
) -> AsyncIterable[str]:
    return invoke_agent_stream(
        normalized_panel_config.panel_id,
        normalized_panel_config,
        runtime.user_input,
        request.session_id,
        request.web_search_enabled,
        request.knowledge_base_enabled,
        system_prompt=runtime.system_prompt_content,
        vector_store_path=runtime.vector_store_path,
        dashboard_template=runtime.dashboard_template,
        enabled_mcp_servers=list(getattr(request, "enabled_mcp_servers", []) or []),
        persist_history=True,
        persist_user_history=request.persist_user_history,
        persist_ai_history=request.persist_ai_history,
        replace_ai_history=request.replace_ai_history,
        exclude_ai_answer_group_id=str(request.exclude_ai_answer_group_id or ""),
        answer_group_id=runtime.answer_group_id,
        raw_user_message=request.message,
        raw_images=runtime.raw_images,
        raw_files=runtime.prepared_files,
        auto_summary_trigger=request.persist_ai_history,
    )


def sse_streaming_response(generator: AsyncIterable[str]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=dict(SSE_RESPONSE_HEADERS),
    )
