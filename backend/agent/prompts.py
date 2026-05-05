"""???????????????"""

import re
import logging
from typing import Any, Optional

from backend.agent.llm import _strip_think_tags, _stringify_user_input
from backend.agent.sources import _merge_sources_with_attachments, _source_is_grounding_evidence

logger = logging.getLogger(__name__)

BUSINESS_SECTION_ORDER = (
    "结论",
    "适用范围",
    "依据来源",
    "执行步骤",
    "风险提示",
)
BUSINESS_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "结论": ("结论", "核心结论", "结论摘要", "摘要结论"),
    "适用范围": ("适用范围", "适用场景", "适用对象", "适用边界"),
    "依据来源": ("依据来源", "来源依据", "证据来源", "参考来源", "引用来源", "来源"),
    "执行步骤": ("执行步骤", "执行建议", "行动建议", "建议动作", "下一步", "落地步骤"),
    "风险提示": ("风险提示", "风险与边界", "注意事项", "风险", "限制说明"),
}
BUSINESS_ANSWER_FORMAT_INSTRUCTIONS = """
请严格按以下五个一级小节输出，且顺序不能调整：
## 结论
## 适用范围
## 依据来源
## 执行步骤
## 风险提示

要求：
1. 用正式、克制、适合周报/PPT 直接引用的中文，不要口语化。
2. 结论必须与证据一致；证据不足时，明确写“暂不下结论”。
3. “依据来源”必须完整列出本次实际使用的来源。
4. 不要编造版本、日期、制度口径或执行动作。
"""

def _canonical_business_section_name(title: str) -> str:
    normalized = re.sub(r"^[#*\-\d.\s]+", "", str(title or "")).strip()
    normalized = normalized.rstrip("：:").strip()
    for canonical, aliases in BUSINESS_SECTION_ALIASES.items():
        if normalized in aliases:
            return canonical
    return ""


def _parse_business_sections(text: str) -> dict[str, str]:
    sections = {section: "" for section in BUSINESS_SECTION_ORDER}
    current_section = ""

    for raw_line in str(text or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current_section and sections[current_section]:
                sections[current_section] += "\n"
            continue

        canonical = _canonical_business_section_name(line)
        if canonical:
            current_section = canonical
            continue

        if not current_section:
            current_section = "结论"
        sections[current_section] += (line.strip() + "\n")

    return {
        section: value.strip()
        for section, value in sections.items()
    }


def _fallback_business_conclusion(raw_output: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(raw_output or "")).strip()
    if not cleaned:
        return "基于当前证据，暂不输出明确业务结论。"
    return cleaned[:220].rstrip("，,；;。") + "。"


def _render_business_sources(sources: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for default_index, source in enumerate(sources, start=1):
        if not _source_is_grounding_evidence(source):
            continue
        citation_index = source.get("index", default_index)
        title = str(source.get("title") or "未知来源").strip() or "未知来源"
        snippet = re.sub(r"\s+", " ", str(source.get("snippet") or "")).strip()
        url = str(source.get("url") or "").strip()
        version_label = str(source.get("version_label") or "").strip()
        lifecycle_status = str(source.get("lifecycle_status") or "").strip()
        flags: list[str] = []
        if version_label:
            flags.append(version_label)
        if lifecycle_status == "current":
            flags.append("当前口径")
        elif lifecycle_status == "superseded":
            flags.append("历史版本")
        elif lifecycle_status == "expired":
            flags.append("已过期")

        line = f"- [^{citation_index}] {title}"
        if flags:
            line += f"（{'；'.join(flags)}）"
        if url:
            line += f" {url}"
        if snippet:
            line += f": {snippet[:120]}"
        lines.append(line)

    if not lines:
        return "- 未返回可核验来源。"
    return "\n".join(lines)


def _build_missing_sources_business_answer() -> str:
    return """## 结论
暂不提供业务结论。本次回答缺少可核验来源，不能直接用于周报、PPT 或对外口径。

## 适用范围
仅用于说明当前证据不足，不适用于制度解释、业务决策或对外传播。

## 依据来源
- 未返回可核验来源，或来源字段缺失。

## 执行步骤
1. 补充相关知识库文档、会话附件或明确的检索范围。
2. 优先核对最新版本、有效期和生效口径。
3. 在来源完整返回后重新生成答案。

## 风险提示
在缺少来源的情况下继续输出明确结论，存在口径混用、版本错误和引用不完整的风险。"""


def _render_business_answer(
    raw_output: str,
    *,
    sources: list[dict[str, Any]],
) -> str:
    sections = _parse_business_sections(raw_output)
    sections["结论"] = sections["结论"] or _fallback_business_conclusion(raw_output)
    sections["适用范围"] = sections["适用范围"] or "适用于本次检索命中的资料口径；超出当前来源覆盖范围的场景需补充核验。"
    sections["依据来源"] = _render_business_sources(sources)
    sections["执行步骤"] = sections["执行步骤"] or "1. 先确认引用的是当前有效版本。\n2. 再按依据来源核对关键事实、数字和口径。\n3. 最后将结论整理到周报、PPT 或执行清单。"
    sections["风险提示"] = sections["风险提示"] or "如资料存在历史版本、失效文档或来源覆盖不足，结论可能出现偏差。"

    rendered_sections: list[str] = []
    for section in BUSINESS_SECTION_ORDER:
        rendered_sections.append(f"## {section}\n{sections[section].strip()}")
    return "\n\n".join(rendered_sections).strip()


def _finalize_business_answer_output(
    output: Any,
    *,
    sources: Optional[list[dict[str, Any]]] = None,
    response_mode: str = "",
) -> str:
    raw_output = _strip_think_tags(_stringify_user_input(output)).strip()
    normalized_mode = str(response_mode or "").strip().lower()
    normalized_sources = [dict(item) for item in (sources or []) if isinstance(item, dict)]
    has_evidence = any(_source_is_grounding_evidence(source) for source in normalized_sources)

    if normalized_mode in {"dashboard", "attachment_dashboard", "knowledge_dashboard", "multimodal"}:
        return raw_output
    if has_evidence:
        return _render_business_answer(raw_output, sources=normalized_sources)
    if normalized_mode in {"agent", "knowledge_grounded"}:
        return _build_missing_sources_business_answer()
    return raw_output


def _finalize_agent_result(
    result: dict[str, Any],
    *,
    user_input: Any,
    raw_files: Optional[list[dict[str, Any]]] = None,
    raw_images: Optional[list[dict[str, Any]]] = None,
    answer_group_id: str = "",
) -> dict[str, Any]:
    finalized = dict(result or {})
    merged_sources = _merge_sources_with_attachments(
        finalized.get("sources", []),
        raw_files=raw_files or [],
        raw_images=raw_images or [],
        answer_group_id=answer_group_id,
    )
    finalized["sources"] = merged_sources
    finalized["output"] = _finalize_business_answer_output(
        finalized.get("output", ""),
        sources=merged_sources,
        response_mode=str(finalized.get("response_mode", "") or ""),
    )
    return finalized
