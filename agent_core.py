"""
LangChain Agent 编排核心
支持 Ollama 本地模型和 OpenRouter 云端模型双后端
支持 Function Calling 和 LangGraph 轻量 Agent 双模式
"""

import os
import sys
import re
import time
import logging
from typing import Optional, Dict, TypedDict, Annotated, Literal
from dotenv import load_dotenv
try:
    from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
except ModuleNotFoundError:
    # 兼容未安装 langchain_classic 的环境
    from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from doc_pipeline import DocPipeline
from chat_store import SQLiteChatMessageHistory
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# 联网搜索开关（由 app.py 在每次对话前设置）
_web_search_enabled: bool = True


def set_web_search_enabled(enabled: bool) -> None:
    """设置联网搜索全局开关"""
    global _web_search_enabled
    _web_search_enabled = enabled


def get_session_history(session_id: str) -> SQLiteChatMessageHistory:
    """
    获取或创建指定 session_id 的历史记录
    
    Args:
        session_id: 会话 ID
    
    Returns:
        该会话的历史消息存储（SQLite 持久化）
    """
    return SQLiteChatMessageHistory(session_id=session_id)


def clear_session_history(session_id: str) -> bool:
    """
    清空指定 session_id 的历史记录
    
    Args:
        session_id: 会话 ID
    
    Returns:
        是否成功清空
    """
    history = SQLiteChatMessageHistory(session_id=session_id)
    history.clear()
    return True




def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
):
    """
    模型工厂函数 - 根据配置返回对应的 LLM 实例

    Args:
        provider: 模型提供方 ('local' 或 'cloud')
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key (本地模型不需要)
        temperature: 温度参数

    Returns:
        LangChain ChatModel 实例
    """
    provider = provider or "local"

    if provider == "cloud":
        # 云端模型 - 使用 OpenAI 兼容接口
        from langchain_openai import ChatOpenAI

        if not api_key:
            raise ValueError("云端模型需要提供 API Key")
        
        if not base_url:
            raise ValueError("云端模型需要提供 Base URL")

        model = model_name or "gpt-3.5-turbo"

        logger.info("使用云端模型: %s (地址: %s)", model, base_url)
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=2,
            api_key=api_key,
            base_url=base_url,
        )

    elif provider == "local":
        # 本地模型 - 使用 Ollama
        from langchain_ollama import ChatOllama

        model = model_name or "qwen3.5-2B"
        base_url = base_url or "http://localhost:11434"

        if not re.match(r'^[a-zA-Z0-9._:/-]+$', model):
            raise ValueError(
                f"Invalid Ollama model name: '{model}'. "
                "Model names cannot contain spaces or special characters. "
                "Valid format: name:tag (e.g., qwen3:4b, llama2:7b)"
            )

        logger.info("使用本地模型: %s (地址: %s)", model, base_url)
        return ChatOllama(
            model=model,
            temperature=0.1,  # 轻微随机性，避免格式僵化
            base_url=base_url,
            num_predict=2048,
            top_p=0.9,  # 限制采样范围
        )

    else:
        raise ValueError(f"不支持的模型提供方: {provider}")


