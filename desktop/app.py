"""InsightDesk desktop window launcher.

Starts the FastAPI backend as a local subprocess, waits for readiness, then
opens the built SPA inside a native pywebview window. Closing the window
shuts the backend down.
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HEALTH_TIMEOUT_SECONDS = 120.0
HEALTH_POLL_INTERVAL_SECONDS = 0.5

_server_process: subprocess.Popen[bytes] | None = None


def find_free_port(start: int, attempts: int = 20) -> int:
    """Return the first free port starting at ``start``, stepping up on conflict.

    Binds without ``SO_REUSEADDR``: on Windows that flag would let this probe
    successfully bind a port already listening elsewhere, hiding real conflicts.
    """
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port found in range {start}-{start + attempts - 1}")


def wait_for_health(port: int, timeout: float = HEALTH_TIMEOUT_SECONDS) -> bool:
    """Poll the backend health endpoint until it responds or timeout."""
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
    return False


def start_backend(port: int) -> subprocess.Popen[bytes]:
    """Launch uvicorn bound to loopback only."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api_server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        creationflags=creationflags,
    )


def stop_backend() -> None:
    global _server_process
    if _server_process is None:
        return
    process, _server_process = _server_process, None
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run() -> None:
    global _server_process
    try:
        import webview
    except ImportError as exc:
        print(
            "缺少 pywebview，请先安装：venv312\\Scripts\\python.exe -m pip install pywebview",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if not (dist_dir / "index.html").is_file():
        print(
            "未找到 frontend/dist/index.html，请先构建前端：cd frontend && npm run build",
            file=sys.stderr,
        )
        raise SystemExit(1)

    port = find_free_port(8000)
    _server_process = start_backend(port)
    atexit.register(stop_backend)

    if not wait_for_health(port):
        stop_backend()
        print(
            f"后端启动失败：http://127.0.0.1:{port}/api/health 在 {HEALTH_TIMEOUT_SECONDS:.0f}s 内未就绪",
            file=sys.stderr,
        )
        raise SystemExit(1)

    webview.create_window(
        "InsightDesk",
        f"http://127.0.0.1:{port}",
        width=1440,
        height=900,
        min_size=(1024, 700),
    )
    try:
        webview.start()
    finally:
        stop_backend()


if __name__ == "__main__":
    run()
