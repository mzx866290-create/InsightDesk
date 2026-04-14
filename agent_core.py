"""
LangChain Agent 编排核心
支持 Ollama 本地模型和 OpenRouter 云端模型双后端
支持 Function Calling 和 LangGraph 轻量 Agent 双模式
"""

import asyncio
import json
import os
import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Optional, Dict, TypedDict, Literal, Callable
from agent_mcp_helpers import load_mcp_tool_overrides
from dotenv import load_dotenv
try:
    from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
except ModuleNotFoundError:
    # 兼容未安装 langchain_classic 的环境
    from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from doc_pipeline import DocPipeline
from chat_store import SQLiteChatMessageHistory, list_session_memory
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# 联网搜索开关（由上层 API / 前端在每次对话前设置）
_web_search_enabled: bool = True
DEFAULT_LLM_TIMEOUT_SECONDS = float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "35"))
DEFAULT_KB_DOC_CHAR_LIMIT = int(os.getenv("KB_DOC_CHAR_LIMIT", "600"))
DEFAULT_KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
DEFAULT_KB_FETCH_K = int(os.getenv("KB_FETCH_K", "10"))
CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"

DASHBOARD_TRIGGER_KEYWORDS = (
    "仪表盘",
    "看板",
    "图表",
    "数据图",
    "可视化",
    "柱状图",
    "柱形图",
    "条形图",
    "折线图",
    "饼图",
    "趋势图",
    "统计图",
    "图形化",
    "dashboard",
)

DEFAULT_DASHBOARD_TEMPLATE: Dict[str, Any] = {
    "enabled": True,
    "title_hint": "知识库数据洞察",
    "focus_metrics": [],
    "preferred_charts": ["bar", "line", "pie"],
    "section_order": ["summary", "metrics", "charts", "table", "evidence", "warnings"],
    "audience_tone": "专业、直观、适合业务汇报",
}

OLLAMA_CONNECTION_ALIASES = {
    "local",
    "ollama",
    "ollama_local",
}
OPENAI_COMPAT_CONNECTION_ALIASES = {
    "cloud",
    "openai",
    "openai_compatible",
    "openrouter",
    "compatible",
    "api",
}


@dataclass(frozen=True)
class BuiltinToolSpec:
    code: str
    name: str
    description: str
    category: Literal["knowledge_base", "web_search", "always"] = "always"


_BUILTIN_TOOL_REGISTRY: list[BuiltinToolSpec] = []


def register_builtin_tool(spec: BuiltinToolSpec) -> None:
    """Register a built-in tool declaration for routing and enablement."""
    if any(item.code == spec.code for item in _BUILTIN_TOOL_REGISTRY):
        raise ValueError(f"Tool code already registered: {spec.code}")
    if any(item.name == spec.name for item in _BUILTIN_TOOL_REGISTRY):
        raise ValueError(f"Tool name already registered: {spec.name}")
    _BUILTIN_TOOL_REGISTRY.append(spec)


def get_builtin_tool_registry() -> tuple[BuiltinToolSpec, ...]:
    return tuple(_BUILTIN_TOOL_REGISTRY)


def _parse_builtin_tool_name_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        candidates = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple)):
        candidates = raw_value
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        normalized.append(name)
        seen.add(name)
    return normalized


def _load_configured_builtin_tool_names() -> Optional[list[str]]:
    raw_names = os.getenv("ENABLED_BUILTIN_TOOLS")
    if raw_names is not None:
        return _parse_builtin_tool_name_list(raw_names)

    config_path = (os.getenv("BUILTIN_TOOL_CONFIG_PATH") or "").strip()
    if not config_path:
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        logger.warning("Builtin tool config file not found: %s", config_path)
        return None
    except json.JSONDecodeError:
        logger.warning("Builtin tool config file is not valid JSON: %s", config_path)
        return None
    except OSError:
        logger.warning("Builtin tool config file could not be read: %s", config_path)
        return None

    if isinstance(payload, dict):
        configured_names = payload.get("enabled_builtin_tools")
    else:
        configured_names = payload

    parsed_names = _parse_builtin_tool_name_list(configured_names)
    if configured_names is None:
        logger.warning(
            "Builtin tool config missing 'enabled_builtin_tools': %s",
            config_path,
        )
        return None
    return parsed_names


def list_enabled_builtin_tool_specs(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
) -> list[BuiltinToolSpec]:
    specs: list[BuiltinToolSpec] = []
    for spec in _BUILTIN_TOOL_REGISTRY:
        if spec.category == "knowledge_base" and not knowledge_base_enabled:
            continue
        if spec.category == "web_search" and not web_search_enabled:
            continue
        specs.append(spec)

    configured_names = _load_configured_builtin_tool_names()
    if configured_names is None:
        return specs

    specs_by_name = {spec.name: spec for spec in specs}
    configured_specs = [
        specs_by_name[name]
        for name in configured_names
        if name in specs_by_name
    ]
    unknown_names = [name for name in configured_names if name not in specs_by_name]
    if unknown_names:
        logger.warning("Ignoring unknown builtin tool names: %s", ", ".join(unknown_names))
    return configured_specs


