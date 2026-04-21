from langchain_core.documents import Document

import backend.doc_pipeline as doc_pipeline
from backend.doc_pipeline import DocPipeline


def test_reranker_load_falls_back_to_cpu_when_cuda_init_fails(monkeypatch):
    init_calls: list[tuple[str, bool]] = []

    class FakeCrossEncoder:
        def __init__(self, model_name, max_length, device, local_files_only=False, token=None):
            init_calls.append((device, local_files_only))
            if device != "cpu":
                raise RuntimeError("CUDA out of memory")
            self.device = device

        def predict(self, pairs):
            return [0.5 for _ in pairs]

    monkeypatch.setattr(doc_pipeline, "CrossEncoder", FakeCrossEncoder)
    monkeypatch.setattr(
        DocPipeline,
        "_resolve_device",
        lambda self, device: device or "cpu",
    )
    DocPipeline._reranker_cache.clear()

    pipeline = DocPipeline(device="cuda")

    reranker = pipeline.reranker

    assert reranker.device == "cpu"
    assert pipeline._reranker_device == "cpu"
    assert ("cuda", True) in init_calls
    assert ("cpu", True) in init_calls


def test_search_with_rerank_retries_prediction_on_cpu_and_clamps_fetch_k(monkeypatch):
    class FakeCrossEncoder:
        def __init__(self, model_name, max_length, device, local_files_only=False, token=None):
            self.device = device

        def predict(self, pairs):
            if self.device != "cpu":
                raise RuntimeError("CUDA out of memory")
            return [0.1, 0.95, 0.5]

    class FakeVectorStore:
        def __init__(self):
            self.search_calls: list[int] = []

        def similarity_search(self, query, k):
            self.search_calls.append(k)
            return [
                Document(page_content="alpha", metadata={"source": "doc-a"}),
                Document(page_content="beta", metadata={"source": "doc-b"}),
                Document(page_content="gamma", metadata={"source": "doc-c"}),
            ]

    monkeypatch.setattr(doc_pipeline, "CrossEncoder", FakeCrossEncoder)
    monkeypatch.setattr(
        DocPipeline,
        "_resolve_device",
        lambda self, device: device or "cpu",
    )
    DocPipeline._reranker_cache.clear()

    pipeline = DocPipeline(device="cuda")
    pipeline.vectorstore = FakeVectorStore()

    results = pipeline.search_with_rerank("test query", k=3, fetch_k=1)

    assert pipeline.vectorstore.search_calls == [3]
    assert [doc.metadata["source"] for doc in results] == ["doc-b", "doc-c", "doc-a"]
    assert pipeline._reranker_device == "cpu"


def test_search_with_rerank_applies_feedback_boost(monkeypatch):
    class FakeCrossEncoder:
        def __init__(self, model_name, max_length, device, local_files_only=False, token=None):
            self.device = device

        def predict(self, pairs):
            return [0.55, 0.56, 0.57]

    class FakeVectorStore:
        def similarity_search(self, query, k):
            return [
                Document(page_content="alpha", metadata={"source": "doc-a"}),
                Document(page_content="beta", metadata={"source": "doc-b"}),
                Document(page_content="gamma", metadata={"source": "doc-c"}),
            ]

    monkeypatch.setattr(doc_pipeline, "CrossEncoder", FakeCrossEncoder)
    monkeypatch.setattr(
        DocPipeline,
        "_resolve_device",
        lambda self, device: device or "cpu",
    )
    monkeypatch.setattr(
        DocPipeline,
        "_load_feedback_summary_map",
        lambda self, source_type="doc": {
            ("doc", "doc-c", ""): {
                "source_type": "doc",
                "source_title": "doc-c",
                "source_url": "",
                "positive_count": 2,
                "negative_count": 0,
                "net_feedback": 2,
                "total_count": 2,
                "last_updated_at": 0.0,
            }
        },
    )
    DocPipeline._reranker_cache.clear()

    pipeline = DocPipeline(device="cpu")
    pipeline.vectorstore = FakeVectorStore()

    results = pipeline.search_with_rerank("test query", k=3, fetch_k=3)

    assert [doc.metadata["source"] for doc in results] == ["doc-c", "doc-b", "doc-a"]
    assert results[0].metadata["feedback_positive_count"] == 2
    assert results[0].metadata["feedback_boost"] > 0


def test_format_debug_entry_exposes_feedback_fields():
    pipeline = DocPipeline(device="cpu")

    entry = pipeline._format_debug_entry(
        Document(
            page_content="Alpha findings and supporting detail",
            metadata={
                "source": "alpha.md",
                "search_score": 0.88,
                "search_channel": "hybrid_rerank",
                "matched_terms": ["alpha"],
                "feedback_boost": 0.14,
                "feedback_net": 1,
                "feedback_positive_count": 2,
                "feedback_negative_count": 1,
            },
        ),
        rank=1,
    )

    assert entry["feedback_boost"] == 0.14
    assert entry["feedback_net"] == 1
    assert entry["feedback_positive_count"] == 2
    assert entry["feedback_negative_count"] == 1


def test_normalize_rerank_scores_handles_invalid_values():
    pipeline = DocPipeline(device="cpu")

    scores = pipeline._normalize_rerank_scores(
        [float("nan"), ["2.5"], None],
        expected=4,
    )

    assert scores == [0.0, 2.5, 0.0, 0.0]
