import asyncio
from types import SimpleNamespace

from backend.helpers.chat_route_helpers import (
    ChatRouteRuntime,
    SSE_RESPONSE_HEADERS,
    build_parallel_agent_streams,
    build_single_agent_stream,
    prepare_chat_route_runtime,
    sse_streaming_response,
)


def test_prepare_chat_route_runtime_builds_expected_payloads():
    calls = {}
    request = SimpleNamespace(
        knowledge_base_enabled=True,
        message="hello",
        images=[SimpleNamespace(name="chart.png")],
        files=[SimpleNamespace(name="brief.txt")],
        answer_group_id="grp-1",
    )

    runtime = prepare_chat_route_runtime(
        request,
        resolve_active_prompt_runtime=lambda enabled: (
            "system prompt" if enabled else "",
            "vector/path" if enabled else "",
            {"theme": "briefing"} if enabled else None,
        ),
        validate_chat_payload=lambda message, images, files: calls.setdefault(
            "validated", (message, len(images), len(files))
        ),
        prepare_chat_files=lambda files: ([{"name": files[0].name}], "[[FILES]]"),
        build_user_input=lambda message, images, attachment_context: (
            f"{message}|{len(images)}|{attachment_context}"
        ),
        base_model_payload=lambda image: {"name": image.name},
    )

    assert runtime == ChatRouteRuntime(
        answer_group_id="grp-1",
        dashboard_template={"theme": "briefing"},
        prepared_files=[{"name": "brief.txt"}],
        raw_images=[{"name": "chart.png"}],
        system_prompt_content="system prompt",
        user_input="hello|1|[[FILES]]",
        vector_store_path="vector/path",
    )
    assert calls["validated"] == ("hello", 1, 1)


def test_prepare_chat_route_runtime_generates_answer_group_id_when_missing():
    request = SimpleNamespace(
        knowledge_base_enabled=False,
        message="hello",
        images=[],
        files=[],
        answer_group_id="",
    )

    runtime = prepare_chat_route_runtime(
        request,
        resolve_active_prompt_runtime=lambda enabled: ("", "", None),
        validate_chat_payload=lambda message, images, files: None,
        prepare_chat_files=lambda files: ([], ""),
        build_user_input=lambda message, images, attachment_context: message,
        base_model_payload=lambda image: image,
        answer_group_id_factory=lambda: "generated-grp",
    )

    assert runtime.answer_group_id == "generated-grp"


def test_build_parallel_agent_streams_assigns_primary_persistence():
    captured = []
    request = SimpleNamespace(
        session_id="session-1",
        web_search_enabled=True,
        knowledge_base_enabled=False,
        message="hello",
    )
    runtime = ChatRouteRuntime(
        answer_group_id="grp-1",
        dashboard_template={"theme": "briefing"},
        prepared_files=[{"name": "brief.txt"}],
        raw_images=[{"name": "chart.png"}],
        system_prompt_content="system prompt",
        user_input="user input",
        vector_store_path="vector/path",
    )
    models = [
        SimpleNamespace(panel_id="panel-1", model="model-a"),
        SimpleNamespace(panel_id="panel-2", model="model-b"),
    ]

    async def fake_invoke_agent_stream(panel_id, mc, user_input, session_id, web_search_enabled, knowledge_base_enabled, **kwargs):
        captured.append(
            {
                "panel_id": panel_id,
                "model": mc.model,
                "user_input": user_input,
                "session_id": session_id,
                "web_search_enabled": web_search_enabled,
                "knowledge_base_enabled": knowledge_base_enabled,
                **kwargs,
            }
        )
        yield f"{panel_id}:done"

    streams = build_parallel_agent_streams(
        models,
        runtime=runtime,
        request=request,
        invoke_agent_stream=fake_invoke_agent_stream,
    )

    async def consume():
        values = []
        for stream in streams:
            async for item in stream:
                values.append(item)
        return values

    values = asyncio.run(consume())

    assert values == ["panel-1:done", "panel-2:done"]
    assert captured[0]["persist_history"] is True
    assert captured[0]["persist_user_history"] is True
    assert captured[0]["auto_summary_trigger"] is True
    assert captured[1]["persist_history"] is False
    assert captured[1]["persist_user_history"] is False
    assert captured[1]["auto_summary_trigger"] is False
    assert captured[0]["raw_images"] == [{"name": "chart.png"}]
    assert captured[0]["raw_files"] == [{"name": "brief.txt"}]


def test_build_single_agent_stream_passes_rerun_flags():
    captured = []
    request = SimpleNamespace(
        session_id="session-1",
        web_search_enabled=False,
        knowledge_base_enabled=True,
        message="hello",
        persist_user_history=False,
        persist_ai_history=True,
        replace_ai_history=True,
        exclude_ai_answer_group_id="grp-old",
    )
    runtime = ChatRouteRuntime(
        answer_group_id="grp-1",
        dashboard_template=None,
        prepared_files=[],
        raw_images=[],
        system_prompt_content="system prompt",
        user_input="user input",
        vector_store_path="vector/path",
    )
    panel_config = SimpleNamespace(panel_id="panel-compare", model="model-a")

    async def fake_invoke_agent_stream(panel_id, mc, user_input, session_id, web_search_enabled, knowledge_base_enabled, **kwargs):
        captured.append(
            {
                "panel_id": panel_id,
                "model": mc.model,
                "user_input": user_input,
                "session_id": session_id,
                "web_search_enabled": web_search_enabled,
                "knowledge_base_enabled": knowledge_base_enabled,
                **kwargs,
            }
        )
        yield "done"

    stream = build_single_agent_stream(
        panel_config,
        runtime=runtime,
        request=request,
        invoke_agent_stream=fake_invoke_agent_stream,
    )

    async def consume():
        return [item async for item in stream]

    assert asyncio.run(consume()) == ["done"]
    assert captured[0]["persist_history"] is True
    assert captured[0]["persist_user_history"] is False
    assert captured[0]["persist_ai_history"] is True
    assert captured[0]["replace_ai_history"] is True
    assert captured[0]["exclude_ai_answer_group_id"] == "grp-old"
    assert captured[0]["answer_group_id"] == "grp-1"


def test_sse_streaming_response_uses_standard_headers():
    async def generator():
        yield "data: {}\n\n"

    response = sse_streaming_response(generator())

    assert response.media_type == "text/event-stream"
    for key, value in SSE_RESPONSE_HEADERS.items():
        assert response.headers[key] == value
