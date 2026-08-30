@echo off
chcp 65001 >nul
title CartoAgent - 地图制图智能体
echo ============================================================
echo   CartoAgent - 地图制图智能体 一键启动
echo ============================================================
echo.

cd /d "%~dp0"

:: 检查后端 venv
if not exist "backend\.venv\Scripts\python.exe" (
    echo [错误] 未找到 Python 虚拟环境: backend\.venv
    echo 请先运行: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

:: 检查前端依赖
if not exist "frontend\vue-app\node_modules" (
    echo [警告] 未找到前端 node_modules，正在安装...
    cd frontend\vue-app
    call npm install
    cd ..\..
)

:: 检查前端构建产物
if not exist "frontend\vue-app\dist\index.html" (
    echo [信息] 未找到前端构建产物，正在构建...
    cd frontend\vue-app
    call npm run build
    cd ..\..
)

:: 检查端口占用
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [警告] 端口 8080 已被占用，正在尝试关闭旧进程...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

echo.
echo [1/2] 启动后端服务 (FastAPI, 端口 8080)...
start "CartoAgent-Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

echo [2/2] 等待后端启动...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo   服务已启动！
echo   前端页面: http://127.0.0.1:8080/app
echo   API文档:  http://127.0.0.1:8080/docs
echo ============================================================
echo.

:: 打开浏览器
start "" "http://127.0.0.1:8080/app"

echo 按任意键关闭此窗口（后端服务将继续在独立窗口运行）...
pause >nul
