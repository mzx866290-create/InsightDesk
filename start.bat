@echo off
chcp 65001 >nul
echo ========================================
echo 启动企业 AI 知识库系统
echo ========================================
echo.

:: 检查虚拟环境
if not exist venv (
    echo [错误] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

:: 检查 .env
if not exist .env (
    echo [警告] .env 文件不存在，使用默认配置
    echo 建议复制 .env.example 为 .env 并配置
    echo.
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 启动应用
echo 正在启动 Streamlit 应用...
echo 浏览器将自动打开 http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

streamlit run app.py
