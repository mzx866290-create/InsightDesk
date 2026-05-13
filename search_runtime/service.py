from __future__ import annotations

import json
import ipaddress
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from .registry import (
    get_search_provider,
    normalize_provider_name,
    normalize_provider_list,
)
from .types import (
    SearchConfigError,
    SearchDocument,
    SearchProviderCapabilities,
    SearchProviderHTTPError,
    SearchResponse,
    SearchRuntimeError,
    SearchTimeoutError,
    UnsupportedSearchProviderError,
    WebResearchResult,
)

logger = logging.getLogger(__name__)

TIME_SENSITIVE_KEYWORDS = (
    "latest",
    "newest",
    "today",
    "yesterday",
    "this week",
    "recent",
    "breaking",
    "live",
    "最新",
    "今天",
    "昨天",
    "刚刚",
    "最近",
    "近期",
    "本周",
    "新闻",
    "动态",
)
DOC_INTENT_KEYWORDS = (
    "docs",
    "documentation",
    "api",
    "sdk",
    "reference",
    "manual",
    "guide",
    "文档",
    "接口",
    "参考",
    "手册",
    "教程",
)
OFFICIAL_INTENT_KEYWORDS = (
    "official",
    "官网",
    "官方",
    "release note",
    "release notes",
    "changelog",
    "公告",
)
NEWS_INTENT_KEYWORDS = (
    "news",
    "announcement",
    "press",
    "新闻",
    "公告",
    "快讯",
    "发布",
)
WEATHER_INTENT_KEYWORDS = (
    "weather",
    "forecast",
    "temperature",
    "rain",
    "aqi",
    "天气",
    "天气预报",
    "预报",
    "气温",
    "温度",
    "降雨",
    "下雨",
    "空气质量",
    "台风",
)
ZH_WEATHER_SEARCH_HINTS = (
    "中国天气网",
    "中央气象台",
    "weather.com.cn",
)
WEATHER_SOURCE_DOMAINS = (
    "weather.com.cn",
    "weather.cma.cn",
    "weather.com",
    "cma.cn",
)
LOW_SIGNAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "pinterest.com",
    "tiktok.com",
)
LOW_TRUST_DOMAINS = (
    "reddit.com",
    "quora.com",
    "zhihu.com",
    "weibo.com",
)
CONVERSATIONAL_PREFIX_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?"
        r"(?:(?:help\s+me|help)\s+)?"
        r"(?:find|look\s*up|search\s+for|tell\s+me\s+about|check)\s+",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:(?:help\s+me|help)\s+)?"
        r"(?:find|look\s*up|search\s+for|tell\s+me\s+about|i\s+want\s+to\s+know\s+about)\s+",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:"
        r"\u8bf7\u95ee|"
        r"\u5e2e\u6211\u67e5\u4e00\u4e0b|"
        r"\u5e2e\u6211\u627e\u4e00\u4e0b|"
        r"\u5e2e\u6211\u641c\u4e00\u4e0b|"
        r"\u67e5\u4e00\u4e0b|"
        r"\u627e\u4e00\u4e0b|"
        r"\u641c\u4e00\u4e0b|"
        r"\u6211\u60f3\u4e86\u89e3|"
        r"\u6211\u60f3\u77e5\u9053|"
        r"\u5173\u4e8e"
        r")\s*",
        re.IGNORECASE,
    ),
)
DOWNLOAD_SUFFIXES = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
)
DOC_HOST_HINTS = (
    "docs.",
    "developer.",
    "developers.",
    "help.",
    "support.",
    "platform.",
    "api.",
    "reference.",
)
STOP_TERMS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "what",
    "when",
    "where",
    "which",
    "how",
    "why",
    "latest",
    "today",
    "news",
    "official",
    "documentation",
    "最新",
    "今天",
    "新闻",
    "官方",
    "文档",
    "一下",
    "请问",
    "关于",
    "怎么",
    "如何",
}


@dataclass(frozen=True)
class SearchQueryPlan:
    original_query: str
    effective_query: str
    query_candidates: tuple[str, ...]
    search_depth: str
    topic: str | None
    time_range: str | None
    include_domains: tuple[str, ...]
    exclude_domains: tuple[str, ...]
    is_time_sensitive: bool
    prefer_docs: bool
    prefer_official: bool
    prefer_weather: bool


def _provider_caveats_for_plan(
    plan: SearchQueryPlan,
    capabilities: SearchProviderCapabilities,
    *,
    include_raw_content: bool,
) -> list[str]:
    caveats: list[str] = []
    provider_name = capabilities.name or "provider"
    if plan.time_range and not capabilities.supports_time_range:
        caveats.append(
            f"{provider_name} does not support strict time filtering; freshness is approximated by query hints and page dates."
        )
    if plan.topic == "news" and not capabilities.supports_news_topic:
        caveats.append(
            f"{provider_name} does not support a dedicated news topic filter; results may include general web pages."
        )
    if include_raw_content and not capabilities.supports_raw_content:
        caveats.append(
            f"{provider_name} does not provide raw content in search responses; downstream analysis relies on snippets or later page fetch."
        )
    if plan.include_domains and not capabilities.supports_domain_filter_native:
        caveats.append(
            f"{provider_name} does not support native domain filtering; domain constraints are applied after retrieval."
        )
    deduped: list[str] = []
    for item in caveats:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _source_marker(documents: list[SearchDocument]) -> str:
    return json.dumps(
        [document.to_source_item(index) for index, document in enumerate(documents, 1)],
        ensure_ascii=False,
    )


