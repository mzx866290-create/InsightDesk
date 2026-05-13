from types import SimpleNamespace

import pytest

from backend.core.app_lifecycle import register_app_lifecycle_handler


def test_register_app_lifecycle_handler_prefers_add_event_handler():
    calls = []

    app = SimpleNamespace(
        add_event_handler=lambda event, handler: calls.append((event, handler))
    )
    handler = object()

    register_app_lifecycle_handler(app, "startup", handler)

    assert calls == [("startup", handler)]


def test_register_app_lifecycle_handler_falls_back_to_router_hook_list():
    handler = object()
    router = SimpleNamespace(on_shutdown=[])
    app = SimpleNamespace(router=router)

    register_app_lifecycle_handler(app, "shutdown", handler)

    assert router.on_shutdown == [handler]


def test_register_app_lifecycle_handler_rejects_unsupported_app():
    with pytest.raises(RuntimeError, match="startup"):
        register_app_lifecycle_handler(SimpleNamespace(), "startup", object())
