<#
.SYNOPSIS
CartoAgent 桌面版一键构建脚本

.DESCRIPTION
执行前端构建 + PyInstaller 打包，产物输出到 dist/CartoAgent/
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CartoAgent 桌面版 - 一键构建" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ===== 1. 检查 Python 环境 =====
Write-Host "[1/4] 检查 Python 环境..." -ForegroundColor Green
$venvPython = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  错误: 未找到 Python 虚拟环境 backend\.venv" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Python: $(& $venvPython --version 2>&1)"

# 检查 pyinstaller
$hasPyInstaller = & $venvPython -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  安装 pyinstaller..." -ForegroundColor Yellow
    & $venvPython -m pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  错误: pyinstaller 安装失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✓ PyInstaller: $hasPyInstaller"
}

# ===== 2. 检查前端构建产物 =====
Write-Host ""
Write-Host "[2/4] 检查前端构建产物..." -ForegroundColor Green
$frontendDist = Join-Path $ProjectRoot "frontend\vue-app\dist\index.html"
if (-not (Test-Path $frontendDist)) {
    Write-Host "  前端未构建，正在构建..." -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "frontend\vue-app")
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  错误: 前端构建失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
}
Write-Host "  ✓ 前端构建产物已就绪"

# ===== 3. 清理旧构建 =====
Write-Host ""
Write-Host "[3/4] 清理旧构建产物..." -ForegroundColor Green
$distDir = Join-Path $ProjectRoot "dist"
$buildDir = Join-Path $ProjectRoot "build"
if (Test-Path $distDir) {
    Remove-Item $distDir -Recurse -Force
    Write-Host "  ✓ 已清理 dist/"
}
if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
    Write-Host "  ✓ 已清理 build/"
}

# ===== 4. PyInstaller 打包 =====
Write-Host ""
Write-Host "[4/4] 执行 PyInstaller 打包..." -ForegroundColor Green
Write-Host "  这可能需要 3-5 分钟，请耐心等待..."
Write-Host ""

Push-Location $ProjectRoot
& $venvPython -m PyInstaller `
    --clean `
    --noconfirm `
    "desktop\CartoAgent.spec"
$exitCode = $LASTEXITCODE
Pop-Location

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "  错误: 打包失败，退出码: $exitCode" -ForegroundColor Red
    exit 1
}

# ===== 完成 =====
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  构建完成！" -ForegroundColor Green
Write-Host "  产物目录: dist\CartoAgent\" -ForegroundColor White
Write-Host "  可执行文件: dist\CartoAgent\CartoAgent.exe" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 估算体积
$size = (Get-ChildItem (Join-Path $ProjectRoot "dist\CartoAgent") -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($size / 1MB, 1)
Write-Host "  程序总大小: ${sizeMB} MB"
