@echo off
chcp 65001 > nul
setlocal

if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000
if "%ALLOW_REMOTE_CLIENTS%"=="" set "ALLOW_REMOTE_CLIENTS=false"

set "REMOTE_ENABLED=0"
if /I "%ALLOW_REMOTE_CLIENTS%"=="1" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="true" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="yes" set "REMOTE_ENABLED=1"
if /I "%ALLOW_REMOTE_CLIENTS%"=="on" set "REMOTE_ENABLED=1"

set "BACKEND_HOST=127.0.0.1"
if "%REMOTE_ENABLED%"=="1" (
    set "ALLOW_REMOTE_CLIENTS=true"
    set "BACKEND_HOST=0.0.0.0"
) else (
    set "ALLOW_REMOTE_CLIENTS=false"
)

if not defined CORS_ALLOW_ORIGINS (
    if "%REMOTE_ENABLED%"=="1" (
        set "CORS_ALLOW_ORIGINS=http://127.0.0.1:%BACKEND_PORT%,http://localhost:%BACKEND_PORT%,http://%COMPUTERNAME%:%BACKEND_PORT%"
    ) else (
        set "CORS_ALLOW_ORIGINS=http://127.0.0.1:%BACKEND_PORT%,http://localhost:%BACKEND_PORT%"
    )
)

if "%REMOTE_ENABLED%"=="1" (
    echo [WARN] Remote access is enabled. The service will listen on all interfaces.
    echo [WARN] Configure ADMIN_API_TOKEN or APP_AUTH_TOKENS_JSON and limit Windows Firewall access.
    echo.
)
if "%CORS_ALLOW_ORIGINS%"=="*" echo [WARN] CORS_ALLOW_ORIGINS=* is unsafe. Use exact trusted origins.

echo Building and starting AI Knowledge Base (production mode)...
echo.

cd /d %~dp0\frontend
call npm run build
if %errorlevel% neq 0 (
    echo Frontend build failed.
    pause
    exit /b 1
)

cd /d %~dp0
start "AI Knowledge Base" cmd /k "chcp 65001 > nul && set BACKEND_PORT=%BACKEND_PORT% && venv312\Scripts\python.exe -m uvicorn backend.api_server:app --port %BACKEND_PORT% --host %BACKEND_HOST%"

timeout /t 2 /nobreak > nul
echo.
echo Started. Open http://localhost:%BACKEND_PORT%
echo.
pause
