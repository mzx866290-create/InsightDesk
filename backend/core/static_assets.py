"""Static frontend asset mounting for the FastAPI app."""

from __future__ import annotations

import os

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST_DIR_ENV = "FRONTEND_DIST_DIR"


def resolve_frontend_dist(backend_file: str) -> str | None:
    """Locate the built SPA directory.

    Resolution order: explicit ``FRONTEND_DIST_DIR`` override, then walking up
    from the backend package to find ``frontend/dist`` at a project root.
    """
    override = os.environ.get(_DIST_DIR_ENV, "").strip()
    if override:
        return override if os.path.isdir(override) else None

    current = os.path.dirname(os.path.abspath(backend_file))
    for _ in range(6):
        candidate = os.path.join(current, "frontend", "dist")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def mount_frontend_static(app, *, backend_file: str) -> None:
    frontend_dist = resolve_frontend_dist(backend_file)
    if not frontend_dist:
        return

    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(frontend_dist, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(frontend_dist, "index.html")
        return FileResponse(index)
