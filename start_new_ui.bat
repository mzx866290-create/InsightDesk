@echo off
chcp 65001 > nul
setlocal

if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=5173
if "%ENABLE_BACKEND_RELOAD%"=="" set ENABLE_BACKEND_RELOAD=0
if "%ALLOW_REMOTE_CLIENTS%"=="" set "ALLOW_REMOTE_CLIENTS=false"
set "BACKEND_EXTRA_ARGS="
if "%ENABLE_BACKEND_RELOAD%"=="1" set "BACKEND_EXTRA_ARGS=--reload"

set "REMOTE_ENABLED=0"
if /I "%ALLOW_REMOTE_CLIENTS%"=="1" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="true" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="yes" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="on" set "REMOTE_ENABLED=1"

set "BACKEND_HOST=127.0.0.1"
set "FRONTEND_HOST=127.0.0.1"
if "%REMOTE_ENABLED%"=="1" (
    set "ALLOW_REMOTE_CLIENTS=true"
    set "BACKEND_HOST=0.0.0.0"
    set "FRONTEND_HOST=0.0.0.0"
) else (
    set "ALLOW_REMOTE_CLIENTS=false"
)

if not defined CORS_ALLOW_ORIGINS (
    if "%REMOTE_ENABLED%"=="1" (
        set "CORS_ALLOW_ORIGINS=http://127.0.0.1:%FRONTEND_PORT%,http://localhost:%FRONTEND_PORT%,http://%COMPUTERNAME%:%FRONTEND_PORT%,http://127.0.0.1:%BACKEND_PORT%,http://localhost:%BACKEND_PORT%,http://%COMPUTERNAME%:%BACKEND_PORT%"
    ) else (
        set "CORS_ALLOW_ORIGINS=http://127.0.0.1:%FRONTEND_PORT%,http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%BACKEND_PORT%,http://localhost:%BACKEND_PORT%"
    )
)

if "%REMOTE_ENABLED%"=="1" (
    echo [WARN] Remote access is enabled. Services will listen on all interfaces.
    echo [WARN] Configure ADMIN_API_TOKEN or APP_AUTH_TOKENS_JSON and limit Windows Firewall access.
    echo [WARN] If using an IP address, set CORS_ALLOW_ORIGINS to that exact trusted frontend origin.
    echo.
)
if "%CORS_ALLOW_ORIGINS%"=="*" echo [WARN] CORS_ALLOW_ORIGINS=* is unsafe. Use exact trusted origins.

echo Starting AI Knowledge Base (React + FastAPI)...
echo.

echo Cleaning existing backend instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'uvicorn backend\.api_server:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" > nul 2>&1

start "FastAPI Backend" cmd /k "chcp 65001 > nul && cd /d %~dp0 && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && venv312\Scripts\python.exe -m uvicorn backend.api_server:app %BACKEND_EXTRA_ARGS% --port %BACKEND_PORT% --host %BACKEND_HOST%"

timeout /t 2 /nobreak > nul

start "React Frontend" cmd /k "chcp 65001 > nul && cd /d %~dp0\frontend && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && npm run dev -- --host %FRONTEND_HOST% --port %FRONTEND_PORT%"

echo.
echo Starting...
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   Frontend:    http://localhost:%FRONTEND_PORT%
echo.
echo Press any key to close this launcher window. Backend and frontend will keep running.
pause > nul
