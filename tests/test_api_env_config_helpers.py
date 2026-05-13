from types import SimpleNamespace

from backend.helpers.env_config_helpers import (
    cors_settings,
    env_bool_setting,
    env_flag,
    env_int,
    env_int_setting,
    integrator_scheduler_config_from_env,
    is_loopback_host,
)


def test_env_int_setting_uses_default_when_missing():
    value, source = env_int_setting(
        "TEST_INT",
        60,
        env_getter=lambda _name: None,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert value == 60
    assert source == "default"


def test_env_flag_and_env_int_use_simple_defaults():
    assert env_flag("FLAG", True, env_getter=lambda _name: None) is True
    assert env_flag("FLAG", False, env_getter=lambda _name: "on") is True
    assert env_flag("FLAG", True, env_getter=lambda _name: "off") is False

    assert env_int("LIMIT", 10, env_getter=lambda _name: None) == 10
    assert env_int("LIMIT", 10, env_getter=lambda _name: "25") == 25
    assert env_int("LIMIT", 10, env_getter=lambda _name: "bad") == 10


def test_env_int_setting_clamps_and_marks_source():
    value, source = env_int_setting(
        "TEST_INT",
        60,
        env_getter=lambda _name: "0",
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        minimum=1,
    )

    assert value == 1
    assert source == "env_clamped"


def test_env_bool_setting_parses_truthy_and_falsy_values():
    truthy, truthy_source = env_bool_setting(
        "TEST_BOOL",
        False,
        env_getter=lambda _name: "yes",
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )
    falsy, falsy_source = env_bool_setting(
        "TEST_BOOL",
        True,
        env_getter=lambda _name: "off",
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert truthy is True
    assert truthy_source == "env"
    assert falsy is False
    assert falsy_source == "env"


def test_integrator_scheduler_config_from_env_uses_defaults():
    config = integrator_scheduler_config_from_env(
        env_getter=lambda _name: None,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert config == {
        "enabled": False,
        "enabled_source": "default",
        "interval_seconds": 60,
        "interval_source": "default",
    }


def test_cors_settings_defaults_to_local_origins_with_credentials():
    origins, allow_credentials = cors_settings(env_getter=lambda _name: None)

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:8000" in origins
    assert allow_credentials is True


def test_cors_settings_disables_credentials_for_wildcard_origin():
    origins, allow_credentials = cors_settings(
        env_getter=lambda _name: "https://app.example.com, *"
    )

    assert origins == ["*"]
    assert allow_credentials is False


def test_cors_settings_parses_explicit_origins():
    origins, allow_credentials = cors_settings(
        env_getter=lambda _name: "https://app.example.com, https://ops.example.com"
    )

    assert origins == ["https://app.example.com", "https://ops.example.com"]
    assert allow_credentials is True


def test_is_loopback_host_accepts_localhost_testclient_and_loopback_ips():
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("testclient") is True
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("203.0.113.10") is False
    assert is_loopback_host("") is False
