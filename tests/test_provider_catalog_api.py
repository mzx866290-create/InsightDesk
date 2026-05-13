import asyncio
import builtins

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.agent.connection import get_llm, list_llm_provider_catalog, normalize_connection_type
from backend.agent.providers import ollama as ollama_provider
from backend.routes.provider_routes import build_provider_router
from backend.schemas.api_models import ProviderCatalogResponse


def test_list_llm_provider_catalog_serializes_registered_providers(monkeypatch):
    for env_key in (
        "OLLAMA_MODEL",
        "OPENAI_COMPAT_MODEL",
        "OPENAI_MODEL",
        "OPENROUTER_MODEL",
        "DEEPSEEK_MODEL",
        "ANTHROPIC_MODEL",
        "GOOGLE_MODEL",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(env_key, raising=False)

    catalog = list_llm_provider_catalog()
    providers = {item["id"]: item for item in catalog["providers"]}

    assert catalog["default_provider"] == "ollama"
    assert catalog["total"] == len(catalog["providers"])
    assert set(providers) == {
        "ollama",
        "openai_compatible",
        "deepseek",
        "anthropic",
        "google",
    }
    assert "local" in providers["ollama"]["aliases"]
    assert "openai" in providers["openai_compatible"]["aliases"]
    assert "deepseek_compatible" in providers["deepseek"]["aliases"]
    assert "claude" in providers["anthropic"]["aliases"]
    assert "gemini" in providers["google"]["aliases"]
    assert providers["ollama"]["capabilities"] == ["chat"]
    assert providers["openai_compatible"]["default_model"] == "gpt-4o-mini"
    assert providers["deepseek"]["default_base_url"] == "https://api.deepseek.com"
    assert providers["deepseek"]["default_model"] == "deepseek-chat"
    assert providers["anthropic"]["default_model"] == "claude-3-5-sonnet-latest"
    assert providers["google"]["default_model"] == "gemini-2.0-flash"


def test_provider_catalog_endpoint_returns_registered_provider_metadata():
    app = FastAPI()
    app.include_router(
        build_provider_router(
            provider_catalog_response_model=ProviderCatalogResponse,
            list_provider_catalog=list_llm_provider_catalog,
        )
    )

    response = TestClient(app).get("/api/providers")

    assert response.status_code == 200
    payload = response.json()
    provider_ids = [item["id"] for item in payload["providers"]]
    assert payload["total"] == 5
    assert provider_ids == [
        "ollama",
        "openai_compatible",
        "deepseek",
        "anthropic",
        "google",
    ]
    assert payload["providers"][0]["connection_type"] == "ollama"
    assert "cloud" in payload["providers"][1]["aliases"]


def test_ollama_provider_lists_installed_models(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen2.5:7b"}, {}, {"name": "llama3.2:3b"}]}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr(ollama_provider.httpx, "AsyncClient", FakeAsyncClient)

    payload = asyncio.run(
        ollama_provider.list_ollama_models(
            "http://example.test:11434",
            timeout=2.5,
        )
    )

    assert payload == {"models": ["qwen2.5:7b", "llama3.2:3b"]}
    assert captured == {
        "timeout": 2.5,
        "url": "http://example.test:11434/api/tags",
    }


def test_provider_catalog_serialization_does_not_import_provider_factories(monkeypatch):
    def fail_on_provider_import(module_name):
        raise AssertionError(f"Unexpected provider import: {module_name}")

    monkeypatch.setattr("backend.agent.connection.import_module", fail_on_provider_import)

    catalog = list_llm_provider_catalog()

    assert catalog["total"] == 5
    assert [item["id"] for item in catalog["providers"]] == [
        "ollama",
        "openai_compatible",
        "deepseek",
        "anthropic",
        "google",
    ]


def test_new_provider_aliases_and_deepseek_base_url_normalization():
    assert normalize_connection_type("deepseek") == "deepseek"
    assert normalize_connection_type("claude") == "anthropic"
    assert normalize_connection_type("gemini") == "google"
    assert normalize_connection_type(base_url="https://api.deepseek.com") == "deepseek"


def test_optional_provider_dependency_error_is_lazy_and_clear(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "langchain_anthropic":
            raise ImportError("test missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(ImportError, match="provider='anthropic'"):
        get_llm("anthropic", api_key="test-key")
