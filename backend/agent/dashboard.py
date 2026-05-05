"""仪表盘模板、触发关键词"""

from __future__ import annotations

import json
import os
import logging
from typing import TYPE_CHECKING, Any, Optional

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from backend.agent.llm import (
    _stringify_user_input,
    _ainvoke_llm_with_timeout,
    _strip_think_tags,
    _astream_llm_with_timeout,
    _ThinkTagStreamFilter,
)
from backend.agent.history import (
    _preserve_system_messages_with_recent_history,
)
from backend.agent.retrieval import (
    _retrieve_kb_documents,
    _dedupe_documents,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline

from backend.agent.dashboard_payload import (
    DASHBOARD_TRIGGER_KEYWORDS,
    DEFAULT_DASHBOARD_TEMPLATE,
    _build_attachment_dashboard_fallback,
    _build_dashboard_sources,
    _extract_attachment_evidence,
    _extract_attachment_sections,
    _extract_json_payload,
    _normalize_dashboard_template,
    _parse_attachment_tables,
    _parse_numeric_dashboard_value,
    _render_attachment_dashboard_card,
    _render_dashboard_card,
    _sanitize_dashboard_payload,
    _should_generate_dashboard,
)


async def _generate_dashboard_from_attachment(
    llm,
    user_input: Any,
    attachment_evidence: list[dict[str, Any]],
    system_prompt: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    template = _normalize_dashboard_template(dashboard_template)
    attachment_sections = _extract_attachment_sections(user_input)
    user_text = _stringify_user_input(user_input).strip()
    evidence_json = json.dumps(attachment_evidence, ensure_ascii=False, indent=2)
    template_json = json.dumps(template, ensure_ascii=False, indent=2)
    role_desc = system_prompt or "你是一个数据分析助手"

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
                "response_mode": "attachment_dashboard",
            }
        if not sanitized["metrics"] and not sanitized["charts"] and not sanitized["table"]:
            return {
                "output": "已读取附件内容，但证据主要是描述性文本，暂时不足以生成可靠图表。建议上传包含数值或分类统计的文件。",
                "sources": sources,
                "response_mode": "attachment_dashboard",
            }
        return {
            "output": _render_attachment_dashboard_card(sanitized),
            "sources": sources,
            "response_mode": "attachment_dashboard",
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
                "response_mode": "attachment_dashboard",
            }
        logger.exception("Attachment dashboard generation failed")
        return {
            "output": "系统已尝试根据附件生成仪表盘，但结构化整理过程失败。请稍后重试，或换一种更明确的指标需求描述。",
            "sources": sources,
            "response_mode": "attachment_dashboard",
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

    attachment_evidence = _extract_attachment_evidence(user_input)
    if attachment_evidence:
        return await _generate_dashboard_from_attachment(
            llm, user_input, attachment_evidence,
            system_prompt=system_prompt,
            dashboard_template=dashboard_template,
        )

    if not knowledge_base_enabled:
        return {
            "output": "当前未开启知识库引用，暂时不能根据知识库生成仪表盘。请先打开知识库开关后再试，或上传包含数据的文件（如 Excel、CSV）。",
            "sources": [],
            "response_mode": "knowledge_dashboard",
        }
    if not pipeline.vector_store_path:
        return {
            "output": "当前角色未绑定专属知识库，暂时无法生成基于知识库证据的仪表盘。请先为角色挂载知识库后再试。",
            "sources": [],
            "response_mode": "knowledge_dashboard",
        }
    if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
        pipeline.load_store()
    if pipeline.vectorstore is None:
        return {
            "output": "当前角色绑定的知识库尚未就绪，暂时无法生成仪表盘。请先检查知识库索引是否已正确加载。",
            "sources": [],
            "response_mode": "knowledge_dashboard",
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
            docs, _ = _retrieve_kb_documents(
                pipeline,
                query,
                top_k=4,
                fetch_k=12,
                preferred_mode="auto",
                use_rerank=True,
                log_context="dashboard",
            )
            gathered_docs.extend(docs)
        except Exception:
            logger.exception("Dashboard retrieval failed for query=%s", query)

    docs = _dedupe_documents(gathered_docs, limit=8)
    if len(docs) < 2:
        return {
            "output": "已检索当前角色绑定的知识库，但缺少足够的可量化证据，暂时无法生成可靠仪表盘。你可以补充包含数字、分类统计或对比口径的资料后再试。",
            "sources": [],
            "response_mode": "knowledge_dashboard",
        }

    evidence, sources = _build_dashboard_sources(docs)
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)
    template_json = json.dumps(template, ensure_ascii=False, indent=2)
    role_desc = system_prompt or "你是一个企业知识库助手"

    dashboard_prompt = f"""{role_desc}

你正在为用户生成一个"只基于知识库证据"的数据仪表盘。你必须严格遵守下面规则：
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
                "response_mode": "knowledge_dashboard",
            }
        if not sanitized["metrics"] and not sanitized["charts"]:
            return {
                "output": "已检索当前角色绑定的知识库，但证据主要是描述性文本，暂时不足以生成可靠图表。建议补充带数值或分类统计的数据后再试。",
                "sources": sources,
                "response_mode": "knowledge_dashboard",
            }
        return {
            "output": _render_dashboard_card(sanitized),
            "sources": sources,
            "response_mode": "knowledge_dashboard",
        }
    except Exception:
        logger.exception("Dashboard generation failed")
        return {
            "output": "系统已尝试根据知识库生成仪表盘，但结构化整理过程失败。请稍后重试，或换一种更明确的指标需求描述。",
            "sources": sources if 'sources' in locals() else [],
            "response_mode": "knowledge_dashboard",
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
        return _strip_think_tags(content)
    return _strip_think_tags(_stringify_user_input(content))


def _build_plain_text_chat_messages(
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [
        SystemMessage(
            content=system_prompt
            or "你是一个中文写作与问答助手。当前请求不需要调用任何工具，请直接基于上下文回答用户问题。始终用中文回答。"
        )
    ]
    messages.extend(_preserve_system_messages_with_recent_history(chat_history, max_recent=8))
    messages.append(HumanMessage(content=user_input))
    return messages


def _plain_text_chat_timeout_seconds(
    user_input: Any,
    chat_history: list[BaseMessage],
) -> float:
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
    messages = _build_plain_text_chat_messages(
        user_input,
        chat_history,
        system_prompt=system_prompt,
    )
    response = await _ainvoke_llm_with_timeout(
        llm,
        messages,
        timeout_seconds=_plain_text_chat_timeout_seconds(user_input, chat_history),
    )
    content = response.content
    if isinstance(content, str):
        return _strip_think_tags(content)
    return _strip_think_tags(_stringify_user_input(content))


async def _astream_plain_text_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
):
    messages = _build_plain_text_chat_messages(
        user_input,
        chat_history,
        system_prompt=system_prompt,
    )
    stream_filter = _ThinkTagStreamFilter()
    async for chunk in _astream_llm_with_timeout(
        llm,
        messages,
        timeout_seconds=_plain_text_chat_timeout_seconds(user_input, chat_history),
    ):
        visible = stream_filter.feed(chunk)
        if visible:
            yield visible

    tail = stream_filter.flush()
    if tail:
        yield tail
