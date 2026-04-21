@echo off
chcp 65001 > nul
setlocal

if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000

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
start "AI Knowledge Base" cmd /k "chcp 65001 > nul && set BACKEND_PORT=%BACKEND_PORT% && venv312\Scripts\python.exe -m uvicorn backend.api_server:app --port %BACKEND_PORT% --host 0.0.0.0"

timeout /t 2 /nobreak > nul
echo.
echo Started. Open http://localhost:%BACKEND_PORT%
echo.
pause
