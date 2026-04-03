$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
}

$script:ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $script:ProjectRoot

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Stop-WithError {
    param(
        [string]$Message,
        [string[]]$Hints = @()
    )

    Write-Host ""
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    foreach ($hint in $Hints) {
        Write-Host "  - $hint" -ForegroundColor Yellow
    }
    exit 1
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($machinePath) { $parts += $machinePath }
    if ($userPath) { $parts += $userPath }
    $env:Path = ($parts -join ";")
}

function Get-CommandPath {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) {
            return $cmd.Source
        }
    }
    return $null
}

function Invoke-Process {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $script:ProjectRoot,
        [switch]$AllowFailure
    )

    $oldLocation = Get-Location
    try {
        Set-Location $WorkingDirectory
        & $FilePath @Arguments
        $exitCode = $LASTEXITCODE
        if (-not $AllowFailure -and $exitCode -ne 0) {
            Stop-WithError "Command failed: $FilePath $($Arguments -join ' ')" @(
                "Please keep the console screenshot and contact the maintainer."
            )
        }
        return $exitCode
    } finally {
        Set-Location $oldLocation
    }
}

function Resolve-PythonCommand {
    $python = Get-CommandPath @("python")
    if ($python) {
        return @{
            FilePath = $python
            Arguments = @()
        }
    }

    $py = Get-CommandPath @("py")
    if ($py) {
        return @{
            FilePath = $py
            Arguments = @("-3")
        }
    }

    return $null
}

function Get-PythonVersion {
    param($PythonCommand)

    $output = & $PythonCommand.FilePath @($PythonCommand.Arguments + @("--version")) 2>&1
    $text = ($output | Out-String).Trim()
    if ($text -match "Python\s+(\d+)\.(\d+)") {
        return [Version]::new([int]$Matches[1], [int]$Matches[2], 0)
    }
    return [Version]::new(0, 0, 0)
}

function Ensure-Winget {
    $winget = Get-CommandPath @("winget")
    if (-not $winget) {
        Stop-WithError "winget was not found on this computer." @(
            "Please install App Installer from Microsoft Store, then re-run the launcher.",
            "If the company blocks winget, ask the maintainer for an offline install package."
        )
    }
    return $winget
}

function Ensure-WingetPackage {
    param(
        [string[]]$CommandNames,
        [string]$DisplayName,
        [string]$WingetId
    )

    $existing = Get-CommandPath $CommandNames
    if ($existing) {
        Write-Ok "$DisplayName is ready."
        return $existing
    }

    $winget = Ensure-Winget
    Write-Info "Installing $DisplayName with winget ..."
    & $winget install --id $WingetId --exact --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Automatic install failed for $DisplayName." @(
            "You can try again manually: winget install --id $WingetId --exact",
            "If a permission dialog appeared, allow it and run the launcher again."
        )
    }

    Refresh-Path
    $installed = Get-CommandPath $CommandNames
    if (-not $installed) {
        Stop-WithError "$DisplayName installation finished but the command is still unavailable." @(
            "Close all terminals and re-run the launcher.",
            "If it still fails, verify the installation from the Start menu."
        )
    }

    Write-Ok "$DisplayName installed successfully."
    return $installed
}

function Read-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*#") {
            continue
        }
        if ($line -match "^\s*$Name\s*=\s*(.*)\s*$") {
            $value = $Matches[1].Trim()
            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return $null
}

function Test-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 5
    )

    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds
        return $true
    } catch {
        return $false
    }
}

function Wait-ForHttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpReady -Url $Url -TimeoutSeconds 5) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Get-PortListeners {
    param([int[]]$Ports)

    $results = @()
    try {
        $results = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -in $Ports }
    } catch {
        $results = @()
    }
    return $results
}

function Get-LanIpAddress {
    try {
        $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -ne "127.0.0.1" -and
                $_.IPAddress -notlike "169.254.*" -and
                -not $_.SkipAsSource
            } |
            Sort-Object InterfaceMetric, ifIndex
        if ($ips) {
            return ($ips | Select-Object -First 1).IPAddress
        }
    } catch {
    }

    $fallback = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
        Where-Object {
            $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
            $_.IPAddressToString -ne "127.0.0.1" -and
            $_.IPAddressToString -notlike "169.254.*"
        } |
        Select-Object -First 1

    if ($fallback) {
        return $fallback.IPAddressToString
    }

    return $null
}

function Ensure-OpenRouterKey {
    param([string]$ApiKey)

    if ($null -eq $ApiKey) {
        $trimmed = ""
    } else {
        $trimmed = $ApiKey.Trim()
    }

    if (-not $trimmed) {
        return $false
    }

    $placeholders = @(
        "your_openrouter_api_key_here",
        "sk-or-v1-xxxxx",
        "your_api_key_here"
    )
    return $trimmed -notin $placeholders
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$Command
    )

    $wrapped = "title $Title && $Command"
    return Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", $wrapped) -PassThru
}

