import pytest

from backend.agent.providers.openai_compatible import _resolve_api_key

MANAGED_KEY_ENV_VARS = (
    "OPENAI_COMPAT_API_KEY",
    "OPENAI_COMPAT_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
)


def _clear_managed_key_env(monkeypatch):
    for env_var in MANAGED_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_explicit_key_is_allowed_for_custom_openai_compatible_url(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-openrouter-key")

    resolved = _resolve_api_key(
        base_url="https://custom.example/v1",
        api_key="client-owned-key",
    )

    assert resolved == "client-owned-key"


def test_openrouter_key_is_rejected_for_untrusted_url_without_leaking_secret(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    secret = "server-openrouter-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    with pytest.raises(ValueError) as exc_info:
        _resolve_api_key(base_url="https://attacker.example/v1", api_key=None)

    assert secret not in str(exc_info.value)


def test_openrouter_key_is_allowed_only_for_its_trusted_url(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-openrouter-key")

    resolved = _resolve_api_key(
        base_url="https://OPENROUTER.ai:443/api/v1/",
        api_key=None,
    )

    assert resolved == "server-openrouter-key"


def test_openai_key_cannot_be_sent_to_openrouter(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "server-openai-key")

    with pytest.raises(ValueError, match="configured provider base URL"):
        _resolve_api_key(base_url="https://openrouter.ai/api/v1", api_key=None)


def test_multiple_managed_keys_select_key_matching_current_provider(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "server-openai-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-openrouter-key")

    resolved = _resolve_api_key(
        base_url="https://openrouter.ai/api/v1",
        api_key=None,
    )

    assert resolved == "server-openrouter-key"


def test_generic_managed_key_requires_a_bound_base_url(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "server-generic-key")

    with pytest.raises(ValueError, match="configured provider base URL"):
        _resolve_api_key(base_url="https://custom.example/v1", api_key=None)


def test_generic_managed_key_uses_only_configured_base_url(monkeypatch):
    _clear_managed_key_env(monkeypatch)
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "server-generic-key")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://gateway.example/v1")

    resolved = _resolve_api_key(
        base_url="https://gateway.example:443/v1/",
        api_key=None,
    )

    assert resolved == "server-generic-key"
