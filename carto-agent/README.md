# CartoAgent - 基于大语言模型和知识图谱的地图制图智能体

> 集成大语言模型与知识图谱的在线地图制图智能体系统：用户通过自然语言描述制图需求，
> 系统自动完成从需求理解、地理数据获取到地图输出的完整流程，并支持类 ArcGIS/QGIS 的
> 矢量编辑（绘制、节点编辑、撤销重做、属性编辑、保存回写）。

> 📖 **结构与模块详解见 [docs/项目结构说明.md](docs/项目结构说明.md)**

## 目录结构（整理后）

```
carto-agent/
├── backend/                 # 后端服务（FastAPI）
│   ├── app/
│   │   ├── api/             # API 路由层（chat / maps / knowledge / settings）
│   │   ├── core/            # 配置、常量、异常、KG 本体
│   │   ├── models/          # Pydantic 数据模型 / Schema
│   │   ├── services/        # 业务服务（agent / llm / map / geo / kg / osm ...）
│   │   └── utils/           # 通用工具
│   ├── data/geo/            # 本地地理数据（GeoJSON，数据流水线生成）
│   ├── scripts/             # 数据流水线脚本（prepare / optimize / clean）
│   ├── runtime/             # 运行时产物（server.pid、服务日志）
│   ├── .env / .env.example  # 环境配置（LLM / Neo4j / 服务）
│   └── requirements.txt
├── frontend/                # 前端（原生 JS 版，后端直接托管）
│   ├── src/
│   │   ├── index.html
│   │   ├── css/style.css
│   │   ├── js/              # 模块化脚本（加载顺序见下）
│   │   │   ├── map.js       # 地图核心（渲染/图层/图例/比例尺/路线/导出）
│   │   │   ├── map-lod.js   # 载负量 LOD 分级（比例尺显隐/抽稀）
│   │   │   ├── map-edit.js  # 编辑模式（绘制/节点/撤销/属性/保存）
│   │   │   ├── chat.js / graph.js / api.js / utils.js / app.js
│   │   └── vendor/          # 本地化第三方库（leaflet-editable.js）
│   └── vue-app/             # Vue 3 备选前端（npm 独立构建）
├── data/                    # 运行数据（maps.json / sessions.json / kg/）
│   └── *.bak / *backup*     # 数据恢复备份（maps.json.bak 等）
├── docs/                    # 文档与长期规划
├── tools/                   # 运维工具（启动 / 补丁 / 测试）
│   ├── start_server.py             # 常规启动
│   ├── start_server_noproxy.py     # 清代理启动（OSM 抓取）
│   ├── patch_def.py                # 一次性补丁
│   ├── fix_system.py               # 系统修复脚本
│   └── test_map_gen.py             # 接口冒烟测试
├── experiments/             # 开发/实验脚本（KG 决策数据、GeoToken 实验）
└── output/                  # 导出/调试产物（debug/）
```

前端脚本加载顺序：`map.js → map-lod.js → map-edit.js → graph.js → app.js`
（lod / edit 通过 `MapPanel.prototype` 扩展核心类）。

## 快速启动

```bash
# 1. 安装依赖（Python 3.10+）
cd backend
pip install -r requirements.txt

# 2. 配置 backend/.env（LLM Provider / API Key）

# 3. 启动后端（默认 8080 端口，清代理保证 OSM 抓取可用）
python ../tools/start_server_noproxy.py

# 4. 访问
#    前端页面  http://localhost:8080/app
#    API 文档  http://localhost:8080/docs
#    健康检查  http://localhost:8080/health
```

## 核心能力

- **自然语言制图**：输入"画一张武汉市交通图"，自动解析城市/地图类型并生成地图
- **多 LLM**：Ollama（本地）/ 通义千问 / OpenAI / DeepSeek / 智谱 GLM（运行时切换）
- **知识图谱增强**：Neo4j（不可用时自动降级内存模式），提供制图约束与样式推荐
- **数据源**：DataV GeoAtlas 行政区划 + OSM（Overpass）路网水系 + 本地精确数据
- **载负量控制**：按比例尺分级显隐图层、大图层要素抽稀
- **矢量编辑**：点/线/面绘制、节点拖拽、复制/简化、属性编辑、撤销重做、保存回写
- **多格式导出**：GeoJSON / SVG / PNG

## 数据流水线（backend/scripts/）

| 脚本 | 用途 |
|---|---|
| `prepare_local_data.py` | 下载湖北市级边界 / 武汉区县 / 旅游 POI / 轨道交通 |
| `prepare_local_geo.py`  | 下载武汉水系/路网（含 multipolygon 大水体），自动清洗 |
| `clean_water_data.py`   | 水系去重叠、同名合并、湖名规范、主湖优先 |
| `optimize_geo_data.py`  | Douglas-Peucker 几何简化（减小数据体积） |

## 环境变量（backend/.env 摘要）

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
OLLAMA_BASE_URL=http://localhost:11434
NEO4J_URI=bolt://localhost:7687
OVERPASS_SERVERS=https://overpass-api.de/api/interpreter,...
PORT=8080
```

## 数据与存储说明

| 路径 | 说明 |
|------|------|
| `data/maps.json` | 已生成地图主文件，超过 10 张自动归档到 `data/archive/maps/` |
| `data/sessions.json` | 会话历史（消息仅存 `map_id` 引用，不内嵌完整地图） |
| `data/archive/` | 历史地图归档 + 迁移前数据备份（zip） |
| `backend/data/geo/` | 本地精确地理数据（区县 / 水系 / 路网 / 旅游等） |
| `backend/data/dem/` | SRTM DEM（等高线生成） |

## 前端说明

- **经典 JS 前端**：`frontend/src/`，后端直接托管，访问 `/app`
- **Vue 3 新版前端**：`frontend/vue-app/`，独立 Vite 构建（开发端口 5173），
  地图渲染与 carto-agent-1 保持一致（features 图层 / LOD 分级 / 制图底图 / 图廓框线）
