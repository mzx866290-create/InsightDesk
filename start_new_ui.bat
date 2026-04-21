@echo off
chcp 65001 > nul
setlocal

if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=5173
if "%ENABLE_BACKEND_RELOAD%"=="" set ENABLE_BACKEND_RELOAD=0
set "BACKEND_EXTRA_ARGS="
if "%ENABLE_BACKEND_RELOAD%"=="1" set "BACKEND_EXTRA_ARGS=--reload"

echo Starting AI Knowledge Base (React + FastAPI)...
echo.

echo Cleaning existing backend instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'uvicorn backend\.api_server:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" > nul 2>&1

start "FastAPI Backend" cmd /k "chcp 65001 > nul && cd /d %~dp0 && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && set ALLOW_REMOTE_CLIENTS=true && set CORS_ALLOW_ORIGINS=* && venv312\Scripts\python.exe -m uvicorn backend.api_server:app %BACKEND_EXTRA_ARGS% --port %BACKEND_PORT% --host 0.0.0.0"

timeout /t 2 /nobreak > nul

start "React Frontend" cmd /k "chcp 65001 > nul && cd /d %~dp0\frontend && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT%"

echo.
echo Starting...
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   Frontend:    http://localhost:%FRONTEND_PORT%
echo.
echo Press any key to close this launcher window. Backend and frontend will keep running.
pause > nul