Write-Section "Check environment"

$pythonCommand = Resolve-PythonCommand
if (-not $pythonCommand) {
    Ensure-WingetPackage -CommandNames @("python", "py") -DisplayName "Python 3" -WingetId "Python.Python.3.12" | Out-Null
    $pythonCommand = Resolve-PythonCommand
}

$pythonVersion = Get-PythonVersion -PythonCommand $pythonCommand
if ($pythonVersion -lt [Version]::new(3, 9, 0)) {
    Stop-WithError "Python 3.9 or newer is required." @(
        "Current detected version: $pythonVersion",
        "Please upgrade Python, then run the launcher again."
    )
}
Write-Ok "Python version is $pythonVersion."

$null = Ensure-WingetPackage -CommandNames @("node") -DisplayName "Node.js LTS" -WingetId "OpenJS.NodeJS.LTS"
$npmCmd = Ensure-WingetPackage -CommandNames @("npm.cmd", "npm") -DisplayName "npm" -WingetId "OpenJS.NodeJS.LTS"

$envPath = Join-Path $script:ProjectRoot ".env"
$envExamplePath = Join-Path $script:ProjectRoot ".env.example"
if (-not (Test-Path $envPath)) {
    Write-Info "Creating .env from .env.example ..."
    Copy-Item $envExamplePath $envPath
    Write-Ok ".env created."
}

$provider = Read-DotEnvValue -Path $envPath -Name "LLM_PROVIDER"
if (-not $provider) {
    $provider = "ollama"
}
$provider = $provider.Trim().ToLowerInvariant()

Write-Section "Prepare project dependencies"

$venvPython = Join-Path $script:ProjectRoot "venv312\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Info "Creating Python virtual environment venv312 ..."
    Invoke-Process -FilePath $pythonCommand.FilePath -Arguments ($pythonCommand.Arguments + @("-m", "venv", "venv312"))
}

$backendDependencyReady = $false
try {
    & $venvPython -c "import fastapi, uvicorn, requests"
    if ($LASTEXITCODE -eq 0) {
        $backendDependencyReady = $true
    }
} catch {
    $backendDependencyReady = $false
}

if (-not $backendDependencyReady) {
    Write-Info "Installing backend dependencies ..."
    Invoke-Process -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Process -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
}
Write-Ok "Backend dependencies are ready."

$frontendModules = Join-Path $script:ProjectRoot "frontend\node_modules"
if (-not (Test-Path $frontendModules)) {
    Write-Info "Installing frontend dependencies ..."
    Invoke-Process -FilePath $npmCmd -Arguments @("install") -WorkingDirectory (Join-Path $script:ProjectRoot "frontend")
}
Write-Ok "Frontend dependencies are ready."

Write-Section "Check model configuration"

switch ($provider) {
    "ollama" {
        $ollamaExe = Ensure-WingetPackage -CommandNames @("ollama") -DisplayName "Ollama" -WingetId "Ollama.Ollama"
        $ollamaBaseUrl = Read-DotEnvValue -Path $envPath -Name "OLLAMA_BASE_URL"
        if (-not $ollamaBaseUrl) {
            $ollamaBaseUrl = "http://localhost:11434"
        }

        if (-not (Test-HttpReady -Url "$ollamaBaseUrl/api/tags" -TimeoutSeconds 3)) {
            Write-Info "Ollama is not running. Starting ollama serve ..."
            Start-Process -FilePath $ollamaExe -ArgumentList @("serve") -WindowStyle Minimized | Out-Null
            if (-not (Wait-ForHttpReady -Url "$ollamaBaseUrl/api/tags" -TimeoutSeconds 25)) {
                Stop-WithError "Ollama service did not become ready." @(
                    "Open a terminal and try: ollama serve",
                    "If Windows Security asked for permission, allow it and run the launcher again."
                )
            }
        }
        Write-Ok "Ollama service is ready."

        $ollamaModel = Read-DotEnvValue -Path $envPath -Name "OLLAMA_MODEL"
        if (-not $ollamaModel) {
            $ollamaModel = "qwen2.5:7b"
        }

        $tagsResponse = Invoke-RestMethod -Method Get -Uri "$ollamaBaseUrl/api/tags" -TimeoutSec 10
        $availableModels = @($tagsResponse.models | ForEach-Object { $_.name })
        if ($availableModels -notcontains $ollamaModel) {
            Write-Info "Pulling Ollama model $ollamaModel ..."
            Invoke-Process -FilePath $ollamaExe -Arguments @("pull", $ollamaModel)
        }
        Write-Ok "Ollama model $ollamaModel is ready."
    }
    "openrouter" {
        $apiKey = Read-DotEnvValue -Path $envPath -Name "OPENROUTER_API_KEY"
        if (-not (Ensure-OpenRouterKey -ApiKey $apiKey)) {
            Stop-WithError "OPENROUTER_API_KEY is missing or still using a placeholder value." @(
                "Open .env and set OPENROUTER_API_KEY to a real key.",
                "Then re-run the launcher."
            )
        }
        Write-Ok "OpenRouter API key looks valid."
    }
    default {
        Stop-WithError "LLM_PROVIDER must be ollama or openrouter." @(
            "Current value: $provider",
            "Please edit .env and set LLM_PROVIDER=ollama or LLM_PROVIDER=openrouter."
        )
    }
}