def _append_sources_marker(text: str, documents: list[SearchDocument]) -> str:
    return f"{text}\n\n__SOURCES__:{_source_marker(documents)}"


def _error_prefix(code: str) -> str:
    return f"❌ [{code}]"


def _describe_search_error(exc: Exception, *, config_message: str) -> str:
    if isinstance(exc, SearchConfigError):
        return f"{_error_prefix('search_config')} {config_message}"
    if isinstance(exc, SearchProviderHTTPError):
        if exc.status_code == 401:
            return (
                f"{_error_prefix('search_auth')} 联网搜索鉴权失败：当前搜索 provider 的 API Key 缺失或无效。"
                " 若使用 Tavily，请更新设置中的 Tavily API Key；"
                " 或配置其他搜索 provider 作为备用。"
            )
        return (
            f"{_error_prefix('search_http_error')} 联网搜索服务返回异常 "
            f"(HTTP {exc.status_code}): {exc.response_text}"
        )
    if isinstance(exc, SearchTimeoutError):
        return f"{_error_prefix('search_timeout')} 联网搜索超时，请稍后重试。"
    if isinstance(exc, UnsupportedSearchProviderError):
        return f"{_error_prefix('search_provider_unsupported')} {exc}"
    return f"{_error_prefix('search_runtime_error')} 联网搜索失败: {exc}"


def _exception_message_chain(exc: Exception, *, limit: int = 4) -> list[str]:
    messages: list[str] = []
    visited: set[int] = set()
    current: BaseException | None = exc

    while current is not None and len(messages) < limit:
        marker = id(current)
        if marker in visited:
            break
        visited.add(marker)

        text = str(current or "").strip()
        if text and text not in messages:
            messages.append(text)

        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

    return messages


def _canonicalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_pairs))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))


def _normalize_domain(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlparse(raw).netloc.lower()
    raw = raw.split("/", 1)[0].split("?", 1)[0]
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(title or "").lower())).strip()


def _sanitize_text(text: str | None, *, max_chars: int, keep_newlines: bool = False) -> str:
    cleaned = str(text or "").replace("\x00", " ").replace("\ufffd", " ")
    cleaned = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f]+", " ", cleaned)
    if keep_newlines:
        cleaned = re.sub(r"\r\n?", "\n", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    else:
        cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" \n\r\t|")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def _looks_like_download_url(url: str | None) -> bool:
    parsed = urlparse(str(url or "").strip())
    path = parsed.path.lower()
    query = parsed.query.lower()
    return path.endswith(DOWNLOAD_SUFFIXES) or any(
        marker in query for marker in ("download=", "download&", "attachment=", "export=", "catalogpdf")
    )


def _looks_like_binary_excerpt(text: str | None) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False

    lowered = raw.lower()
    if lowered.startswith("%pdf-"):
        return True
    if any(marker in lowered for marker in ("endobj", "endstream", "xref", "startxref", "/filter/flatedecode")):
        return True
    if raw.count("\ufffd") >= 3:
        return True

    sample = raw[:320]
    if not sample:
        return False
    suspicious_tokens = len(
        re.findall(r"(?:\b\d+\s+\d+\s+obj\b|/type\s*/page|/length\s+\d+|stream\b|endobj\b)", sample, flags=re.IGNORECASE)
    )
    weird_punctuation_ratio = sum(ch in "<>{}[]/%\\" for ch in sample) / max(1, len(sample))
    return suspicious_tokens >= 2 or weird_punctuation_ratio >= 0.18


