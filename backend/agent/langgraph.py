"""LangGraph agent workflow construction."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.agent.langgraph_helpers import (
    AgentState,
    _emit_stream_item,
    _emit_workflow_state,
    _graph_configurable_value,
    _rewrite_search_query,
)
from backend.agent.fallbacks import _build_kb_timeout_fallback
from backend.agent.llm import (
    _ThinkTagStreamFilter,
    _ainvoke_llm_with_timeout,
    _astream_llm_with_timeout,
    _compact_tool_result_for_prompt,
    _is_timeout_error,
    _stringify_user_input,
    _strip_think_tags,
)
from backend.agent.prompts import BUSINESS_ANSWER_FORMAT_INSTRUCTIONS
from backend.agent.runtime_intent import _looks_like_reasoning_only_output
from backend.agent.runtime_plain_chat import _heuristic_langgraph_tool_choice
from backend.agent.runtime_tools import build_runtime_tools
from backend.agent.sources import (
    _build_retrieval_meta_from_sources,
    _extract_sources_from_marked_result,
)
from backend.agent.tool_registry import _build_enabled_tool_directory

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline

async def build_langgraph_agent(
    llm,
    pipeline: DocPipeline,
    verbose: bool = True,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
):
    """
    构建 LangGraph 轻量 Agent (适合小模型)
    
    Args:
        llm: LLM 实例
        pipeline: DocPipeline 实例
        verbose: 是否显示详细日志
    
    Returns:
        编译后的 LangGraph 实例
    """
    tools_list = await build_runtime_tools(
        pipeline,
        web_search_enabled=web_search_enabled,
        knowledge_base_enabled=knowledge_base_enabled,
    )
    tools_by_name = {tool.name: tool for tool in tools_list}
    tools_dict, tool_options, allowed_choices = _build_enabled_tool_directory(
        tools_by_name,
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
    )

    async def classify_intent(
        state: AgentState,
        config: RunnableConfig | None = None,
    ) -> AgentState:
        """节点1: 分类用户意图，选择工具"""
        started_at = time.monotonic()
        _emit_workflow_state(config, "classify_intent", "running")
        user_input = state["input"]
        chat_history = state.get("chat_history", [])
        state.setdefault("sources", [])
        state.setdefault("retrieval_meta", {})

        try:
            heuristic_choice = _heuristic_langgraph_tool_choice(
                user_input,
                knowledge_base_enabled=knowledge_base_enabled,
                web_search_enabled=web_search_enabled,
            )
            if heuristic_choice and (heuristic_choice in tools_dict or heuristic_choice == "0"):
                logger.info("[LangGraph] heuristic tool_choice=%s", heuristic_choice)
                state["tool_choice"] = heuristic_choice
                _emit_workflow_state(
                    config,
                    "classify_intent",
                    "completed",
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                )
                return state

            history_text = ""
            if chat_history:
                recent_history = chat_history[-4:]
                for msg in recent_history:
                    if isinstance(msg, HumanMessage):
                        history_text += f"用户: {msg.content}\n"
                    elif isinstance(msg, AIMessage):
                        history_text += f"助手: {msg.content}\n"

            role_desc = system_prompt or "你是一个企业知识库助手"
            available_tools = "\n".join(tool_options)
            classify_prompt = (
                f"{role_desc}\n"
                "如果用户提到知识库、上传文档、附件、已有资料、简历内容，优先选择知识库工具，不要把它当成普通寒暄。\n"
                "请根据用户问题选择最合适的工具编号，只输出一个数字。\n\n"
                f"{available_tools}\n\n"
                f"{history_text}"
                f"用户: {user_input}\n\n"
                f"请只输出一个数字：0 或 {allowed_choices or '无'}"
            )

            response = await _ainvoke_llm_with_timeout(llm, classify_prompt, timeout_seconds=20)
            choice = response.content.strip()
            
            choice_char = ""
            for char in choice:
                if char == "0" or char in allowed_choices:
                    choice_char = char
                    break
            
            if not choice_char:
                choice_char = "0"
            
            logger.info("[LangGraph] tool_choice=%s", choice_char)
            
            state["tool_choice"] = choice_char
            _emit_workflow_state(
                config,
                "classify_intent",
                "completed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            return state
            
        except Exception as exc:
            logger.exception("[LangGraph] 意图分类失败")
            state["tool_choice"] = "0"
            _emit_workflow_state(
                config,
                "classify_intent",
                "failed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                error=str(exc),
            )
            return state
    
    async def execute_tool(
        state: AgentState,
        config: RunnableConfig | None = None,
    ) -> AgentState:
        """节点2: 执行选定的工具"""
        import json as _json
        started_at = time.monotonic()
        tool_choice = state["tool_choice"]
        user_input = state["input"]
        chat_history = state.get("chat_history", [])

        _emit_workflow_state(config, "execute_tool", "running")
        
        if tool_choice not in tools_dict:
            state["tool_result"] = ""
            state["sources"] = []
            state["retrieval_meta"] = {}
            _emit_workflow_state(
                config,
                "execute_tool",
                "completed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            return state
        
        tool_func = tools_dict[tool_choice]
        
        try:
            logger.info("[LangGraph] tool_name=%s 开始执行", tool_func.name)
            t0 = time.monotonic()
            
            # Query rewriting for web search tools (2=web_search, 3=quick_answer)
            actual_input = user_input
            if tool_choice in ("2", "3"):
                actual_input = await _rewrite_search_query(llm, user_input, chat_history)
            
            # Determine the correct parameter name for the tool
            if "question" in tool_func.args:
                params = {"question": actual_input}
            elif "user_question" in tool_func.args:
                params = {"user_question": actual_input}
            elif "search_query" in tool_func.args:
                params = {"search_query": actual_input}
            elif "query" in tool_func.args:
                params = {"query": actual_input}
            elif "url" in tool_func.args:
                params = {"url": actual_input}
            else:
                params = {}

            _emit_workflow_state(
                config,
                "execute_tool",
                "running",
                tool_name=tool_func.name,
                tool_params=params,
            )
            
            result = await tool_func.ainvoke(params)
            
            latency_ms = int((time.monotonic() - t0) * 1000)

            # Extract __SOURCES__ marker if present
            result, sources = _extract_sources_from_marked_result(result)

            state["tool_result"] = result
            state["sources"] = sources
            state["retrieval_meta"] = _build_retrieval_meta_from_sources(sources) or {}
            logger.info("[LangGraph] tool_name=%s latency_ms=%d result_len=%d sources=%d",
                        tool_func.name, latency_ms, len(result), len(sources))
            _emit_workflow_state(
                config,
                "execute_tool",
                "completed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                tool_name=tool_func.name,
                tool_params=params,
                tool_result_summary=_compact_tool_result_for_prompt(result, max_chars=220),
                retrieval_meta=state.get("retrieval_meta") or None,
            )
            
        except Exception as e:
            logger.exception("[LangGraph] tool_name=%s 执行失败", tool_func.name)
            state["tool_result"] = f"❌ 工具执行失败: {str(e)}"
            state["sources"] = []
            state["retrieval_meta"] = {}
            _emit_workflow_state(
                config,
                "execute_tool",
                "failed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                tool_name=tool_func.name,
                error=str(e),
            )
        
        return state
    
    async def generate_answer(
        state: AgentState,
        config: RunnableConfig | None = None,
    ) -> AgentState:
        """节点3: 生成最终回答，并在引用文档时注入脚注标记"""
        started_at = time.monotonic()
        _emit_workflow_state(config, "generate_answer", "running")
        user_input = state["input"]
        tool_result = state.get("tool_result", "")
        prompt_tool_result = _compact_tool_result_for_prompt(tool_result, max_chars=1800)
        chat_history = state.get("chat_history", [])
        sources = state.get("sources", [])
        
        history_text = ""
        if chat_history:
            recent_history = chat_history[-4:]
            for msg in recent_history:
                if isinstance(msg, HumanMessage):
                    history_text += f"用户: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    history_text += f"助手: {msg.content}\n"
        
        role_desc = system_prompt or "你是一个企业知识库助手"
        streaming_enabled = callable(_graph_configurable_value(config, "stream_item_sink", None))
        streamed_output_parts: list[str] = []

        # Build citation hint so the model knows which index maps to which source
        citation_hint = ""
        if sources:
            cite_lines = [
                f"  [{s.get('index', i+1)}] {s.get('title', '未知来源')}"
                for i, s in enumerate(sources)
            ]
            citation_hint = (
                "\n\n可用引用来源（在答案中用 [^数字] 标注引用，例如 [^1]）:\n"
                + "\n".join(cite_lines)
                + "\n"
            )

        # Structured intent card instructions
        intent_instructions = """
