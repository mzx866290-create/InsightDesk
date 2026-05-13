"""Environment configuration adapters for API runtime wiring."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from backend.helpers.env_config_helpers import (
    cors_settings as cors_settings_impl,
    env_flag as env_flag_impl,
    env_int as env_int_impl,
    env_int_setting as env_int_setting_impl,
    integrator_scheduler_config_from_env,
    is_loopback_host,
)

logger = logging.getLogger(__name__)


def env_flag(name: str, default: bool = False) -> bool:
    return env_flag_impl(name, default, env_getter=os.getenv)


def env_int(name: str, default: int) -> int:
    return env_int_impl(name, default, env_getter=os.getenv)


def env_int_setting(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    runtime_logger: Any | None = None,
) -> tuple[int, str]:
    return env_int_setting_impl(
        name,
        default,
        env_getter=os.getenv,
        logger=runtime_logger or logger,
        minimum=minimum,
        maximum=maximum,
    )


def cors_settings() -> tuple[list[str], bool]:
    return cors_settings_impl(env_getter=os.getenv)


def integrator_scheduler_config(
    runtime_logger: Any | None = None,
    *,
    env_getter: Callable[[str], str | None] = os.getenv,
) -> dict[str, Any]:
    return integrator_scheduler_config_from_env(
        env_getter=env_getter,
        logger=runtime_logger or logger,
    )
