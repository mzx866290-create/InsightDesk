@echo off
chcp 65001 >nul
echo ========================================
echo 企业 AI 知识库系统 - 快速安装脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

echo [1/4] 创建虚拟环境...
if not exist venv (
    python -m venv venv
    echo ✓ 虚拟环境创建成功
) else (
    echo ✓ 虚拟环境已存在
)

echo.
echo [2/4] 激活虚拟环境并安装依赖...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
echo ✓ 依赖安装完成

echo.
echo [3/4] 配置环境变量...
if not exist .env (
    copy .env.example .env
    echo ✓ 已创建 .env 文件，请编辑配置
    echo.
    echo 重要提示：
    echo - Ollama 模式：设置 LLM_PROVIDER=ollama，并运行 ollama pull qwen2.5:7b
    echo - OpenRouter 模式：设置 LLM_PROVIDER=openrouter，并配置 OPENROUTER_API_KEY
    echo.
    notepad .env
) else (
    echo ✓ .env 文件已存在
)

echo.
echo [4/4] 安装完成！
echo.
echo ========================================
echo 启动方式：
echo   1. 激活虚拟环境: venv\Scripts\activate
echo   2. 启动应用: streamlit run app.py
echo.
echo 或直接运行: start.bat
echo ========================================
echo.
pause
