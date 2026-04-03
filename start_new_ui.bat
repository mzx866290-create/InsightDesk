@echo off
chcp 65001 > nul
setlocal

if "%BACKEND_PORT%"=="" set BACKEND_PORT=8080
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=3000

echo Starting AI Knowledge Base (React + FastAPI)...
echo.

start "FastAPI Backend" cmd /k "chcp 65001 > nul && cd /d %~dp0 && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && venv312\Scripts\python.exe -m uvicorn api_server:app --reload --port %BACKEND_PORT% --host 0.0.0.0"

timeout /t 2 /nobreak > nul

start "React Frontend" cmd /k "chcp 65001 > nul && cd /d %~dp0\frontend && set BACKEND_PORT=%BACKEND_PORT% && set FRONTEND_PORT=%FRONTEND_PORT% && npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT%"

echo.
echo Starting...
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   Frontend:    http://localhost:%FRONTEND_PORT%
echo.
echo Press any key to close this launcher window. Backend and frontend will keep running.
pause > nul