def _build_enabled_tool_directory(
    tools_by_name: dict[str, Any],
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> tuple[dict[str, Any], list[str], str]:
    tools_dict: dict[str, Any] = {}
    tool_options = ["0 - 不需要工具（用于打招呼、闲聊、感谢等）"]

    for spec in list_enabled_builtin_tool_specs(
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
    ):
        tool_obj = tools_by_name.get(spec.name)
        if tool_obj is None:
            logger.warning("Tool declared but not instantiated: %s", spec.name)
            continue
        tools_dict[spec.code] = tool_obj
        tool_options.append(f"{spec.code} - {spec.description}")

    allowed_choices = "".join(sorted(tools_dict.keys()))
    return tools_dict, tool_options, allowed_choices


for _builtin_tool_spec in (
    BuiltinToolSpec(
        code="1",
        name="query_knowledge",
        description="查询企业知识库（用于查询内部文档、公司资料）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="4",
        name="get_knowledge_stats",
        description="知识库统计（用于查询知识库状态、文档数量）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="5",
        name="reload_knowledge_base",
        description="重载知识库（用于刷新知识库）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="2",
        name="web_search",
        description="联网搜索（用于查询实时信息、新闻、外部知识）",
        category="web_search",
    ),
    BuiltinToolSpec(
        code="3",
        name="quick_answer",
        description="快速问答（用于快速获取网络答案）",
        category="web_search",
    ),
    BuiltinToolSpec(
        code="6",
        name="fetch_webpage",
        description="抓取网页全文（用于读取搜索结果中的具体网页内容）",
        category="web_search",
    ),
):
    register_builtin_tool(_builtin_tool_spec)


def set_web_search_enabled(enabled: bool) -> None:
    """设置联网搜索全局开关"""
    global _web_search_enabled
    _web_search_enabled = enabled


def normalize_connection_type(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """Normalize legacy provider names into a compatibility-first connection type."""
    raw_provider = (provider or "").strip().lower()
    raw_base_url = (base_url or "").strip().lower()

    if raw_provider in OLLAMA_CONNECTION_ALIASES:
        return "ollama"
    if raw_provider in OPENAI_COMPAT_CONNECTION_ALIASES:
        return "openai_compatible"

    if raw_base_url:
        if "11434" in raw_base_url or raw_base_url.rstrip("/").endswith("ollama"):
            return "ollama"
        return "openai_compatible"

    return "ollama"


def default_base_url_for_connection_type(connection_type: str) -> str:
    normalized = normalize_connection_type(connection_type)
    if normalized == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return (
        os.getenv("OPENAI_COMPAT_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENROUTER_BASE_URL")
        or "https://openrouter.ai/api/v1"
    )


def default_model_for_connection_type(connection_type: str) -> str:
    normalized = normalize_connection_type(connection_type)
    if normalized == "ollama":
        return os.getenv("OLLAMA_MODEL", "qwen3.5-2B:latest")

    return (
        os.getenv("OPENAI_COMPAT_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or "gpt-4o-mini"
    )


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


def _has_image_input(user_input: Any) -> bool:
    if not isinstance(user_input, list):
        return False
    return any(
        isinstance(item, dict) and item.get("type") == "image_url"
        for item in user_input
    )


def _stringify_user_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        text_parts = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                text_parts.append(str(item["text"]))
            elif item.get("type") == "image_url":
                image_count += 1
        if image_count:
            text_parts.append(f"[用户上传了 {image_count} 张图片]")
        return "\n".join(part for part in text_parts if part).strip()
    return str(user_input)


def _collapse_file_context_for_history(text: str) -> str:
    pattern = (
        re.escape(CHAT_FILE_CONTEXT_START_MARKER)
        + r"(.*?)"
        + re.escape(CHAT_FILE_CONTEXT_END_MARKER)
    )
    matches = re.findall(pattern, text or "", flags=re.DOTALL)
    if not matches:
        return (text or "").strip()

    file_names: list[str] = []
    for block in matches:
        file_names.extend(
            [
                name.strip()
                for name in re.findall(r"File name:\s*(.+)", block)
                if name.strip()
            ]
        )

    if file_names:
        display_names = "、".join(file_names[:3])
        if len(file_names) > 3:
            display_names += " 等"
        summary = f"[用户上传了 {len(file_names)} 个文件: {display_names}]"
    else:
        summary = "[用户上传了附件文件]"

    collapsed = re.sub(pattern, summary, text or "", flags=re.DOTALL).strip()
    return re.sub(r"\n{3,}", "\n\n", collapsed).strip()


def _summarize_user_input_for_history(user_input: Any) -> str:
    if isinstance(user_input, str):
        return _collapse_file_context_for_history(user_input)
    if isinstance(user_input, list):
        text_parts = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                text_parts.append(_collapse_file_context_for_history(str(item["text"])))
            elif item.get("type") == "image_url":
                image_count += 1
        if image_count:
            text_parts.append(f"[用户上传了 {image_count} 张图片]")
        return "\n".join(part for part in text_parts if part).strip()
    return _collapse_file_context_for_history(str(user_input))


def _clip_attachment_source_snippet(text: str, max_chars: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + " ...[节选]"


def _build_attachment_sources(
    raw_files: Optional[list[dict[str, Any]]] = None,
    raw_images: Optional[list[dict[str, Any]]] = None,
    answer_group_id: str = "",
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for index, file in enumerate(raw_files or [], start=1):
        if not isinstance(file, dict):
            continue
        title = str(file.get("name") or "").strip() or f"会话附件 {index}"
        snippet = _clip_attachment_source_snippet(str(file.get("extracted_text") or ""))
        if not snippet:
            snippet = "该附件已加入当前会话上下文，可作为回答依据。"
        media_type = str(file.get("media_type") or "application/octet-stream").strip()
        signature = ("attachment", title, snippet)
        if signature in seen:
            continue
        seen.add(signature)
        source: dict[str, Any] = {
            "type": "attachment",
            "title": title,
            "snippet": snippet,
            "attachment_kind": "file",
            "media_type": media_type,
        }
        data_url = str(file.get("data_url") or "").strip()
        if data_url:
            source["data_url"] = data_url
        if answer_group_id:
            source["answer_group_id"] = answer_group_id
        sources.append(source)

    for index, image in enumerate(raw_images or [], start=1):
        if not isinstance(image, dict):
            continue
        title = str(image.get("name") or "").strip() or f"会话图片 {index}"
        snippet = "用户在当前会话上传了这张图片，可结合视觉内容一起理解回答。"
        media_type = str(image.get("media_type") or "image/png").strip()
        signature = ("attachment", title, snippet)
        if signature in seen:
            continue
        seen.add(signature)
        source = {
            "type": "attachment",
            "title": title,
            "snippet": snippet,
            "attachment_kind": "image",
            "media_type": media_type,
        }
        data_url = str(image.get("data_url") or "").strip()
        if data_url:
            source["data_url"] = data_url
        if answer_group_id:
            source["answer_group_id"] = answer_group_id
        sources.append(source)

    return sources


def _merge_sources_with_attachments(
    existing_sources: Optional[list[dict[str, Any]]] = None,
    raw_files: Optional[list[dict[str, Any]]] = None,
    raw_images: Optional[list[dict[str, Any]]] = None,
    answer_group_id: str = "",
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for source in existing_sources or []:
        if not isinstance(source, dict):
            continue
        normalized = dict(source)
        signature = (
            str(normalized.get("type") or "").strip(),
            str(normalized.get("title") or "").strip(),
            str(normalized.get("snippet") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(normalized)

    for source in _build_attachment_sources(
        raw_files=raw_files,
        raw_images=raw_images,
        answer_group_id=answer_group_id,
    ):
        signature = (
            str(source.get("type") or "").strip(),
            str(source.get("title") or "").strip(),
            str(source.get("snippet") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(source)

    return merged


async def _ainvoke_llm_with_timeout(
    llm,
    payload: Any,
    timeout_seconds: Optional[float] = None,
):
    """统一为 LLM 调用增加超时，避免知识库场景长时间挂起。"""
    timeout = timeout_seconds or DEFAULT_LLM_TIMEOUT_SECONDS
    try:
        return await asyncio.wait_for(llm.ainvoke(payload), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"LLM request timed out after {int(timeout)}s") from exc


def _is_timeout_error(exc: BaseException) -> bool:
    """归一化识别超时异常，避免对已兜底场景打印整段堆栈。"""
    if isinstance(exc, TimeoutError):
        return True
    return "timed out" in str(exc).lower()


def _compact_tool_result_for_prompt(tool_result: str, max_chars: int = 1800) -> str:
    """压缩工具结果，降低云端模型在长上下文下的失败概率。"""
    text = (tool_result or "").strip()
    if not text:
        return ""

    # 去掉残留的 sources marker，并清理不可见控制字符。
    marker = "__SOURCES__:"
    if marker in text:
        text = text.partition(marker)[0].rstrip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)

    if len(text) <= max_chars:
        return text

    sections = [section.strip() for section in text.split("\n\n---\n\n") if section.strip()]
    if not sections:
        return text[: max_chars - 18].rstrip() + "\n...[内容已截断]"

    compact_sections: list[str] = []
    seen_signatures: set[str] = set()
    remaining = max_chars

    for section in sections:
        lines = [line.rstrip() for line in section.splitlines() if line.strip()]
        if not lines:
            continue

        header = lines[0]
        body = "\n".join(lines[1:]).strip()
        normalized_body = re.sub(r"\s+", " ", body)
        signature = normalized_body[:240]
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        # 每段只保留核心内容，避免重复长片段把 prompt 撑爆。
        body_limit = min(520, max(180, remaining - len(header) - 20))
        if len(body) > body_limit:
            body = body[:body_limit].rstrip() + "\n...[节选]"

        compact = header if not body else f"{header}\n{body}"
        compact_len = len(compact) + (8 if compact_sections else 0)
        if compact_len > remaining and compact_sections:
            break

        compact_sections.append(compact)
        remaining -= compact_len
        if remaining <= 120:
            break

    compact_text = "\n\n---\n\n".join(compact_sections).strip()
    if not compact_text:
        compact_text = text[: max_chars - 18].rstrip() + "\n...[内容已截断]"
    elif len(compact_text) < len(text):
        compact_text += "\n\n[已自动压缩知识库片段，保留高相关内容]"
    return compact_text


def _trim_knowledge_doc_content(content: str, max_chars: int = DEFAULT_KB_DOC_CHAR_LIMIT) -> str:
    cleaned = re.sub(r"\s+", " ", (content or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + " ...[节选]"


def _strip_think_tags(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if re.search(r"<think>", cleaned, flags=re.IGNORECASE):
        cleaned = re.split(r"<think>", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip()


def _trim_session_memory_content(content: str, max_chars: int = 280) -> str:
    cleaned = re.sub(r"\s+", " ", (content or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _session_memory_kind_label(kind: str, meta: Optional[dict[str, Any]] = None) -> str:
    source = str((meta or {}).get("source") or "").strip().lower()
    if (kind or "").strip().lower() == "summary":
        return "自动阶段摘要" if source == "auto" else "阶段摘要"
    return {
        "fact": "稳定事实",
        "decision": "已确认决策",
        "todo": "后续待办",
    }.get((kind or "").strip().lower(), "长期记忆")


def _build_session_memory_message(
    memories: list[dict[str, Any]],
) -> Optional[SystemMessage]:
    normalized_memories = [
        memory for memory in memories if isinstance(memory, dict) and str(memory.get("content") or "").strip()
    ]
    if not normalized_memories:
        return None

    normalized_memories.sort(
        key=lambda memory: (
            float(memory.get("updated_at") or 0),
            float(memory.get("created_at") or 0),
            str(memory.get("id") or ""),
        )
    )

    auto_summaries: list[dict[str, Any]] = []
    manual_memories_by_kind: dict[str, list[dict[str, Any]]] = {
        "decision": [],
        "todo": [],
        "fact": [],
        "summary": [],
    }
    for memory in normalized_memories:
        kind = str(memory.get("kind") or "").strip().lower()
        meta = memory.get("meta") if isinstance(memory.get("meta"), dict) else {}
        if kind == "summary" and str(meta.get("source") or "").strip().lower() == "auto":
            auto_summaries.append(memory)
            continue
        manual_memories_by_kind.setdefault(kind or "fact", []).append(memory)

    ordered_memories: list[dict[str, Any]] = []
    ordered_memories.extend(auto_summaries[-1:])
    ordered_memories.extend(manual_memories_by_kind.get("decision", [])[-3:])
    ordered_memories.extend(manual_memories_by_kind.get("todo", [])[-3:])
    ordered_memories.extend(manual_memories_by_kind.get("fact", [])[-4:])
    ordered_memories.extend(manual_memories_by_kind.get("summary", [])[-2:])

    if not ordered_memories:
        return None

    lines = [
        "以下是当前会话沉淀出的长期记忆，包含自动阶段摘要与手动固定项。回答后续问题时请优先保持一致；如果用户明确提出变更，以最新指令为准。",
    ]
    count = 0

    for memory in ordered_memories:
        if not isinstance(memory, dict):
            continue
        content = _trim_session_memory_content(str(memory.get("content") or ""))
        if not content:
            continue
        count += 1
        meta = memory.get("meta") if isinstance(memory.get("meta"), dict) else {}
        lines.append(
            f"{count}. [{_session_memory_kind_label(str(memory.get('kind') or 'fact'), meta)}] {content}"
        )

    if count == 0:
        return None

    return SystemMessage(content="\n".join(lines))


def _preserve_system_messages_with_recent_history(
    chat_history: list[BaseMessage],
    max_recent: int = 8,
) -> list[BaseMessage]:
    if max_recent <= 0:
        return [message for message in chat_history if isinstance(message, SystemMessage)]

    non_system_messages = [
        message for message in chat_history if not isinstance(message, SystemMessage)
    ]
    keep_ids = {id(message) for message in non_system_messages[-max_recent:]}
    return [
        message
        for message in chat_history
        if isinstance(message, SystemMessage) or id(message) in keep_ids
    ]


def _normalized_intent_text(user_input: Any) -> str:
    return re.sub(r"\s+", "", _stringify_user_input(user_input or "")).lower()


def _heuristic_langgraph_tool_choice(
    user_input: Any,
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> str:
    text = _normalized_intent_text(user_input)
    if not text:
        return ""

    if knowledge_base_enabled:
        if "知识库" in text and any(
            keyword in text for keyword in ("重载", "重新加载", "刷新", "重新索引")
        ):
            return "5"

        if "知识库" in text and any(
            keyword in text
            for keyword in ("状态", "统计", "多少", "几份", "几个", "路径", "健康", "监控")
        ):
            return "4"

        if "知识库" in text:
            return "1"

        file_scope_markers = ("上传", "附件", "文档", "材料", "资料", "简历", "履历", "库里")
        kb_actions = ("读取", "读到", "检索", "搜索", "总结", "复述", "概括", "提取", "分析", "重写", "润色", "改写")
        if any(marker in text for marker in file_scope_markers) and any(
            action in text for action in kb_actions
        ):
            return "1"

        if _looks_like_resume_request(user_input) and any(
            marker in text for marker in ("我的", "之前", "上传", "已有", "资料", "经历", "项目")
        ):
            return "1"

    if web_search_enabled and any(keyword in text for keyword in ("最新", "今天", "新闻", "联网", "网上")):
        return "2"

    return ""


def _looks_like_reasoning_only_output(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return True
    return lowered.startswith("<think>") or lowered.startswith("thinking process:")


def _looks_like_resume_request(user_input: Any) -> bool:
    text = _stringify_user_input(user_input)
    return any(keyword in text for keyword in ("简历", "履历", "CV", "求职"))


def _build_resume_timeout_fallback(tool_result: str, sources: list[dict[str, Any]]) -> str:
    sections = [section.strip() for section in tool_result.split("\n\n---\n\n") if section.strip()]
    experience_items: list[str] = []
    project_items: list[str] = []

    for section in sections[:2]:
        body = re.sub(r"^【文档\s*\d+:\s*.*?】\s*", "", section)
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue

        for match in re.finditer(
            r"(\d{4}\.\d{2}-\d{4}\.\d{2})\s+([^|]+?)\s*\|\s*([^0-9]+?)(.*?)(?=(\d{4}\.\d{2}-\d{4}\.\d{2})|项目介绍|$)",
            body,
        ):
            period = match.group(1).strip()
            company = match.group(2).strip()
            role = match.group(3).strip()
            desc = match.group(4).strip(" ；;。")
            bullets = [frag.strip(" ；;。") for frag in re.split(r"[；;。]", desc) if frag.strip()]
            top_bullets = bullets[:3]
            if top_bullets:
                formatted = "\n".join(f"  - {item}" for item in top_bullets)
                experience_items.append(f"- {period} | {company} | {role}\n{formatted}")

        project_match = re.search(
            r"项目介绍\s*(.*?)\s*项目职责[:：]\s*(.*?)\s*项目结果[:：]\s*(.*)",
            body,
        )
        if project_match:
            project_name = project_match.group(1).strip() or "项目经历"
            duties = [frag.strip(" ；;。") for frag in re.split(r"[；;。]", project_match.group(2)) if frag.strip()]
            outcomes = [frag.strip(" ；;。") for frag in re.split(r"[；;。]", project_match.group(3)) if frag.strip()]
            project_lines = []
            if duties:
                project_lines.append(f"  - 项目职责：{duties[0]}")
            if outcomes:
                project_lines.append(f"  - 项目结果：{outcomes[0]}")
            if project_lines:
                project_items.append(f"- {project_name}\n" + "\n".join(project_lines))

    source_lines = []
    for src in sources[:2]:
        title = src.get("title", "未知来源")
        snippet = str(src.get("snippet", "")).strip()
        if snippet:
            source_lines.append(f"- {title}: {snippet[:120]}")

    parts = [
        "知识库检索已完成，但模型在整理时响应超时。下面先给你一版可直接继续编辑的简历草稿：",
        "",
        "**工作经历优化版**",
    ]
    parts.extend(experience_items or ["- 未从知识库中稳定提取到完整工作经历，请检查原始简历文档结构。"])
    parts.append("")
    parts.append("**项目经历优化版**")
    parts.extend(project_items or ["- 未从知识库中稳定提取到完整项目经历，请检查原始项目描述内容。"])
    if source_lines:
        parts.append("")
        parts.append("**本次引用的知识库片段**")
        parts.extend(source_lines)
    parts.append("")
    parts.append("可以继续发送“把这版改成产品经理/测试工程师/运营岗位简历”，我会基于这份草稿继续细化。")
    return "\n".join(parts)


def _build_generic_timeout_fallback(tool_result: str, sources: list[dict[str, Any]]) -> str:
    sections = [section.strip() for section in tool_result.split("\n\n---\n\n") if section.strip()]
    snippets = []
    for section in sections[:2]:
        body = re.sub(r"^【文档\s*\d+:\s*.*?】\s*", "", section)
        # 去掉 Markdown 标题符号（## ### 等）
        body = re.sub(r"#+\s+", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            snippets.append(f"- {body[:220]}")
    if not snippets:
        for src in sources[:2]:
            snippet = str(src.get("snippet", "")).strip()
            snippet = re.sub(r"#+\s+", "", snippet)
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if snippet:
                snippets.append(f"- {snippet[:220]}")

    parts = [
        "知识库检索已完成，但模型在整理结果时响应超时。下面先返回最相关的知识库摘要：",
        "",
    ]
    parts.extend(snippets or ["- 当前没有拿到足够稳定的摘要内容。"])
    parts.append("")
    parts.append("如果你愿意，可以继续发一条更具体的问题，我会基于这些片段继续缩小范围处理。")
    return "\n".join(parts)


def _build_kb_timeout_fallback(
    user_input: Any,
    tool_result: str,
    sources: list[dict[str, Any]],
) -> str:
    if _looks_like_resume_request(user_input):
        return _build_resume_timeout_fallback(tool_result, sources)
    return _build_generic_timeout_fallback(tool_result, sources)


def _extract_json_payload(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("json payload not found")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("json payload is not an object")
    return payload


def _normalize_dashboard_template(raw_template: Any) -> dict[str, Any]:
    template = dict(DEFAULT_DASHBOARD_TEMPLATE)
    if isinstance(raw_template, str) and raw_template.strip():
        try:
            raw_template = json.loads(raw_template)
        except json.JSONDecodeError:
            raw_template = {}
    if not isinstance(raw_template, dict):
        raw_template = {}

    template["enabled"] = raw_template.get("enabled") is not False

    title_hint = str(raw_template.get("title_hint", "")).strip()
    if title_hint:
        template["title_hint"] = title_hint

    focus_metrics = raw_template.get("focus_metrics", [])
    if isinstance(focus_metrics, list):
        template["focus_metrics"] = [str(item).strip() for item in focus_metrics if str(item).strip()]

    preferred_charts = raw_template.get("preferred_charts", [])
    if isinstance(preferred_charts, list):
        valid = [str(item).strip() for item in preferred_charts if str(item).strip() in {"bar", "line", "pie"}]
        if valid:
            template["preferred_charts"] = valid

    section_order = raw_template.get("section_order", [])
    if isinstance(section_order, list):
        valid_sections = [
            str(item).strip()
            for item in section_order
            if str(item).strip() in {"summary", "metrics", "charts", "table", "evidence", "warnings"}
        ]
        if valid_sections:
            template["section_order"] = valid_sections

    audience_tone = str(raw_template.get("audience_tone", "")).strip()
    if audience_tone:
        template["audience_tone"] = audience_tone

    return template


def _should_generate_dashboard(user_input: Any) -> bool:
    text = _stringify_user_input(user_input).lower()
    if any(keyword in text for keyword in DASHBOARD_TRIGGER_KEYWORDS):
        return True
    chart_pattern = re.compile(r"(柱状图|柱形图|条形图|折线图|饼图|趋势图|统计图|dashboard)")
    return bool(chart_pattern.search(text))


def _dedupe_documents(documents: list[Document], limit: int = 8) -> list[Document]:
    unique: list[Document] = []
    seen: set[str] = set()
    for doc in documents:
        source = str(doc.metadata.get("source", ""))
        signature = f"{source}|{doc.page_content[:180].strip()}"
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(doc)
        if len(unique) >= limit:
            break
    return unique


def _merge_same_source_chunks(documents: list[Document], max_chars_per_source: int = 3000) -> list[Document]:
    """
    将来自同一源文件的多个 chunk 合并为一个完整上下文块。
    对简历类文档特别有效：避免检索时只拿到半截工作经历。
    每个源文件合并后的内容上限为 max_chars_per_source 字符。
    """
    from collections import OrderedDict
    # 按 source 聚合，保持首次出现顺序
    source_groups: OrderedDict[str, list[str]] = OrderedDict()
    source_meta: dict[str, dict] = {}

    for doc in documents:
        source = str(doc.metadata.get("source", "未知来源"))
        if source not in source_groups:
            source_groups[source] = []
            source_meta[source] = doc.metadata
        content = doc.page_content.strip()
        if content:
            source_groups[source].append(content)

    merged: list[Document] = []
    for source, parts in source_groups.items():
        # 去重相邻重复片段
        deduped: list[str] = []
        for part in parts:
            if not deduped or part[:60] != deduped[-1][:60]:
                deduped.append(part)

        combined = "\n\n".join(deduped)
        if len(combined) > max_chars_per_source:
            combined = combined[:max_chars_per_source].rstrip() + "\n...[内容已截断，仅展示前段]"

        merged.append(
            Document(
                page_content=combined,
                metadata={**source_meta[source], "merged_chunks": len(deduped)},
            )
        )

    return merged


def _build_dashboard_sources(docs: list[Document]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for index, doc in enumerate(docs, start=1):
        snippet = re.sub(r"\s+", " ", doc.page_content).strip()[:240]
        title = str(doc.metadata.get("source", f"文档 {index}")).strip() or f"文档 {index}"
        evidence_id = f"e{index}"
        evidence.append(
            {
                "id": evidence_id,
                "title": title,
                "snippet": snippet,
                "source_type": "doc",
            }
        )
        sources.append(
            {
                "type": "doc",
                "title": title,
                "snippet": snippet,
                "index": index,
            }
        )
    return evidence, sources


def _sanitize_dashboard_payload(
    payload: dict[str, Any],
    allowed_evidence: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    evidence_list = allowed_evidence if allowed_evidence is not None else payload.get("evidence", [])
    evidence_ids = {
        str(item.get("id")).strip()
        for item in evidence_list
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }

    sanitized_evidence = []
    for item in evidence_list:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id", "")).strip()
        if not evidence_id:
            continue
        sanitized_evidence.append(
            {
                "id": evidence_id,
                "title": str(item.get("title", "未知来源")).strip() or "未知来源",
                "snippet": str(item.get("snippet", "")).strip(),
                "source_type": str(item.get("source_type", "doc")).strip() or "doc",
            }
        )

    metrics = []
    for metric in payload.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        refs = [
            ref for ref in [str(item).strip() for item in metric.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        if not refs:
            continue
        metrics.append(
            {
                "label": str(metric.get("label", "")).strip() or "指标",
                "value": metric.get("value", ""),
                "unit": str(metric.get("unit", "")).strip(),
                "trend": str(metric.get("trend", "")).strip() or "flat",
                "delta": str(metric.get("delta", "")).strip(),
                "highlight": bool(metric.get("highlight", False)),
                "evidence_ids": refs,
            }
        )

    charts = []
    for chart in payload.get("charts", []):
        if not isinstance(chart, dict):
            continue
        refs = [
            ref for ref in [str(item).strip() for item in chart.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        chart_data = chart.get("chart_data")
        chart_type = str(chart.get("type", "")).strip()
        if chart_type not in {"bar", "line", "pie"}:
            continue
        if not refs or not isinstance(chart_data, dict):
            continue
        labels = [str(item) for item in chart_data.get("labels", [])]
        datasets = []
        for dataset in chart_data.get("datasets", []):
            if not isinstance(dataset, dict):
                continue
            data_values = dataset.get("data", [])
            if not isinstance(data_values, list):
                continue
            numeric_values = []
            valid = True
            for value in data_values:
                try:
                    numeric_values.append(float(value))
                except (TypeError, ValueError):
                    valid = False
                    break
            if not valid or len(numeric_values) != len(labels):
                continue
            datasets.append(
                {
                    "label": str(dataset.get("label", "")).strip() or "数据",
                    "data": numeric_values,
                }
            )
        if not labels or not datasets:
            continue
        charts.append(
            {
                "title": str(chart.get("title", "")).strip() or "图表",
                "type": chart_type,
                "description": str(chart.get("description", "")).strip(),
                "evidence_ids": refs,
                "chart_data": {
                    "type": chart_type,
                    "labels": labels,
                    "datasets": datasets,
                },
            }
        )

    table_payload = payload.get("table")
    table = None
    if isinstance(table_payload, dict):
        refs = [
            ref for ref in [str(item).strip() for item in table_payload.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        columns = [str(item).strip() for item in table_payload.get("columns", []) if str(item).strip()]
        rows = table_payload.get("rows", [])
        if refs and columns and isinstance(rows, list) and rows:
            safe_rows = []
            for row in rows:
                if isinstance(row, dict):
                    safe_rows.append({str(key): value for key, value in row.items() if str(key) in columns})
            if safe_rows:
                table = {
                    "title": str(table_payload.get("title", "")).strip() or "数据明细",
                    "columns": columns,
                    "rows": safe_rows,
                    "evidence_ids": refs,
                }

    warnings = [str(item).strip() for item in payload.get("warnings", []) if str(item).strip()]

    return {
        "title": str(payload.get("title", "")).strip() or "知识库仪表盘",
        "summary": str(payload.get("summary", "")).strip(),
        "metrics": metrics,
        "charts": charts,
        "table": table,
        "evidence": sanitized_evidence,
        "warnings": warnings,
    }


def _render_dashboard_card(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", "").strip()
    title = payload.get("title", "知识库仪表盘")
    intro = f"已根据当前角色绑定的知识库整理出可证据化的仪表盘：{title}"
    if summary:
        intro = f"{intro}\n\n{summary}"
    card_json = json.dumps(payload, ensure_ascii=False)
    return f"{intro}\n\n:::dashboard-card\n{card_json}\n:::"


def _render_attachment_dashboard_card(payload: dict[str, Any]) -> str:
    summary = str(payload.get("summary", "")).strip()
    title = str(payload.get("title", "")).strip() or "数据仪表盘"
    intro = f"已根据您上传的附件整理出仪表盘：{title}"
    if summary:
        intro = f"{intro}\n\n{summary}"
    card_json = json.dumps(payload, ensure_ascii=False)
    return f"{intro}\n\n:::dashboard-card\n{card_json}\n:::"


def _extract_attachment_sections(user_input: Any) -> list[dict[str, Any]]:
    user_text = _stringify_user_input(user_input)
    pattern = (
        re.escape(CHAT_FILE_CONTEXT_START_MARKER)
        + r"(.*?)"
        + re.escape(CHAT_FILE_CONTEXT_END_MARKER)
    )
    blocks = re.findall(pattern, user_text, flags=re.DOTALL)
    if not blocks:
        return []

    sections: list[dict[str, Any]] = []
    attachment_counter = 0
    attachment_marker_re = re.compile(r"(?m)^\[附件\s*\d+\]\s*$")

    for block in blocks:
        matches = list(attachment_marker_re.finditer(block))
        if not matches:
            content = block.strip()
            if not content:
                continue
            attachment_counter += 1
            sections.append(
                {
                    "id": f"a{attachment_counter}",
                    "title": f"会话附件 {attachment_counter}",
                    "source": "会话附件",
                    "source_type": "attachment",
                    "snippet": content[:2000],
                    "content": content,
                }
            )
            continue

        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
            raw_section = block[start:end].strip()
            if not raw_section:
                continue

            lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
            if not lines:
                continue

            file_name = f"会话附件 {attachment_counter + 1}"
            content_lines: list[str] = []
            for line in lines[1:]:
                if ("文件名" in line or line.lower().startswith("file")) and ("：" in line or ":" in line):
                    _, _, remainder = line.replace("：", ":", 1).partition(":")
                    candidate = remainder.strip()
                    if candidate:
                        file_name = candidate
                    continue
                normalized_line = line.replace("：", ":")
                if normalized_line in {"内容:", "正文:", "content:"}:
                    continue
                content_lines.append(line)

            content = "\n".join(content_lines).strip()
            if not content:
                continue

            attachment_counter += 1
            sections.append(
                {
                    "id": f"a{attachment_counter}",
                    "title": file_name,
                    "source": "会话附件",
                    "source_type": "attachment",
                    "snippet": content[:2000],
                    "content": content,
                }
            )

    return sections


def _extract_attachment_evidence(user_input: Any) -> list[dict[str, Any]]:
    """
    从 user_input 的附件标记块中提取文本，构建成 evidence 格式。
    当用户上传了文件（Excel/CSV/PDF 等），附件内容会被注入到 prompt 中，
    被 CHAT_FILE_CONTEXT_START/END_MARKER 包裹。本函数将其提取并转换为
    与 _build_dashboard_sources() 输出一致的 evidence list，供仪表盘生成使用。
    """
    return [
        {
            "id": section["id"],
            "title": section["title"],
            "source": section["source"],
            "source_type": section["source_type"],
            "snippet": section["snippet"],
        }
        for section in _extract_attachment_sections(user_input)
    ]


def _parse_numeric_dashboard_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace(",", "")
    if normalized.endswith("%"):
        normalized = normalized[:-1].strip()

    if not re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return None

    return float(normalized)


def _coerce_dashboard_cell_value(value: str) -> Any:
    numeric_value = _parse_numeric_dashboard_value(value)
    if numeric_value is None:
        return value.strip()
    if numeric_value.is_integer():
        return int(numeric_value)
    return round(numeric_value, 6)


def _is_rate_like_metric(label: str) -> bool:
    lowered = (label or "").strip().lower()
    return any(
        token in lowered
        for token in ("率", "ratio", "ctr", "cvr", "roi", "转化", "占比")
    )


def _looks_like_date_dimension(label: str, sample_values: list[str]) -> bool:
    lowered = (label or "").strip().lower()
    if any(token in lowered for token in ("date", "日期", "时间", "月份", "month", "day", "周", "week")):
        return True
    return any(re.search(r"\d{4}[-/]\d{1,2}([-/]\d{1,2})?", value) for value in sample_values[:3])


def _parse_attachment_tables(text: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    current_table: dict[str, Any] | None = None

    def ensure_table(sheet_name: str | None) -> dict[str, Any]:
        nonlocal current_table
        normalized_name = (sheet_name or "").strip()
        if current_table is not None and current_table["sheet_name"] == normalized_name:
            return current_table
        current_table = {
            "sheet_name": normalized_name,
            "columns": [],
            "rows": [],
        }
        tables.append(current_table)
        return current_table

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        sheet_match = re.match(r"^[【\[]?\s*Sheet\s*[:：]\s*(.+?)\s*[】\]]?$", line, flags=re.IGNORECASE)
        if sheet_match:
            ensure_table(sheet_match.group(1).strip())
            continue

        row_match = re.match(r"^行\s*\d+\s*[:：]\s*(.+)$", line)
        row_text = row_match.group(1).strip() if row_match else ""
        if not row_text and "|" in line and ("：" in line or ":" in line):
            row_text = line
        if not row_text:
            continue

        row: dict[str, Any] = {}
        for cell in [item.strip() for item in row_text.split("|") if item.strip()]:
            if "：" in cell:
                key, value = cell.split("：", 1)
            elif ":" in cell:
                key, value = cell.split(":", 1)
            else:
                continue
            key = key.strip()
            value = value.strip()
            if not key or not value:
                continue
            row[key] = _coerce_dashboard_cell_value(value)

        if not row:
            continue

        table = current_table or ensure_table("")
        for column in row:
            if column not in table["columns"]:
                table["columns"].append(column)
        table["rows"].append(row)

    return [table for table in tables if table["rows"]]


def _build_attachment_dashboard_fallback(
    attachment_sections: list[dict[str, Any]],
    template: dict[str, Any],
) -> dict[str, Any] | None:
    parsed_candidates: list[dict[str, Any]] = []
    for section in attachment_sections:
        for table in _parse_attachment_tables(section.get("content", "")):
            parsed_candidates.append({"section": section, "table": table})

    if not parsed_candidates:
        return None

    def candidate_score(candidate: dict[str, Any]) -> tuple[int, int]:
        table = candidate["table"]
        rows = table.get("rows", [])
        numeric_columns = 0
        for column in table.get("columns", []):
            values = [
                _parse_numeric_dashboard_value(row.get(column))
                for row in rows
                if row.get(column) not in (None, "")
            ]
            if values and all(value is not None for value in values):
                numeric_columns += 1
        return (len(rows), numeric_columns)

    best_candidate = max(parsed_candidates, key=candidate_score)
    section = best_candidate["section"]
    table = best_candidate["table"]
    columns = list(table.get("columns", []))
    rows = list(table.get("rows", []))

    numeric_columns: list[tuple[str, list[float]]] = []
    dimension_candidates: list[tuple[str, list[str]]] = []
    for column in columns:
        raw_values = [row.get(column) for row in rows if row.get(column) not in (None, "")]
        if not raw_values:
            continue
        numeric_values = [_parse_numeric_dashboard_value(value) for value in raw_values]
        if all(value is not None for value in numeric_values):
            numeric_columns.append((column, [float(value) for value in numeric_values if value is not None]))
            continue
        dimension_candidates.append((column, [str(value) for value in raw_values]))

    if not numeric_columns and not rows:
        return None

    preferred_metric_tokens = (
        "销售额", "营收", "收入", "金额", "gmv",
        "订单", "销量", "访问", "流量", "用户", "客户", "转化", "率",
    )

    def metric_sort_key(item: tuple[str, list[float]]) -> tuple[int, int, str]:
        label = item[0]
        lowered = label.lower()
        preferred_rank = 0
        for index, token in enumerate(preferred_metric_tokens):
            if token in lowered:
                preferred_rank = len(preferred_metric_tokens) - index
                break
        return (preferred_rank, len(item[1]), label)

    numeric_columns.sort(key=metric_sort_key, reverse=True)

    preferred_dimension_tokens = (
        "日期", "时间", "月份", "date", "month",
        "区域", "地区", "城市", "省份",
        "产品", "品类", "类别", "渠道", "部门",
    )

    def dimension_sort_key(item: tuple[str, list[str]]) -> tuple[int, int, str]:
        label = item[0]
        lowered = label.lower()
        preferred_rank = 0
        for index, token in enumerate(preferred_dimension_tokens):
            if token in lowered:
                preferred_rank = len(preferred_dimension_tokens) - index
                break
        return (preferred_rank, len(item[1]), label)

    dimension_candidates.sort(key=dimension_sort_key, reverse=True)

    metrics: list[dict[str, Any]] = []
    for index, (label, values) in enumerate(numeric_columns[:3]):
        if not values:
            continue
        if _is_rate_like_metric(label):
            aggregate_value = sum(values) / len(values)
            if 0 <= aggregate_value <= 1:
                metric_value: str | int | float = round(aggregate_value * 100, 2)
            else:
                metric_value = round(aggregate_value, 2)
            unit = "%"
        else:
            aggregate_value = sum(values)
            metric_value = int(aggregate_value) if aggregate_value.is_integer() else round(aggregate_value, 2)
            unit = ""
        metrics.append(
            {
                "label": label,
                "value": metric_value,
                "unit": unit,
                "trend": "flat",
                "delta": "",
                "highlight": index == 0,
                "evidence_ids": [section["id"]],
            }
        )

    charts: list[dict[str, Any]] = []
    if numeric_columns:
        dimension_label = dimension_candidates[0][0] if dimension_candidates else ""
        metric_label = numeric_columns[0][0]
        chart_rows = []
        for row in rows:
            raw_metric = row.get(metric_label)
            metric_value = _parse_numeric_dashboard_value(raw_metric)
            if metric_value is None:
                continue
            if dimension_label:
                raw_dimension = row.get(dimension_label)
                if raw_dimension in (None, ""):
                    continue
                label_value = str(raw_dimension)
            else:
                label_value = f"第{len(chart_rows) + 1}行"
            chart_rows.append((label_value, float(metric_value)))
            if len(chart_rows) >= 8:
                break

        if len(chart_rows) >= 2:
            preferred_charts = template.get("preferred_charts", [])
            chart_type = "line" if dimension_label and _looks_like_date_dimension(
                dimension_label,
                [label for label, _ in chart_rows],
            ) else "bar"
            if chart_type not in {"bar", "line", "pie"}:
                chart_type = "bar"
            if preferred_charts and chart_type not in preferred_charts:
                preferred_chart = preferred_charts[0]
                if preferred_chart in {"bar", "line", "pie"}:
                    chart_type = preferred_chart

            charts.append(
                {
                    "title": f"{metric_label}趋势" if chart_type == "line" else f"{metric_label}对比",
                    "type": chart_type,
                    "description": (
                        f"按{dimension_label}展示{metric_label}"
                        if dimension_label
                        else f"展示{metric_label}的前 {len(chart_rows)} 条记录"
                    ),
                    "evidence_ids": [section["id"]],
                    "chart_data": {
                        "type": chart_type,
                        "labels": [label for label, _ in chart_rows],
                        "datasets": [
                            {
                                "label": metric_label,
                                "data": [value for _, value in chart_rows],
                            }
                        ],
                    },
                }
            )

    table_rows = [
        {column: row.get(column, "") for column in columns}
        for row in rows[:12]
    ]
    evidence = [
        {
            "id": item["id"],
            "title": item["title"],
            "snippet": item["snippet"],
            "source_type": item.get("source_type", "attachment"),
        }
        for item in attachment_sections
    ]

    title_hint = str(template.get("title_hint", "")).strip()
    sheet_name = str(table.get("sheet_name", "")).strip()
    attachment_title = str(section.get("title", "会话附件")).strip() or "会话附件"
    card_title = title_hint or (f"{sheet_name}数据看板" if sheet_name else f"{attachment_title}数据看板")

    summary_parts = [f"已从 {attachment_title} 中识别出 {len(rows)} 条记录"]
    if sheet_name:
        summary_parts.append(f"当前展示工作表“{sheet_name}”")
    if metrics:
        summary_parts.append(f"提炼出 {len(metrics)} 个核心指标")
    elif numeric_columns:
        summary_parts.append("已提取数值列，可继续细化成更明确的业务指标")
    else:
        summary_parts.append("当前以明细表形式展示，适合继续指定维度和指标")

    warnings: list[str] = []
    if len(rows) > len(table_rows):
        warnings.append(f"为便于展示，仅展示前 {len(table_rows)} 条明细记录。")
    if len(parsed_candidates) > 1:
        warnings.append("检测到多个附件或工作表，当前优先展示记录数最多的一组数据。")
    if not charts:
        warnings.append("已保留数据明细，但当前自动图表维度不够稳定，建议进一步指定维度和指标。")

    return {
        "title": card_title,
        "summary": "；".join(summary_parts) + "。",
        "metrics": metrics,
        "charts": charts,
        "table": {
            "title": sheet_name or "数据明细",
            "columns": columns,
            "rows": table_rows,
            "evidence_ids": [section["id"]],
        } if columns and table_rows else None,
        "evidence": evidence,
        "warnings": warnings,
    }


async def _generate_dashboard_from_attachment(
    llm,
    user_input: Any,
    attachment_evidence: list[dict[str, Any]],
    system_prompt: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    基于会话附件内容生成仪表盘（无需知识库）。
    复用与知识库路径相同的 LLM 调用、JSON 解析、payload 净化和卡片渲染逻辑。
    """
    template = _normalize_dashboard_template(dashboard_template)
    attachment_sections = _extract_attachment_sections(user_input)
    user_text = _stringify_user_input(user_input).strip()
    evidence_json = json.dumps(attachment_evidence, ensure_ascii=False, indent=2)
    template_json = json.dumps(template, ensure_ascii=False, indent=2)
    role_desc = system_prompt or "你是一个数据分析助手"

    # 构建 sources（附件来源引用）
    sources: list[dict[str, Any]] = [
        {
            "type": "attachment",
            "title": ev.get("title", ev.get("source", "会话附件")),
            "snippet": (ev.get("snippet") or "")[:200],
        }
        for ev in attachment_evidence
    ]

    dashboard_prompt = f"""{role_desc}

你正在为用户生成一个"基于用户上传附件"的数据仪表盘。你必须严格遵守下面规则：
1. 只能使用给定 evidence 中已经出现的信息，不得补充外部知识，不得臆造数字。
2. 只有有 evidence_ids 支撑的指标、图表、表格才允许输出。
3. 所有图表类型只能是 bar、line、pie。
4. 如果证据不足以形成可靠图表，可以减少图表数量，但仍需说明原因。
5. 只输出 JSON 对象，不要输出 Markdown，不要解释。

当前仪表盘模板:
{template_json}

用户请求:
{user_text}

可用证据（来自用户上传的附件）:
{evidence_json}

请输出 JSON，格式必须为：
{{
  "title": "仪表盘标题",
  "summary": "1-2 句摘要",
  "metrics": [
    {{
      "label": "指标名",
      "value": 123,
      "unit": "个",
      "trend": "up",
      "delta": "+12%",
      "highlight": true,
      "evidence_ids": ["a1"]
    }}
  ],
  "charts": [
    {{
      "title": "图表标题",
      "type": "bar",
      "description": "一句图表说明",
      "evidence_ids": ["a1"],
      "chart_data": {{
        "type": "bar",
        "labels": ["A", "B"],
        "datasets": [
          {{
            "label": "系列1",
            "data": [1, 2]
          }}
        ]
      }}
    }}
  ],
  "table": {{
    "title": "数据明细",
    "columns": ["列1", "列2"],
    "rows": [
      {{"列1": "A", "列2": 1}}
    ],
    "evidence_ids": ["a1"]
  }},
  "evidence": {evidence_json},
  "warnings": ["如果证据不足或口径有限，在这里说明"]
}}
"""
    try:
        response = await _ainvoke_llm_with_timeout(llm, dashboard_prompt)
        payload = _extract_json_payload(_stringify_user_input(response.content))
        sanitized = _sanitize_dashboard_payload(payload, allowed_evidence=attachment_evidence)
        sanitized["evidence"] = attachment_evidence
        if not sanitized["evidence"]:
            return {
                "output": "已读取附件内容，但模型未能整理出可核验的仪表盘证据，建议检查附件是否包含数值数据。",
                "sources": sources,
            }
        if not sanitized["metrics"] and not sanitized["charts"] and not sanitized["table"]:
            return {
                "output": "已读取附件内容，但证据主要是描述性文本，暂时不足以生成可靠图表。建议上传包含数值或分类统计的文件。",
                "sources": sources,
            }
        return {
            "output": _render_attachment_dashboard_card(sanitized),
            "sources": sources,
        }
    except Exception as exc:
        fallback_payload = _build_attachment_dashboard_fallback(attachment_sections, template)
        if fallback_payload:
            logger.warning(
                "Attachment dashboard generation fell back to deterministic table rendering: %s",
                exc,
            )
            return {
                "output": _render_attachment_dashboard_card(fallback_payload),
                "sources": sources,
            }
        logger.exception("Attachment dashboard generation failed")
        return {
            "output": "系统已尝试根据附件生成仪表盘，但结构化整理过程失败。请稍后重试，或换一种更明确的指标需求描述。",
            "sources": sources,
        }


async def _generate_dashboard_from_knowledge(
    llm,
    pipeline: DocPipeline,
    user_input: Any,
    system_prompt: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
    knowledge_base_enabled: bool = True,
) -> Optional[dict[str, Any]]:
    template = _normalize_dashboard_template(dashboard_template)
    if not template.get("enabled", True):
        return None

    if not _should_generate_dashboard(user_input):
        return None

    # ── 附件优先路径 ──────────────────────────────────────────────────────────
    # 只要 prompt 中含有附件内容块，就直接用附件作为证据生成仪表盘，
    # 完全无需知识库。这样用户上传 Excel/CSV/PDF 后即可直接可视化，
    # 无论知识库是否开启或就绪。
    attachment_evidence = _extract_attachment_evidence(user_input)
    if attachment_evidence:
        return await _generate_dashboard_from_attachment(
            llm, user_input, attachment_evidence,
            system_prompt=system_prompt,
            dashboard_template=dashboard_template,
        )
    # ── 附件路径结束 ──────────────────────────────────────────────────────────

    if not knowledge_base_enabled:
        return {
            "output": "当前未开启知识库引用，暂时不能根据知识库生成仪表盘。请先打开知识库开关后再试，或上传包含数据的文件（如 Excel、CSV）。",
            "sources": [],
        }
    if not pipeline.vector_store_path:
        return {
            "output": "当前角色未绑定专属知识库，暂时无法生成基于知识库证据的仪表盘。请先为角色挂载知识库后再试。",
            "sources": [],
        }
    if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
        pipeline.load_store()
    if pipeline.vectorstore is None:
        return {
            "output": "当前角色绑定的知识库尚未就绪，暂时无法生成仪表盘。请先检查知识库索引是否已正确加载。",
            "sources": [],
        }

    user_text = _stringify_user_input(user_input).strip()
    if not user_text:
        return None

    query_candidates = [user_text]
    query_candidates.extend(template.get("focus_metrics", [])[:4])

    gathered_docs: list[Document] = []
    for query in query_candidates:
        query = str(query).strip()
        if not query:
            continue
        try:
            gathered_docs.extend(pipeline.search_with_rerank(query, k=4, fetch_k=12))
        except Exception:
            logger.exception("Dashboard retrieval failed for query=%s", query)

    docs = _dedupe_documents(gathered_docs, limit=8)
    if len(docs) < 2:
        return {
            "output": "已检索当前角色绑定的知识库，但缺少足够的可量化证据，暂时无法生成可靠仪表盘。你可以补充包含数字、分类统计或对比口径的资料后再试。",
            "sources": [],
        }

    evidence, sources = _build_dashboard_sources(docs)
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)
    template_json = json.dumps(template, ensure_ascii=False, indent=2)
    role_desc = system_prompt or "你是一个企业知识库助手"

    dashboard_prompt = f"""{role_desc}

你正在为用户生成一个“只基于知识库证据”的数据仪表盘。你必须严格遵守下面规则：
1. 只能使用给定 evidence 中已经出现的信息，不得补充外部知识，不得臆造数字。
2. 只有有 evidence_ids 支撑的指标、图表、表格才允许输出。
3. 所有图表类型只能是 bar、line、pie。
4. 如果证据不足以形成可靠图表，可以减少图表数量，但仍需说明原因。
5. 只输出 JSON 对象，不要输出 Markdown，不要解释。

当前仪表盘模板:
{template_json}

用户请求:
{user_text}

可用证据:
{evidence_json}

请输出 JSON，格式必须为：
{{
  "title": "仪表盘标题",
  "summary": "1-2 句摘要",
  "metrics": [
    {{
      "label": "指标名",
      "value": 123,
      "unit": "个",
      "trend": "up",
      "delta": "+12%",
      "highlight": true,
      "evidence_ids": ["e1"]
    }}
  ],
  "charts": [
    {{
      "title": "图表标题",
      "type": "bar",
      "description": "一句图表说明",
      "evidence_ids": ["e1", "e2"],
      "chart_data": {{
        "type": "bar",
        "labels": ["A", "B"],
        "datasets": [
          {{
            "label": "系列1",
            "data": [1, 2]
          }}
        ]
      }}
    }}
  ],
  "table": {{
    "title": "数据明细",
    "columns": ["列1", "列2"],
    "rows": [
      {{"列1": "A", "列2": 1}}
    ],
    "evidence_ids": ["e1"]
  }},
  "evidence": {evidence_json},
  "warnings": ["如果证据不足或口径有限，在这里说明"]
}}
"""

    try:
        response = await _ainvoke_llm_with_timeout(llm, dashboard_prompt)
        payload = _extract_json_payload(_stringify_user_input(response.content))
        sanitized = _sanitize_dashboard_payload(payload, allowed_evidence=evidence)
        sanitized["evidence"] = evidence
        if not sanitized["evidence"]:
            return {
                "output": "知识库检索到了相关内容，但模型未能整理出可核验的仪表盘证据，暂时只适合继续用文字方式分析。",
                "sources": sources,
            }
        if not sanitized["metrics"] and not sanitized["charts"]:
            return {
                "output": "已检索当前角色绑定的知识库，但证据主要是描述性文本，暂时不足以生成可靠图表。建议补充带数值或分类统计的数据后再试。",
                "sources": sources,
            }
        return {
            "output": _render_dashboard_card(sanitized),
            "sources": sources,
        }
    except Exception:
        logger.exception("Dashboard generation failed")
        return {
            "output": "系统已尝试根据知识库生成仪表盘，但结构化整理过程失败。请稍后重试，或换一种更明确的指标需求描述。",
            "sources": sources if 'sources' in locals() else [],
        }


async def _direct_multimodal_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    system_prompt: Optional[str] = None,
) -> str:
    messages: list[BaseMessage] = [
        SystemMessage(
            content=system_prompt
            or "你是一个企业知识库助手。当前用户上传了图片，请直接基于图片和问题作答。不要调用任何工具，始终用中文回答。"
        )
    ]
    messages.extend(_preserve_system_messages_with_recent_history(chat_history, max_recent=8))
    messages.append(HumanMessage(content=user_input))
    response = await _ainvoke_llm_with_timeout(llm, messages)
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return _stringify_user_input(content)


def _should_bypass_tools_for_plain_text_chat(
    user_input: Any,
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> bool:
    """纯文本创作/问答场景直接走聊天链路，避免云端模型被 Agent/工具额外拖慢。"""
    if _has_image_input(user_input):
        return False
    if _should_generate_dashboard(user_input):
        return False

    text = _stringify_user_input(user_input).strip()
    if not text:
        return False

    heuristic_choice = _heuristic_langgraph_tool_choice(
        user_input,
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
    )
    return not heuristic_choice


def _plain_text_chat_timeout_seconds(
    user_input: Any,
    chat_history: list[BaseMessage],
) -> float:
    """长文本纯聊天适当放宽超时，降低小说/续写类请求被过早截断的概率。"""
    total_chars = len(_stringify_user_input(user_input))
    recent_history = _preserve_system_messages_with_recent_history(chat_history, max_recent=6)
    for message in recent_history:
        content = getattr(message, "content", "")
        total_chars += len(_stringify_user_input(content))

    if total_chars >= 9000:
        return 180.0
    if total_chars >= 5000:
        return 140.0
    if total_chars >= 2500:
        return 110.0
    return 90.0


async def _direct_plain_text_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
) -> str:
    messages: list[BaseMessage] = [
        SystemMessage(
            content=system_prompt
            or "你是一个中文写作与问答助手。当前请求不需要调用任何工具，请直接基于上下文回答用户问题。始终用中文回答。"
        )
    ]
    messages.extend(_preserve_system_messages_with_recent_history(chat_history, max_recent=8))
    messages.append(HumanMessage(content=user_input))
    response = await _ainvoke_llm_with_timeout(
        llm,
        messages,
        timeout_seconds=_plain_text_chat_timeout_seconds(user_input, chat_history),
    )
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return _stringify_user_input(content)




def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
):
    """
    模型工厂函数 - 根据兼容连接配置返回对应的 LLM 实例

    Args:
        provider: 连接类型或其别名（如 `ollama` / `openai_compatible`，也兼容旧的 `local` / `cloud`）
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key（兼容 OpenAI 接口时可为空，空时会自动注入占位 key）
        temperature: 温度参数

    Returns:
        LangChain ChatModel 实例
    """
    connection_type = normalize_connection_type(provider, base_url)

    if connection_type == "openai_compatible":
        # OpenAI-compatible 兼容接口
        from langchain_openai import ChatOpenAI

        base_url = base_url or default_base_url_for_connection_type(connection_type)
        model = model_name or default_model_for_connection_type(connection_type)
        # 默认给云端接口更宽裕的网络超时，避免上层 40s/60s 预算未到就先被底层 HTTP 截断。
        request_timeout = float(os.getenv("CLOUD_LLM_TIMEOUT_SECONDS", "70"))
        resolved_api_key = (
            api_key
            or os.getenv("OPENAI_COMPAT_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or "sk-no-key-required"
        )

        logger.info("使用 OpenAI-compatible 模型: %s (地址: %s)", model, base_url)
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            timeout=request_timeout,
            max_retries=0,
            api_key=resolved_api_key,
            base_url=base_url,
        )

    if connection_type == "ollama":
        # Ollama 本地模型
        from langchain_ollama import ChatOllama

        model = model_name or default_model_for_connection_type(connection_type)
        base_url = base_url or default_base_url_for_connection_type(connection_type)

        if not re.match(r'^[a-zA-Z0-9._:/-]+$', model):
            raise ValueError(
                f"Invalid Ollama model name: '{model}'. "
                "Model names cannot contain spaces or special characters. "
                "Valid format: name:tag (e.g., qwen3:4b, llama2:7b)"
            )

        logger.info("使用本地模型: %s (地址: %s)", model, base_url)
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
            num_predict=2048,
            top_p=0.9,  # 限制采样范围
        )

    raise ValueError(f"不支持的连接类型: {provider}")


def create_tools(
    pipeline: DocPipeline,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
):
    """
    创建所有工具函数
    
    Args:
        pipeline: DocPipeline 实例
    
    Returns:
        工具函数列表
    """
    @tool
    async def query_knowledge(question: str, top_k: int = DEFAULT_KB_TOP_K) -> str:
        """
        从企业内部知识库中检索相关文档片段 (使用 Rerank 二段重排)

        Args:
            question: 用户问题
            top_k: 返回的文档片段数量，默认取 `DEFAULT_KB_TOP_K`

        Returns:
            格式化的文档片段,包含来源信息
        """
        try:
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
            if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
                pipeline.load_store()
            
            if pipeline.vectorstore is None:
                return "⚠️ 知识库未初始化,请先上传文档"

            docs = pipeline.search_with_rerank(
                question,
                k=top_k,
                fetch_k=DEFAULT_KB_FETCH_K,
            )
            docs = _dedupe_documents(docs, limit=top_k)

            if not docs:
                return "未找到相关文档"

            # 当检索结果来自同一源文件（如简历），合并 chunk 避免信息割裂
            unique_sources = {doc.metadata.get("source", "") for doc in docs}
            if len(unique_sources) < len(docs):
                # 存在来自同一文件的多个 chunk，执行合并
                docs = _merge_same_source_chunks(docs, max_chars_per_source=3600)
                logger.info(
                    "[query_knowledge] 合并同源 chunk → %d 个来源块", len(docs)
                )

            results = []
            sources_meta = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source", "未知来源")
                # 合并后内容较长，适当提高单片段字符上限
                max_chars = 2400 if doc.metadata.get("merged_chunks", 1) > 1 else DEFAULT_KB_DOC_CHAR_LIMIT
                content = _trim_knowledge_doc_content(doc.page_content, max_chars=max_chars)
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
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
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
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
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
        if not web_search_enabled:
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
        if not web_search_enabled:
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

        if not web_search_enabled:
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

    declared_tools = {
        "query_knowledge": query_knowledge,
        "reload_knowledge_base": reload_knowledge_base,
        "get_knowledge_stats": get_knowledge_stats,
        "web_search": web_search,
        "quick_answer": quick_answer,
        "fetch_webpage": fetch_webpage,
    }
    return [
        declared_tools[spec.name]
        for spec in list_enabled_builtin_tool_specs(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
        )
        if spec.name in declared_tools
    ]


async def build_runtime_tools(
    pipeline: DocPipeline,
    *,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    mcp_tool_loader: Callable[..., Any] = load_mcp_tool_overrides,
):
    builtin_tools = create_tools(
        pipeline,
        web_search_enabled=web_search_enabled,
        knowledge_base_enabled=knowledge_base_enabled,
    )
    tools_by_name = {tool.name: tool for tool in builtin_tools}
    expected_tool_names = set(tools_by_name)

    mcp_tools = await mcp_tool_loader(
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
        expected_tool_names=expected_tool_names,
    )

    overridden_names: list[str] = []
    for name, tool in mcp_tools.items():
        if name not in tools_by_name:
            continue
        tools_by_name[name] = tool
        overridden_names.append(name)

    if overridden_names:
        logger.info(
            "Using MCP-backed tool overrides: %s",
            ", ".join(sorted(overridden_names)),
        )

    return [
        tools_by_name[spec.name]
        for spec in list_enabled_builtin_tool_specs(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
        )
        if spec.name in tools_by_name
    ]


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
        response = await _ainvoke_llm_with_timeout(llm, rewrite_prompt, timeout_seconds=20)
        rewritten = response.content.strip()
        logger.info("[QueryRewrite] original=%s -> rewritten=%s", user_input[:50], rewritten[:50])
        return rewritten if rewritten else user_input
    except Exception:
        logger.exception("[QueryRewrite] 查询重写失败")
        return user_input


class AgentState(TypedDict):
    """LangGraph Agent 状态"""
    input: Any
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

    def _graph_configurable_value(config: Any, key: str, default: Any) -> Any:
        if not config:
            return default
        try:
            configurable = config.get("configurable", {})
        except Exception:
            configurable = {}
        if not isinstance(configurable, dict):
            return default
        return configurable.get(key, default)

    def _emit_workflow_state(
        config: Any,
        node_name: str,
        status: Literal["running", "completed", "failed"],
        *,
        duration_ms: Optional[int] = None,
        tool_name: str = "",
        tool_params: Optional[dict[str, Any]] = None,
        tool_result_summary: str = "",
        error: str = "",
    ) -> None:
        sink = _graph_configurable_value(config, "workflow_event_sink", None)
        if not callable(sink):
            return

        payload: dict[str, Any] = {
            "type": "workflow_state",
            "node_name": node_name,
            "status": status,
            "timestamp": int(time.time() * 1000),
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if tool_name:
            payload["tool_name"] = tool_name
        if tool_params:
            payload["tool_params"] = tool_params
        if tool_result_summary:
            payload["tool_result_summary"] = tool_result_summary
        if error:
            payload["error"] = error

        try:
            sink(payload)
        except Exception:
            logger.exception("[LangGraph] workflow event sink failed node=%s", node_name)
    
    async def classify_intent(state: AgentState, config: Any = None) -> AgentState:
        """节点1: 分类用户意图，选择工具"""
        started_at = time.monotonic()
        _emit_workflow_state(config, "classify_intent", "running")
        user_input = state["input"]
        chat_history = state.get("chat_history", [])
        state.setdefault("sources", [])

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
    
    async def execute_tool(state: AgentState, config: Any = None) -> AgentState:
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
            _emit_workflow_state(
                config,
                "execute_tool",
                "completed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                tool_name=tool_func.name,
                tool_params=params,
                tool_result_summary=_compact_tool_result_for_prompt(result, max_chars=220),
            )
            
        except Exception as e:
            logger.exception("[LangGraph] tool_name=%s 执行失败", tool_func.name)
            state["tool_result"] = f"❌ 工具执行失败: {str(e)}"
            state["sources"] = []
            _emit_workflow_state(
                config,
                "execute_tool",
                "failed",
                duration_ms=int((time.monotonic() - started_at) * 1000),
                tool_name=tool_func.name,
                error=str(e),
            )
        
        return state
    
    async def generate_answer(state: AgentState, config: Any = None) -> AgentState:
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

请基于以上信息，用自然、友好的语言回答用户问题。如有引用来源请在对应句子末尾添加 [^数字] 标注："""
        else:
            answer_prompt = f"""{role_desc}。直接回答用户问题。{intent_instructions}
{history_text}
用户: {user_input}

请用自然、友好的语言回答："""
        
        try:
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

            # 带知识库时再用更短的片段重试一次，兼容部分云端中转对长 prompt 不稳定的问题。
            if tool_result:
                retry_tool_result = _compact_tool_result_for_prompt(tool_result, max_chars=900)
                retry_prompt = f"""{role_desc}。根据检索摘要回答用户问题。{citation_hint}
{history_text}
用户问题: {user_input}

检索摘要:
{retry_tool_result}

请只保留最关键的信息，用自然、友好的语言简洁回答用户问题。如有引用来源请在对应句子末尾添加 [^数字] 标注："""
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
    
    if agent_mode == "auto":
        if provider == "openai_compatible":
            actual_mode = "function_calling"
        else:
            actual_mode = "langgraph"
        logger.info(
            "[Auto] provider=%s -> agent_mode=%s (openai_compatible=function_calling, ollama=langgraph)",
            provider,
            actual_mode,
        )
    else:
        actual_mode = agent_mode
    
    llm = get_llm(provider, model_name, base_url, api_key, temperature)

    def _configurable_value(config: Optional[dict], key: str, default: Any) -> Any:
        if not config:
            return default
        configurable = config.get("configurable", {})
        if not isinstance(configurable, dict):
            return default
        return configurable.get(key, default)

    def _configurable_list(config: Optional[dict], key: str) -> list[dict[str, Any]]:
        value = _configurable_value(config, key, [])
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _attach_configured_task_meta(
        result: dict[str, Any],
        config: Optional[dict],
    ) -> dict[str, Any]:
        task_id = str(_configurable_value(config, "task_id", "") or "")
        task_type = str(_configurable_value(config, "task_type", "") or "")
        if task_id:
            result["task_id"] = task_id
        if task_type:
            result["task_type"] = task_type
        return result

    def _load_chat_history(
        session_id: str,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
    ) -> list[BaseMessage]:
        history = SQLiteChatMessageHistory(session_id=session_id)
        session_memory = list_session_memory(
            session_id,
            limit=10,
            db_path=history.db_path,
        )
        memory_message = _build_session_memory_message(session_memory)
        if panel_id and exclude_ai_answer_group_id:
            chat_history = list(
                history.get_panel_messages_for_rerun(
                    panel_id,
                    exclude_ai_answer_group_id,
                )
            )
        elif panel_id:
            chat_history = list(history.get_panel_messages(panel_id))
        else:
            chat_history = list(history.messages)

        if memory_message is not None:
            return [memory_message, *chat_history]
        return chat_history

    def _build_workflow_snapshot(
        workflow_events: Optional[list[dict[str, Any]]] = None,
    ) -> list[dict[str, Any]]:
        node_labels = {
            "classify_intent": "意图分类",
            "execute_tool": "工具执行",
            "generate_answer": "答案生成",
        }
        ordered_node_ids = [
            "classify_intent",
            "execute_tool",
            "generate_answer",
        ]
        snapshots: dict[str, dict[str, Any]] = {
            node_id: {
                "id": node_id,
                "name": node_id,
                "displayName": node_labels.get(node_id, node_id),
                "status": "pending",
            }
            for node_id in ordered_node_ids
        }

        for event in workflow_events or []:
            if not isinstance(event, dict) or event.get("type") != "workflow_state":
                continue
            node_name = str(event.get("node_name") or "").strip()
            if not node_name:
                continue

            node = snapshots.get(node_name)
            if node is None:
                node = {
                    "id": node_name,
                    "name": node_name,
                    "displayName": node_labels.get(node_name, node_name),
                    "status": "pending",
                }
                snapshots[node_name] = node
                ordered_node_ids.append(node_name)

            status = str(event.get("status") or node.get("status") or "pending")
            timestamp_raw = event.get("timestamp")
            try:
                timestamp = int(timestamp_raw) if timestamp_raw is not None else 0
            except (TypeError, ValueError):
                timestamp = 0

            if status == "running" and timestamp and not node.get("startTime"):
                node["startTime"] = timestamp
            if status in {"completed", "failed"} and timestamp:
                node["endTime"] = timestamp

            duration_raw = event.get("duration_ms")
            if duration_raw is not None:
                try:
                    node["duration"] = int(duration_raw)
                except (TypeError, ValueError):
                    pass
            elif node.get("startTime") and node.get("endTime"):
                node["duration"] = int(node["endTime"]) - int(node["startTime"])

            tool_name = str(event.get("tool_name") or "").strip()
            if tool_name:
                node["toolName"] = tool_name

            tool_params = event.get("tool_params")
            if isinstance(tool_params, dict) and tool_params:
                node["toolParams"] = tool_params

            tool_result = str(event.get("tool_result_summary") or "").strip()
            if tool_result:
                node["toolResult"] = tool_result

            error = str(event.get("error") or "").strip()
            if error:
                node["error"] = error

            node["status"] = status

        return [snapshots[node_id] for node_id in ordered_node_ids]

    def _persist_panel_history(
        session_id: str,
        user_input: Any,
        output: str,
        *,
        panel_id: str = "",
        model_id: str = "",
        answer_group_id: str = "",
        persist_user_history: bool = True,
        persist_ai_history: bool = True,
        replace_ai_history: bool = False,
        raw_user_message: str = "",
        raw_images: Optional[list[dict[str, Any]]] = None,
        raw_files: Optional[list[dict[str, Any]]] = None,
        sources: Optional[list[dict[str, Any]]] = None,
        workflow_nodes: Optional[list[dict[str, Any]]] = None,
        task_id: str = "",
        task_type: str = "",
    ) -> None:
        history = SQLiteChatMessageHistory(session_id=session_id)
        summarized_input = _summarize_user_input_for_history(user_input)
        display_input = str(raw_user_message or "").strip()
        if answer_group_id and (persist_user_history or persist_ai_history):
            history.add_user_message_once(
                display_input or summarized_input,
                answer_group_id=answer_group_id,
                images=raw_images or [],
                files=raw_files or [],
            )
        elif persist_user_history:
            history.add_user_message(
                display_input or summarized_input,
                images=raw_images or [],
                files=raw_files or [],
            )
        if persist_ai_history and output.strip():
            if replace_ai_history and answer_group_id and panel_id:
                history.delete_ai_messages_for_answer_group(panel_id, answer_group_id)
            history.add_ai_message(
                output,
                model_id=model_id,
                panel_id=panel_id,
                answer_group_id=answer_group_id,
                sources=sources or [],
                workflow_nodes=workflow_nodes or [],
                task_id=task_id,
                task_type=task_type,
            )
    
    logger.info("初始化工具...")
    pipeline = DocPipeline(
        vector_store_path=vector_store_path if knowledge_base_enabled else None
    )

    async def _run_plain_chat_once(
        session_id: str,
        user_input: Any,
        panel_id: str = "",
        exclude_ai_answer_group_id: str = "",
    ) -> dict[str, Any]:
        chat_history = _load_chat_history(
            session_id,
            panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
        )

        if _has_image_input(user_input):
            output = await _direct_multimodal_answer(
                llm,
                user_input,
                chat_history,
                system_prompt=system_prompt,
            )
            return {"output": output, "sources": []}

        dashboard_result = await _generate_dashboard_from_knowledge(
            llm,
            pipeline,
            user_input,
            system_prompt=system_prompt,
            dashboard_template=dashboard_template,
            knowledge_base_enabled=knowledge_base_enabled,
        )
        if dashboard_result:
            return dashboard_result

        output = await _direct_plain_text_answer(
            llm,
            user_input,
            chat_history,
            system_prompt=system_prompt,
        )
        return {"output": output, "sources": []}
    
    if actual_mode == "langgraph":
        langgraph_app = await build_langgraph_agent(
            llm,
            pipeline,
            verbose,
            system_prompt=system_prompt,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
        )
        
        class LangGraphAgentWrapper:
            """包装 LangGraph agent 以兼容原有调用方式"""
            def __init__(self, app):
                self.app = app

            async def _run_once(
                self,
                session_id: str,
                user_input: Any,
                panel_id: str = "",
                exclude_ai_answer_group_id: str = "",
                workflow_event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
            ) -> dict[str, Any]:
                chat_history = _load_chat_history(
                    session_id,
                    panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )
                if _has_image_input(user_input):
                    output = await _direct_multimodal_answer(
                        llm,
                        user_input,
                        chat_history,
                        system_prompt=system_prompt,
                    )
                    return {"output": output, "sources": []}

                dashboard_result = await _generate_dashboard_from_knowledge(
                    llm,
                    pipeline,
                    user_input,
                    system_prompt=system_prompt,
                    dashboard_template=dashboard_template,
                    knowledge_base_enabled=knowledge_base_enabled,
                )
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
                try:
                    result_state = await self.app.ainvoke(state, config=graph_config)
                except TypeError as exc:
                    if "config" not in str(exc):
                        raise
                    result_state = await self.app.ainvoke(state)
                output = result_state.get("output", "")
                sources = result_state.get("sources", [])
                return {"output": output, "sources": sources}

            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                user_input = inputs.get("input", "")

                result = await self._run_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                    workflow_event_sink=_configurable_value(config, "workflow_event_sink", None),
                )
                result = _attach_configured_task_meta(result, config)
                result["sources"] = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )
                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        result.get("output", ""),
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=result.get("sources", []),
                        workflow_nodes=result.get("workflow_nodes", []),
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )
                return result

            async def astream_answer(self, user_input: Any, config: dict = None):
                """流式输出：先运行完整推理，再逐块 yield 答案，最后按需写入历史。"""
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                workflow_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
                workflow_events: list[dict[str, Any]] = []
                event_loop = asyncio.get_running_loop()

                def workflow_event_sink(payload: dict[str, Any]) -> None:
                    event_loop.call_soon_threadsafe(workflow_queue.put_nowait, payload)

                run_task = asyncio.create_task(
                    self._run_once(
                        session_id,
                        user_input,
                        panel_id=panel_id,
                        exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                        workflow_event_sink=workflow_event_sink,
                    )
                )

                try:
                    while True:
                        if run_task.done():
                            break
                        try:
                            workflow_event = await asyncio.wait_for(
                                workflow_queue.get(),
                                timeout=0.05,
                            )
                        except asyncio.TimeoutError:
                            continue
                        workflow_events.append(workflow_event)
                        yield workflow_event

                    while not workflow_queue.empty():
                        workflow_event = workflow_queue.get_nowait()
                        workflow_events.append(workflow_event)
                        yield workflow_event

                    result = await run_task
                except Exception:
                    if not run_task.done():
                        run_task.cancel()
                        await asyncio.gather(run_task, return_exceptions=True)
                    raise
                result = _attach_configured_task_meta(result, config)
                output = result.get("output", "")
                sources = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )
                workflow_nodes = _build_workflow_snapshot(workflow_events)
                result["workflow_nodes"] = workflow_nodes

                # Yield sources metadata first (as a special dict)
                if sources:
                    yield {"type": "sources", "sources": sources}

                chunk_size = 20
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)

                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        output,
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=sources,
                        workflow_nodes=workflow_nodes,
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )
        
        agent_wrapper = LangGraphAgentWrapper(langgraph_app)
        logger.info("✓ 使用 LangGraph 轻量 Agent 模式（适合小模型）")
        return agent_wrapper

    if actual_mode == "plain_chat":
        class PlainChatWrapper:
            async def _run_once(
                self,
                session_id: str,
                user_input: Any,
                panel_id: str = "",
                exclude_ai_answer_group_id: str = "",
            ) -> dict[str, Any]:
                return await _run_plain_chat_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )

            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                user_input = inputs.get("input", "")
                result = await self._run_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )
                result = _attach_configured_task_meta(result, config)
                result["sources"] = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )
                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        result.get("output", ""),
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=result.get("sources", []),
                        workflow_nodes=result.get("workflow_nodes", []),
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )
                return result

            async def astream_answer(self, user_input: Any, config: dict = None):
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                result = await self._run_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )
                result = _attach_configured_task_meta(result, config)
                output = result.get("output", "")
                sources = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )

                if sources:
                    yield {"type": "sources", "sources": sources}

                chunk_size = 20
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)

                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        output,
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=sources,
                        workflow_nodes=result.get("workflow_nodes", []),
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )

        logger.info("✓ 使用直连聊天模式（绕过 Agent / 工具链）")
        return PlainChatWrapper()
    
    else:
        all_tools = await build_runtime_tools(
            pipeline,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
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
            class PlainChatWrapper:
                async def _run_once(
                    self,
                    session_id: str,
                    user_input: Any,
                    panel_id: str = "",
                    exclude_ai_answer_group_id: str = "",
                ) -> dict[str, Any]:
                    return await _run_plain_chat_once(
                        session_id,
                        user_input,
                        panel_id=panel_id,
                        exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                    )

                async def ainvoke(self, inputs: dict, config: dict = None):
                    session_id = _configurable_value(config, "session_id", "default")
                    persist_history = bool(_configurable_value(config, "persist_history", True))
                    panel_id = str(_configurable_value(config, "panel_id", "") or "")
                    model_id = str(_configurable_value(config, "model_id", "") or "")
                    answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                    exclude_ai_answer_group_id = str(
                        _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                    )
                    persist_user_history = bool(
                        _configurable_value(config, "persist_user_history", persist_history)
                    )
                    persist_ai_history = bool(
                        _configurable_value(config, "persist_ai_history", persist_history)
                    )
                    replace_ai_history = bool(
                        _configurable_value(config, "replace_ai_history", False)
                    )
                    raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                    raw_images = _configurable_list(config, "raw_images")
                    raw_files = _configurable_list(config, "raw_files")
                    user_input = inputs.get("input", "")
                    result = await self._run_once(
                        session_id,
                        user_input,
                        panel_id=panel_id,
                        exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                    )
                    result = _attach_configured_task_meta(result, config)
                    result["sources"] = _merge_sources_with_attachments(
                        result.get("sources", []),
                        raw_files=raw_files,
                        raw_images=raw_images,
                        answer_group_id=answer_group_id,
                    )
                    if persist_user_history or persist_ai_history:
                        _persist_panel_history(
                            session_id,
                            user_input,
                            result.get("output", ""),
                            panel_id=panel_id,
                            model_id=model_id,
                            answer_group_id=answer_group_id,
                            persist_user_history=persist_user_history,
                            persist_ai_history=persist_ai_history,
                            replace_ai_history=replace_ai_history,
                            raw_user_message=raw_user_message,
                            raw_images=raw_images,
                            raw_files=raw_files,
                            sources=result.get("sources", []),
                            workflow_nodes=result.get("workflow_nodes", []),
                            task_id=str(result.get("task_id", "") or ""),
                            task_type=str(result.get("task_type", "") or ""),
                        )
                    return result

                async def astream_answer(self, user_input: Any, config: dict = None):
                    session_id = _configurable_value(config, "session_id", "default")
                    persist_history = bool(_configurable_value(config, "persist_history", True))
                    panel_id = str(_configurable_value(config, "panel_id", "") or "")
                    model_id = str(_configurable_value(config, "model_id", "") or "")
                    answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                    exclude_ai_answer_group_id = str(
                        _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                    )
                    persist_user_history = bool(
                        _configurable_value(config, "persist_user_history", persist_history)
                    )
                    persist_ai_history = bool(
                        _configurable_value(config, "persist_ai_history", persist_history)
                    )
                    replace_ai_history = bool(
                        _configurable_value(config, "replace_ai_history", False)
                    )
                    raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                    raw_images = _configurable_list(config, "raw_images")
                    raw_files = _configurable_list(config, "raw_files")
                    result = await self._run_once(
                        session_id,
                        user_input,
                        panel_id=panel_id,
                        exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                    )
                    result = _attach_configured_task_meta(result, config)
                    output = result.get("output", "")
                    sources = _merge_sources_with_attachments(
                        result.get("sources", []),
                        raw_files=raw_files,
                        raw_images=raw_images,
                        answer_group_id=answer_group_id,
                    )

                    if sources:
                        yield {"type": "sources", "sources": sources}

                    chunk_size = 20
                    for i in range(0, len(output), chunk_size):
                        yield output[i : i + chunk_size]
                        await asyncio.sleep(0.01)

                    if persist_user_history or persist_ai_history:
                        _persist_panel_history(
                            session_id,
                            user_input,
                            output,
                            panel_id=panel_id,
                            model_id=model_id,
                            answer_group_id=answer_group_id,
                            persist_user_history=persist_user_history,
                            persist_ai_history=persist_ai_history,
                            replace_ai_history=replace_ai_history,
                            raw_user_message=raw_user_message,
                            raw_images=raw_images,
                            raw_files=raw_files,
                            sources=sources,
                            workflow_nodes=result.get("workflow_nodes", []),
                            task_id=str(result.get("task_id", "") or ""),
                            task_type=str(result.get("task_type", "") or ""),
                        )

            return PlainChatWrapper()

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

        class FunctionCallingAgentWrapper:
            async def _run_once(
                self,
                session_id: str,
                user_input: Any,
                panel_id: str = "",
                exclude_ai_answer_group_id: str = "",
            ) -> dict[str, Any]:
                chat_history = _load_chat_history(
                    session_id,
                    panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )

                if _has_image_input(user_input):
                    output = await _direct_multimodal_answer(
                        llm,
                        user_input,
                        chat_history,
                        system_prompt=system_prompt,
                    )
                    return {"output": output, "sources": []}

                if _should_bypass_tools_for_plain_text_chat(
                    user_input,
                    knowledge_base_enabled=knowledge_base_enabled,
                    web_search_enabled=web_search_enabled,
                ):
                    output = await _direct_plain_text_answer(
                        llm,
                        user_input,
                        chat_history,
                        system_prompt=system_prompt,
                    )
                    return {"output": output, "sources": []}

                dashboard_result = await _generate_dashboard_from_knowledge(
                    llm,
                    pipeline,
                    user_input,
                    system_prompt=system_prompt,
                    dashboard_template=dashboard_template,
                    knowledge_base_enabled=knowledge_base_enabled,
                )
                if dashboard_result:
                    return dashboard_result

                return await agent_executor.ainvoke(
                    {"input": user_input, "chat_history": chat_history}
                )

            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                user_input = inputs.get("input", "")
                result = await self._run_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )
                result = _attach_configured_task_meta(result, config)
                result["sources"] = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )
                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        result.get("output", ""),
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=result.get("sources", []),
                        workflow_nodes=result.get("workflow_nodes", []),
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )
                return result

            async def astream_answer(self, user_input: Any, config: dict = None):
                session_id = _configurable_value(config, "session_id", "default")
                persist_history = bool(_configurable_value(config, "persist_history", True))
                panel_id = str(_configurable_value(config, "panel_id", "") or "")
                model_id = str(_configurable_value(config, "model_id", "") or "")
                answer_group_id = str(_configurable_value(config, "answer_group_id", "") or "")
                exclude_ai_answer_group_id = str(
                    _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
                )
                persist_user_history = bool(
                    _configurable_value(config, "persist_user_history", persist_history)
                )
                persist_ai_history = bool(
                    _configurable_value(config, "persist_ai_history", persist_history)
                )
                replace_ai_history = bool(
                    _configurable_value(config, "replace_ai_history", False)
                )
                raw_user_message = str(_configurable_value(config, "raw_user_message", "") or "")
                raw_images = _configurable_list(config, "raw_images")
                raw_files = _configurable_list(config, "raw_files")
                result = await self._run_once(
                    session_id,
                    user_input,
                    panel_id=panel_id,
                    exclude_ai_answer_group_id=exclude_ai_answer_group_id,
                )
                result = _attach_configured_task_meta(result, config)
                output = result.get("output", "")
                sources = _merge_sources_with_attachments(
                    result.get("sources", []),
                    raw_files=raw_files,
                    raw_images=raw_images,
                    answer_group_id=answer_group_id,
                )

                if sources:
                    yield {"type": "sources", "sources": sources}

                chunk_size = 20
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)

                if persist_user_history or persist_ai_history:
                    _persist_panel_history(
                        session_id,
                        user_input,
                        output,
                        panel_id=panel_id,
                        model_id=model_id,
                        answer_group_id=answer_group_id,
                        persist_user_history=persist_user_history,
                        persist_ai_history=persist_ai_history,
                        replace_ai_history=replace_ai_history,
                        raw_user_message=raw_user_message,
                        raw_images=raw_images,
                        raw_files=raw_files,
                        sources=sources,
                        workflow_nodes=result.get("workflow_nodes", []),
                        task_id=str(result.get("task_id", "") or ""),
                        task_type=str(result.get("task_type", "") or ""),
                    )

        return FunctionCallingAgentWrapper()


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
