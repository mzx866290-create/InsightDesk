"""High-level agent builder and compatibility wrappers."""

import logging
from importlib import import_module
from typing import Any, Optional

from backend.agent.connection import get_llm, normalize_connection_type
from backend.agent.llm import _normalize_runtime_system_prompt

logger = logging.getLogger(__name__)

_LAZY_HELPER_EXPORTS: dict[str, tuple[str, str]] = {
    "_attach_configured_task_meta": (
        "backend.agent.builder_context",
        "_attach_configured_task_meta",
    ),
    "_build_invocation_config": (
        "backend.agent.builder_context",
        "_build_invocation_config",
    ),
    "_build_workflow_snapshot": (
        "backend.agent.builder_context",
        "_build_workflow_snapshot",
    ),
    "_configurable_list": ("backend.agent.builder_context", "_configurable_list"),
    "_configurable_value": ("backend.agent.builder_context", "_configurable_value"),
    "_load_chat_history": ("backend.agent.builder_history", "_load_chat_history"),
    "_persist_agent_result_history": (
        "backend.agent.builder_history",
        "_persist_agent_result_history",
    ),
    "_persist_output_history": (
        "backend.agent.builder_history",
        "_persist_output_history",
    ),
    "_persist_panel_history": (
        "backend.agent.builder_history",
        "_persist_panel_history",
    ),
    "_ainvoke_agent_wrapper": (
        "backend.agent.builder_streaming",
        "_ainvoke_agent_wrapper",
    ),
    "_astream_langgraph_wrapper": (
        "backend.agent.builder_streaming",
        "_astream_langgraph_wrapper",
    ),
}

__all__ = [
    "build_agent",
    "test_agent",
    *_LAZY_HELPER_EXPORTS,
]


def __getattr__(name: str) -> Any:
    if name not in _LAZY_HELPER_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_HELPER_EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def _resolve_requested_agent_mode(
    *,
    provider: str,
    requested_mode: str,
    web_search_enabled: bool,
) -> tuple[str, str]:
    """Return the concrete runtime mode and why it was selected."""
    normalized_requested_mode = str(requested_mode or "auto").strip().lower() or "auto"

    if normalized_requested_mode == "auto":
        if provider == "openai_compatible":
            return "function_calling", "auto_openai_compatible"
        return "langgraph", "auto_non_openai_provider"

    if normalized_requested_mode == "plain_chat" and web_search_enabled:
        if provider == "openai_compatible":
            return "function_calling", "plain_chat_requires_tool_router_for_web_search"
        return "langgraph", "plain_chat_requires_tool_router_for_web_search"

    return normalized_requested_mode, "requested"