def create_tools(pipeline: DocPipeline):
    """
    创建所有工具函数
    
    Args:
        pipeline: DocPipeline 实例
    
    Returns:
        工具函数列表
    """
    @tool
    async def query_knowledge(question: str, top_k: int = 3) -> str:
        """
        从企业内部知识库中检索相关文档片段 (使用 Rerank 二段重排)

        Args:
            question: 用户问题
            top_k: 返回的文档片段数量 (默认 3, 经过 Rerank 精排)

        Returns:
            格式化的文档片段,包含来源信息
        """
        try:
            if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
                pipeline.load_store()
            
            if pipeline.vectorstore is None:
                return "⚠️ 知识库未初始化,请先上传文档"

            docs = pipeline.search_with_rerank(question, k=top_k, fetch_k=10)

            if not docs:
                return "未找到相关文档"

            results = []
            sources_meta = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source", "未知来源")
                content = doc.page_content.strip()
                results.append(f"【文档 {i}: {source}】\n{content}")
                sources_meta.append({
                    "type": "doc",
                    "title": source,
                    "snippet": content[:200],
                    "index": i,
                })

            # Embed sources metadata as a JSON comment at the end for execute_tool to parse
            import json as _json
            sources_marker = f"\n\n__SOURCES__:{_json.dumps(sources_meta, ensure_ascii=False)}"
            return "\n\n---\n\n".join(results) + sources_marker

        except Exception as e:
            logger.exception("tool=query_knowledge 检索失败")
            return f"❌ 检索失败: {str(e)}"

    @tool
    async def reload_knowledge_base() -> str:
        """
        重新加载知识库 (在文档更新后调用)

        Returns:
            加载状态信息
        """
        try:
            success = pipeline.load_store()
            if success:
                stats = pipeline.get_stats()
                return f"✓ 知识库重载成功\n总文档数: {stats['total_docs']}\n路径: {stats['store_path']}"
            else:
                return "⚠️ 知识库不存在或加载失败"
        except Exception as e:
            logger.exception("tool=reload_knowledge_base 重载失败")
            return f"❌ 重载失败: {str(e)}"

    @tool
    async def get_knowledge_stats() -> str:
        """
        获取知识库统计信息

        Returns:
            知识库状态和统计数据
        """
        try:
            if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
                pipeline.load_store()
            
            stats = pipeline.get_stats()
            return f"""知识库状态: {stats['status']}
总文档片段数: {stats.get('total_docs', 0)}
存储路径: {stats.get('store_path', 'N/A')}"""
        except Exception as e:
            logger.exception("tool=get_knowledge_stats 获取统计失败")
            return f"❌ 获取统计信息失败: {str(e)}"

    @tool
    async def web_search(search_query: str, max_results: int = 5) -> str:
        """
        搜索互联网获取实时信息

        Args:
            search_query: 搜索关键词
            max_results: 最大返回结果数 (默认 5)

        Returns:
            格式化的搜索结果,包含标题、链接和摘要
        """
        if not _web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"

        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            return "❌ 未配置 TAVILY_API_KEY,无法使用联网搜索功能"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": search_query,
                        "max_results": max_results,
                        "api_key": api_key,
                        "search_depth": "basic",
                        "include_answer": True,
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                answer = data.get("answer", "")

                if not results:
                    return f"未找到相关搜索结果: {search_query}"

                output = []

                if answer:
                    output.append(f"【AI 总结】\n{answer}\n")

                output.append(f"【搜索结果 - {search_query}】\n")

                for i, result in enumerate(results, 1):
                    title = result.get("title", "无标题")
                    url = result.get("url", "")
                    content = result.get("content", "")

                    output.append(f"{i}. {title}\n链接: {url}\n摘要: {content}")

            # Embed sources metadata
            import json as _json
            sources_meta = [
                {
                    "type": "web",
                    "title": r.get("title", "无标题"),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                    "index": idx,
                }
                for idx, r in enumerate(results, 1)
            ]
            sources_marker = f"\n\n__SOURCES__:{_json.dumps(sources_meta, ensure_ascii=False)}"
            return "\n\n---\n\n".join(output) + sources_marker

        except httpx.HTTPStatusError as e:
            logger.error("tool=web_search HTTP错误 status=%d", e.response.status_code)
            return f"❌ 搜索 API 请求失败 (HTTP {e.response.status_code}): {e.response.text}"
        except httpx.TimeoutException:
            logger.warning("tool=web_search 请求超时")
            return "❌ 搜索请求超时,请稍后重试"
        except Exception as e:
            logger.exception("tool=web_search 搜索失败")
            return f"❌ 搜索失败: {str(e)}"

    @tool
    async def quick_answer(user_question: str) -> str:
        """
        快速问答 - 直接返回 AI 总结答案,不返回详细搜索结果

        Args:
            user_question: 问题

        Returns:
            AI 总结的答案
        """
        if not _web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"

        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            return "❌ 未配置 TAVILY_API_KEY"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": user_question,
                        "max_results": 3,
                        "api_key": api_key,
                        "search_depth": "basic",
                        "include_answer": True,
                    },
                )
                response.raise_for_status()
                data = response.json()

                answer = data.get("answer", "")
                if answer:
                    return f"【网络搜索答案】\n{answer}"
                else:
                    return "未能生成答案,请使用 web_search 查看详细结果"

        except Exception as e:
            logger.exception("tool=quick_answer 失败")
            return f"❌ 快速问答失败: {str(e)}"

    @tool
    async def fetch_webpage(url: str) -> str:
        """
        抓取指定网页的全文内容

        Args:
            url: 网页 URL

        Returns:
            网页的纯文本内容（截断至 8000 字符）
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return "❌ 缺少 beautifulsoup4 依赖，请运行: pip install beautifulsoup4"

        if not _web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                
                # Remove unwanted tags
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                
                # Extract text
                text = soup.get_text(separator="\n", strip=True)
                
                # Clean up multiple newlines
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)
                
                # Truncate to 8000 characters
                max_chars = 8000
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n\n...[内容已截断]"
                
                return f"【网页内容 - {url}】\n\n{text}"

        except httpx.HTTPStatusError as e:
            logger.error("tool=fetch_webpage HTTP错误 status=%d url=%s", e.response.status_code, url)
            return f"❌ 无法访问网页 (HTTP {e.response.status_code}): {url}"
        except httpx.TimeoutException:
            logger.warning("tool=fetch_webpage 请求超时 url=%s", url)
            return f"❌ 网页请求超时: {url}"
        except Exception as e:
            logger.exception("tool=fetch_webpage 抓取失败 url=%s", url)
            return f"❌ 抓取网页失败: {str(e)}"

    return [query_knowledge, reload_knowledge_base, get_knowledge_stats, web_search, quick_answer, fetch_webpage]


async def _rewrite_search_query(llm, user_input: str, chat_history: list[BaseMessage]) -> str:
    """
    重写搜索查询以包含对话上下文
    
    Args:
        llm: LLM 实例
        user_input: 用户原始输入
        chat_history: 对话历史
    
    Returns:
        优化后的搜索查询
    """
    if not chat_history:
        return user_input
    
    history_text = ""
    recent_history = chat_history[-4:]
    for msg in recent_history:
        if isinstance(msg, HumanMessage):
            history_text += f"用户: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"助手: {msg.content}\n"
    
    if not history_text.strip():
        return user_input
    
    rewrite_prompt = f"""你是搜索查询优化器。根据对话上下文，将用户的问题改写为最优的搜索引擎查询词。
