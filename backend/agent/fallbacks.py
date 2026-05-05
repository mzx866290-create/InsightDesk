"""Fallback responses for tool-grounded agent runs."""

import re
from typing import Any

from backend.agent.runtime_plain_chat import _looks_like_resume_request


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
            desc = match.group(4).strip(" ：。")
            bullets = [frag.strip(" ：。") for frag in re.split(r"[；。]", desc) if frag.strip()]
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
            duties = [frag.strip(" ：。") for frag in re.split(r"[；。]", project_match.group(2)) if frag.strip()]
            outcomes = [frag.strip(" ：。") for frag in re.split(r"[；。]", project_match.group(3)) if frag.strip()]
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
    parts.append("可以继续发送一个更具体的问题，我会基于这些片段继续缩小范围处理。")
    return "\n".join(parts)


def _build_kb_timeout_fallback(
    user_input: Any,
    tool_result: str,
    sources: list[dict[str, Any]],
) -> str:
    if _looks_like_resume_request(user_input):
        return _build_resume_timeout_fallback(tool_result, sources)
    return _build_generic_timeout_fallback(tool_result, sources)
