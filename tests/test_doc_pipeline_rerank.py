from langchain_core.documents import Document

import doc_pipeline
from doc_pipeline import DocPipeline


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


def test_normalize_rerank_scores_handles_invalid_values():
    pipeline = DocPipeline(device="cpu")

    scores = pipeline._normalize_rerank_scores(
        [float("nan"), ["2.5"], None],
        expected=4,
    )

    assert scores == [0.0, 2.5, 0.0, 0.0]