【结构化卡片输出规范】
当用户请求以下类型的分析时，在普通文字回答之外额外输出对应的结构化卡片块（:::intent:::），以便前端自动渲染为交互式组件：

1. 简历分析 / 候选人评估 → 输出 :::resume-card 块：
:::resume-card
{"name":"姓名","position":"应聘职位","skills":["技能1","技能2"],"score":85,"summary":"综合评价","highlights":["亮点1"],"experience":"工作经历","education":"教育背景"}
:::

2. 数据汇总 / 统计报告 → 输出 :::data-summary 块：
:::data-summary
{"title":"报告标题","description":"描述","metrics":[{"label":"指标名","value":100,"unit":"个","trend":"up","delta":"+10%","highlight":true}],"note":"备注"}
:::

仅在用户明确请求上述分析类型时输出卡片块，其他情况下正常用文字回答。
"""

        if tool_result:
            prompt_tool_result = _compact_tool_result_for_prompt(tool_result, max_chars=2400)
            answer_prompt = f"""{role_desc}。根据工具返回的信息回答用户问题。你已经拿到了用户的资料，不要再要求用户重复上传、重复粘贴或重新提供背景信息。{citation_hint}{intent_instructions}
{history_text}
用户问题: {user_input}

工具返回的信息:
{prompt_tool_result}

