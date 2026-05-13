from __future__ import annotations

import ipaddress
from typing import Any, Callable


def env_flag(
    name: str,
    default: bool = False,
    *,
    env_getter: Callable[[str], str | None],
) -> bool:
    raw = env_getter(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_int(
    name: str,
    default: int,
    *,
    env_getter: Callable[[str], str | None],
) -> int:
    raw = env_getter(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def env_int_setting(
    name: str,
    default: int,
    *,
    env_getter: Callable[[str], str | None],
    logger: Any,
    minimum: int | None = None,
    maximum: int | None = None,
) -> tuple[int, str]:
    raw = env_getter(name)
    value = int(default)
    source = "default"

    if raw is not None:
        try:
            value = int(str(raw).strip())
            source = "env"
        except (TypeError, ValueError):
            logger.warning("Invalid %s=%r; using default=%s", name, raw, default)
            value = int(default)
            source = "invalid_env"

    if minimum is not None and value < minimum:
        logger.warning("%s=%r is below minimum=%s; using %s", name, raw, minimum, minimum)
        value = int(minimum)
        source = f"{source}_clamped"

    if maximum is not None and value > maximum:
        logger.warning("%s=%r is above maximum=%s; using %s", name, raw, maximum, maximum)
        value = int(maximum)
        source = f"{source}_clamped"

    return int(value), source


def env_bool_setting(
    name: str,
    default: bool,
    *,
    env_getter: Callable[[str], str | None],
    logger: Any,
) -> tuple[bool, str]:
    raw = env_getter(name)
    if raw is None:
        return bool(default), "default"

    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True, "env"
    if normalized in {"0", "false", "no", "off"}:
        return False, "env"

    logger.warning("Invalid %s=%r; using default=%s", name, raw, default)
    return bool(default), "invalid_env"


def cors_settings(
    *,
    env_getter: Callable[[str], str | None],
) -> tuple[list[str], bool]:
    raw = str(env_getter("CORS_ALLOW_ORIGINS") or "").strip()
    if not raw:
        return (
            [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            ],
            True,
        )

    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if "*" in origins:
        return ["*"], False
    return origins, True


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def integrator_scheduler_config_from_env(
    *,
    env_getter: Callable[[str], str | None],
    logger: Any,
) -> dict[str, Any]:
    enabled, enabled_source = env_bool_setting(
        "INTEGRATOR_SCHEDULER_ENABLED",
        False,
        env_getter=env_getter,
        logger=logger,
    )
    interval_seconds, interval_source = env_int_setting(
        "INTEGRATOR_SCHEDULER_INTERVAL_SECONDS",
        60,
        minimum=1,
        env_getter=env_getter,
        logger=logger,
    )
    return {
        "enabled": enabled,
        "enabled_source": enabled_source,
        "interval_seconds": interval_seconds,
        "interval_source": interval_source,
    }