def _content_readability_score(title: str, snippet: str) -> float:
    text = _sanitize_text(f"{title} {snippet}", max_chars=600)
    if not text:
        return 0.0
    if _looks_like_binary_excerpt(text):
        return 0.0

    chars = len(text)
    word_like = len(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", text))
    signal_ratio = word_like / max(1, chars)
    punctuation_ratio = sum(ch in "<>{}[]/%\\" for ch in text) / max(1, chars)

    score = 0.35 + 0.45 * signal_ratio + 0.2 * min(1.0, chars / 220)
    if punctuation_ratio >= 0.15:
        score -= 0.18
    return min(1.0, max(0.0, score))


def _titles_similar(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if left in right or right in left:
        return min(len(left), len(right)) >= 18
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return overlap >= 0.8 and min(len(left_tokens), len(right_tokens)) >= 3


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    lowered = str(text or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _extract_domain_filters(query: str) -> tuple[list[str], str]:
    include_domains: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        domain = _normalize_domain(match.group(1))
        if domain and domain not in include_domains:
            include_domains.append(domain)
        return " "

    cleaned = re.sub(
        r"(?:site:|domain:|站点:|域名:)\s*([A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        _replace,
        str(query or ""),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return include_domains, cleaned


def _append_search_hints(query: str, hints: Sequence[str]) -> str:
    result = str(query or "").strip()
    lowered = result.lower()
    for hint in hints:
        normalized = hint.strip()
        if not normalized:
            continue
        if normalized.lower() in lowered:
            continue
        result = f"{result} {normalized}".strip()
        lowered = result.lower()
    return result


def _strip_conversational_prefixes(query: str) -> str:
    cleaned = str(query or "").strip()
    if not cleaned:
        return ""

    while cleaned:
        updated = cleaned
        for pattern in CONVERSATIONAL_PREFIX_PATTERNS:
            updated = pattern.sub("", updated).strip()
        updated = updated.strip(" ,，。:：;；!?！？-")
        if updated == cleaned:
            break
        cleaned = updated

    return re.sub(r"\s+", " ", cleaned).strip()


def _build_keyword_focus_query(text: str) -> str:
    tokens = re.findall(
        r"[A-Za-z][A-Za-z0-9_.:+/#-]{1,}|[\u4e00-\u9fff]{2,}|\d{4}",
        str(text or ""),
    )
    selected: list[str] = []
    seen: set[str] = set()
    for item in tokens:
        token = item.strip()
        normalized = token.lower()
        if len(token) < 2 or normalized in STOP_TERMS or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(token)
        if len(selected) >= 8:
            break
    return " ".join(selected).strip()


def _dedupe_query_candidates(candidates: Sequence[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for item in candidates:
        normalized = re.sub(r"\s+", " ", str(item or "")).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return tuple(deduped)


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content or "").strip()


def _extract_json_payload(text: str) -> object | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _extract_planned_query(text: str) -> str:
    payload = _extract_json_payload(text)
    if isinstance(payload, dict):
        for key in ("query", "search_query", "optimized_query", "primary_query"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        raw_queries = payload.get("queries")
        if isinstance(raw_queries, list):
            for item in raw_queries:
                value = str(item.get("query") if isinstance(item, dict) else item).strip()
                if value:
                    return value

    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.strip("\"'` \n\r\t")
    for prefix in ("query:", "search query:", "optimized query:", "primary query:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    return re.split(r"[\r\n]+", cleaned, maxsplit=1)[0].strip()


async def rewrite_search_query_with_llm(
    llm: object | None,
    user_query: str,
    *,
    chat_history: str = "",
    timeout_seconds: int | None = None,
) -> str:
    """Let the model choose the best web-search query, with deterministic fallback."""
    fallback_query = rewrite_search_query_for_web(user_query)
    if llm is None:
        return fallback_query

    normalized_query = str(user_query or "").strip()
    if not normalized_query:
        return fallback_query

    context_block = f"\nConversation context:\n{chat_history.strip()}\n" if chat_history.strip() else ""
    prompt = f"""You are a web search strategy planner.
Return JSON only:
{{
  "query": "one best search-engine query"
}}

Rules:
- Decide the best query from the user's information need; do not rely on backend hard-coded local rules.
- Keep exact dates, locations, organization names, product names, and domain constraints from the user.
- Add official/public-source wording only when it helps the intent, for example announcements, policy, documentation, recruitment, filings, or datasets.
- Do not invent specific websites, domains, cities, or agencies that the user did not mention.
- Prefer concise search terms over full conversational questions.

User query: {normalized_query}
{context_block}"""

    try:
        if timeout_seconds is not None:
            import asyncio

            response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout_seconds)
        else:
            response = await llm.ainvoke(prompt)
        planned_query = _extract_planned_query(_response_text(response))
        normalized = rewrite_search_query_for_web(planned_query or normalized_query)
        return normalized or fallback_query
    except Exception:
        logger.exception("LLM search query planning failed")
        return fallback_query


def _apply_query_preferences(
    query: str,
    *,
    prefer_official: bool,
    prefer_news: bool,
    include_domains: Sequence[str],
) -> str:
    effective_query = str(query or "").strip()
    if prefer_news:
        hints = (
            ("latest news",)
            if not _contains_cjk(effective_query)
            else ("\u6700\u65b0", "\u65b0\u95fb")
        )
        return _append_search_hints(effective_query, hints)
    return effective_query


def _build_query_candidates(
    *,
    original_query: str,
    base_query: str,
    prefer_official: bool,
    prefer_news: bool,
    include_domains: Sequence[str],
    prefer_weather: bool = False,
) -> tuple[str, tuple[str, ...]]:
    normalized_base_query = _strip_conversational_prefixes(base_query) or str(base_query or "").strip()
    effective_query = _apply_query_preferences(
        normalized_base_query,
        prefer_official=prefer_official,
        prefer_news=prefer_news,
        include_domains=include_domains,
    )
    if prefer_weather and _contains_cjk(normalized_base_query):
        effective_query = _append_search_hints(effective_query, ZH_WEATHER_SEARCH_HINTS)
    keyword_focus_query = _build_keyword_focus_query(normalized_base_query)
    keyword_effective_query = _apply_query_preferences(
        keyword_focus_query,
        prefer_official=prefer_official,
        prefer_news=prefer_news,
        include_domains=include_domains,
    )
    if prefer_weather and _contains_cjk(normalized_base_query):
        keyword_effective_query = _append_search_hints(
            keyword_effective_query,
            ZH_WEATHER_SEARCH_HINTS,
        )
    return effective_query, _dedupe_query_candidates(
        (
            effective_query,
            keyword_effective_query,
            normalized_base_query,
            keyword_focus_query,
            original_query,
        )
    )


def _is_query_retryable_error(exc: Exception) -> bool:
    return isinstance(exc, SearchProviderHTTPError) and exc.status_code in {400, 422}


def _infer_time_range(query: str) -> str | None:
    lowered = str(query or "").lower()
    if any(keyword in lowered for keyword in ("today", "breaking", "live", "today's", "今天", "刚刚")):
        return "day"
    if any(keyword in lowered for keyword in ("this week", "latest", "recent", "newest", "本周", "最新", "近期", "最近", "新闻")):
        return "week"
    if any(keyword in lowered for keyword in ("this month", "month", "本月")):
        return "month"
    return None


def _extract_query_terms(text: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_.:-]{1,}|[\u4e00-\u9fff]{2,}|\d{4}", str(text or ""))
    normalized: list[str] = []
    for item in candidates:
        token = item.strip().lower()
        if len(token) < 2 or token in STOP_TERMS:
            continue
        if token not in normalized:
            normalized.append(token)
    return normalized[:12]


def _normalize_provider_score(raw_score: float | None) -> float:
    if raw_score is None:
        return 0.55
    score = float(raw_score)
    if 0.0 <= score <= 1.0:
        return score
    return max(0.0, min(1.0, score / 100.0 if score > 10 else score / 10.0))


def _parse_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None

    if parsed is None:
        match = re.search(r"(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?", raw)
        if not match:
            return None
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3) or "1")
        try:
            parsed = datetime(year, month, day, tzinfo=UTC)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_doc_like_domain(domain: str) -> bool:
    lowered = _normalize_domain(domain)
    return any(hint in lowered for hint in DOC_HOST_HINTS) or lowered.endswith((".gov", ".edu", ".ac.uk"))


def _domain_matches(domain: str | None, patterns: Sequence[str]) -> bool:
    normalized = _normalize_domain(domain)
    if not normalized:
        return False
    for item in patterns:
        pattern = _normalize_domain(item)
        if not pattern:
            continue
        if normalized == pattern or normalized.endswith(f".{pattern}"):
            return True
    return False


def _build_query_plan(
    query: str,
    *,
    search_depth: str = "basic",
    topic: str | None = None,
    time_range: str | None = None,
) -> SearchQueryPlan:
    original_query = str(query or "").strip()
    include_domains, stripped_query = _extract_domain_filters(original_query)
    base_query = stripped_query or original_query
    normalized_base_query = _strip_conversational_prefixes(base_query) or base_query

    is_time_sensitive = _contains_any(normalized_base_query, TIME_SENSITIVE_KEYWORDS)
    prefer_weather = _contains_any(normalized_base_query, WEATHER_INTENT_KEYWORDS)
    prefer_docs = _contains_any(normalized_base_query, DOC_INTENT_KEYWORDS)
    prefer_official = prefer_docs or _contains_any(normalized_base_query, OFFICIAL_INTENT_KEYWORDS)
    prefer_news = (
        _contains_any(normalized_base_query, NEWS_INTENT_KEYWORDS) or is_time_sensitive
    ) and not prefer_weather

    effective_query, query_candidates = _build_query_candidates(
        original_query=original_query,
        base_query=base_query,
        prefer_official=prefer_official,
        prefer_news=prefer_news,
        include_domains=include_domains,
        prefer_weather=prefer_weather,
    )
    if False and prefer_official and not include_domains:
        hints = ("official documentation", "release notes") if not _contains_cjk(base_query) else ("官网", "官方文档")
        effective_query = _append_search_hints(effective_query, hints)
    elif False and prefer_news:
        hints = ("latest news",) if not _contains_cjk(base_query) else ("最新", "新闻")
        effective_query = _append_search_hints(effective_query, hints)

    resolved_topic = str(topic or "").strip().lower() or None
    if resolved_topic is None and prefer_news:
        resolved_topic = "news"

    resolved_time_range = str(time_range or "").strip().lower() or None
    if prefer_weather:
        resolved_time_range = None
    elif resolved_time_range is None:
        resolved_time_range = _infer_time_range(normalized_base_query)

    resolved_search_depth = str(search_depth or "basic").strip().lower() or "basic"
    if resolved_search_depth == "basic" and (is_time_sensitive or prefer_docs or include_domains):
        resolved_search_depth = "advanced"

    exclude_domains = tuple(domain for domain in LOW_SIGNAL_DOMAINS if domain not in include_domains)
    return SearchQueryPlan(
        original_query=original_query,
        effective_query=effective_query,
        query_candidates=query_candidates,
        search_depth=resolved_search_depth,
        topic=resolved_topic,
        time_range=resolved_time_range,
        include_domains=tuple(include_domains),
        exclude_domains=exclude_domains,
        is_time_sensitive=is_time_sensitive,
        prefer_docs=prefer_docs,
        prefer_official=prefer_official,
        prefer_weather=prefer_weather,
    )


def rewrite_search_query_for_web(
    query: str,
    *,
    search_depth: str = "basic",
    topic: str | None = None,
    time_range: str | None = None,
) -> str:
    return _build_query_plan(
        query,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
    ).effective_query


def _compute_domain_trust(domain: str | None, plan: SearchQueryPlan) -> float:
    normalized = _normalize_domain(domain)
    if not normalized:
        return 0.45 if plan.is_time_sensitive else 0.6
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        return 0.18
    if _domain_matches(normalized, plan.include_domains):
        return 1.0
    if _domain_matches(normalized, LOW_SIGNAL_DOMAINS):
        return 0.1
    if _domain_matches(normalized, LOW_TRUST_DOMAINS):
        return 0.4
    if normalized.endswith((".gov", ".edu", ".ac.uk")):
        return 0.95
    if plan.prefer_weather and _domain_matches(normalized, WEATHER_SOURCE_DOMAINS):
        return 0.94
    if plan.prefer_official and _is_doc_like_domain(normalized):
        return 0.92
    if _is_doc_like_domain(normalized):
        return 0.88
    return 0.72


def _compute_freshness_score(published_at: str | None, plan: SearchQueryPlan) -> float:
    parsed = _parse_datetime(published_at)
    if parsed is None:
        return 0.35 if plan.is_time_sensitive else 0.65

    age_days = max(0.0, (datetime.now(UTC) - parsed).total_seconds() / 86400.0)
    if age_days <= 1:
        return 1.0
    if age_days <= 7:
        return 0.95
    if age_days <= 30:
        return 0.88
    if age_days <= 180:
        return 0.72
    if age_days <= 365:
        return 0.58
    return 0.32 if plan.is_time_sensitive else 0.48


def _score_document(
    document: SearchDocument,
    *,
    query_terms: Sequence[str],
    plan: SearchQueryPlan,
) -> SearchDocument:
    sanitized_title = _sanitize_text(document.title, max_chars=240)
    sanitized_snippet = _sanitize_text(document.snippet, max_chars=600)
    sanitized_raw_text = _sanitize_text(document.raw_text, max_chars=8000, keep_newlines=True)
    normalized_domain = _normalize_domain(document.domain or urlparse(document.url).netloc)
    title_blob = _normalize_title(sanitized_title)
    snippet_blob = _normalize_title(sanitized_raw_text or sanitized_snippet)

    matched_terms: list[str] = []
    title_hits = 0
    snippet_hits = 0
    for term in query_terms:
        if term in title_blob:
            title_hits += 1
            matched_terms.append(term)
        elif term in snippet_blob:
            snippet_hits += 1
            matched_terms.append(term)

    match_score = min(1.0, 0.2 + 0.35 * min(1.0, title_hits / max(1, min(len(query_terms), 3))) + 0.2 * min(1.0, snippet_hits / max(1, min(len(query_terms), 4))))
    if not query_terms:
        match_score = 0.6

    provider_score = _normalize_provider_score(document.score)
    trust_score = _compute_domain_trust(normalized_domain, plan)
    freshness_score = _compute_freshness_score(document.published_at, plan)
    readability_score = _content_readability_score(sanitized_title, sanitized_raw_text or sanitized_snippet)
    download_like = _looks_like_download_url(document.url)
    binary_like = _looks_like_binary_excerpt(sanitized_raw_text or sanitized_snippet or sanitized_title)

    confidence = (
        0.4 * match_score
        + 0.25 * trust_score
        + 0.2 * freshness_score
        + 0.15 * provider_score
    )
    if _domain_matches(normalized_domain, plan.include_domains):
        confidence = min(1.0, confidence + 0.08)
    if readability_score >= 0.8:
        confidence = min(1.0, confidence + 0.05)
    elif readability_score < 0.45:
        confidence = max(0.0, confidence - 0.12)
    if download_like:
        confidence = max(0.0, confidence - 0.08)
    if binary_like:
        confidence = max(0.0, confidence - 0.45)

    evidence_tags: list[str] = []
    if _domain_matches(normalized_domain, plan.include_domains):
        evidence_tags.append("explicit_domain_match")
    if plan.prefer_official and _is_doc_like_domain(normalized_domain):
        evidence_tags.append("official_domain")
    if download_like:
        evidence_tags.append("download_url")
    if freshness_score >= 0.9:
        evidence_tags.append("fresh_source")
    if title_hits > 0:
        evidence_tags.append("title_term_match")
    if snippet_hits > 0:
        evidence_tags.append("snippet_term_match")
    if provider_score >= 0.8:
        evidence_tags.append("provider_high_score")
    if readability_score >= 0.8:
        evidence_tags.append("high_readability")
    elif readability_score < 0.45:
        evidence_tags.append("low_readability")
    if binary_like:
        evidence_tags.append("binary_excerpt")

    if confidence >= 0.75:
        source_quality = "high"
    elif confidence >= 0.55:
        source_quality = "medium"
    else:
        source_quality = "low"

    return SearchDocument(
        doc_id=document.doc_id,
        provider=document.provider,
        source_type=document.source_type,
        title=sanitized_title or document.title,
        url=document.url,
        snippet=sanitized_snippet,
        raw_text=sanitized_raw_text,
        published_at=document.published_at,
        fetched_at=document.fetched_at,
        domain=normalized_domain or document.domain,
        author=document.author,
        score=round(confidence, 4),
        provider_score=round(provider_score, 4),
        confidence=round(confidence, 4),
        trust_score=round(trust_score, 4),
        freshness_score=round(freshness_score, 4),
        source_quality=source_quality,
        retrieval_query=plan.effective_query,
        matched_terms=list(dict.fromkeys(matched_terms)),
        evidence_tags=list(dict.fromkeys([*document.evidence_tags, *evidence_tags])),
    )


def _is_weather_relevant_document(document: SearchDocument) -> bool:
    domain = _normalize_domain(document.domain or urlparse(document.url).netloc)
    if _domain_matches(domain, WEATHER_SOURCE_DOMAINS):
        return True

    text = _normalize_title(f"{document.title} {document.snippet} {document.raw_text}")
    return any(keyword.lower() in text for keyword in WEATHER_INTENT_KEYWORDS)


def _prepare_search_documents(
    documents: Sequence[SearchDocument],
    *,
    plan: SearchQueryPlan,
) -> list[SearchDocument]:
    query_terms = _extract_query_terms(plan.original_query)
    prepared: list[SearchDocument] = []

    for document in documents:
        normalized_domain = _normalize_domain(document.domain or urlparse(document.url).netloc)
        if plan.include_domains and not _domain_matches(normalized_domain, plan.include_domains):
            continue
        if plan.exclude_domains and _domain_matches(normalized_domain, plan.exclude_domains):
            continue
        scored = _score_document(document, query_terms=query_terms, plan=plan)
        if plan.prefer_weather and not _is_weather_relevant_document(scored):
            continue
        text_payload = (scored.raw_text or scored.snippet or scored.title).strip()
        if "binary_excerpt" in scored.evidence_tags:
            continue
        if "download_url" in scored.evidence_tags and float(scored.confidence or 0.0) < 0.62:
            continue
        if not text_payload:
            continue
        if len(text_payload) < 8 and len((scored.title or "").strip()) < 10 and float(scored.confidence or 0.0) < 0.5:
            continue
        prepared.append(scored)

    prepared.sort(
        key=lambda item: (
            float(item.confidence or 0.0),
            float(item.trust_score or 0.0),
            float(item.freshness_score or 0.0),
            len(item.matched_terms or []),
        ),
        reverse=True,
    )
    return prepared


def dedupe_search_documents(
    documents: Sequence[SearchDocument],
    *,
    limit: int | None = None,
    max_per_domain: int | None = None,
) -> list[SearchDocument]:
    deduped: list[SearchDocument] = []
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    seen_title_snippets: set[tuple[str, str]] = set()
    domain_counts: dict[str, int] = {}

    for document in documents:
        canonical_url = _canonicalize_url(document.url)
        normalized_title = _normalize_title(document.title)
        normalized_snippet = re.sub(r"\s+", " ", (document.raw_text or document.snippet or "").lower()).strip()[:180]
        normalized_domain = _normalize_domain(document.domain) or _normalize_domain(canonical_url)

        if canonical_url and canonical_url in seen_urls:
            continue
        if normalized_title and any(_titles_similar(normalized_title, item) for item in seen_titles):
            if not canonical_url or not normalized_snippet:
                continue
            title_signature = (normalized_title, normalized_snippet)
            if title_signature in seen_title_snippets:
                continue
            seen_title_snippets.add(title_signature)
        if max_per_domain is not None and normalized_domain:
            if domain_counts.get(normalized_domain, 0) >= max_per_domain:
                continue

        normalized_document = SearchDocument(
            doc_id=document.doc_id,
            provider=document.provider,
            source_type=document.source_type,
            title=document.title,
            url=canonical_url or document.url,
            snippet=document.snippet,
            raw_text=document.raw_text,
            published_at=document.published_at,
            fetched_at=document.fetched_at,
            domain=normalized_domain,
            author=document.author,
            score=document.score,
            provider_score=document.provider_score,
            confidence=document.confidence,
            trust_score=document.trust_score,
            freshness_score=document.freshness_score,
            source_quality=document.source_quality,
            retrieval_query=document.retrieval_query,
            matched_terms=list(document.matched_terms or []),
            evidence_tags=list(document.evidence_tags or []),
        )

        if canonical_url:
            seen_urls.add(canonical_url)
        if normalized_title:
            seen_titles.append(normalized_title)
        if normalized_title and normalized_snippet:
            seen_title_snippets.add((normalized_title, normalized_snippet))
        if normalized_domain:
            domain_counts[normalized_domain] = domain_counts.get(normalized_domain, 0) + 1

        deduped.append(normalized_document)
        if limit is not None and len(deduped) >= limit:
            break

    return deduped


async def search_web(
    query: str,
    *,
    max_results: int = 5,
    provider: str | None = None,
    providers: Sequence[str] | None = None,
    search_depth: str = "basic",
    topic: str | None = None,
    time_range: str | None = None,
    include_answer: bool = True,
    include_raw_content: bool = False,
) -> SearchResponse:
    plan = _build_query_plan(
        query,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
    )
    explicit_provider_list = providers is not None
    provider_names = normalize_provider_list(providers if explicit_provider_list else provider)
    responses: list[SearchResponse] = []
    errors: list[Exception] = []
    provider_capabilities: list[SearchProviderCapabilities] = []
    provider_caveats: list[str] = []

    for provider_name in provider_names:
        try:
            provider_instance = get_search_provider(provider_name)
            capability = (
                provider_instance.get_capabilities()
                if hasattr(provider_instance, "get_capabilities")
                else SearchProviderCapabilities(name=provider_name)
            )
            response = None
            query_candidates = plan.query_candidates or (plan.effective_query,)
            for index, candidate_query in enumerate(query_candidates):
                try:
                    candidate_response = await provider_instance.search(
                        candidate_query,
                        max_results=max_results,
                        search_depth=plan.search_depth,
                        include_answer=include_answer,
                        topic=plan.topic,
                        time_range=plan.time_range,
                        include_raw_content=include_raw_content,
                    )
                except SearchRuntimeError as exc:
                    if _is_query_retryable_error(exc) and index < len(query_candidates) - 1:
                        continue
                    raise

                candidate_response.rewritten_query = candidate_query
                for document in candidate_response.results:
                    document.retrieval_query = candidate_query
                response = candidate_response
                has_usable_results = bool(
                    _prepare_search_documents(candidate_response.results, plan=plan)
                )
                if (
                    (candidate_response.results and (has_usable_results or not plan.prefer_weather))
                    or index == len(query_candidates) - 1
                ):
                    if candidate_query != plan.effective_query and candidate_response.results:
                        fallback_note = (
                            f"{provider_name} retried the search with a simplified query variant."
                        )
                        if fallback_note not in provider_caveats:
                            provider_caveats.append(fallback_note)
                    break

            if response is None:
                continue
            if (
                plan.prefer_weather
                and response.results
                and not _prepare_search_documents(response.results, plan=plan)
            ):
                provider_caveats.append(
                    f"{provider_name} returned results without weather signals; trying another provider."
                )
                continue
        except SearchRuntimeError as exc:
            logger.warning("search_web runtime issue provider=%s error=%s", provider_name, exc)
            errors.append(exc)
            continue
        except Exception as exc:
            logger.exception("search_web failed provider=%s", provider_name)
            errors.append(exc)
            continue

        provider_capabilities.append(capability)
        for caveat in _provider_caveats_for_plan(
            plan,
            capability,
            include_raw_content=include_raw_content,
        ):
            if caveat not in provider_caveats:
                provider_caveats.append(caveat)
        responses.append(response)
        if response.results and not explicit_provider_list:
            break

    if not responses:
        if errors:
            first_error = errors[0]
            if isinstance(first_error, SearchRuntimeError):
                raise first_error
            raise SearchRuntimeError(str(first_error)) from first_error
        return SearchResponse(
            query=query,
            provider="+".join(provider_names),
            results=[],
            search_depth=plan.search_depth,
            rewritten_query=(plan.query_candidates[0] if plan.query_candidates else plan.effective_query),
            topic=plan.topic,
            time_range=plan.time_range,
            include_domains=list(plan.include_domains),
            exclude_domains=list(plan.exclude_domains),
            provider_capabilities=provider_capabilities,
            provider_caveats=provider_caveats,
        )

    merged_results: list[SearchDocument] = []
    provider_labels: list[str] = []
    answer = ""
    for response in responses:
        provider_labels.append(response.provider)
        if response.answer and not answer:
            answer = response.answer
        merged_results.extend(response.results)

    ranked_results = _prepare_search_documents(merged_results, plan=plan)

    max_per_domain = None if plan.include_domains else 2
    rewritten_query = next(
        (
            response.rewritten_query
            for response in responses
            if response.results and response.rewritten_query
        ),
        plan.query_candidates[0] if plan.query_candidates else plan.effective_query,
    )
    return SearchResponse(
        query=query,
        provider=" + ".join(dict.fromkeys(provider_labels)),
        results=dedupe_search_documents(ranked_results, limit=max_results, max_per_domain=max_per_domain),
        answer=answer,
        search_depth=plan.search_depth,
        rewritten_query=rewritten_query,
        topic=plan.topic,
        time_range=plan.time_range,
        include_domains=list(plan.include_domains),
        exclude_domains=list(plan.exclude_domains),
        provider_capabilities=provider_capabilities,
        provider_caveats=provider_caveats,
    )


def format_search_results(query: str, response: SearchResponse) -> str:
    output: list[str] = []

    if response.answer:
        output.append(f"【AI 总结】\n{response.answer}\n")

    header = f"【搜索结果 - {query}】"
    if response.rewritten_query and response.rewritten_query != query:
        header += f"\n检索词: {response.rewritten_query}"
    output.append(header)

    for index, result in enumerate(response.results, 1):
        meta_bits: list[str] = []
        if result.domain:
            meta_bits.append(f"域名: {result.domain}")
        if result.published_at:
            meta_bits.append(f"发布时间: {result.published_at}")
        if result.confidence is not None:
            meta_bits.append(f"置信度: {result.confidence:.2f}")
        if result.source_quality:
            meta_bits.append(f"质量: {result.source_quality}")

        output.append(
            f"{index}. {result.title or '无标题'}\n"
            f"链接: {result.url}\n"
            f"{' | '.join(meta_bits) if meta_bits else '来源元数据: 无'}\n"
            f"摘要: {result.snippet}"
        )

    return _append_sources_marker("\n\n---\n\n".join(output), response.results)


async def search_web_text(
    query: str,
    *,
    max_results: int = 5,
    provider: str | None = None,
    search_depth: str = "basic",
) -> str:
    provider_name = normalize_provider_name(provider) if provider else None

    try:
        response = await search_web(
            query,
            max_results=max_results,
            provider=provider_name,
            search_depth=search_depth,
            include_answer=True,
        )
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider，无法使用联网搜索功能。",
        )
    except Exception as exc:
        logger.exception("search_web_text failed provider=%s", provider_name or "default")
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider，无法使用联网搜索功能。",
        )

    if not response.results:
        if response.include_domains:
            return f"未找到与指定站点相关的搜索结果: {', '.join(response.include_domains)}"
        return f"未找到相关搜索结果: {query}"

    return format_search_results(query, response)


async def quick_answer_text(
    user_question: str,
    *,
    provider: str | None = None,
    max_results: int = 3,
    search_depth: str = "basic",
) -> str:
    provider_name = normalize_provider_name(provider) if provider else None

    try:
        response = await search_web(
            user_question,
            max_results=max_results,
            provider=provider_name,
            search_depth=search_depth,
            include_answer=True,
        )
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider。",
        )
    except Exception as exc:
        logger.exception("quick_answer_text failed provider=%s", provider_name or "default")
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider。",
        )

    if response.answer:
        top_sources = [item.title for item in response.results[:2] if item.title]
        source_line = f"\n来源: {'；'.join(top_sources)}" if top_sources else ""
        return _append_sources_marker(f"【网络搜索答案】\n{response.answer}{source_line}", response.results)
    if response.results:
        return format_search_results(user_question, response)
    return "未能生成答案，请使用 web_search 查看详细搜索结果。"


