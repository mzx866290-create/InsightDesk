from pathlib import Path

import doc_pipeline
from doc_pipeline import DocPipeline


class _FakeVectorStore:
    def __init__(self):
        self.saved_path = None

    def save_local(self, path: str) -> None:
        self.saved_path = path
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.faiss").write_bytes(b"faiss")
        (target / "index.pkl").write_bytes(b"pickle")


def test_save_vectorstore_uses_ascii_staging_dir_for_unicode_windows_path(
    monkeypatch, tmp_path
):
    unicode_target = tmp_path / "知识库"
    ascii_temp = tmp_path / "ascii_temp"
    ascii_temp.mkdir()

    pipeline = DocPipeline(vector_store_path=str(unicode_target))
    pipeline.vectorstore = _FakeVectorStore()

    monkeypatch.setattr(doc_pipeline.sys, "platform", "win32")
    monkeypatch.setattr(doc_pipeline.tempfile, "gettempdir", lambda: str(ascii_temp))

    pipeline._save_vectorstore_local()

    assert (unicode_target / "index.faiss").exists()
    assert (unicode_target / "index.pkl").exists()
    assert pipeline.vectorstore.saved_path is not None
    assert "知识库" not in pipeline.vectorstore.saved_path


def test_load_vectorstore_uses_ascii_staging_dir_for_unicode_windows_path(
    monkeypatch, tmp_path
):
    unicode_target = tmp_path / "知识库"
    unicode_target.mkdir()
    (unicode_target / "index.faiss").write_bytes(b"faiss")
    (unicode_target / "index.pkl").write_bytes(b"pickle")

    ascii_temp = tmp_path / "ascii_temp"
    ascii_temp.mkdir()
    seen = {}

    def fake_load_local(path: str, embeddings, allow_dangerous_deserialization: bool):
        seen["path"] = path
        seen["embeddings"] = embeddings
        seen["allow"] = allow_dangerous_deserialization
        return "loaded-store"

    monkeypatch.setattr(doc_pipeline.sys, "platform", "win32")
    monkeypatch.setattr(doc_pipeline.tempfile, "gettempdir", lambda: str(ascii_temp))
    monkeypatch.setattr(
        DocPipeline,
        "embeddings",
        property(lambda self: "fake-embeddings"),
    )
    monkeypatch.setattr(doc_pipeline.FAISS, "load_local", fake_load_local)

    pipeline = DocPipeline(vector_store_path=str(unicode_target))

    loaded = pipeline._load_vectorstore_local()

    assert loaded == "loaded-store"
    assert seen["allow"] is True
    assert seen["embeddings"] == "fake-embeddings"
    assert "知识库" not in seen["path"]
