@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ========================================
echo InsightDesk Desktop Launcher
echo ========================================
echo.

if not exist "venv312\Scripts\python.exe" (
    echo [ERROR] venv312 not found. Run setup.bat first.
    pause
    exit /b 1
)

if not exist "frontend\dist\index.html" (
    echo [ERROR] frontend/dist not found. Build it first: cd frontend ^&^& npm run build
    pause
    exit /b 1
)

"venv312\Scripts\python.exe" "desktop\app.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Desktop launch failed with code %EXIT_CODE%. See messages above.
    pause
)
exit /b %EXIT_CODE%
