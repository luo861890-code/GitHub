# CartoAgent - 基于大语言模型和知识图谱的地图制图智能体

> 集成大语言模型（LLM）与知识图谱（KG）的在线地图制图智能体系统：用户通过自然语言描述制图需求，
> 系统自动完成从需求理解、地理数据获取到地图输出的完整流程，并支持类 ArcGIS/QGIS 的
> 矢量编辑（绘制、节点编辑、撤销重做、属性编辑、保存回写）。

---

## 快速开始

### 一键启动（推荐）

**Windows 用户**：双击 `start.bat` 或在 PowerShell 中运行 `.\start.ps1`

脚本会自动：
1. 检查 Python 虚拟环境和前端依赖
2. 构建前端（如未构建）
3. 启动后端服务（FastAPI，端口 8080）
4. 打开浏览器访问前端页面

### 手动启动

```bash
# 1. 启动后端
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# 2. 启动前端开发服务器（另一个终端，可选）
cd frontend/vue-app
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面（生产构建） | http://127.0.0.1:8080/app |
| 前端开发服务器 | http://127.0.0.1:5173 |
| API 文档（Swagger） | http://127.0.0.1:8080/docs |
| 知识图谱面板 | 前端内集成 |

---

## 系统架构

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Leaflet + Pinia + vue-router + D3 |
| 后端 | Python 3.11+ + FastAPI + Uvicorn |
| LLM | DeepSeek API（可配置 OpenAI/通义千问等） |
| 知识图谱 | Neo4j（可选，本地文件兜底） |
| 地理数据 | OpenStreetMap（Overpass API）+ DataV GeoAtlas + 本地 GeoJSON |
| 地图渲染 | Leaflet + 自研 MapPanel（legacy JS） |

### 核心模块

```
carto-agent/
├── backend/                    # 后端服务（FastAPI）
│   ├── app/
│   │   ├── api/                # API 路由层
│   │   │   ├── chat.py         #   智能体对话（SSE 流式）
│   │   │   ├── maps.py         #   地图 CRUD
│   │   │   ├── knowledge.py    #   知识图谱查询
│   │   │   └── settings.py     #   系统配置
│   │   ├── core/               # 核心配置与常量
│   │   │   ├── config.py       #   全局配置（LLM/Neo4j/端口）
│   │   │   ├── constants.py    #   地图类型/OSM查询/图层目录
│   │   │   ├── cartographic_standards.py  # 制图学规范
│   │   │   ├── label_spec.py   #   注记规范
│   │   │   ├── layer_catalog.py #  图层分类目录
│   │   │   ├── crs_manager.py  #   坐标参考系管理
│   │   │   └── kg_ontology.py  #   知识图谱本体
│   │   ├── models/             # Pydantic 数据模型
│   │   ├── services/           # 业务服务层
│   │   │   ├── agent_service.py #   智能体核心（ReAct+KG决策）
│   │   │   ├── map_service.py  #   地图生成与管理
│   │   │   ├── osm_service.py  #   OSM 数据获取（含缓存）
│   │   │   ├── geo_service.py  #   DataV GeoAtlas 行政区划
│   │   │   ├── kg_service.py   #   知识图谱服务
│   │   │   ├── llm_service.py  #   LLM 调用封装
│   │   │   ├── qa_service.py   #   地图质量评估
│   │   │   ├── generalization/ #   地图综合（化简/合并/载负量）
│   │   │   ├── label/          #   注记自动放置
│   │   │   ├── cartography/    #   制图符号与样式
│   │   │   └── data_quality/   #   数据质量检查
│   │   └── utils/              # 通用工具
│   ├── .venv/                  # Python 虚拟环境
│   └── .env                    # 环境变量（LLM API Key 等）
├── frontend/                   # 前端（Vue 3 + Vite）
│   └── vue-app/
│       ├── public/legacy/      # 经典 JS 做图模块（Leaflet MapPanel）
│       │   ├── map.js          #   地图渲染核心
│       │   ├── map-edit.js     #   矢量编辑
│       │   ├── map-lod.js      #   载负量 LOD 分级
│       │   └── leaflet-editable.js
│       ├── src/
│       │   ├── components/     # Vue 组件（图层面板/聊天/编辑器等）
│       │   ├── stores/         # Pinia 状态管理
│       │   ├── services/       # API 封装
│       │   └── types/          # TypeScript 类型
│       └── dist/               # 构建产物（由后端托管）
├── data/                       # 运行数据
│   ├── users/local/            # 用户数据（地图/会话/归档）
│   ├── system_maps/            # 系统预置地图
│   └── kg/                     # 知识图谱数据
├── docs/                       # 文档与规划
├── benchmarks/                 # 性能基准测试
├── start.bat / start.ps1      # 一键启动脚本
└── README.md
```

### 智能体工作流

```
用户自然语言输入
    ↓
