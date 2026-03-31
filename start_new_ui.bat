@echo off
chcp 65001 > nul
echo 正在启动 AI 知识库 (新版 React 界面)...
echo.

REM 启动 FastAPI 后端
start "FastAPI 后端" cmd /k "chcp 65001 > nul && cd /d %~dp0 && venv312\Scripts\python.exe -m uvicorn api_server:app --reload --port 8000 --host 0.0.0.0"

REM 等待后端启动
timeout /t 2 /nobreak > nul

REM 启动 React 前端 (开发模式)
start "React 前端" cmd /k "chcp 65001 > nul && cd /d %~dp0\frontend && npm run dev"

echo.
echo 启动中...
echo   后端 API:  http://localhost:8000
echo   前端界面:  http://localhost:3000
echo.
echo 按任意键退出本窗口（后端和前端将继续运行）
pause > nul
