@echo off
chcp 65001 >nul
echo ========================================
echo 启动 InsightDesk
echo ========================================
echo.
echo 正在启动 React + FastAPI 版本...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0launch_windows.ps1"