需求解析（LLM）→ 提取城市/地图类型/特殊要求
    ↓
知识检索（KG）→ 制图约束、符号规范、配色方案
    ↓
KG 决策查询 → 图层配置、注记规则、载负量阈值
    ↓
工具匹配 → 自动推荐工具链（数据获取/综合/注记/质检）
    ↓
任务规划 → 制定数据获取和地图生成计划
    ↓
地图生成 → OSM/DataV 数据获取 → 图层构建 → 样式应用 → 注记放置
    ↓
质量评估 → 数据完整性/拓扑连接/注记密度/符号规范
    ↓
输出地图 → 前端渲染 + 可编辑 + 可导出
```

---

## 核心功能

### 1. 自然语言制图
- 支持"生成武汉市交通图""做一张北京旅游地图"等自然语言指令
- 智能体自动解析需求、选择数据、配置样式、放置注记
- SSE 流式输出，实时显示思考过程和进度

### 2. 多类型地图支持
| 地图类型 | 说明 |
|----------|------|
| 行政区划图 | 标准政区面+注记+行政中心 |
| 交通图 | 道路分级+铁路地铁+交通枢纽 |
| 水系图 | 河流湖泊+水库+水系注记 |
| 旅游图 | 景点+酒店+交通+旅游路线 |
| 地势图 | DEM+等高线+坡度坡向 |
| 基础地图 | 通用底图+POI+注记 |
| 医疗/教育/商业/绿化 | 专题图（点密度+分级色彩） |

### 3. 地图编辑（类 QGIS）
- 矢量要素绘制（点/线/面）
- 节点编辑（增删/拖拽）
- 撤销/重做
- 属性编辑
- 样式修改（颜色/宽度/透明度）
- 图层管理（显隐/排序/分组）

### 4. 知识图谱驱动
- Neo4j 存储制图学知识（符号规范/配色方案/注记规则）
- 智能体制图决策基于 KG 查询
- 支持知识图谱可视化浏览

### 5. 数据质量保证
- 坐标有效性校验
- 拓扑连接性检查
- 注记密度控制（载负量 LOD）
- 符号规范符合性检查
- 数据完整性审计

---

## 环境配置

### 后端环境变量（backend/.env）

```env
# LLM 配置
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Neo4j 配置（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# 服务配置
HOST=0.0.0.0
PORT=8080
DEBUG=true

# 安全配置（可选）
API_TOKEN=your-secret-token
```

### 系统要求

- Python 3.11+
- Node.js 18+
- （可选）Neo4j 5.x（不配置时使用本地文件兜底）
- Windows 10/11 或 Linux/macOS

---

## 数据来源

| 数据类型 | 来源 |
|----------|------|
| 行政区划 | DataV GeoAtlas（阿里云 DataV 官方行政区划） |
| 道路/铁路/水系/POI | OpenStreetMap（Overpass API，含本地缓存） |
| 地形/DEM | SRTM（可选） |
| 制图知识 | 内置知识图谱（可扩展到 Neo4j） |

---

## 文档索引

- [项目结构说明](docs/项目结构说明.md)
- [架构设计](docs/ARCHITECTURE.md)
- [部署指南](docs/DEPLOYMENT.md)
- [API 文档](http://127.0.0.1:8080/docs)（运行后访问）
- [制图规范参考](docs/cartographic_standards.md)

---

## 许可证

本项目仅供学习和研究使用。
