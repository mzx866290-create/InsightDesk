# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for the InsightDesk backend.

Build (from the repo root, using the project venv):
    venv312\\Scripts\\python.exe -m PyInstaller --noconfirm --clean \
        --distpath desktop\\pyinstaller\\dist \
        --workpath desktop\\pyinstaller\\build \
        desktop\\pyinstaller\\insightdesk-backend.spec

The output (desktop/pyinstaller/dist/insightdesk-backend/) is a portable
onedir bundle consumed by the Electron shell as an extraResource.
frontend/dist is bundled so the frozen backend serves the SPA on a single
port (backend/core/static_assets.py resolves frontend/dist by walking up
from its module file, which lives under _MEIPASS when frozen).
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

hiddenimports = [
    "backend",
    "backend.api_server",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
]
hiddenimports += collect_submodules("backend")

datas = [
    (os.path.join(ROOT, "frontend", "dist"), "frontend/dist"),
]

a = Analysis(
    [os.path.join(SPECPATH, "backend_main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="insightdesk-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="insightdesk-backend",
)