只输出改写后的查询词，不要解释。

对话上下文:
{history_text}

用户问题: {user_input}

优化后的搜索查询:"""
    
    try:
        response = await llm.ainvoke(rewrite_prompt)
        rewritten = response.content.strip()
        logger.info("[QueryRewrite] original=%s -> rewritten=%s", user_input[:50], rewritten[:50])
        return rewritten if rewritten else user_input
    except Exception as e:
        logger.exception("[QueryRewrite] 查询重写失败")
        return user_input


class AgentState(TypedDict):
    """LangGraph Agent 状态"""
    input: str
    chat_history: list[BaseMessage]
    tool_choice: str
    tool_result: str
    sources: list  # [{"type": "doc"|"web", "title": str, "url"?: str, "snippet": str}]
    output: str


async def build_langgraph_agent(
    llm,
    pipeline: DocPipeline,
    verbose: bool = True,
    system_prompt: Optional[str] = None,
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
    tools_list = create_tools(pipeline)
    tools_dict = {
        "1": tools_list[0],  # query_knowledge
        "2": tools_list[3],  # web_search
        "3": tools_list[4],  # quick_answer
        "4": tools_list[2],  # get_knowledge_stats
        "5": tools_list[1],  # reload_knowledge_base
        "6": tools_list[5],  # fetch_webpage
    }
    
    async def classify_intent(state: AgentState) -> AgentState:
        """节点1: 分类用户意图，选择工具"""
        user_input = state["input"]
        chat_history = state.get("chat_history", [])
        state.setdefault("sources", [])
        
        history_text = ""
        if chat_history:
            recent_history = chat_history[-4:]
            for msg in recent_history:
                if isinstance(msg, HumanMessage):
                    history_text += f"用户: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    history_text += f"助手: {msg.content}\n"
        
        role_desc = system_prompt or "你是一个企业知识库助手"
        classify_prompt = f"""{role_desc}。根据用户问题选择最合适的工具编号（只输出一个数字）：

