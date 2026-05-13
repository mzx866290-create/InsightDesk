"""Runtime wrapper classes used by the high-level agent builder."""

import asyncio
from typing import Any, Callable, Optional

from backend.agent.builder_context import (
    _attach_configured_task_meta,
    _build_invocation_config,
)
from backend.agent.builder_history import _load_chat_history, _persist_output_history
from backend.agent.builder_streaming import (
    _ainvoke_agent_wrapper,
    _astream_langgraph_wrapper,
)
from backend.agent.dashboard import _generate_dashboard_from_knowledge
from backend.agent.llm import (
    _has_image_input,
    cancel_llm_usage_capture,
    estimate_llm_answer_token_usage,
    finish_llm_usage_capture,
    start_llm_usage_capture,
)
from backend.agent.prompts import _finalize_agent_result
from backend.agent.runtime_plain_chat import (
    _astream_plain_text_answer,
    _direct_multimodal_answer,
    _direct_plain_text_answer,
    _should_bypass_tools_for_plain_text_chat,
)
from backend.agent.sources import (
    _extract_sources_from_intermediate_steps,
    _merge_sources_with_attachments,
)


class _BaseAgentWrapper:
    def __init__(
        self,
        *,
        llm: Any,
        pipeline: Any,
        system_prompt: str | None,
        dashboard_template: dict[str, Any] | None,
        knowledge_base_enabled: bool,
        web_search_enabled: bool = True,
        requested_agent_mode: str = "auto",
        actual_agent_mode: str = "auto",
        agent_mode_reason: str = "",
    ) -> None:
        self.llm = llm
        self.pipeline = pipeline
        self.system_prompt = system_prompt
        self.dashboard_template = dashboard_template
        self.knowledge_base_enabled = knowledge_base_enabled
        self.web_search_enabled = web_search_enabled
        self.requested_agent_mode = requested_agent_mode
        self.actual_agent_mode = actual_agent_mode
        self.agent_mode_reason = agent_mode_reason

    async def _run_plain_chat_once(
        self,
        session_id: str,
        user_input: Any,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
        omit_history: bool = False,
    ) -> dict[str, Any]:
        chat_history = _load_chat_history(
            session_id,
            panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            omit_history=omit_history,
        )

        if _has_image_input(user_input):
            output = await _direct_multimodal_answer(
                self.llm,
                user_input,
                chat_history,
                system_prompt=self.system_prompt,
            )
            return {"output": output, "sources": [], "response_mode": "multimodal"}

        dashboard_result = await self._generate_dashboard_result(user_input)
        if dashboard_result:
            return dashboard_result

        output = await _direct_plain_text_answer(
            self.llm,
            user_input,
            chat_history,
            system_prompt=self.system_prompt,
        )
        return {"output": output, "sources": [], "response_mode": "plain_text"}

    async def _generate_dashboard_result(self, user_input: Any) -> dict[str, Any] | None:
        return await _generate_dashboard_from_knowledge(
            self.llm,
            self.pipeline,
            user_input,
            system_prompt=self.system_prompt,
            dashboard_template=self.dashboard_template,
            knowledge_base_enabled=self.knowledge_base_enabled,
        )

    async def _stream_direct_plain_text_answer(
        self,
        invocation: Any,
        user_input: Any,
        chat_history: list[Any],
    ):
        sources = _merge_sources_with_attachments(
            [],
            raw_files=invocation.raw_files,
            raw_images=invocation.raw_images,
            answer_group_id=invocation.answer_group_id,
        )
        if sources:
            yield {"type": "sources", "sources": sources}

        output_parts: list[str] = []
        usage_token = start_llm_usage_capture()
        try:
            async for chunk in _astream_plain_text_answer(
                self.llm,
                user_input,
                chat_history,
                system_prompt=self.system_prompt,
            ):
                output_parts.append(chunk)
                yield chunk
            token_usage = finish_llm_usage_capture(
                usage_token,
                panel_id=invocation.panel_id,
                model_id=invocation.model_id,
            )
        except Exception:
            cancel_llm_usage_capture(usage_token)
            raise

        output = "".join(output_parts)
        if not token_usage.get("call_count") and output.strip():
            token_usage = estimate_llm_answer_token_usage(
                user_input,
                output,
                panel_id=invocation.panel_id,
                model_id=invocation.model_id,
            )

        _persist_output_history(
            invocation,
            user_input,
            output,
            sources=sources,
            workflow_nodes=[],
            token_usage=token_usage,
        )
        yield {"type": "token_usage", "token_usage": token_usage}

    async def _stream_finalized_run_once(
        self,
        user_input: Any,
        config: dict | None,
        invocation: Any,
    ):
        usage_token = start_llm_usage_capture()
        try:
            result = await self._run_once(
                invocation.session_id,
                user_input,
                panel_id=invocation.panel_id,
                exclude_ai_answer_group_id=invocation.exclude_ai_answer_group_id,
                omit_history=invocation.omit_history,
            )
            token_usage = finish_llm_usage_capture(
                usage_token,
                panel_id=invocation.panel_id,
                model_id=invocation.model_id,
            )
        except Exception:
            cancel_llm_usage_capture(usage_token)
            raise
        result = _attach_configured_task_meta(result, config)
        result = _finalize_agent_result(
            result,
            user_input=user_input,
            raw_files=invocation.raw_files,
            raw_images=invocation.raw_images,
            answer_group_id=invocation.answer_group_id,
        )
        result["token_usage"] = token_usage
        output = result.get("output", "")
        sources = result.get("sources", [])
        if not token_usage.get("call_count") and str(output or "").strip():
            token_usage = estimate_llm_answer_token_usage(
                user_input,
                output,
                panel_id=invocation.panel_id,
                model_id=invocation.model_id,
            )
            result["token_usage"] = token_usage

        if sources:
            yield {"type": "sources", "sources": sources}

        chunk_size = 20
        for i in range(0, len(output), chunk_size):
            yield output[i : i + chunk_size]
            await asyncio.sleep(0.01)

        _persist_output_history(
            invocation,
            user_input,
            output,
            sources=sources,
            workflow_nodes=result.get("workflow_nodes", []),
            task_id=str(result.get("task_id", "") or ""),
            task_type=str(result.get("task_type", "") or ""),
            token_usage=token_usage,
        )
        yield {"type": "token_usage", "token_usage": token_usage}


