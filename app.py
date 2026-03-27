"""
企业专属 AI 知识库系统 - Streamlit 前端
支持文档上传、智能问答、模型切换
"""

import streamlit as st
import asyncio
import os
import sys
import logging
import tempfile
import threading
import requests
import uuid
from dotenv import load_dotenv

from agent_core import build_agent, clear_session_history
from doc_pipeline import DocPipeline

load_dotenv()

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """配置根 logger，仅在首次调用时生效。"""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)

# 页面配置
st.set_page_config(
    page_title="企业AI知识库",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义样式
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def run_async(coro):
    """在独立线程中运行异步代码,避免事件循环冲突"""
    result = None
    exception = None

    def _run():
        nonlocal result, exception
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
            loop.close()
        except Exception as e:
            exception = e

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()

    if exception:
        raise exception
    return result


def get_ollama_models(base_url: str) -> list[str]:
    """
    从 Ollama API 获取已安装的模型列表
    
    Args:
        base_url: Ollama API 地址 (例如: http://localhost:11434)
    
    Returns:
        模型名称列表 (例如: ["qwen3:4b", "llama2:7b"])
    """
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return [m["name"] for m in models]
    except requests.RequestException as e:
        logger.warning("无法连接 Ollama (%s): %s", base_url, e)
        return []


def _default_agent_config() -> dict:
    """从 .env 读取默认 Agent 配置，避免 UI 与环境变量不一致。"""
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if llm_provider == "openrouter":
        provider = "cloud"
        model = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        api_key = os.getenv("OPENROUTER_API_KEY", "")
    else:
        provider = "local"
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        api_key = ""
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": 0.3,
        "agent_mode": "auto",
    }


