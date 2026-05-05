"""Static frontend asset mounting for the FastAPI app."""

from __future__ import annotations

import os

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend_static(app, *, backend_file: str) -> None:
    frontend_dist = os.path.join(os.path.dirname(backend_file), "frontend", "dist")
    if not os.path.isdir(frontend_dist):
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