class LangGraphAgentWrapper(_BaseAgentWrapper):
    def __init__(self, app: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.app = app

    async def _run_once(
        self,
        session_id: str,
        user_input: Any,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
        omit_history: bool = False,
        workflow_event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
        stream_item_sink: Optional[Callable[[Any], None]] = None,
    ) -> dict[str, Any]:
        chat_history = _load_chat_history(
            session_id,
            panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            omit_history=omit_history,
        )
        if _has_image_input(user_input):
            output = await _direct_multimodal_answer(
                self.llm,
                user_input,
                chat_history,
                system_prompt=self.system_prompt,
            )
            return {"output": output, "sources": [], "response_mode": "multimodal"}

        dashboard_result = await self._generate_dashboard_result(user_input)
        if dashboard_result:
            return dashboard_result

        state = {
            "input": user_input,
            "chat_history": chat_history,
            "tool_choice": "",
            "tool_result": "",
            "sources": [],
            "output": "",
        }
        graph_config: dict[str, Any] = {"configurable": {}}
        if workflow_event_sink:
            graph_config["configurable"]["workflow_event_sink"] = workflow_event_sink
        if stream_item_sink:
            graph_config["configurable"]["stream_item_sink"] = stream_item_sink
        try:
            result_state = await self.app.ainvoke(state, config=graph_config)
        except TypeError as exc:
            if "config" not in str(exc):
                raise
            result_state = await self.app.ainvoke(state)

        output = result_state.get("output", "")
        sources = result_state.get("sources", [])
        tool_choice = str(result_state.get("tool_choice", "") or "").strip()
        tool_result = str(result_state.get("tool_result", "") or "").strip()
        native_stream_chunks = [
            str(item)
            for item in list(result_state.get("_native_stream_chunks") or [])
            if str(item or "").strip()
        ]
        grounded_answer = bool(sources) or (tool_choice and tool_choice != "0") or bool(tool_result)
        return {
            "output": output,
            "sources": sources,
            "response_mode": "knowledge_grounded" if grounded_answer else "plain_text",
            "_native_stream_chunks": native_stream_chunks,
        }

    async def ainvoke(self, inputs: dict, config: dict = None):
        return await _ainvoke_agent_wrapper(
            self,
            inputs,
            config,
            supports_workflow_event_sink=True,
        )

    async def astream_answer(self, user_input: Any, config: dict = None):
        async for item in _astream_langgraph_wrapper(self, user_input, config):
            yield item


class PlainChatWrapper(_BaseAgentWrapper):
    def __init__(self, *args: Any, stream_policy: str = "bypass", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.stream_policy = stream_policy

    async def _run_once(
        self,
        session_id: str,
        user_input: Any,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
        omit_history: bool = False,
    ) -> dict[str, Any]:
        return await self._run_plain_chat_once(
            session_id,
            user_input,
            panel_id=panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            omit_history=omit_history,
        )

    async def ainvoke(self, inputs: dict, config: dict = None):
        return await _ainvoke_agent_wrapper(self, inputs, config)

    async def astream_answer(self, user_input: Any, config: dict = None):
        invocation = _build_invocation_config(config)
        chat_history = _load_chat_history(
            invocation.session_id,
            invocation.panel_id,
            exclude_ai_answer_group_id=invocation.exclude_ai_answer_group_id,
            omit_history=invocation.omit_history,
        )

        if self.stream_policy == "no_tools" and not _has_image_input(user_input):
            dashboard_result = await self._generate_dashboard_result(user_input)
            if not dashboard_result and not invocation.raw_files and not invocation.raw_images:
                async for item in self._stream_direct_plain_text_answer(
                    invocation,
                    user_input,
                    chat_history,
                ):
                    yield item
                return

        if (
            self.stream_policy == "bypass"
            and _should_bypass_tools_for_plain_text_chat(
                user_input,
                knowledge_base_enabled=self.knowledge_base_enabled,
                web_search_enabled=self.web_search_enabled,
            )
            and not invocation.raw_files
            and not invocation.raw_images
        ):
            async for item in self._stream_direct_plain_text_answer(
                invocation,
                user_input,
                chat_history,
            ):
                yield item
            return

        async for item in self._stream_finalized_run_once(user_input, config, invocation):
            yield item


class FunctionCallingAgentWrapper(_BaseAgentWrapper):
    def __init__(self, agent_executor: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.agent_executor = agent_executor

    async def _run_once(
        self,
        session_id: str,
        user_input: Any,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
        omit_history: bool = False,
    ) -> dict[str, Any]:
        chat_history = _load_chat_history(
            session_id,
            panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            omit_history=omit_history,
        )

        if _has_image_input(user_input):
            output = await _direct_multimodal_answer(
                self.llm,
                user_input,
                chat_history,
                system_prompt=self.system_prompt,
            )
            return {"output": output, "sources": [], "response_mode": "multimodal"}

        if not self.web_search_enabled and _should_bypass_tools_for_plain_text_chat(
            user_input,
            knowledge_base_enabled=self.knowledge_base_enabled,
            web_search_enabled=self.web_search_enabled,
        ):
            output = await _direct_plain_text_answer(
                self.llm,
                user_input,
                chat_history,
                system_prompt=self.system_prompt,
            )
            return {"output": output, "sources": [], "response_mode": "plain_text"}

        dashboard_result = await self._generate_dashboard_result(user_input)
        if dashboard_result:
            return dashboard_result

        result = await self.agent_executor.ainvoke(
            {"input": user_input, "chat_history": chat_history}
        )
        intermediate_steps = result.get("intermediate_steps", [])
        if not result.get("sources"):
            result["sources"] = _extract_sources_from_intermediate_steps(
                intermediate_steps
            )
        result["response_mode"] = (
            "agent" if result.get("sources") or intermediate_steps else "plain_text"
        )
        return result

    async def ainvoke(self, inputs: dict, config: dict = None):
        return await _ainvoke_agent_wrapper(self, inputs, config)

    async def astream_answer(self, user_input: Any, config: dict = None):
        invocation = _build_invocation_config(config)
        chat_history = _load_chat_history(
            invocation.session_id,
            invocation.panel_id,
            exclude_ai_answer_group_id=invocation.exclude_ai_answer_group_id,
            omit_history=invocation.omit_history,
        )
        if (
            not self.web_search_enabled
            and _should_bypass_tools_for_plain_text_chat(
                user_input,
                knowledge_base_enabled=self.knowledge_base_enabled,
                web_search_enabled=self.web_search_enabled,
            )
            and not invocation.raw_files
            and not invocation.raw_images
        ):
            async for item in self._stream_direct_plain_text_answer(
                invocation,
                user_input,
                chat_history,
            ):
                yield item
            return

        async for item in self._stream_finalized_run_once(user_input, config, invocation):
            yield item
