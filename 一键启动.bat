@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo AI Knowledge Base Launcher
echo ========================================
echo.

set "PS_EXEC="
where pwsh >nul 2>nul && set "PS_EXEC=pwsh"
if not defined PS_EXEC set "PS_EXEC=powershell"

%PS_EXEC% -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_windows.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Launch did not complete. Please keep this window screenshot for support.
) else (
    echo Launch flow completed.
)
echo.
pause
exit /b %EXIT_CODE%