1 - 查询企业知识库（用于查询内部文档、公司资料）
2 - 联网搜索（用于查询实时信息、新闻、外部知识）
3 - 快速问答（用于快速获取网络答案）
4 - 知识库统计（用于查询知识库状态、文档数量）
5 - 重载知识库（用于刷新知识库）
6 - 抓取网页全文（用于读取搜索结果中的具体网页内容）
0 - 不需要工具（用于打招呼、闲聊、感谢等）

{history_text}
用户: {user_input}

请只输出一个数字（0-6）："""

        try:
            response = await llm.ainvoke(classify_prompt)
            choice = response.content.strip()
            
            choice_char = ""
            for char in choice:
                if char in "0123456":
                    choice_char = char
                    break
            
            if not choice_char:
                choice_char = "0"
            
            logger.info("[LangGraph] tool_choice=%s", choice_char)
            
            state["tool_choice"] = choice_char
            return state
            
        except Exception as e:
            logger.exception("[LangGraph] 意图分类失败")
            state["tool_choice"] = "0"
            return state
    
    async def execute_tool(state: AgentState) -> AgentState:
        """节点2: 执行选定的工具"""
        import json as _json
        tool_choice = state["tool_choice"]
        user_input = state["input"]
        chat_history = state.get("chat_history", [])
        
        if tool_choice not in tools_dict:
            state["tool_result"] = ""
            state["sources"] = []
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
            elif "url" in tool_func.args:
                params = {"url": actual_input}
            else:
                params = {}
            
            result = await tool_func.ainvoke(params)
            
            latency_ms = int((time.monotonic() - t0) * 1000)

            # Extract __SOURCES__ marker if present
            sources: list = []
            sources_marker = "__SOURCES__:"
            if sources_marker in result:
                clean_result, _, sources_json = result.partition(sources_marker)
                try:
                    sources = _json.loads(sources_json)
                except Exception:
                    pass
                result = clean_result.rstrip()

            state["tool_result"] = result
            state["sources"] = sources
            logger.info("[LangGraph] tool_name=%s latency_ms=%d result_len=%d sources=%d",
                        tool_func.name, latency_ms, len(result), len(sources))
            
        except Exception as e:
            logger.exception("[LangGraph] tool_name=%s 执行失败", tool_func.name)
            state["tool_result"] = f"❌ 工具执行失败: {str(e)}"
            state["sources"] = []
        
        return state
    
    async def generate_answer(state: AgentState) -> AgentState:
        """节点3: 生成最终回答，并在引用文档时注入脚注标记"""
        import json as _json
        user_input = state["input"]
        tool_result = state.get("tool_result", "")
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
            answer_prompt = f"""{role_desc}。根据工具返回的信息回答用户问题。{citation_hint}{intent_instructions}
{history_text}
用户问题: {user_input}

工具返回的信息:
{tool_result}

请基于以上信息，用自然、友好的语言回答用户问题。如有引用来源请在对应句子末尾添加 [^数字] 标注："""
        else:
            answer_prompt = f"""{role_desc}。直接回答用户问题。{intent_instructions}
{history_text}
用户: {user_input}