async def build_agent(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    agent_mode: str = "auto",
    verbose: bool = True,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    vector_store_path: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
    enabled_mcp_servers: list[str] | None = None,
):
    """
    构建带工具的 Agent

    Args:
        provider: 连接类型或别名（兼容 `ollama` / `openai_compatible` / `local` / `cloud`）
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key
        temperature: 温度参数
        agent_mode: Agent 模式 ('auto', 'function_calling', 'langgraph')
            - 'auto': 按 provider 自动分流（openai_compatible -> function_calling；ollama -> langgraph）
            - 'function_calling': 强制使用 Function Calling (需要模型支持)
            - 'langgraph': 强制使用 LangGraph 轻量 Agent
        verbose: 是否显示详细日志

    Returns:
        Agent 实例 (包装了记忆管理)
    """
    provider = normalize_connection_type(provider, base_url)
    system_prompt = _normalize_runtime_system_prompt(system_prompt)

    requested_agent_mode = str(agent_mode or "auto").strip().lower() or "auto"
    actual_mode, agent_mode_reason = _resolve_requested_agent_mode(
        provider=provider,
        requested_mode=requested_agent_mode,
        web_search_enabled=web_search_enabled,
    )

    if requested_agent_mode == "auto":
        logger.info(
            "[Auto] provider=%s -> agent_mode=%s (openai_compatible=function_calling, ollama=langgraph)",
            provider,
            actual_mode,
        )
    elif requested_agent_mode != actual_mode:
        logger.info(
            "联网搜索已开启：plain_chat 请求升级为 %s 工具路由模式",
            actual_mode,
        )
    
    llm = get_llm(provider, model_name, base_url, api_key, temperature)

    logger.info("初始化工具...")
    from backend.agent.builder_wrappers import (
        FunctionCallingAgentWrapper,
        LangGraphAgentWrapper,
        PlainChatWrapper,
    )
    from backend.agent.langgraph import build_langgraph_agent
    from backend.agent.runtime_tools import build_runtime_tools
    from backend.doc_pipeline import DocPipeline

    pipeline = DocPipeline(
        vector_store_path=vector_store_path if knowledge_base_enabled else None
    )
    wrapper_kwargs: dict[str, Any] = {
        "llm": llm,
        "pipeline": pipeline,
        "system_prompt": system_prompt,
        "dashboard_template": dashboard_template,
        "knowledge_base_enabled": knowledge_base_enabled,
        "web_search_enabled": web_search_enabled,
        "requested_agent_mode": requested_agent_mode,
        "actual_agent_mode": actual_mode,
        "agent_mode_reason": agent_mode_reason,
    }
    
    if actual_mode == "langgraph":
        langgraph_app = await build_langgraph_agent(
            llm,
            pipeline,
            verbose,
            system_prompt=system_prompt,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
        )
        agent_wrapper = LangGraphAgentWrapper(langgraph_app, **wrapper_kwargs)
        logger.info("✓ 使用 LangGraph 轻量 Agent 模式（适合小模型）")
        return agent_wrapper

    if actual_mode == "plain_chat":
        logger.info("✓ 使用直连聊天模式（绕过 Agent / 工具链）")
        return PlainChatWrapper(**wrapper_kwargs)
    
    else:
        agent_executor_cls = globals().get("AgentExecutor")
        create_agent_fn = globals().get("create_tool_calling_agent")
        if agent_executor_cls is None or create_agent_fn is None:
            from langchain_classic.agents import AgentExecutor as agent_executor_cls
            from langchain_classic.agents import create_tool_calling_agent as create_agent_fn
        from langchain_core.prompts import ChatPromptTemplate

        all_tools = await build_runtime_tools(
            pipeline,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
            enabled_mcp_servers=enabled_mcp_servers,
        )
        
        logger.info("加载了 %d 个工具: %s", len(all_tools), [t.name for t in all_tools])
        
        base_system = system_prompt or "你是一个企业知识库助手，可以查询内部文档和联网搜索。请根据用户问题选择合适的工具来回答。"
        system_msg = base_system + """

【工具调用规范】
- 每个工具最多调用一次，除非首次返回结果明确不足且需要补充不同信息
- 获取到足够信息后立即生成最终回答，不要继续调用工具
- 工具返回错误或无结果时，直接基于已有信息回答，不要重复调用同一工具
- 始终用中文回答用户问题"""

        if not all_tools:
            return PlainChatWrapper(stream_policy="no_tools", **wrapper_kwargs)

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        base_agent = create_agent_fn(llm, all_tools, prompt)
        
        agent_executor = agent_executor_cls(
            agent=base_agent,
            tools=all_tools,
            verbose=verbose,
            max_iterations=25,
            max_execution_time=120,
            handle_parsing_errors=True,
            # `create_tool_calling_agent` 在当前 langchain_classic 版本下
            # 超时/迭代上限时仅支持 `force`，否则会抛出
            # "Got unsupported early_stopping_method `generate`"。
            early_stopping_method="force",
            return_intermediate_steps=True,
        )
        
        logger.info("✓ Agent 已启用多轮对话记忆 (Session 级别)")
        logger.info("✓ 使用 Function Calling 模式（需要模型支持工具调用）")

        return FunctionCallingAgentWrapper(agent_executor, **wrapper_kwargs)


async def test_agent():
    """测试 Agent 功能"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    logger.info("=" * 60)
    logger.info("Testing InsightDesk Agent")
    logger.info("=" * 60)

    agent = await build_agent(verbose=True)

    test_queries = [
        "知识库里有多少文档?",
        "今天的新闻有什么?",
    ]

    for query in test_queries:
        logger.info("问题: %s", query)
        result = await agent.ainvoke(
            {"input": query},
            config={"configurable": {"session_id": "test-session"}}
        )
        logger.info("回答: %s", result["output"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_agent())
