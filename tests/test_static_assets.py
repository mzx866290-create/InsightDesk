"""Tests for frontend static asset mounting."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.static_assets import mount_frontend_static, resolve_frontend_dist


def _build_dist(root, *, with_assets: bool = True):
    dist = root / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    if with_assets:
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_resolve_frontend_dist_walks_up_from_backend_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FRONTEND_DIST_DIR", raising=False)
    project_root = tmp_path / "project"
    _build_dist(project_root)
    backend_file = project_root / "backend" / "core" / "static_assets.py"
    backend_file.parent.mkdir(parents=True)
    backend_file.write_text("", encoding="utf-8")

    resolved = resolve_frontend_dist(str(backend_file))

    assert resolved == str(project_root / "frontend" / "dist")


def test_resolve_frontend_dist_env_override(tmp_path, monkeypatch):
    override = _build_dist(tmp_path / "custom-dist-root")
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(override))

    resolved = resolve_frontend_dist(str(tmp_path / "missing" / "backend.py"))

    assert resolved == str(override)


def test_resolve_frontend_dist_env_override_ignores_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(tmp_path / "nope"))
    backend_file = tmp_path / "backend.py"
    backend_file.write_text("", encoding="utf-8")

    assert resolve_frontend_dist(str(backend_file)) is None


def test_resolve_frontend_dist_returns_none_without_dist(tmp_path, monkeypatch):
    monkeypatch.delenv("FRONTEND_DIST_DIR", raising=False)
    backend_file = tmp_path / "backend.py"
    backend_file.write_text("", encoding="utf-8")

    assert resolve_frontend_dist(str(backend_file)) is None


def test_mount_frontend_static_serves_spa(tmp_path, monkeypatch):
    monkeypatch.delenv("FRONTEND_DIST_DIR", raising=False)
    _build_dist(tmp_path)
    backend_file = tmp_path / "api_server.py"
    backend_file.write_text("", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    mount_frontend_static(app, backend_file=str(backend_file))

    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/").text == "<html></html>"
    assert client.get("/workspaces/123").status_code == 200
    asset_response = client.get("/assets/app.js")
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log(1)"


def test_mount_frontend_static_skips_when_dist_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("FRONTEND_DIST_DIR", raising=False)
    backend_file = tmp_path / "api_server.py"
    backend_file.write_text("", encoding="utf-8")

    app = FastAPI()
    mount_frontend_static(app, backend_file=str(backend_file))

    client = TestClient(app)
    assert client.get("/").status_code == 404