请用自然、友好的语言回答："""
        
        try:
            response = await llm.ainvoke(answer_prompt)
            state["output"] = response.content.strip()
            logger.info("[LangGraph] 生成回答完成 output_len=%d", len(state["output"]))
            
        except Exception as e:
            logger.exception("[LangGraph] 生成回答失败")
            state["output"] = f"❌ 生成回答失败: {str(e)}"
        
        return state
    
    def should_use_tool(state: AgentState) -> Literal["execute_tool", "generate_answer"]:
        """条件边: 判断是否需要使用工具"""
        tool_choice = state.get("tool_choice", "0")
        if tool_choice in ("1", "2", "3", "4", "5", "6"):
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


async def build_agent(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    agent_mode: str = "auto",
    verbose: bool = True,
    system_prompt: Optional[str] = None,
):
    """
    构建带工具的 Agent

    Args:
        provider: 模型提供方 ('local' 或 'cloud')
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key
        temperature: 温度参数
        agent_mode: Agent 模式 ('auto', 'function_calling', 'langgraph')
            - 'auto': 本地模型用 LangGraph, 云端模型用 Function Calling
            - 'function_calling': 强制使用 Function Calling (需要模型支持)
            - 'langgraph': 强制使用 LangGraph 轻量 Agent
        verbose: 是否显示详细日志

    Returns:
        Agent 实例 (包装了记忆管理)
    """
    provider = provider or "local"
    
    if agent_mode == "auto":
        actual_mode = "langgraph" if provider == "local" else "function_calling"
        logger.info("[Auto] provider=%s -> agent_mode=%s", provider, actual_mode)
    else:
        actual_mode = agent_mode
    
    llm = get_llm(provider, model_name, base_url, api_key, temperature)
    
    logger.info("初始化工具...")
    pipeline = DocPipeline()
    
    if actual_mode == "langgraph":
        langgraph_app = await build_langgraph_agent(llm, pipeline, verbose, system_prompt=system_prompt)
        
        class LangGraphAgentWrapper:
            """包装 LangGraph agent 以兼容原有调用方式"""
            def __init__(self, app):
                self.app = app
            
            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = config.get("configurable", {}).get("session_id", "default") if config else "default"
                
                history = SQLiteChatMessageHistory(session_id=session_id)
                
                user_input = inputs.get("input", "")
                
                state = {
                    "input": user_input,
                    "chat_history": list(history.messages),
                    "tool_choice": "",
                    "tool_result": "",
                    "sources": [],
                    "output": "",
                }
                
                result_state = await self.app.ainvoke(state)
                
                output = result_state.get("output", "")
                sources = result_state.get("sources", [])
                
                history.add_user_message(user_input)
                history.add_ai_message(output)
                
                return {"output": output, "sources": sources}

            async def astream_answer(self, user_input: str, config: dict = None):
                """流式输出：先运行完整推理，再逐块 yield 答案，最后 yield sources 字典"""
                result = await self.ainvoke({"input": user_input}, config=config)
                output = result.get("output", "")
                sources = result.get("sources", [])

                # Yield sources metadata first (as a special dict)
                if sources:
                    yield {"type": "sources", "sources": sources}

                chunk_size = 20
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)
        
        agent_wrapper = LangGraphAgentWrapper(langgraph_app)
        logger.info("✓ 使用 LangGraph 轻量 Agent 模式（适合小模型）")
        return agent_wrapper
    
    else:
        all_tools = create_tools(pipeline)
        
        logger.info("加载了 %d 个工具: %s", len(all_tools), [t.name for t in all_tools])
        
        system_msg = system_prompt or "你是一个企业知识库助手，可以查询内部文档和联网搜索。请根据用户问题选择合适的工具来回答。"
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        base_agent = create_tool_calling_agent(llm, all_tools, prompt)
        
        agent_executor = AgentExecutor(
            agent=base_agent,
            tools=all_tools,
            verbose=verbose,
            max_iterations=15,
            max_execution_time=90,
            return_intermediate_steps=False,
        )
        
        agent_with_memory = RunnableWithMessageHistory(
            agent_executor,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="output",
        )
        
        logger.info("✓ Agent 已启用多轮对话记忆 (Session 级别)")
        logger.info("✓ 使用 Function Calling 模式（需要模型支持工具调用）")
        
        return agent_with_memory


async def test_agent():
    """测试 Agent 功能"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    logger.info("=" * 60)
    logger.info("测试企业 AI 知识库 Agent")
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
