@echo off
chcp 65001 >nul
echo ========================================
echo 企业 AI 知识库系统 - 快速安装脚本
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

echo [1/5] 创建虚拟环境...
if not exist venv312 (
    python -m venv venv312
    echo [OK] 已创建 venv312
) else (
    echo [OK] venv312 已存在
)

echo.
echo [2/5] 安装后端依赖...
call venv312\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/5] 安装前端依赖...
if exist frontend\package.json (
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
    popd
    echo [OK] 前端依赖安装完成
) else (
    echo [警告] 未找到 frontend\package.json，跳过前端依赖安装
)

echo.
echo [4/5] 检查环境变量...
if not exist .env (
    copy .env.example .env >nul
    echo [OK] 已创建 .env，请按需补充配置
    notepad .env
) else (
    echo [OK] .env 已存在
)

echo.
echo [5/5] 安装完成
echo.
echo ========================================
echo 启动方式：
echo   1. 双击 start.bat
echo   2. 或运行 launch_windows.ps1
echo   3. 或使用 docker compose up --build -d
echo.
echo 默认入口已切换为 React + FastAPI。
echo 旧版 Streamlit 前端已废弃。
echo ========================================
echo.
pause
