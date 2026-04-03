$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot "venv312\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found at $Python"
}

Push-Location $ProjectRoot
try {
    & $Python -m py_compile api_server.py agent_core.py chat_store.py deck_service.py
    & $Python -m pytest tests/test_phase1_api.py

    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm run build
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