async def fetch_webpage_document(url: str, *, max_chars: int = 8000) -> SearchDocument:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise SearchRuntimeError("缺少 beautifulsoup4 依赖，请运行: pip install beautifulsoup4") from exc

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("fetch_webpage_document HTTP error status=%d url=%s", exc.response.status_code, url)
        raise SearchProviderHTTPError(exc.response.status_code, exc.response.text) from exc
    except httpx.TimeoutException as exc:
        logger.warning("fetch_webpage_document timeout url=%s", url)
        raise SearchTimeoutError("网页请求超时") from exc
    except Exception as exc:
        logger.exception("fetch_webpage_document failed url=%s", url)
        raise SearchRuntimeError(f"抓取网页失败: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).split("\n") if line.strip()]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n...[内容已截断]"

    parsed = urlparse(url)
    plan = _build_query_plan(url)
    document = SearchDocument(
        doc_id=f"fetch:{url}",
        provider="fetch",
        source_type="web",
        title=url,
        url=_canonicalize_url(url) or url,
        snippet=text[:200],
        raw_text=text,
        domain=_normalize_domain(parsed.netloc) or None,
        retrieval_query=url,
        evidence_tags=["page_fetch"],
    )
    return _score_document(document, query_terms=_extract_query_terms(url), plan=plan)


async def fetch_webpage_text(url: str, *, max_chars: int = 8000) -> str:
    try:
        document = await fetch_webpage_document(url, max_chars=max_chars)
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="缺少网页抓取依赖。",
        )
    return _append_sources_marker(f"【网页内容 - {url}】\n\n{document.raw_text}", [document])


