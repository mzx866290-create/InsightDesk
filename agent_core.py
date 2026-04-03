"""
LangChain Agent 编排核心
支持 Ollama 本地模型和 OpenRouter 云端模型双后端
支持 Function Calling 和 LangGraph 轻量 Agent 双模式
"""

import asyncio
import json
import os
import sys
import re
import time
import logging
from typing import Any, Optional, Dict, TypedDict, Annotated, Literal
from dotenv import load_dotenv
try:
    from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
except ModuleNotFoundError:
    # 兼容未安装 langchain_classic 的环境
    from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from doc_pipeline import DocPipeline
from chat_store import SQLiteChatMessageHistory
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# 联网搜索开关（由 app.py 在每次对话前设置）
_web_search_enabled: bool = True
DEFAULT_LLM_TIMEOUT_SECONDS = float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "35"))
DEFAULT_KB_DOC_CHAR_LIMIT = int(os.getenv("KB_DOC_CHAR_LIMIT", "600"))
DEFAULT_KB_TOP_K = int(os.getenv("KB_TOP_K", "8"))
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
    "title_hint": "知识库数据洞察",
    "focus_metrics": [],
    "preferred_charts": ["bar", "line", "pie"],
    "section_order": ["summary", "metrics", "charts", "table", "evidence", "warnings"],
    "audience_tone": "专业、直观、适合业务汇报",
}


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
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


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