请基于以上信息回答用户问题。{BUSINESS_ANSWER_FORMAT_INSTRUCTIONS}
如有引用来源，请在对应句子末尾添加 [^数字] 标注。"""
        else:
            answer_prompt = f"""{role_desc}。直接回答用户问题。{intent_instructions}
{history_text}
用户: {user_input}

请用自然、友好的语言回答："""
        
        try:
            if streaming_enabled:
                stream_filter = _ThinkTagStreamFilter()
                raw_output_parts: list[str] = []
                async for chunk in _astream_llm_with_timeout(
                    llm,
                    answer_prompt,
                    timeout_seconds=60,
                ):
                    raw_output_parts.append(chunk)
                    visible = stream_filter.feed(chunk)
                    if visible:
                        streamed_output_parts.append(visible)
                        _emit_stream_item(config, visible)

                tail = stream_filter.flush()
                if tail:
                    streamed_output_parts.append(tail)
                    _emit_stream_item(config, tail)

                raw_output = "".join(raw_output_parts).strip()
                state["output"] = "".join(streamed_output_parts).strip()
            else:
                # Even without a stream sink, prefer native token streaming so
                # wrappers can optionally replay original token chunks.
                try:
                    raw_output_parts: list[str] = []
                    async for chunk in _astream_llm_with_timeout(
                        llm,
                        answer_prompt,
                        timeout_seconds=60,
                    ):
                        raw_output_parts.append(chunk)

                    raw_output = "".join(raw_output_parts).strip()
                    state["output"] = _strip_think_tags(raw_output)
                    native_stream_chunks = [
                        _strip_think_tags(str(chunk))
                        for chunk in raw_output_parts
                        if str(chunk or "").strip()
                    ]
                    native_stream_chunks = [
                        chunk for chunk in native_stream_chunks if chunk
                    ]
                    if native_stream_chunks:
                        state["_native_stream_chunks"] = native_stream_chunks
                except Exception:
                    response = await _ainvoke_llm_with_timeout(llm, answer_prompt, timeout_seconds=60)
                    raw_output = (
                        response.content.strip()
                        if isinstance(response.content, str)
                        else _stringify_user_input(response.content)
                    )
                    state["output"] = _strip_think_tags(raw_output)
            if tool_result and (
                not state["output"] or _looks_like_reasoning_only_output(raw_output)
            ):
                state["output"] = _build_kb_timeout_fallback(user_input, tool_result, sources)
                if streaming_enabled and not streamed_output_parts:
                    _emit_stream_item(config, state["output"])
                logger.warning(
                    "[LangGraph] 检测到思维链泄漏，回退到知识库兜底结果 output_len=%d",
                    len(state["output"]),
                )
                _emit_workflow_state(
                    config,
                    "generate_answer",
                    "completed",
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                )
                return state
            logger.info("[LangGraph] 生成回答完成 output_len=%d", len(state["output"]))
            _emit_workflow_state(
                config,
                "generate_answer",
                "completed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            
        except Exception as e:
            if _is_timeout_error(e):
                logger.warning(
                    "[LangGraph] 生成回答超时 tool_result_len=%d compact_len=%d error=%s",
                    len(tool_result),
                    len(prompt_tool_result),
                    e,
                )
            else:
                logger.exception(
                    "[LangGraph] 生成回答失败 tool_result_len=%d compact_len=%d",
                    len(tool_result),
                    len(prompt_tool_result),
                )

            if streaming_enabled and streamed_output_parts:
                note = "\n\n[回答在流式生成过程中中断，以下内容可能不完整，请重试。]"
                state["output"] = f"{''.join(streamed_output_parts).strip()}{note}"
                _emit_stream_item(config, note)
                _emit_workflow_state(
                    config,
                    "generate_answer",
                    "failed",
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                    error=str(e),
                )
                return state

            # 带知识库时再用更短的片段重试一次，兼容部分云端中转对长 prompt 不稳定的问题。
            if tool_result:
                retry_tool_result = _compact_tool_result_for_prompt(tool_result, max_chars=900)
                retry_prompt = f"""{role_desc}。根据检索摘要回答用户问题。{citation_hint}
{history_text}
用户问题: {user_input}