def init_session_state():
    """初始化会话状态"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agent" not in st.session_state:
        st.session_state.agent = None

    if "agent_config" not in st.session_state:
        st.session_state.agent_config = _default_agent_config()
    
    # 初始化 Session ID (用于多轮对话记忆)
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        logger.info("[Session] 创建新会话: %s", st.session_state.session_id)


def build_agent_sync(provider: str, model: str, base_url: str, api_key: str, temperature: float, agent_mode: str = "auto"):
    """同步方式构建 Agent"""
    return run_async(
        build_agent(
            provider=provider,
            model_name=model,
            base_url=base_url,
            api_key=api_key if api_key else None,
            temperature=temperature,
            agent_mode=agent_mode,
        )
    )


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("⚙️ 系统配置")

        st.subheader("🤖 模型设置")

        provider = st.selectbox(
            "模型类型",
            options=["local", "cloud"],
            index=0 if st.session_state.agent_config["provider"] == "local" else 1,
            help="本地模型(Ollama等) 或 云端模型(OpenRouter/OpenAI等)",
        )

        if provider == "local":
            default_base_url_temp = "http://localhost:11434" if provider == "local" else "https://openrouter.ai/api/v1"
            current_base_url = st.session_state.agent_config.get("base_url", default_base_url_temp)
            
            available_models = get_ollama_models(current_base_url)
            
            if available_models:
                model_options = available_models + ["自定义..."]
                current_model = st.session_state.agent_config.get("model", "qwen2.5:7b")
                
                if current_model in available_models:
                    default_index = available_models.index(current_model)
                else:
                    default_index = len(available_models)
                
                selected_model = st.selectbox(
                    "Model ID",
                    options=model_options,
                    index=default_index,
                    help="选择已安装的 Ollama 模型",
                )
                
                if selected_model == "自定义...":
                    model = st.text_input(
                        "自定义模型名称",
                        value=current_model if current_model not in available_models else "",
                        help="⚠️ 必须与 `ollama list` 显示的名称完全一致",
                    )
                else:
                    model = selected_model
            else:
                st.warning(f"⚠️ 无法连接到 Ollama ({current_base_url}),请检查服务是否运行")
                model = st.text_input(
                    "Model ID",
                    value=st.session_state.agent_config.get("model", "qwen2.5:7b"),
                    help="⚠️ 必须与 `ollama list` 显示的名称完全一致",
                )
        else:
            model = st.text_input(
                "Model ID",
                value=st.session_state.agent_config.get("model", "gpt-3.5-turbo"),
                help="例如: gpt-4, deepseek-chat, claude-3-opus",
            )

        default_base_url = "http://localhost:11434" if provider == "local" else "https://openrouter.ai/api/v1"
        base_url = st.text_input(
            "Base URL",
            value=st.session_state.agent_config.get("base_url", default_base_url),
            help="API 服务地址",
        )

        if provider == "cloud":
            api_key = st.text_input(
                "API Key",
                value=st.session_state.agent_config.get("api_key", ""),
                type="password",
                help="云端模型的 API Key",
            )
        else:
            api_key = ""
            st.info("💡 本地模型无需 API Key")

        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.agent_config["temperature"],
            step=0.1,
            help="控制回答的随机性,越低越确定",
        )
        
        agent_mode = st.selectbox(
            "Agent 模式",
            options=["auto", "langgraph", "function_calling"],
            index=["auto", "langgraph", "function_calling"].index(st.session_state.agent_config.get("agent_mode", "auto")),
            help="auto: 本地用 LangGraph(快), 云端用 Function Calling | langgraph: 轻量模式(适合小模型) | function_calling: 原生工具调用(需模型支持)",
        )

        config_changed = (
            provider != st.session_state.agent_config["provider"]
            or model != st.session_state.agent_config.get("model")
            or agent_mode != st.session_state.agent_config.get("agent_mode", "auto")
            or base_url != st.session_state.agent_config.get("base_url")
            or api_key != st.session_state.agent_config.get("api_key")
            or temperature != st.session_state.agent_config["temperature"]
        )

        if config_changed:
            if st.button("🔄 应用配置", type="primary", use_container_width=True):
                with st.spinner("重新初始化 Agent..."):
                    try:
                        agent = build_agent_sync(
                            provider, model, base_url, api_key, temperature, agent_mode
                        )
                        st.session_state.agent = agent
                        st.session_state.agent_config = {
                            "provider": provider,
                            "model": model,
                            "base_url": base_url,
                            "api_key": api_key,
                            "temperature": temperature,
                            "agent_mode": agent_mode,
                        }
                        st.success("✓ 配置已更新")
                        st.rerun()
                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Agent 初始化失败: {error_msg}")
                        
                        if provider == "local" and ("not found" in error_msg.lower() or "404" in error_msg):
                            available = get_ollama_models(base_url)
                            if available:
                                st.info(
                                    f"💡 模型 '{model}' 未安装。\n\n"
                                    f"**已安装的模型**:\n" + 
                                    "\n".join([f"- {m}" for m in available]) +
                                    f"\n\n或运行: `ollama pull {model}`"
                                )
                            else:
                                st.info(
                                    f"💡 请先安装模型:\n\n"
                                    f"```bash\n"
                                    f"ollama pull {model}\n"
                                    f"```"
                                )
                        elif "invalid" in error_msg.lower() or "model name" in error_msg.lower():
                            st.info(
                                "💡 模型名称格式不正确。\n\n"
                                "Ollama 模型名称格式: `name:tag`\n"
                                "例如: `qwen3:4b`, `llama2:7b`\n\n"
                                "不能包含空格或特殊字符。"
                            )

        st.divider()

        # 文档管理
        st.subheader("📁 文档管理")

        uploaded_files = st.file_uploader(
            "上传企业文档",
            type=["pdf", "docx", "doc", "md", "csv", "txt"],
            accept_multiple_files=True,
            help="支持 PDF、Word、Markdown、CSV、TXT 格式",
        )

        if uploaded_files:
            if st.button("📥 导入知识库", type="primary", use_container_width=True):
                with st.spinner("处理文档中..."):
                    try:
                        pipeline = DocPipeline()

                        temp_paths = []
                        for uploaded_file in uploaded_files:
                            temp_path = os.path.join(
                                tempfile.gettempdir(), uploaded_file.name
                            )
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.read())
                            temp_paths.append(temp_path)

                        count = pipeline.ingest(temp_paths)
                        st.success(f"✓ 已导入 {count} 个文档片段")

                        for path in temp_paths:
                            try:
                                os.remove(path)
                            except OSError as e:
                                logger.warning("临时文件删除失败 %s: %s", path, e)

                    except Exception as e:
                        st.error(f"❌ 导入失败: {e}")

        if st.button("📊 查看知识库统计", use_container_width=True):
            try:
                pipeline = DocPipeline()
                pipeline.load_store()
                stats = pipeline.get_stats()
                st.info(
                    f"**知识库状态**: {stats['status']}  \n"
                    f"**文档片段数**: {stats.get('total_docs', 0)}  \n"
                    f"**存储路径**: {stats.get('store_path', 'N/A')}"
                )
            except Exception as e:
                st.warning(f"无法获取统计信息: {e}")

        st.divider()

        # 对话管理
        st.subheader("💬 对话管理")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ 清空显示历史", use_container_width=True):
                st.session_state.messages = []
                st.success("✓ 已清空前端显示")
                st.rerun()
        
        with col2:
            if st.button("🧠 清空记忆", use_container_width=True):
                session_id = st.session_state.session_id
                success = clear_session_history(session_id)
                if success:
                    st.success("✓ 已清空 Agent 记忆")
                else:
                    st.info("记忆已为空")
                st.rerun()
        
        if st.button("🔄 重置会话", type="secondary", use_container_width=True):
            # 创建新的 Session ID
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.success("✓ 已创建新会话")
            logger.info("[Session] 重置会话: %s", st.session_state.session_id)
            st.rerun()
        
        # 显示当前 Session ID (调试用)
        with st.expander("🔍 会话信息"):
            st.code(f"Session ID: {st.session_state.session_id[:8]}...", language="text")


def render_chat():
    """渲染聊天界面"""
    st.markdown('<div class="main-header">🏢 企业专属 AI 知识库</div>', unsafe_allow_html=True)

    # 初始化 Agent
    if st.session_state.agent is None:
        with st.spinner("正在初始化 AI Agent..."):
            try:
                config = st.session_state.agent_config
                agent = build_agent_sync(
                    config["provider"],
                    config.get("model"),
                    config.get("base_url"),
                    config.get("api_key"),
                    config["temperature"],
                    config.get("agent_mode", "auto"),
                )
                st.session_state.agent = agent
                st.success("✓ Agent 初始化成功")
            except Exception as e:
                st.error(f"❌ Agent 初始化失败: {e}")
                st.info("请检查:\n1. 本地模型服务是否运行\n2. Base URL 是否正确\n3. API Key 是否有效")
                st.stop()

    config = st.session_state.agent_config
    session_id_short = st.session_state.session_id[:8]
    agent_mode_display = config.get("agent_mode", "auto")
    st.caption(
        f"当前模型: {config['provider']} | {config.get('model', 'default')} | Agent: {agent_mode_display} | T={config['temperature']} | 会话: {session_id_short}..."
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("请输入您的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    # 调用 Agent 时传入 session_id (启用多轮对话记忆)
                    result = run_async(
                        st.session_state.agent.ainvoke(
                            {"input": prompt},
                            config={"configurable": {"session_id": st.session_state.session_id}}
                        )
                    )

                    # AgentExecutor 返回 {"output": "答案"}
                    answer = result.get("output", str(result))

                    st.markdown(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )

                except Exception as e:
                    import traceback
                    logger.exception("Agent 调用失败 session_id=%s", st.session_state.session_id)
                    err_str = str(e).lower()

                    if "timeout" in err_str or "timed out" in err_str:
                        friendly = "请求超时，请稍后重试。如使用本地模型，请确认 Ollama 服务正常运行。"
                    elif "connection" in err_str or "connect" in err_str or "refused" in err_str:
                        friendly = "无法连接到模型服务，请检查 Ollama 是否启动或 Base URL 是否正确。"
                    elif "api key" in err_str or "unauthorized" in err_str or "401" in err_str:
                        friendly = "API Key 无效或未配置，请在侧边栏检查 API Key 设置。"
                    elif "not found" in err_str or "404" in err_str:
                        friendly = "模型未找到，请确认模型名称与 ollama list 中的名称一致。"
                    else:
                        friendly = f"生成回答时出错，请查看详细信息。"

                    st.error(f"❌ {friendly}")
                    with st.expander("🔍 详细错误信息 (调试用)"):
                        st.code(traceback.format_exc(), language="python")

                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"❌ {friendly}"}
                    )


def validate_config() -> None:
    """启动时校验关键配置，将问题以 warning 形式记录并在 UI 侧边栏提示。"""
    issues = []

    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if llm_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key or "your_" in api_key:
            issues.append("OPENROUTER_API_KEY 未配置或仍为占位符，云端模型将无法使用")

    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_key or "your_" in tavily_key:
        issues.append("TAVILY_API_KEY 未配置，联网搜索功能不可用")

    for msg in issues:
        logger.warning("[配置校验] %s", msg)

    if issues and "config_warnings_shown" not in st.session_state:
        st.session_state.config_warnings_shown = True
        with st.sidebar:
            for msg in issues:
                st.warning(f"⚠️ {msg}")


def main():
    """主函数"""
    _setup_logging()
    init_session_state()
    validate_config()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