async def _generate_dashboard_from_knowledge(
    llm,
    pipeline: DocPipeline,
    user_input: Any,
    system_prompt: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
    knowledge_base_enabled: bool = True,
) -> Optional[dict[str, Any]]:
    if not _should_generate_dashboard(user_input):
        return None
    if not knowledge_base_enabled:
        return {
            "output": "当前未开启知识库引用，暂时不能根据知识库生成仪表盘。请先打开知识库开关后再试。",
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

    template = _normalize_dashboard_template(dashboard_template)
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
    messages.extend(chat_history[-8:])
    messages.append(HumanMessage(content=user_input))
    response = await _ainvoke_llm_with_timeout(llm, messages)
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
        request_timeout = float(os.getenv("CLOUD_LLM_TIMEOUT_SECONDS", "25"))

        logger.info("使用云端模型: %s (地址: %s)", model, base_url)
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            timeout=request_timeout,
            max_retries=0,
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
            temperature=temperature,
            base_url=base_url,
            num_predict=2048,
            top_p=0.9,  # 限制采样范围
        )

    else:
        raise ValueError(f"不支持的模型提供方: {provider}")


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
            top_k: 返回的文档片段数量 (默认 3, 经过 Rerank 精排)

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

            docs = pipeline.search_with_rerank(question, k=top_k, fetch_k=20)
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
        response = await _ainvoke_llm_with_timeout(llm, rewrite_prompt, timeout_seconds=20)
        rewritten = response.content.strip()
        logger.info("[QueryRewrite] original=%s -> rewritten=%s", user_input[:50], rewritten[:50])
        return rewritten if rewritten else user_input
    except Exception as e:
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
    tools_list = create_tools(
        pipeline,
        web_search_enabled=web_search_enabled,
        knowledge_base_enabled=knowledge_base_enabled,
    )
    tools_by_name = {tool.name: tool for tool in tools_list}
    tools_dict: dict[str, Any] = {}
    tool_options = ["0 - 不需要工具（用于打招呼、闲聊、感谢等）"]

    if knowledge_base_enabled:
        tools_dict["1"] = tools_by_name["query_knowledge"]
        tools_dict["4"] = tools_by_name["get_knowledge_stats"]
        tools_dict["5"] = tools_by_name["reload_knowledge_base"]
        tool_options.extend(
            [
                "1 - 查询企业知识库（用于查询内部文档、公司资料）",
                "4 - 知识库统计（用于查询知识库状态、文档数量）",
                "5 - 重载知识库（用于刷新知识库）",
            ]
        )

    if web_search_enabled:
        tools_dict["2"] = tools_by_name["web_search"]
        tools_dict["3"] = tools_by_name["quick_answer"]
        tools_dict["6"] = tools_by_name["fetch_webpage"]
        tool_options.extend(
            [
                "2 - 联网搜索（用于查询实时信息、新闻、外部知识）",
                "3 - 快速问答（用于快速获取网络答案）",
                "6 - 抓取网页全文（用于读取搜索结果中的具体网页内容）",
            ]
        )

    allowed_choices = "".join(sorted(tools_dict.keys()))
    
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
        available_tools = "\n".join(tool_options)
        classify_prompt = (
            f"{role_desc}\n"
            "请根据用户问题选择最合适的工具编号，只输出一个数字。\n\n"
            f"{available_tools}\n\n"
            f"{history_text}"
            f"用户: {user_input}\n\n"
            f"请只输出一个数字：0 或 {allowed_choices or '无'}"
        )

        try:
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
            answer_prompt = f"""{role_desc}。根据工具返回的信息回答用户问题。{citation_hint}{intent_instructions}
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
            state["output"] = response.content.strip()
            logger.info("[LangGraph] 生成回答完成 output_len=%d", len(state["output"]))
            
        except Exception as e:
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
                    state["output"] = _strip_think_tags(
                        response.content.strip() if isinstance(response.content, str) else _stringify_user_input(response.content)
                    )
                    logger.info(
                        "[LangGraph] 重试生成回答成功 output_len=%d",
                        len(state["output"]),
                    )
                    return state
                except Exception:
                    logger.exception("[LangGraph] 压缩重试后仍生成失败")

                state["output"] = _build_kb_timeout_fallback(user_input, tool_result, sources)
                logger.warning(
                    "[LangGraph] 云端生成失败后返回知识库兜底结果 output_len=%d",
                    len(state["output"]),
                )
                return state

            state["output"] = f"❌ 生成回答失败: {str(e)}"
        
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
        provider: 模型提供方 ('local' 或 'cloud')
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key
        temperature: 温度参数
        agent_mode: Agent 模式 ('auto', 'function_calling', 'langgraph')
            - 'auto': 本地模型默认使用 LangGraph，云端模型默认使用 Function Calling
            - 'function_calling': 强制使用 Function Calling (需要模型支持)
            - 'langgraph': 强制使用 LangGraph 轻量 Agent
        verbose: 是否显示详细日志

    Returns:
        Agent 实例 (包装了记忆管理)
    """
    provider = provider or "local"
    
    if agent_mode == "auto":
        actual_mode = "function_calling" if provider == "cloud" else "langgraph"
        logger.info("[Auto] provider=%s -> agent_mode=%s", provider, actual_mode)
    else:
        actual_mode = agent_mode
    
    llm = get_llm(provider, model_name, base_url, api_key, temperature)
    
    logger.info("初始化工具...")
    pipeline = DocPipeline(
        vector_store_path=vector_store_path if knowledge_base_enabled else None
    )
    
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
            
            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = config.get("configurable", {}).get("session_id", "default") if config else "default"
                
                history = SQLiteChatMessageHistory(session_id=session_id)
                
                user_input = inputs.get("input", "")
                chat_history = list(history.messages)

                if _has_image_input(user_input):
                    output = await _direct_multimodal_answer(
                        llm,
                        user_input,
                        chat_history,
                        system_prompt=system_prompt,
                    )
                    history.add_user_message(_summarize_user_input_for_history(user_input))
                    history.add_ai_message(output)
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
                    history.add_user_message(_summarize_user_input_for_history(user_input))
                    history.add_ai_message(dashboard_result["output"])
                    return dashboard_result
                
                state = {
                    "input": user_input,
                    "chat_history": chat_history,
                    "tool_choice": "",
                    "tool_result": "",
                    "sources": [],
                    "output": "",
                }
                
                result_state = await self.app.ainvoke(state)
                
                output = result_state.get("output", "")
                sources = result_state.get("sources", [])
                
                history.add_user_message(_summarize_user_input_for_history(user_input))
                history.add_ai_message(output)
                
                return {"output": output, "sources": sources}

            async def astream_answer(self, user_input: Any, config: dict = None):
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
        all_tools = create_tools(
            pipeline,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
        )
        if not knowledge_base_enabled:
            all_tools = [
                tool
                for tool in all_tools
                if tool.name not in {"query_knowledge", "reload_knowledge_base", "get_knowledge_stats"}
            ]
        if not web_search_enabled:
            all_tools = [
                tool
                for tool in all_tools
                if tool.name not in {"web_search", "quick_answer", "fetch_webpage"}
            ]
        
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
                async def ainvoke(self, inputs: dict, config: dict = None):
                    session_id = config.get("configurable", {}).get("session_id", "default") if config else "default"
                    history = SQLiteChatMessageHistory(session_id=session_id)
                    user_input = inputs.get("input", "")
                    dashboard_result = await _generate_dashboard_from_knowledge(
                        llm,
                        pipeline,
                        user_input,
                        system_prompt=system_prompt,
                        dashboard_template=dashboard_template,
                        knowledge_base_enabled=knowledge_base_enabled,
                    )
                    if dashboard_result:
                        history.add_user_message(_summarize_user_input_for_history(user_input))
                        history.add_ai_message(dashboard_result["output"])
                        return dashboard_result
                    response = await _ainvoke_llm_with_timeout(
                        llm,
                        [
                            SystemMessage(
                                content=system_prompt or "你是一个企业知识库助手，请直接根据上下文回答用户问题，并始终用中文回答。"
                            ),
                            *list(history.messages)[-8:],
                            HumanMessage(content=user_input),
                        ],
                    )
                    output = response.content.strip() if isinstance(response.content, str) else _stringify_user_input(response.content)
                    history.add_user_message(_summarize_user_input_for_history(user_input))
                    history.add_ai_message(output)
                    return {"output": output, "sources": []}

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
            early_stopping_method="generate",
            return_intermediate_steps=True,
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
        
        class FunctionCallingAgentWrapper:
            async def ainvoke(self, inputs: dict, config: dict = None):
                session_id = config.get("configurable", {}).get("session_id", "default") if config else "default"
                user_input = inputs.get("input", "")

                if _has_image_input(user_input):
                    history = SQLiteChatMessageHistory(session_id=session_id)
                    output = await _direct_multimodal_answer(
                        llm,
                        user_input,
                        list(history.messages),
                        system_prompt=system_prompt,
                    )
                    history.add_user_message(_summarize_user_input_for_history(user_input))
                    history.add_ai_message(output)
                    return {"output": output, "sources": []}

                history = SQLiteChatMessageHistory(session_id=session_id)
                dashboard_result = await _generate_dashboard_from_knowledge(
                    llm,
                    pipeline,
                    user_input,
                    system_prompt=system_prompt,
                    dashboard_template=dashboard_template,
                    knowledge_base_enabled=knowledge_base_enabled,
                )
                if dashboard_result:
                    history.add_user_message(_summarize_user_input_for_history(user_input))
                    history.add_ai_message(dashboard_result["output"])
                    return dashboard_result

                return await agent_with_memory.ainvoke(inputs, config=config)

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
