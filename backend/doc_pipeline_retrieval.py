"""Retrieval: semantic, keyword, hybrid, feedback boost and rerank search.

Split out of backend.doc_pipeline as a mixin; composed by DocPipeline.
"""

"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import logging
import re
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


class DocPipelineRetrievalMixin:
    _document_governance_boost: Any
    _predict_rerank_scores: Any
    vectorstore: Any

    def search(self, query: str, k: int = 4) -> List[Document]:
        """
        检索相关文档片段 (纯余弦相似度)

        Args:
            query: 查询文本
            k: 返回的文档数量

        Returns:
            相关文档列表
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        return list(self.vectorstore.similarity_search(query, k=k))

    def search_with_scores(self, query: str, k: int = 4) -> List[tuple[Document, float]]:
        """
        检索相关文档片段并保留原始向量分数

        Args:
            query: 查询文本
            k: 返回的文档数量

        Returns:
            (文档, 分数) 列表；FAISS 分数越小表示越接近
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        try:
            return list(self.vectorstore.similarity_search_with_score(query, k=k))
        except Exception:
            logger.exception("similarity_search_with_score 失败，回退到 similarity_search")
            return [(doc, 0.0) for doc in self.vectorstore.similarity_search(query, k=k)]

    @staticmethod
    def _normalize_feedback_lookup_text(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).lower()

    def _load_feedback_summary_map(
        self,
        *,
        source_type: str = "doc",
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        try:
            from backend.chat_store import aggregate_retrieval_feedback_by_source

            summary = aggregate_retrieval_feedback_by_source(source_type=source_type)
        except Exception:
            logger.exception("加载 retrieval feedback 聚合失败 source_type=%s", source_type)
            return {}

        feedback_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in summary:
            key = (
                self._normalize_feedback_lookup_text(item.get("source_type")),
                self._normalize_feedback_lookup_text(item.get("source_title")),
                self._normalize_feedback_lookup_text(item.get("source_url")),
            )
            feedback_map[key] = item
        return feedback_map

    def _feedback_signal_for_doc(
        self,
        doc: Document,
        feedback_map: dict[tuple[str, str, str], dict[str, Any]],
        *,
        source_type: str = "doc",
    ) -> dict[str, Any]:
        metadata = doc.metadata or {}
        source_title = self._normalize_feedback_lookup_text(
            metadata.get("source") or metadata.get("title") or ""
        )
        source_url = self._normalize_feedback_lookup_text(
            metadata.get("url") or metadata.get("source_url") or ""
        )
        lookup_keys = [
            (self._normalize_feedback_lookup_text(source_type), source_title, source_url),
            (self._normalize_feedback_lookup_text(source_type), source_title, ""),
        ]
        for key in lookup_keys:
            signal = feedback_map.get(key)
            if signal:
                return signal
        return {
            "source_type": source_type,
            "source_title": source_title,
            "source_url": source_url,
            "positive_count": 0,
            "negative_count": 0,
            "net_feedback": 0,
            "total_count": 0,
            "last_updated_at": 0.0,
        }

    @staticmethod
    def _feedback_boost(signal: dict[str, Any]) -> float:
        positive_count = int(signal.get("positive_count") or 0)
        negative_count = int(signal.get("negative_count") or 0)
        net_feedback = int(signal.get("net_feedback") or 0)
        boost = positive_count * 0.08 + net_feedback * 0.06 - negative_count * 0.12
        return round(max(-0.45, min(0.35, boost)), 4)

    def _apply_feedback_metadata(
        self,
        doc: Document,
        *,
        feedback_signal: dict[str, Any],
        score: float | None = None,
        score_key: str = "search_score",
    ) -> Document:
        feedback_boost = self._feedback_boost(feedback_signal)
        metadata = dict(doc.metadata or {})
        metadata.update(
            {
                "feedback_boost": feedback_boost,
                "feedback_net": int(feedback_signal.get("net_feedback") or 0),
                "feedback_positive_count": int(feedback_signal.get("positive_count") or 0),
                "feedback_negative_count": int(feedback_signal.get("negative_count") or 0),
            }
        )
        if score is not None:
            metadata[score_key] = round(float(score), 6)
        return Document(page_content=doc.page_content, metadata=metadata)

    @staticmethod
    def _copy_document_with_metadata(doc: Document, **extra_metadata: Any) -> Document:
        metadata = dict(doc.metadata or {})
        metadata.update(extra_metadata)
        return Document(page_content=doc.page_content, metadata=metadata)

    @staticmethod
    def _normalize_keyword_text(text: str) -> str:
        normalized = str(text or "").strip().lower()
        return re.sub(r"\s+", " ", normalized)

    def _extract_keyword_terms(self, text: str) -> List[str]:
        normalized = self._normalize_keyword_text(text)
        if not normalized:
            return []

        terms: list[str] = []
        seen: set[str] = set()
        for raw_token in KEYWORD_TOKEN_PATTERN.findall(normalized):
            token = raw_token.strip()
            if not token:
                continue
            candidates = [token]
            if re.search(r"[\u4e00-\u9fff]", token) and len(token) >= 4:
                candidates.extend(token[index : index + 2] for index in range(len(token) - 1))
            for candidate in candidates:
                candidate = candidate.strip()
                if not candidate:
                    continue
                if len(candidate) < 2 and not re.search(r"[\u4e00-\u9fff]", candidate):
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                terms.append(candidate)
        return terms

    def _all_index_documents(self) -> List[Document]:
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        docstore = getattr(self.vectorstore, "docstore", None)
        raw_dict = getattr(docstore, "_dict", None)
        if isinstance(raw_dict, dict):
            return [item for item in raw_dict.values() if isinstance(item, Document)]
        return []

    @staticmethod
    def _document_key(doc: Document) -> str:
        metadata = doc.metadata or {}
        stable_id = (
            metadata.get("chunk_id")
            or metadata.get("id")
            or metadata.get("doc_id")
            or metadata.get("source")
        )
        snippet = re.sub(r"\s+", " ", doc.page_content or "")[:200]
        return f"{stable_id or 'unknown'}::{snippet}"

    def _score_keyword_document(self, query: str, doc: Document) -> dict[str, Any]:
        query_text = self._normalize_keyword_text(query)
        content_text = self._normalize_keyword_text(doc.page_content)
        source_text = self._normalize_keyword_text(doc.metadata.get("source", ""))
        title_text = self._normalize_keyword_text(doc.metadata.get("title", ""))
        source_haystack = " ".join(part for part in (source_text, title_text) if part).strip()
        haystack = " ".join(part for part in (source_haystack, content_text) if part).strip()
        terms = self._extract_keyword_terms(query_text)

        matched_terms: list[str] = []
        term_score = 0.0
        source_term_score = 0.0
        for term in terms:
            hit_count = haystack.count(term)
            if hit_count <= 0:
                continue
            matched_terms.append(term)
            term_weight = min(2.8, 0.5 + len(term) * 0.18)
            term_score += min(hit_count, 3) * term_weight

            source_hits = source_haystack.count(term)
            if source_hits > 0:
                source_term_score += min(source_hits, 2) * (term_weight + 0.5)

        matched_terms = list(dict.fromkeys(matched_terms))
        phrase_score = 4.0 if query_text and query_text in content_text else 0.0
        source_phrase_score = 3.0 if query_text and query_text in source_haystack else 0.0
        coverage = len(matched_terms) / max(1, len(terms))
        score = phrase_score + source_phrase_score + term_score + source_term_score + coverage * 2.0
        return {
            "score": round(score, 4),
            "matched_terms": matched_terms,
            "coverage": round(coverage, 4),
            "score_breakdown": {
                "phrase": round(phrase_score, 4),
                "source_phrase": round(source_phrase_score, 4),
                "term_overlap": round(term_score, 4),
                "source_overlap": round(source_term_score, 4),
                "coverage": round(coverage * 2.0, 4),
            },
        }

    def keyword_search(self, query: str, k: int = 4) -> List[Document]:
        """
        基于关键词匹配的轻量检索，适合精确术语/缩写/编号问题
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        feedback_map = self._load_feedback_summary_map(source_type="doc")
        scored_docs: list[tuple[Document, dict[str, Any], dict[str, Any]]] = []
        for doc in self._all_index_documents():
            score_meta = self._score_keyword_document(query, doc)
            if score_meta["score"] <= 0:
                continue
            feedback_signal = self._feedback_signal_for_doc(doc, feedback_map, source_type="doc")
            feedback_boost = self._feedback_boost(feedback_signal)
            governance_boost = self._document_governance_boost(doc)
            score_meta["score"] = round(score_meta["score"] + feedback_boost + governance_boost, 4)
            score_meta["score_breakdown"] = {
                **score_meta["score_breakdown"],
                "feedback_boost": feedback_boost,
                "governance_boost": governance_boost,
            }
            scored_docs.append((doc, score_meta, feedback_signal))

        scored_docs.sort(key=lambda item: item[1]["score"], reverse=True)
        top_docs: list[Document] = []
        for rank, (doc, score_meta, feedback_signal) in enumerate(
            scored_docs[: max(1, int(k or 1))], start=1
        ):
            top_docs.append(
                self._apply_feedback_metadata(
                    self._copy_document_with_metadata(
                        doc,
                        search_channel="keyword",
                        search_rank=rank,
                        governance_boost=score_meta["score_breakdown"].get("governance_boost", 0.0),
                        matched_terms=score_meta["matched_terms"],
                        keyword_coverage=score_meta["coverage"],
                        score_breakdown=score_meta["score_breakdown"],
                    ),
                    feedback_signal=feedback_signal,
                    score=score_meta["score"],
                )
            )
        return top_docs

    def hybrid_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 10,
        use_rerank: bool = False,
    ) -> List[Document]:
        """
        混合检索：向量召回 + 关键词召回，然后做融合排序，可选二段重排
        """
        debug_payload = self.debug_retrieval(
            query,
            search_k=k,
            fetch_k=fetch_k,
            retrieval_mode="hybrid",
            use_rerank=use_rerank,
        )
        results = debug_payload.get("top_results") or []
        docs: list[Document] = []
        for item in results:
            docs.append(
                Document(
                    page_content=str(item.get("full_content") or item.get("snippet") or ""),
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        return docs

    def _format_debug_entry(self, doc: Document, *, rank: int) -> dict[str, Any]:
        metadata = dict(doc.metadata or {})
        snippet = re.sub(r"\s+", " ", doc.page_content or "").strip()
        search_score = metadata.get("search_score")
        if search_score is None:
            search_score = metadata.get("rrf_score")
        matched_terms = metadata.get("matched_terms")
        if not isinstance(matched_terms, list):
            matched_terms = []
        feedback_boost = float(metadata.get("feedback_boost", 0.0) or 0.0)
        governance_boost = float(
            metadata.get("governance_boost", self._document_governance_boost(doc)) or 0.0
        )
        feedback_net = int(metadata.get("feedback_net", 0) or 0)
        feedback_positive_count = int(metadata.get("feedback_positive_count", 0) or 0)
        feedback_negative_count = int(metadata.get("feedback_negative_count", 0) or 0)

        return {
            "rank": rank,
            "source": metadata.get("source", "未知"),
            "snippet": snippet[:200],
            "full_content": doc.page_content,
            "score": float(search_score or 0.0),
            "channel": metadata.get("search_channel", "semantic"),
            "matched_terms": matched_terms,
            "feedback_boost": feedback_boost,
            "governance_boost": governance_boost,
            "feedback_net": feedback_net,
            "feedback_positive_count": feedback_positive_count,
            "feedback_negative_count": feedback_negative_count,
            "version_label": metadata.get("kb_version_label") or "",
            "lifecycle_status": metadata.get("kb_lifecycle_status") or "",
            "is_latest": bool(metadata.get("kb_is_latest")),
            "is_expired": bool(metadata.get("kb_is_expired")),
            "score_breakdown": metadata.get("score_breakdown") or {},
            "metadata": metadata,
        }

    def _semantic_candidates(self, query: str, fetch_k: int) -> List[Document]:
        pairs = self.search_with_scores(query, k=fetch_k)
        feedback_map = self._load_feedback_summary_map(source_type="doc")
        candidates: list[Document] = []
        for rank, (doc, raw_score) in enumerate(pairs, start=1):
            feedback_signal = self._feedback_signal_for_doc(doc, feedback_map, source_type="doc")
            base_score = round(1.0 / (1.0 + max(float(raw_score), 0.0)), 6)
            feedback_boost = self._feedback_boost(feedback_signal)
            governance_boost = self._document_governance_boost(doc)
            adjusted_score = round(base_score + feedback_boost + governance_boost, 6)
            candidates.append(
                self._apply_feedback_metadata(
                    self._copy_document_with_metadata(
                        doc,
                        search_channel="semantic",
                        search_rank=rank,
                        governance_boost=governance_boost,
                        # FAISS 距离越小越好，这里转成可比较的正向分值供调试显示。
                        vector_distance=round(float(raw_score), 6),
                        score_breakdown={
                            "semantic_base": base_score,
                            "feedback_boost": feedback_boost,
                            "governance_boost": governance_boost,
                        },
                    ),
                    feedback_signal=feedback_signal,
                    score=adjusted_score,
                )
            )
        candidates.sort(
            key=lambda item: float(item.metadata.get("search_score", 0.0) or 0.0),
            reverse=True,
        )
        return candidates

    def _hybrid_candidates(
        self,
        query: str,
        *,
        fetch_k: int,
    ) -> tuple[List[Document], List[Document], List[Document]]:
        semantic_docs = self._semantic_candidates(query, fetch_k)
        keyword_docs = self.keyword_search(query, k=fetch_k)

        fused_map: dict[str, dict[str, Any]] = {}
        for rank, doc in enumerate(semantic_docs, start=1):
            key = self._document_key(doc)
            fused_map[key] = {
                "doc": doc,
                "semantic_rank": rank,
                "semantic_score": doc.metadata.get("search_score", 0.0),
                "keyword_rank": None,
                "keyword_score": 0.0,
            }

        for rank, doc in enumerate(keyword_docs, start=1):
            key = self._document_key(doc)
            if key not in fused_map:
                fused_map[key] = {
                    "doc": doc,
                    "semantic_rank": None,
                    "semantic_score": 0.0,
                    "keyword_rank": rank,
                    "keyword_score": doc.metadata.get("search_score", 0.0),
                }
            else:
                fused_map[key]["keyword_rank"] = rank
                fused_map[key]["keyword_score"] = doc.metadata.get("search_score", 0.0)
                if (doc.metadata.get("search_score", 0.0) or 0.0) > (
                    fused_map[key]["doc"].metadata.get("search_score", 0.0) or 0.0
                ):
                    fused_map[key]["doc"] = self._copy_document_with_metadata(
                        fused_map[key]["doc"],
                        matched_terms=doc.metadata.get("matched_terms", []),
                        keyword_coverage=doc.metadata.get("keyword_coverage", 0.0),
                    )

        fused_docs: list[Document] = []
        for item in fused_map.values():
            semantic_rank = item["semantic_rank"]
            keyword_rank = item["keyword_rank"]
            rrf_score = 0.0
            governance_boost = self._document_governance_boost(item["doc"])
            if semantic_rank is not None:
                rrf_score += 1.0 / (60 + semantic_rank)
            if keyword_rank is not None:
                rrf_score += 1.0 / (60 + keyword_rank)

            fused_docs.append(
                self._copy_document_with_metadata(
                    item["doc"],
                    search_channel="hybrid",
                    rrf_score=round(rrf_score, 6),
                    governance_boost=governance_boost,
                    search_score=round(
                        rrf_score
                        + float(item["doc"].metadata.get("feedback_boost", 0.0) or 0.0)
                        + governance_boost,
                        6,
                    ),
                    semantic_rank=semantic_rank,
                    semantic_score=item["semantic_score"],
                    keyword_rank=keyword_rank,
                    keyword_score=item["keyword_score"],
                    score_breakdown={
                        "semantic_rrf": round(
                            1.0 / (60 + semantic_rank), 6
                        )
                        if semantic_rank is not None
                        else 0.0,
                        "keyword_rrf": round(
                            1.0 / (60 + keyword_rank), 6
                        )
                        if keyword_rank is not None
                        else 0.0,
                        "feedback_boost": float(item["doc"].metadata.get("feedback_boost", 0.0) or 0.0),
                        "governance_boost": governance_boost,
                    },
                )
            )

        fused_docs.sort(
            key=lambda doc: float(doc.metadata.get("search_score", 0.0) or 0.0),
            reverse=True,
        )
        return semantic_docs, keyword_docs, fused_docs

    def debug_retrieval(
        self,
        query: str,
        *,
        search_k: int = 5,
        fetch_k: int = 10,
        retrieval_mode: str = "semantic",
        use_rerank: bool = False,
    ) -> dict[str, Any]:
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        safe_top_k = max(1, int(search_k or 1))
        safe_fetch_k = max(safe_top_k, int(fetch_k or safe_top_k))
        mode = str(retrieval_mode or "semantic").strip().lower()
        if mode not in {"semantic", "keyword", "hybrid"}:
            mode = "semantic"

        query_text = str(query or "").strip()
        rewrite_query = query_text
        query_terms = self._extract_keyword_terms(rewrite_query)

        semantic_candidates: List[Document] = []
        keyword_candidates: List[Document] = []
        fused_candidates: List[Document] = []
        top_docs: List[Document] = []
        search_mode = mode

        if mode == "semantic":
            semantic_candidates = self._semantic_candidates(rewrite_query, safe_fetch_k)
            if use_rerank and semantic_candidates:
                try:
                    rerank_scores = self._predict_rerank_scores(rewrite_query, semantic_candidates)
                    ranked_results = sorted(
                        zip(semantic_candidates, rerank_scores),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                    top_docs = [
                        self._copy_document_with_metadata(
                            doc,
                            search_channel="semantic_rerank",
                            search_score=round(
                                float(score)
                                + float(doc.metadata.get("feedback_boost", 0.0) or 0.0)
                                + float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                                6,
                            ),
                            rerank_score=round(
                                float(score)
                                + float(doc.metadata.get("feedback_boost", 0.0) or 0.0)
                                + float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                                6,
                            ),
                            score_breakdown={
                                **(doc.metadata.get("score_breakdown") or {}),
                                "rerank": round(float(score), 6),
                                "feedback_boost": float(doc.metadata.get("feedback_boost", 0.0) or 0.0),
                                "governance_boost": float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                            },
                        )
                        for doc, score in ranked_results[:safe_top_k]
                    ]
                    search_mode = "semantic_rerank"
                except Exception:
                    logger.exception("semantic debug rerank 失败，回退到语义检索候选")
                    top_docs = semantic_candidates[:safe_top_k]
            else:
                top_docs = semantic_candidates[:safe_top_k]

        elif mode == "keyword":
            keyword_candidates = self.keyword_search(rewrite_query, k=safe_fetch_k)
            top_docs = keyword_candidates[:safe_top_k]
            search_mode = "keyword"

        else:
            semantic_candidates, keyword_candidates, fused_candidates = self._hybrid_candidates(
                rewrite_query,
                fetch_k=safe_fetch_k,
            )
            if use_rerank and fused_candidates:
                try:
                    rerank_scores = self._predict_rerank_scores(rewrite_query, fused_candidates)
                    ranked_results = sorted(
                        zip(fused_candidates, rerank_scores),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                    top_docs = [
                        self._copy_document_with_metadata(
                            doc,
                            search_channel="hybrid_rerank",
                            search_score=round(
                                float(score)
                                + float(doc.metadata.get("feedback_boost", 0.0) or 0.0)
                                + float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                                6,
                            ),
                            rerank_score=round(
                                float(score)
                                + float(doc.metadata.get("feedback_boost", 0.0) or 0.0)
                                + float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                                6,
                            ),
                            score_breakdown={
                                **(doc.metadata.get("score_breakdown") or {}),
                                "rerank": round(float(score), 6),
                                "feedback_boost": float(doc.metadata.get("feedback_boost", 0.0) or 0.0),
                                "governance_boost": float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                            },
                        )
                        for doc, score in ranked_results[:safe_top_k]
                    ]
                    search_mode = "hybrid_rerank"
                except Exception:
                    logger.exception("hybrid debug rerank 失败，回退到融合候选")
                    top_docs = fused_candidates[:safe_top_k]
            else:
                top_docs = fused_candidates[:safe_top_k]
                search_mode = "hybrid"

        matched_terms = sorted(
            {
                term
                for doc in top_docs
                for term in (doc.metadata.get("matched_terms") or [])
                if isinstance(term, str) and term.strip()
            }
        )
        unique_sources = {
            str(doc.metadata.get("source", "") or "").strip()
            for doc in top_docs
            if str(doc.metadata.get("source", "") or "").strip()
        }

        return {
            "results_count": len(top_docs),
            "search_mode": search_mode,
            "retrieval_mode": mode,
            "search_k": safe_top_k,
            "top_k": safe_top_k,
            "fetch_k": safe_fetch_k,
            "rewrite_query": rewrite_query,
            "rewrite_applied": False,
            "query_terms": query_terms,
            "top_results": [
                self._format_debug_entry(doc, rank=index)
                for index, doc in enumerate(top_docs, start=1)
            ],
            "semantic_candidates": [
                self._format_debug_entry(doc, rank=index)
                for index, doc in enumerate(semantic_candidates[:safe_fetch_k], start=1)
            ],
            "keyword_candidates": [
                self._format_debug_entry(doc, rank=index)
                for index, doc in enumerate(keyword_candidates[:safe_fetch_k], start=1)
            ],
            "fused_candidates": [
                self._format_debug_entry(doc, rank=index)
                for index, doc in enumerate(fused_candidates[:safe_fetch_k], start=1)
            ],
            "coverage": {
                "unique_sources": len(unique_sources),
                "source_ratio": round(len(unique_sources) / max(1, len(top_docs)), 4),
                "matched_terms": matched_terms,
                "matched_term_count": len(matched_terms),
            },
        }

    def search_with_rerank(
        self, query: str, k: int = 3, fetch_k: int = 10
    ) -> List[Document]:
        """
        二段重排检索: FAISS 粗排 + BGE-Reranker 精排

        流程:
        1. FAISS 检索 Top fetch_k 个候选文档 (余弦相似度粗排)
        2. 使用 BGE-Reranker 对候选文档重新打分 (语义相关性精排)
        3. 返回得分最高的 Top k 个文档

        Args:
            query: 查询文本
            k: 最终返回的文档数量 (默认 3)
            fetch_k: 初次检索的候选文档数量 (默认 10)

        Returns:
            重排后的文档列表 (按相关性降序)
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        safe_k = max(1, int(k or 1))
        safe_fetch_k = max(safe_k, int(fetch_k or safe_k))
        if safe_fetch_k != fetch_k or safe_k != k:
            logger.warning(
                "Adjusted rerank parameters: k=%s->%d fetch_k=%s->%d",
                k,
                safe_k,
                fetch_k,
                safe_fetch_k,
            )

        # 第一阶段: FAISS 粗排 (检索更多候选)
        candidates = self.vectorstore.similarity_search(query, k=safe_fetch_k)

        if not candidates:
            return []

        try:
            scores = self._predict_rerank_scores(query, candidates)
        except Exception:
            logger.exception("Reranker 失败，回退到 FAISS similarity_search")
            return list(candidates[:safe_k])

        feedback_map = self._load_feedback_summary_map(source_type="doc")
        scored_candidates: list[tuple[Document, float, dict[str, Any]]] = []
        for doc, score in zip(candidates, scores):
            feedback_signal = self._feedback_signal_for_doc(doc, feedback_map, source_type="doc")
            feedback_boost = self._feedback_boost(feedback_signal)
            governance_boost = self._document_governance_boost(doc)
            adjusted_score = round(float(score) + feedback_boost + governance_boost, 6)
            scored_candidates.append(
                (
                    self._copy_document_with_metadata(doc, governance_boost=governance_boost),
                    adjusted_score,
                    feedback_signal,
                )
            )

        # 按得分降序排序
        ranked_results = sorted(
            scored_candidates, key=lambda x: x[1], reverse=True
        )

        # 返回 Top k
        top_docs = [
            self._apply_feedback_metadata(
                self._copy_document_with_metadata(
                    doc,
                    search_channel="semantic_rerank",
                    rerank_score=adjusted_score,
                    governance_boost=float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                    score_breakdown={
                        "rerank": round(
                            adjusted_score
                            - self._feedback_boost(feedback_signal)
                            - float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                            6,
                        ),
                        "feedback_boost": self._feedback_boost(feedback_signal),
                        "governance_boost": float(doc.metadata.get("governance_boost", 0.0) or 0.0),
                    },
                ),
                feedback_signal=feedback_signal,
                score=adjusted_score,
            )
            for doc, adjusted_score, feedback_signal in ranked_results[:safe_k]
        ]

        logger.info(
            "[Rerank] query=%s... fetch_k=%d top_k=%d scores=%s",
            query[:30],
            safe_fetch_k,
            safe_k,
            [f"{s:.4f}" for _, s, _ in ranked_results[:safe_k]],
        )
        for i, (doc, score, _) in enumerate(ranked_results[:safe_k], 1):
            source = doc.metadata.get("source", "未知")
            logger.debug("  %d. %s (得分: %.4f)", i, source, score)

        return top_docs

