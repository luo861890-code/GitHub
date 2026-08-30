# CartoAgent 一键启动脚本 (PowerShell)
# 用法: .\start.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CartoAgent - 地图制图智能体 一键启动" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查后端 venv
$venvPython = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[错误] 未找到 Python 虚拟环境 backend\.venv" -ForegroundColor Red
    Write-Host "请先创建虚拟环境并安装依赖"
    Read-Host "按回车退出"
    exit 1
}

# 检查前端依赖
$nodeModules = Join-Path $ProjectRoot "frontend\vue-app\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "[信息] 安装前端依赖..." -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "frontend\vue-app")
    npm install
    Pop-Location
}

# 检查前端构建产物
$distIndex = Join-Path $ProjectRoot "frontend\vue-app\dist\index.html"
if (-not (Test-Path $distIndex)) {
    Write-Host "[信息] 构建前端..." -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "frontend\vue-app")
    npm run build
    Pop-Location
}

# 检查端口占用并关闭旧进程
$port8080 = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 8080 }
if ($port8080) {
    Write-Host "[警告] 端口 8080 已被占用，关闭旧进程..." -ForegroundColor Yellow
    $port8080 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# 启动后端
Write-Host ""
Write-Host "[1/2] 启动后端服务 (FastAPI, 端口 8080)..." -ForegroundColor Green
$backendDir = Join-Path $ProjectRoot "backend"
$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload")
Start-Process -FilePath $venvPython -ArgumentList $uvicornArgs -WorkingDirectory $backendDir -WindowStyle Normal

Write-Host "[2/2] 等待后端启动..." -ForegroundColor Green
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  服务已启动！" -ForegroundColor Green
Write-Host "  前端页面: http://127.0.0.1:8080/app" -ForegroundColor White
Write-Host "  API文档:  http://127.0.0.1:8080/docs" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 打开浏览器
Start-Process "http://127.0.0.1:8080/app"

Write-Host "按回车关闭此窗口（后端服务将继续在独立窗口运行）..."
Read-Host