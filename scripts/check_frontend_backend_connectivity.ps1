param(
    [int]$BackendPort = 18771,
    [int]$FrontendPort = 18772,
    [int]$StartupTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot "venv312\Scripts\python.exe"
$FrontendRoot = Join-Path $ProjectRoot "frontend"

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found at $Python"
}
if (-not (Test-Path $FrontendRoot)) {
    throw "Frontend directory not found at $FrontendRoot"
}

$BackendOut = Join-Path $ProjectRoot "tmp-backend-connect.out.log"
$BackendErr = Join-Path $ProjectRoot "tmp-backend-connect.err.log"
$FrontendOut = Join-Path $ProjectRoot "tmp-frontend-connect.out.log"
$FrontendErr = Join-Path $ProjectRoot "tmp-frontend-connect.err.log"
$FrontendScript = Join-Path $ProjectRoot "tmp-start-frontend-connect.ps1"

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][int]$Seconds
    )

    for ($Index = 0; $Index -lt $Seconds; $Index++) {
        Start-Sleep -Seconds 1
        try {
            $Response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
            if ($Response.StatusCode -eq 200) {
                return $Response
            }
        } catch {
            # Server may still be starting. Keep polling until timeout.
        }
    }
    throw "Timed out waiting for $Url"
}

function Stop-TestProcess {
    param([System.Diagnostics.Process]$Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath $BackendOut, $BackendErr, $FrontendOut, $FrontendErr, $FrontendScript -ErrorAction SilentlyContinue

$BackendProcess = $null
$FrontendProcess = $null

try {
    $BackendProcess = Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "backend.api_server:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $BackendOut `
        -RedirectStandardError $BackendErr `
        -WindowStyle Hidden `
        -PassThru

    $BackendCatalog = Wait-HttpOk "http://127.0.0.1:$BackendPort/api/delivery-templates/catalog" $StartupTimeoutSeconds
    $BackendSessions = Wait-HttpOk "http://127.0.0.1:$BackendPort/api/sessions" 15

    @"
`$ErrorActionPreference = "Stop"
`$env:BACKEND_HOST = "127.0.0.1"
`$env:BACKEND_PORT = "$BackendPort"
`$env:FRONTEND_PORT = "$FrontendPort"
Set-Location "$FrontendRoot"
npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort
"@ | Set-Content -LiteralPath $FrontendScript -Encoding UTF8

    $FrontendProcess = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FrontendScript) `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput $FrontendOut `
        -RedirectStandardError $FrontendErr `
        -WindowStyle Hidden `
        -PassThru

    $FrontendRootResponse = Wait-HttpOk "http://127.0.0.1:$FrontendPort/" $StartupTimeoutSeconds
    $ProxyCatalog = Wait-HttpOk "http://127.0.0.1:$FrontendPort/api/delivery-templates/catalog" $StartupTimeoutSeconds
    $ProxySessions = Wait-HttpOk "http://127.0.0.1:$FrontendPort/api/sessions" 15

    $BackendCatalogJson = $BackendCatalog.Content | ConvertFrom-Json
    $BackendSessionsJson = $BackendSessions.Content | ConvertFrom-Json
    $ProxyCatalogJson = $ProxyCatalog.Content | ConvertFrom-Json
    $ProxySessionsJson = $ProxySessions.Content | ConvertFrom-Json

    [pscustomobject]@{
        ok = $true
        backend_catalog_status = $BackendCatalog.StatusCode
        backend_catalog_templates = @($BackendCatalogJson.templates).Count
        backend_sessions_status = $BackendSessions.StatusCode
        backend_sessions = @($BackendSessionsJson.sessions).Count
        frontend_status = $FrontendRootResponse.StatusCode
        proxy_catalog_status = $ProxyCatalog.StatusCode
        proxy_catalog_templates = @($ProxyCatalogJson.templates).Count
        proxy_sessions_status = $ProxySessions.StatusCode
        proxy_sessions = @($ProxySessionsJson.sessions).Count
        backend_port = $BackendPort
        frontend_port = $FrontendPort
    } | ConvertTo-Json -Compress
} catch {
    Write-Host "--- backend stderr tail ---"
    if (Test-Path $BackendErr) {
        Get-Content $BackendErr -Tail 80
    }
    Write-Host "--- frontend stdout tail ---"
    if (Test-Path $FrontendOut) {
        Get-Content $FrontendOut -Tail 80
    }
    Write-Host "--- frontend stderr tail ---"
    if (Test-Path $FrontendErr) {
        Get-Content $FrontendErr -Tail 80
    }
    throw
} finally {
    Stop-TestProcess $FrontendProcess
    Stop-TestProcess $BackendProcess
    Remove-Item -LiteralPath $FrontendScript -ErrorAction SilentlyContinue

    Start-Sleep -Seconds 1
    foreach ($Port in @($BackendPort, $FrontendPort)) {
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            }
    }
}
