# -*- mode: python ; coding: utf-8 -*-
"""
CartoAgent 桌面版 PyInstaller 打包配置

构建命令:
    pyinstaller desktop/CartoAgent.spec

产物: dist/CartoAgent/ 目录（单目录模式，体积更小启动更快）
"""
import os
import sys

block_cipher = None

# 项目根目录（spec 文件在 desktop/ 下，上一级是项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))  # type: ignore[name-defined]
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "vue-app", "dist")
GEO_DATA_DIR = os.path.join(BACKEND_DIR, "data", "geo")
DEM_DATA_DIR = os.path.join(BACKEND_DIR, "data", "dem")
SYSTEM_MAPS_DIR = os.path.join(PROJECT_ROOT, "data", "system_maps")
KG_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "kg")

# 收集数据文件（保留目录结构）
datas = []

# 前端构建产物
if os.path.exists(FRONTEND_DIST):
    datas.append((FRONTEND_DIST, "frontend/vue-app/dist"))

# GeoJSON 地理数据
if os.path.exists(GEO_DATA_DIR):
    datas.append((GEO_DATA_DIR, "backend/data/geo"))

# DEM 高程数据（可选，体积大，按需包含）
if os.path.exists(DEM_DATA_DIR):
    # 只包含武汉周边的 6 个 tile，避免体积过大
    for f in os.listdir(DEM_DATA_DIR):
        if f.endswith(".hgt") and not f.endswith(".gz"):
            datas.append((os.path.join(DEM_DATA_DIR, f), "backend/data/dem"))

# 系统预置地图
if os.path.exists(SYSTEM_MAPS_DIR):
    datas.append((SYSTEM_MAPS_DIR, "data/system_maps"))

# 知识图谱初始数据
if os.path.exists(KG_DATA_DIR):
    datas.append((KG_DATA_DIR, "data/kg"))

# 隐藏导入（PyInstaller 无法自动检测的动态导入）
hiddenimports = [
    # FastAPI / Uvicorn
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # Pydantic
    "pydantic_settings",
    "pydantic.deprecated.decorator",
    # 地理计算
    "shapely",
    "shapely.geometry",
    "shapely.ops",
    "pyproj",
    # LLM
    "openai",
    # 其他
    "PIL",
    "PIL.Image",
    "numpy",
    "neo4j",
]

a = Analysis(
    ["desktop/app.py"],
    pathex=[
        BACKEND_DIR,
        os.path.join(PROJECT_ROOT, "desktop"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除体积大且用不到的模块
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "pytest",
        "langchain",
        "httpx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CartoAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 窗口模式，不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "desktop", "assets", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CartoAgent",
)
