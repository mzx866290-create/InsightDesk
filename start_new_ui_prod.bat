@echo off
chcp 65001 > nul
echo 正在构建并启动 AI 知识库 (生产模式，单端口)...
echo.

REM 构建前端
cd /d %~dp0\frontend
call npm run build
if %errorlevel% neq 0 (
    echo 前端构建失败！
    pause
    exit /b 1
)

REM 启动 FastAPI（同时托管前端静态文件）
cd /d %~dp0
start "AI 知识库" cmd /k "chcp 65001 > nul && venv312\Scripts\python.exe -m uvicorn api_server:app --port 8000 --host 0.0.0.0"

timeout /t 2 /nobreak > nul
echo.
echo 已启动！访问地址：http://localhost:8000
echo.
pause
