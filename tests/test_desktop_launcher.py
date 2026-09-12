"""Tests for the desktop launcher helpers."""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import desktop.app as desktop_app


class _FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.wait_timeout: float | None = None

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeout = timeout
        return 0

    def kill(self) -> None:
        self.killed = True


def test_find_free_port_skips_occupied_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        occupied = sock.getsockname()[1]

        found = desktop_app.find_free_port(occupied, attempts=5)

    assert found > occupied


def test_find_free_port_returns_start_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]

    assert desktop_app.find_free_port(free) == free


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args) -> None:
        return


def test_wait_for_health_true_when_backend_ready():
    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert desktop_app.wait_for_health(
            server.server_address[1], timeout=5
        )
    finally:
        server.shutdown()
        server.server_close()


def test_wait_for_health_false_on_timeout():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]

    assert not desktop_app.wait_for_health(closed_port, timeout=0.2)


def test_start_backend_uses_loopback_and_selected_port(monkeypatch):
    captured: dict = {}

    class _StubPopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(desktop_app.subprocess, "Popen", _StubPopen)

    desktop_app.start_backend(8123)

    args = captured["args"]
    assert args[:3] == [sys.executable, "-m", "uvicorn"]
    assert "--host" in args and "127.0.0.1" in args
    assert "--port" in args and "8123" in args
    assert captured["kwargs"]["cwd"] == str(desktop_app.PROJECT_ROOT)


def test_stop_backend_terminates_then_waits(monkeypatch):
    fake = _FakeProcess()
    monkeypatch.setattr(desktop_app, "_server_process", fake)

    desktop_app.stop_backend()

    assert fake.terminated
    assert not fake.killed
    assert fake.wait_timeout == 10
    assert desktop_app._server_process is None


def test_stop_backend_kills_when_terminate_times_out(monkeypatch):
    class _StuckProcess(_FakeProcess):
        def wait(self, timeout: float | None = None) -> int:
            if self.terminated and not self.killed:
                raise subprocess.TimeoutExpired(cmd="uvicorn", timeout=timeout or 10)
            return 0

    fake = _StuckProcess()
    monkeypatch.setattr(desktop_app, "_server_process", fake)

    desktop_app.stop_backend()

    assert fake.killed
    assert desktop_app._server_process is None


def test_stop_backend_noop_without_process(monkeypatch):
    monkeypatch.setattr(desktop_app, "_server_process", None)

    desktop_app.stop_backend()

    assert desktop_app._server_process is None


def test_run_opens_window_after_health(monkeypatch, tmp_path):
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    monkeypatch.setattr(desktop_app, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop_app, "find_free_port", lambda start, attempts=20: 8123)
    fake = _FakeProcess()
    monkeypatch.setattr(desktop_app, "start_backend", lambda port: fake)
    monkeypatch.setattr(desktop_app, "wait_for_health", lambda port, timeout=None: True)

    opened: dict = {}

    class _StubWebview:
        @staticmethod
        def create_window(title, url, **kwargs):
            opened["title"] = title
            opened["url"] = url
            opened.update(kwargs)

        @staticmethod
        def start():
            opened["started"] = True

    monkeypatch.setitem(sys.modules, "webview", _StubWebview)

    desktop_app.run()

    assert opened["title"] == "InsightDesk"
    assert opened["url"] == "http://127.0.0.1:8123"
    assert opened["started"]
    assert fake.terminated


def test_run_exits_without_frontend_dist(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "webview", object())

    try:
        desktop_app.run()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit when dist is missing")
