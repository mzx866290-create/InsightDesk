param(
    [switch]$WithConnectivity
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot "venv312\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found at $Python"
}

Push-Location $ProjectRoot
try {
    $BackendFiles = @(
        "backend\api_server.py"
        "backend\agent_core.py"
        "backend\chat_store.py"
        "backend\deck_service.py"
    )

    & $Python -m py_compile @BackendFiles
    & $Python -m pytest -q

    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm run build
    } finally {
        Pop-Location
    }

    if ($WithConnectivity) {
        & (Join-Path $ProjectRoot "scripts\check_frontend_backend_connectivity.ps1")
    }
} finally {
    Pop-Location
}
