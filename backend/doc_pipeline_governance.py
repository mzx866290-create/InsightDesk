"""Document governance: dedupe, versioning and metadata enrichment.

Split out of backend.doc_pipeline as a mixin; composed by DocPipeline.
"""

"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, List
from langchain_core.documents import Document



logger = logging.getLogger(__name__)

from backend.doc_pipeline_constants import (  # noqa: F401
    KEYWORD_TOKEN_PATTERN,
    VERSION_TOKEN_PATTERN,
    DATE_TOKEN_PATTERN,
    COMPACT_DATE_TOKEN_PATTERN,
    EXPIRY_HINT_PATTERN,
)


class DocPipelineGovernanceMixin:
    @staticmethod
    def _normalize_source_key(source: Any) -> str:
        normalized = str(source or "").strip().lower()
        normalized = normalized.replace("\\", "/")
        return re.sub(r"\s+", " ", normalized)

    @staticmethod
    def _normalize_topic_key(source: Any) -> str:
        stem = Path(str(source or "").strip()).stem.lower()
        stem = COMPACT_DATE_TOKEN_PATTERN.sub(" ", stem)
        stem = DATE_TOKEN_PATTERN.sub(" ", stem)
        stem = VERSION_TOKEN_PATTERN.sub(" ", stem)
        stem = re.sub(
            r"(最新版|最新|终版|定稿|旧版|历史版|归档|archive|draft|final|old|new)",
            " ",
            stem,
            flags=re.IGNORECASE,
        )
        stem = re.sub(r"[_\W]+", " ", stem)
        stem = re.sub(r"\s+", " ", stem).strip()
        return stem or Path(str(source or "").strip()).stem.lower()

    @staticmethod
    def _parse_date_parts(year: str, month: str, day: str) -> int | None:
        try:
            parsed = time.strptime(
                f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
                "%Y-%m-%d",
            )
        except ValueError:
            return None
        return int(time.mktime(parsed))

    def _extract_date_candidates(self, text: Any) -> list[int]:
        normalized = str(text or "")
        timestamps: list[int] = []
        for match in DATE_TOKEN_PATTERN.finditer(normalized):
            timestamp = self._parse_date_parts(match.group(1), match.group(2), match.group(3))
            if timestamp is not None:
                timestamps.append(timestamp)
        for match in COMPACT_DATE_TOKEN_PATTERN.finditer(normalized):
            timestamp = self._parse_date_parts(match.group(1), match.group(2), match.group(3))
            if timestamp is not None:
                timestamps.append(timestamp)
        return timestamps

    def _extract_expiry_timestamp(self, text: Any) -> int | None:
        normalized = str(text or "")
        match = EXPIRY_HINT_PATTERN.search(normalized)
        if not match:
            return None
        if match.group(2) and match.group(3) and match.group(4):
            return self._parse_date_parts(match.group(2), match.group(3), match.group(4))
        if match.group(5) and match.group(6) and match.group(7):
            return self._parse_date_parts(match.group(5), match.group(6), match.group(7))
        return None

    @staticmethod
    def _extract_version_number(text: Any) -> float:
        match = VERSION_TOKEN_PATTERN.search(str(text or ""))
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _extract_version_label(text: Any) -> str:
        match = VERSION_TOKEN_PATTERN.search(str(text or ""))
        if not match:
            return ""
        return match.group(0).strip(" _-")

    @staticmethod
    def _content_hash(text: Any) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        return hashlib.sha1(normalized.encode("utf-8", "ignore")).hexdigest()

    def _governance_rank(self, metadata: dict[str, Any]) -> tuple[int, float, int, int, str]:
        source_updated_at = int(float(metadata.get("kb_source_updated_at") or 0) or 0)
        effective_ts = int(float(metadata.get("kb_effective_ts") or 0) or 0)
        version_number = float(metadata.get("kb_version_number") or 0.0)
        expiry_ts = int(float(metadata.get("kb_expiry_ts") or 0) or 0)
        is_expired = bool(metadata.get("kb_is_expired")) or (
            expiry_ts > 0 and expiry_ts < int(time.time())
        )
        source_key = str(metadata.get("kb_source_key") or "").strip()
        return (
            0 if is_expired else 1,
            version_number,
            effective_ts,
            source_updated_at,
            source_key,
        )

    def _apply_document_governance_metadata(self, doc: Document) -> Document:
        metadata = dict(doc.metadata or {})
        source = str(metadata.get("source") or metadata.get("title") or "unknown").strip() or "unknown"
        file_path = str(metadata.get("file_path") or "").strip()
        source_key = str(metadata.get("kb_source_key") or self._normalize_source_key(source))
        topic_key = str(metadata.get("kb_topic_key") or self._normalize_topic_key(source))
        content_hash = str(metadata.get("kb_content_hash") or self._content_hash(doc.page_content))
        version_label = str(metadata.get("kb_version_label") or self._extract_version_label(source))
        if not version_label:
            version_label = self._extract_version_label(str(doc.page_content or "")[:500])
        version_number = float(metadata.get("kb_version_number") or self._extract_version_number(source))
        if version_number <= 0:
            version_number = self._extract_version_number(str(doc.page_content or "")[:500])
        source_updated_at = float(metadata.get("kb_source_updated_at") or 0.0)
        if source_updated_at <= 0 and file_path and os.path.exists(file_path):
            try:
                source_updated_at = float(os.path.getmtime(file_path))
            except OSError:
                source_updated_at = 0.0

        effective_ts = int(float(metadata.get("kb_effective_ts") or 0) or 0)
        if effective_ts <= 0:
            source_dates = self._extract_date_candidates(source)
            effective_ts = max(source_dates) if source_dates else 0

        expiry_ts = int(float(metadata.get("kb_expiry_ts") or 0) or 0)
        if expiry_ts <= 0:
            expiry_ts = int(self._extract_expiry_timestamp(str(doc.page_content or "")[:1600]) or 0)
        is_expired = bool(metadata.get("kb_is_expired")) or (
            expiry_ts > 0 and expiry_ts < int(time.time())
        )

        metadata.update(
            {
                "kb_source_key": source_key,
                "kb_topic_key": topic_key,
                "kb_content_hash": content_hash,
                "kb_dedupe_signature": f"{topic_key}::{content_hash}",
                "kb_version_label": version_label,
                "kb_version_number": version_number,
                "kb_effective_ts": effective_ts,
                "kb_expiry_ts": expiry_ts,
                "kb_is_expired": is_expired,
                "kb_source_updated_at": source_updated_at,
            }
        )
        return Document(page_content=doc.page_content, metadata=metadata)

    def _dedupe_index_documents(self, documents: List[Document]) -> List[Document]:
        unique_docs: list[Document] = []
        seen_signatures: set[str] = set()
        for doc in documents:
            signature = str((doc.metadata or {}).get("kb_dedupe_signature") or "").strip()
            if not signature:
                signature = self._content_hash(doc.page_content)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_docs.append(doc)
        return unique_docs

    def _apply_topic_version_status(self, documents: List[Document]) -> List[Document]:
        winning_source_by_topic: dict[str, str] = {}
        grouped_sources: dict[str, dict[str, tuple[int, float, int, int, str]]] = {}

        for doc in documents:
            metadata = dict(doc.metadata or {})
            topic_key = str(metadata.get("kb_topic_key") or "").strip() or "default"
            source_key = str(metadata.get("kb_source_key") or metadata.get("source") or "").strip() or "unknown"
            rank = self._governance_rank(metadata)
            topic_sources = grouped_sources.setdefault(topic_key, {})
            current_rank = topic_sources.get(source_key)
            if current_rank is None or rank > current_rank:
                topic_sources[source_key] = rank

        for topic_key, source_ranks in grouped_sources.items():
            winning_source_by_topic[topic_key] = max(
                source_ranks.items(),
                key=lambda item: item[1],
            )[0]

        governed_docs: list[Document] = []
        for doc in documents:
            metadata = dict(doc.metadata or {})
            topic_key = str(metadata.get("kb_topic_key") or "").strip() or "default"
            source_key = str(metadata.get("kb_source_key") or metadata.get("source") or "").strip() or "unknown"
            expiry_ts = int(float(metadata.get("kb_expiry_ts") or 0) or 0)
            is_expired = bool(metadata.get("kb_is_expired")) or (
                expiry_ts > 0 and expiry_ts < int(time.time())
            )
            is_latest = winning_source_by_topic.get(topic_key) == source_key
            lifecycle_status = "expired" if is_expired else ("current" if is_latest else "superseded")
            metadata.update(
                {
                    "kb_is_latest": is_latest,
                    "kb_lifecycle_status": lifecycle_status,
                }
            )
            governed_docs.append(Document(page_content=doc.page_content, metadata=metadata))
        return governed_docs

    def _prepare_documents_for_index(self, documents: List[Document]) -> List[Document]:
        governed_docs = [self._apply_document_governance_metadata(doc) for doc in documents]
        deduped_docs = self._dedupe_index_documents(governed_docs)
        return self._apply_topic_version_status(deduped_docs)

    @staticmethod
    def _document_governance_boost(doc: Document) -> float:
        metadata = doc.metadata or {}
        boost = 0.0
        expiry_ts = int(float(metadata.get("kb_expiry_ts") or 0) or 0)
        is_expired = bool(metadata.get("kb_is_expired")) or (
            expiry_ts > 0 and expiry_ts < int(time.time())
        )
        if metadata.get("kb_is_latest") is True:
            boost += 0.16
        elif metadata.get("kb_is_latest") is False:
            boost -= 0.08
        if str(metadata.get("kb_lifecycle_status") or "").strip() == "superseded":
            boost -= 0.14
        if is_expired:
            boost -= 0.35
        return round(max(-0.5, min(0.25, boost)), 4)

