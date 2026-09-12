# Builds the packaged Windows backend (PyInstaller onedir) that the
# Electron shell bundles as an extraResource.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path $PSScriptRoot "venv312\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

& $python -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
}

& $python -m PyInstaller --noconfirm --clean `
    --distpath desktop\pyinstaller\dist `
    --workpath desktop\pyinstaller\build `
    --log-level WARN `
    desktop\pyinstaller\insightdesk-backend.spec

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Backend bundle: desktop\pyinstaller\dist\insightdesk-backend\insightdesk-backend.exe"
Write-Host "Next: cd desktop\electron; npm install; npm run dist  (NSIS installer)"
