@echo off
chcp 65001 >nul
echo ========================================
echo 启动企业 AI 知识库系统
echo ========================================
echo.
echo 正在启动 React + FastAPI 版本...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0launch_windows.ps1"