检索摘要:
{retry_tool_result}

请只保留最关键的信息回答用户问题。{BUSINESS_ANSWER_FORMAT_INSTRUCTIONS}
如有引用来源，请在对应句子末尾添加 [^数字] 标注。"""
                try:
                    logger.warning(
                        "[LangGraph] 使用压缩知识库结果重试生成 compact_len=%d",
                        len(retry_tool_result),
                    )
                    response = await _ainvoke_llm_with_timeout(llm, retry_prompt, timeout_seconds=40)
                    retry_raw_output = (
                        response.content.strip()
                        if isinstance(response.content, str)
                        else _stringify_user_input(response.content)
                    )
                    state["output"] = _strip_think_tags(retry_raw_output)
                    if not state["output"] or _looks_like_reasoning_only_output(retry_raw_output):
                        state["output"] = _build_kb_timeout_fallback(
                            user_input, tool_result, sources
                        )
                        logger.warning(
                            "[LangGraph] 压缩重试命中思维链泄漏，回退到知识库兜底结果 output_len=%d",
                            len(state["output"]),
                        )
                        _emit_workflow_state(
                            config,
                            "generate_answer",
                            "completed",
                            duration_ms=int((time.monotonic() - started_at) * 1000),
                        )
                        return state
                    logger.info(
                        "[LangGraph] 重试生成回答成功 output_len=%d",
                        len(state["output"]),
                    )
                    _emit_workflow_state(
                        config,
                        "generate_answer",
                        "completed",
                        duration_ms=int((time.monotonic() - started_at) * 1000),
                    )
                    return state
                except Exception as retry_exc:
                    if _is_timeout_error(retry_exc):
                        logger.warning(
                            "[LangGraph] 压缩重试后仍超时 error=%s",
                            retry_exc,
                        )
                    else:
                        logger.exception("[LangGraph] 压缩重试后仍生成失败")

                state["output"] = _build_kb_timeout_fallback(user_input, tool_result, sources)
                logger.warning(
                    "[LangGraph] 云端生成失败后返回知识库兜底结果 output_len=%d",
                    len(state["output"]),
                )
                _emit_workflow_state(
                    config,
                    "generate_answer",
                    "completed",
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                )
                return state

            state["output"] = f"❌ 生成回答失败: {str(e)}"
            _emit_workflow_state(
                config,
                "generate_answer",
                "failed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                error=str(e),
            )
        
        return state
    
    def should_use_tool(state: AgentState) -> Literal["execute_tool", "generate_answer"]:
        """条件边: 判断是否需要使用工具"""
        tool_choice = state.get("tool_choice", "0")
        if tool_choice in tools_dict:
            return "execute_tool"
        return "generate_answer"
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_node("generate_answer", generate_answer)
    
    workflow.set_entry_point("classify_intent")
    
    workflow.add_conditional_edges(
        "classify_intent",
        should_use_tool,
        {
            "execute_tool": "execute_tool",
            "generate_answer": "generate_answer",
        }
    )
    
    workflow.add_edge("execute_tool", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    app = workflow.compile()
    
    logger.info("✓ LangGraph 轻量 Agent 已构建（最多 2 次 LLM 调用）")
    
    return app
