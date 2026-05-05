"""LLM 调用超时、结果压缩、流式辅助"""

import asyncio
import os
import re
import logging
import time
from typing import Any, Optional

from backend.core.runtime_metrics import record_llm_call

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT_SECONDS = float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "90"))
PLACEHOLDER_SYSTEM_PROMPTS = {"无", "none", "null", "n/a"}


def _safe_positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _llm_model_name(llm: Any) -> str:
    for attr in ("model", "model_name", "model_id", "deployment_name"):
        value = getattr(llm, attr, None)
        if value:
            return str(value).strip() or "unknown"

    default_params = getattr(llm, "_default_params", None)
    if isinstance(default_params, dict):
        for key in ("model", "model_name", "model_id"):
            value = default_params.get(key)
            if value:
                return str(value).strip() or "unknown"
    return "unknown"


def _llm_provider_name(llm: Any) -> str:
    for attr in ("provider", "llm_provider"):
        value = getattr(llm, attr, None)
        if value:
            return str(value).strip().lower() or "unknown"

    module = str(getattr(llm.__class__, "__module__", "") or "").lower()
    name = str(getattr(llm.__class__, "__name__", "") or "").lower()
    haystack = f"{module}.{name}"
    if "ollama" in haystack:
        return "ollama"
    if "openai" in haystack:
        return "openai"
    if "openrouter" in haystack:
        return "openrouter"
    if "anthropic" in haystack:
        return "anthropic"
    return "unknown"


def _usage_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _extract_llm_token_usage(response: Any) -> dict[str, int]:
    usage_candidates: list[dict[str, Any]] = []

    usage_metadata = _usage_mapping(getattr(response, "usage_metadata", None))
    if usage_metadata:
        usage_candidates.append(usage_metadata)

    response_metadata = _usage_mapping(getattr(response, "response_metadata", None))
    token_usage = _usage_mapping(response_metadata.get("token_usage"))
    if token_usage:
        usage_candidates.append(token_usage)
    if response_metadata:
        usage_candidates.append(response_metadata)

    llm_output = _usage_mapping(getattr(response, "llm_output", None))
    llm_output_usage = _usage_mapping(llm_output.get("token_usage"))
    if llm_output_usage:
        usage_candidates.append(llm_output_usage)

    for usage in usage_candidates:
        prompt_tokens = _safe_positive_int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or usage.get("prompt_eval_count")
        )
        completion_tokens = _safe_positive_int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or usage.get("eval_count")
        )
        total_tokens = _safe_positive_int(
            usage.get("total_tokens")
            or usage.get("total_token_count")
            or prompt_tokens + completion_tokens
        )
        if prompt_tokens or completion_tokens or total_tokens:
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _record_llm_call_result(
    llm: Any,
    *,
    status: str,
    started_at: float,
    response: Any = None,
) -> None:
    usage = _extract_llm_token_usage(response)
    record_llm_call(
        provider=_llm_provider_name(llm),
        model=_llm_model_name(llm),
        status=status,
        latency_seconds=time.perf_counter() - started_at,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
    )


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


def _normalize_runtime_system_prompt(system_prompt: Optional[str]) -> Optional[str]:
    normalized = str(system_prompt or "").strip()
    if not normalized:
        return None
    if normalized.lower() in PLACEHOLDER_SYSTEM_PROMPTS:
        return None
    return normalized


async def _ainvoke_llm_with_timeout(
    llm,
    payload: Any,
    timeout_seconds: Optional[float] = None,
):
    """统一为 LLM 调用增加超时，避免知识库场景长时间挂起。"""
    timeout = timeout_seconds or DEFAULT_LLM_TIMEOUT_SECONDS
    started_at = time.perf_counter()
    try:
        response = await asyncio.wait_for(llm.ainvoke(payload), timeout=timeout)
        _record_llm_call_result(llm, status="success", started_at=started_at, response=response)
        return response
    except asyncio.TimeoutError as exc:
        _record_llm_call_result(llm, status="timeout", started_at=started_at)
        raise TimeoutError(f"LLM request timed out after {int(timeout)}s") from exc
    except Exception:
        _record_llm_call_result(llm, status="error", started_at=started_at)
        raise


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


def _strip_think_tags(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if re.search(r"<think>", cleaned, flags=re.IGNORECASE):
        cleaned = re.split(r"<think>", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip()


class _ThinkTagStreamFilter:
    OPEN_TAG = "<think>"
    CLOSE_TAG = "</think>"

    def __init__(self) -> None:
        self._pending = ""
        self._inside_think = False

    def feed(self, chunk: str) -> str:
        data = f"{self._pending}{chunk or ''}"
        self._pending = ""
        if not data:
            return ""

        out: list[str] = []
        index = 0

        while index < len(data):
            lowered = data.lower()
            if self._inside_think:
                end = lowered.find(self.CLOSE_TAG, index)
                if end == -1:
                    keep = min(len(self.CLOSE_TAG) - 1, len(data) - index)
                    self._pending = data[-keep:] if keep > 0 else ""
                    return "".join(out)
                index = end + len(self.CLOSE_TAG)
                self._inside_think = False
                continue

            start = lowered.find(self.OPEN_TAG, index)
            if start == -1:
                tail = data[index:]
                keep = 0
                max_prefix = min(len(self.OPEN_TAG) - 1, len(tail))
                for length in range(max_prefix, 0, -1):
                    if self.OPEN_TAG.startswith(tail[-length:].lower()):
                        keep = length
                        break
                visible_end = len(data) - keep
                if visible_end > index:
                    out.append(data[index:visible_end])
                self._pending = data[visible_end:]
                return "".join(out)

            if start > index:
                out.append(data[index:start])
            index = start + len(self.OPEN_TAG)
            self._inside_think = True

        return "".join(out)

    def flush(self) -> str:
        if self._inside_think:
            self._pending = ""
            return ""
        pending = self._pending
        self._pending = ""
        if not pending:
            return ""
        if self.OPEN_TAG.startswith(pending.lower()):
            return ""
        return pending


def _stringify_stream_chunk_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("type") == "text":
            return _stringify_stream_chunk_content(content.get("text", ""))
        if "content" in content:
            return _stringify_stream_chunk_content(content.get("content", ""))
        return str(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            piece = _stringify_stream_chunk_content(item)
            if piece:
                parts.append(piece)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


async def _astream_llm_with_timeout(
    llm,
    payload: Any,
    timeout_seconds: Optional[float] = None,
):
    timeout = timeout_seconds or DEFAULT_LLM_TIMEOUT_SECONDS
    if not hasattr(llm, "astream"):
        response = await _ainvoke_llm_with_timeout(llm, payload, timeout_seconds=timeout)
        text = _stringify_stream_chunk_content(getattr(response, "content", response))
        if text:
            yield text
        return

    started_at = time.perf_counter()
    try:
        async with asyncio.timeout(timeout):
            async for chunk in llm.astream(payload):
                text = _stringify_stream_chunk_content(getattr(chunk, "content", chunk))
                if text:
                    yield text
        _record_llm_call_result(llm, status="success", started_at=started_at)
    except asyncio.TimeoutError as exc:
        _record_llm_call_result(llm, status="timeout", started_at=started_at)
        raise TimeoutError(f"LLM request timed out after {int(timeout)}s") from exc
    except Exception:
        _record_llm_call_result(llm, status="error", started_at=started_at)
        raise