Write-Section "Check existing services"

$backendPort = 8080
if ($env:BACKEND_PORT) {
    $backendPort = [int]$env:BACKEND_PORT
}

$frontendPort = 3000
if ($env:FRONTEND_PORT) {
    $frontendPort = [int]$env:FRONTEND_PORT
}

$backendHealthUrl = "http://127.0.0.1:$backendPort/api/health"
$frontendUrl = "http://127.0.0.1:$frontendPort"

$backendReady = Test-HttpReady -Url $backendHealthUrl -TimeoutSeconds 3
$frontendReady = Test-HttpReady -Url $frontendUrl -TimeoutSeconds 3

if ($backendReady -and $frontendReady) {
    Write-Warn "Frontend and backend already appear to be running."
} else {
    $listeners = Get-PortListeners -Ports @($frontendPort, $backendPort)
    if ($listeners) {
        $ports = ($listeners.LocalPort | Sort-Object -Unique) -join ", "
        Stop-WithError "Port(s) $ports are already in use." @(
            "Close the existing program using these ports, then run the launcher again.",
            "If this is your previous project window, keep it and open http://localhost:$frontendPort directly."
        )
    }

    Write-Section "Start services"

    $backendCommand = "chcp 65001 > nul && cd /d `"$script:ProjectRoot`" && set BACKEND_PORT=$backendPort && set FRONTEND_PORT=$frontendPort && set ALLOW_REMOTE_CLIENTS=true && set CORS_ALLOW_ORIGINS=* && `"$venvPython`" -m uvicorn api_server:app --host 0.0.0.0 --port $backendPort"
    $frontendCommand = "chcp 65001 > nul && cd /d `"$($script:ProjectRoot)\frontend`" && set BACKEND_PORT=$backendPort && set FRONTEND_PORT=$frontendPort && `"$npmCmd`" run dev -- --host 0.0.0.0 --port $frontendPort"

    $null = Start-ServiceWindow -Title "AI Backend" -Command $backendCommand
    if (-not (Wait-ForHttpReady -Url $backendHealthUrl -TimeoutSeconds 40)) {
        Stop-WithError "Backend failed to start." @(
            "Please check the backend command window for the detailed error.",
            "If the error mentions Python packages, re-run the launcher after the network is available."
        )
    }
    Write-Ok "Backend started."

    $null = Start-ServiceWindow -Title "AI Frontend" -Command $frontendCommand
    if (-not (Wait-ForHttpReady -Url $frontendUrl -TimeoutSeconds 50)) {
        Stop-WithError "Frontend failed to start." @(
            "Please check the frontend command window for the detailed error.",
            "If the error mentions npm or esbuild, try running the launcher again."
        )
    }
    Write-Ok "Frontend started."
}

Write-Section "Available addresses"

$lanIp = Get-LanIpAddress
Write-Host "Local page : http://localhost:$frontendPort" -ForegroundColor Green
if ($lanIp) {
    Write-Host "LAN page   : http://$lanIp`:$frontendPort" -ForegroundColor Green
    Write-Host "Local API  : http://localhost:$backendPort/docs" -ForegroundColor Green
    Write-Host "LAN API    : http://$lanIp`:$backendPort/docs" -ForegroundColor Green
    Write-Host ""
    Write-Warn "If coworkers still cannot open the LAN address, check that both computers are on the same network and allow Windows Firewall access for ports $frontendPort and $backendPort."
} else {
    Write-Warn "Could not detect a LAN IPv4 address automatically."
}

try {
    Start-Process "http://localhost:$frontendPort" | Out-Null
    Write-Ok "Browser opened. Keep the backend and frontend windows running while coworkers are using the system."
} catch {
    Write-Warn "Could not open the browser automatically. Please open http://localhost:$frontendPort manually."
    Write-Ok "Backend and frontend are ready. Keep their windows running while coworkers are using the system."
}