async def run_web_research(
    query: str,
    *,
    planned_query: str | None = None,
    max_results: int = 8,
    provider: str | None = None,
    providers: Sequence[str] | None = None,
    search_depth: str = "advanced",
    topic: str | None = None,
    time_range: str | None = None,
) -> WebResearchResult:
    provider_names = providers if providers is not None else provider
    search_query = str(planned_query or "").strip() or query
    response = await search_web(
        search_query,
        max_results=max_results,
        providers=provider_names if isinstance(provider_names, Sequence) and not isinstance(provider_names, str) else None,
        provider=provider if isinstance(provider_names, str) or provider_names is None else None,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
        include_answer=True,
    )

    highlights: list[str] = []
    for result in response.results[:3]:
        snippet = result.snippet.strip()
        if snippet:
            highlights.append(snippet if len(snippet) <= 160 else f"{snippet[:157]}...")

    summary = (response.answer or "").strip()
    return WebResearchResult(
        query=query,
        provider=response.provider or normalize_provider_name(provider),
        provider_summary=response.provider or normalize_provider_name(provider),
        answer=response.answer,
        summary=summary,
        rewritten_query=response.rewritten_query or search_query,
        sources=response.results,
        highlights=highlights,
        provider_capabilities=response.provider_capabilities,
        caveats=list(response.provider_caveats),
    )


def describe_runtime_error(exc: Exception) -> str:
    if isinstance(exc, SearchRuntimeError):
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider，无法使用联网搜索功能。",
        )
    messages = _exception_message_chain(exc)
    if not messages:
        return str(exc)
    if len(messages) == 1:
        return messages[0]
    return f"{messages[0]} | 原因: {' | '.join(messages[1:])}"
