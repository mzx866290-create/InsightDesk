from types import SimpleNamespace

from backend.helpers.model_config_helpers import (
    base_model_payload,
    model_config_payload,
    normalize_model_config,
)


class FakePydanticV2Model:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self):
        return {"source": "v2", **self.payload}

    def dict(self):
        return {"source": "v1", **self.payload}


class FakePydanticV1Model:
    def __init__(self, payload):
        self.payload = payload

    def dict(self):
        return {"source": "v1", **self.payload}


def _model_config_cls(**data):
    return SimpleNamespace(**data)


def _normalize_connection_type(provider, base_url=None):
    normalized = str(provider or "").strip().lower()
    if normalized in {"openai", "openai_compatible"}:
        return "openai_compatible"
    if str(base_url or "").startswith("https://"):
        return "openai_compatible"
    return "ollama"


def _default_base_url(connection_type):
    return {
        "ollama": "http://localhost:11434",
        "openai_compatible": "https://openrouter.ai/api/v1",
    }[connection_type]


def _default_model(connection_type):
    return {
        "ollama": "qwen3.5-2B:latest",
        "openai_compatible": "gpt-4o-mini",
    }[connection_type]


def test_model_config_payload_copies_plain_dict_without_mutating_source():
    source = {"provider": "ollama", "api_key": " secret "}

    payload = model_config_payload(source)
    payload["provider"] = "changed"

    assert source["provider"] == "ollama"
    assert payload["api_key"] == " secret "


def test_model_config_payload_prefers_pydantic_v2_model_dump():
    payload = model_config_payload(FakePydanticV2Model({"provider": "ollama"}))

    assert payload == {"source": "v2", "provider": "ollama"}


def test_model_config_payload_supports_pydantic_v1_dict():
    payload = model_config_payload(FakePydanticV1Model({"provider": "ollama"}))

    assert payload == {"source": "v1", "provider": "ollama"}


def test_base_model_payload_supports_mapping_fallback():
    assert base_model_payload({"panel_id": "panel-main"}) == {"panel_id": "panel-main"}


def test_normalize_model_config_normalizes_connection_and_trims_secrets():
    normalized = normalize_model_config(
        {
            "panel_id": "panel-main",
            "provider": "openai",
            "model": "",
            "base_url": "",
            "api_key": " sk-test ",
            "api_key_ref": " cmk-main ",
            "temperature": 0.3,
            "agent_mode": "auto",
        },
        model_config_cls=_model_config_cls,
        normalize_connection_type=_normalize_connection_type,
        default_base_url_for_connection_type=_default_base_url,
        default_model_for_connection_type=_default_model,
    )

    assert normalized.connection_type == "openai_compatible"
    assert normalized.provider == "openai_compatible"
    assert normalized.base_url == "https://openrouter.ai/api/v1"
    assert normalized.model == "gpt-4o-mini"
    assert normalized.api_key == "sk-test"
    assert normalized.api_key_ref == "cmk-main"


def test_normalize_model_config_preserves_explicit_base_url_and_model():
    normalized = normalize_model_config(
        {
            "panel_id": "panel-main",
            "connection_type": "ollama",
            "provider": "openai",
            "model": " custom-model ",
            "base_url": " http://localhost:11434 ",
            "api_key": "",
            "temperature": 0.3,
            "agent_mode": "auto",
        },
        model_config_cls=_model_config_cls,
        normalize_connection_type=_normalize_connection_type,
        default_base_url_for_connection_type=_default_base_url,
        default_model_for_connection_type=_default_model,
    )

    assert normalized.connection_type == "ollama"
    assert normalized.provider == "ollama"
    assert normalized.base_url == "http://localhost:11434"
    assert normalized.model == "custom-model"
