# CartoAgent 桌面版

将地图制图智能体封装为独立桌面程序，无需安装 Python / Node.js，开箱即用。

## 架构

```
┌──────────────────────────────────────────────┐
│              PyWebView 窗口                   │  ← GUI 壳层
│  ┌────────────────────────────────────────┐  │
│  │  Vue 3 前端 (WebView2 / WebKit)        │  │
│  └───────────────────┬────────────────────┘  │
│                      │ HTTP (127.0.0.1:8765)  │
│  ┌───────────────────▼────────────────────┐  │
│  │  FastAPI 后端 (子线程 uvicorn)         │  │  ← 内嵌服务
│  │  - 地图生成 / 编辑 / 导出              │  │
│  │  - 知识图谱 / 对话智能体               │  │
│  │  - 本地 GeoJSON 数据                  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
         用户数据目录: %APPDATA%/CartoAgent/
```

## 目录结构

```
desktop/
├── app.py              # 桌面应用主入口
├── server.py           # 内嵌后端服务器管理
├── tray.py             # 系统托盘（可选）
├── paths.py            # 路径管理（开发/打包双模式）
├── __init__.py
├── CartoAgent.spec     # PyInstaller 打包配置
├── build.ps1           # 一键构建脚本（Windows）
├── requirements.txt    # 桌面版额外依赖
└── README.md           # 本文档
```

## 开发模式运行

```powershell
# 1. 安装桌面依赖
pip install pywebview pystray Pillow

# 2. 确保前端已构建
cd frontend/vue-app
npm run build

# 3. 启动桌面应用
python desktop/app.py
```

## 打包构建

```powershell
# 一键构建（自动完成前端构建 + PyInstaller 打包）
.\desktop\build.ps1

# 产物位置
dist\CartoAgent\CartoAgent.exe
```

## 数据目录

桌面版将用户数据存储在系统用户目录下，与程序分离：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%\CartoAgent\` |
| macOS | `~/Library/Application Support/CartoAgent/` |
| Linux | `~/.local/share/CartoAgent/` |

目录结构：
```
CartoAgent/
├── users/local/          # 用户地图、会话
├── system_maps/          # 系统预置地图
├── kg/                   # 知识图谱数据
├── cache/                # 运行时缓存（OSM 等）
├── logs/                 # 日志文件
└── config.env            # 用户配置（LLM Key 等）
```

## 配置

首次启动后，用户可以在应用内「设置」页面配置 LLM API Key，配置会写入 `config.env`。

也可以手动编辑 `config.env`，支持的配置项同 `backend/.env`。

## 功能对比

| 功能 | Web 版 | 桌面版 |
|------|--------|--------|
| 地图生成/编辑/导出 | ✓ | ✓ |
| 对话智能体 | ✓ | ✓ |
| 知识图谱 | ✓ | ✓（无 Neo4j 时降级为内存模式） |
| 多用户 | ✓ | ✗（单用户本地） |
| 联网部署 | ✓ | ✗（本地运行） |
| 系统托盘 | - | ✓ |
| 零依赖安装 | ✗ | ✓ |

## 技术栈

- **桌面壳层**: pywebview + WebView2 (Windows) / WebKit (macOS)
- **后端**: Python 3.12 + FastAPI + Uvicorn（内嵌子线程）
- **前端**: Vue 3 + Vite + TypeScript
- **打包**: PyInstaller（单目录模式）
- **系统托盘**: pystray + Pillow（可选，未安装自动降级）
