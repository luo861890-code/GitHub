# CartoAgent - 基于大语言模型和知识图谱的地图制图智能体

> 集成大语言模型与知识图谱的在线地图制图智能体系统：用户通过自然语言描述制图需求，
> 系统自动完成从需求理解、地理数据获取到地图输出的完整流程，并支持类 ArcGIS/QGIS 的
> 矢量编辑（绘制、节点编辑、撤销重做、属性编辑、保存回写）。

> 📖 **结构与模块详解见 [docs/项目结构说明.md](docs/项目结构说明.md)**
> 📚 **全部文档索引见 [docs/README.md](docs/README.md)**

## 目录结构（整理后）

```
carto-agent/
├── backend/                 # 后端服务（FastAPI）
│   ├── app/
│   │   ├── api/             # API 路由层（chat / maps / knowledge / settings）
│   │   ├── core/            # 配置、常量、CRS、制图Profile、KG 本体、交通参考
│   │   ├── models/          # Pydantic 数据模型 / Schema
│   │   ├── services/        # 业务服务（agent/llm/map/geo/kg/osm/qa/generalization/label/cartography…）
│   │   └── utils/           # 通用工具（geometry 几何函数等）
│   ├── data/
│   │   ├── geo/             # 本地地理数据（GeoJSON，数据流水线生成）
│   │   ├── kg/              # 本体导出文件（carto_ontology.ttl）
│   │   └── dem/             # SRTM DEM（等高线生成，体积大不入库）
│   ├── scripts/             # 数据流水线脚本（prepare / optimize / clean）
│   ├── runtime/             # 运行时产物（server.pid、服务日志）
│   ├── .env / .env.example  # 环境配置（LLM / Neo4j / 服务）
│   └── requirements.txt
├── frontend/                # 前端（Vue 3 + Vite）
│   └── vue-app/
│       ├── index.html       # 入口，加载 Leaflet 与经典 JS 做图模块
│       ├── public/legacy/   # 经典 JS 做图模块（MapPanel，供 Vue 复用）
│       │   ├── config.js    #   全局配置（默认中心 / 主题 / 瓦片）
│       │   ├── utils.js / api.js
│       │   ├── map.js       #   MapPanel 核心（做图渲染）
│       │   ├── map-lod.js   #   载负量 LOD 分级
│       │   ├── map-edit.js  #   矢量编辑
│       │   └── leaflet-editable.js
│       ├── src/             # Vue 3 源码
│       │   ├── components/  #   面板 / 编辑器组件（LegacyMapPanel 等）
│       │   ├── stores/      #   Pinia 状态（app / chat / map / kg / edit）
│       │   ├── services/    #   API 封装
│       │   ├── types/       #   TypeScript 类型
│       │   └── config/      #   前端配置
│       ├── package.json / vite.config.ts
│       └── tsconfig*.json
├── data/                    # 运行数据（maps.json / sessions.json / kg/）
│   └── *.bak / *backup*     # 数据恢复备份（maps.json.bak 等）
├── benchmarks/              # 四类地图 × 四尺度最终 Benchmark（16 组，JSON）
├── docs/                    # 文档与长期规划
├── tools/                   # 运维/开发工具（详见 tools/README.md）
├── experiments/             # 开发/实验脚本（KG 决策数据、GeoToken 实验）
└── output/                  # 导出/调试产物（debug/）
```

前端做图模块加载顺序：`config.js → utils.js → api.js → map.js → map-lod.js → map-edit.js`
（lod / edit 通过 `MapPanel.prototype` 扩展核心类）。

## 快速启动

```bash
# 1. 安装后端依赖（Python 3.10+）
cd backend
pip install -r requirements.txt

# 2. 配置 backend/.env（LLM Provider / API Key）

# 3. 启动后端（默认 8080 端口，清代理保证 OSM 抓取可用）
python ../tools/start_server_noproxy.py

# 4. 启动前端（Vue 3 + Vite，默认 5173，/api 与 /ws 代理到 8080）
cd ../frontend/vue-app
npm install
npm run dev

# 5. 访问
#    前端页面  http://localhost:5173
#    API 文档  http://localhost:8080/docs
#    健康检查  http://localhost:8080/health
```

## 核心能力

- **自然语言制图**：输入"画一张武汉市交通图"，自动解析城市/地图类型并生成地图
- **多 LLM**：Ollama（本地）/ 通义千问 / OpenAI / DeepSeek / 智谱 GLM（运行时切换）
- **知识图谱增强**：Neo4j（不可用时自动降级内存模式），提供制图约束与样式推荐
- **数据源**：DataV GeoAtlas 行政区划 + OSM（Overpass）路网水系 + 本地精确数据
- **CRS / 投影**：CRSManager（pyproj 真实 4326/3857/4547 转换），米制几何简化/缓冲/距离
- **制图综合**：GeneralizationEngine（选取/简化/聚合/位移/坍缩/夸张 + 多尺度规则 + 要素召回 + 拓扑门禁）
- **统一符号**：SymbolRegistry（15 类符号，禁止 LLM 随机配色）
- **注记引擎**：LabelEngine（点/线注记候选、碰撞消解、格网容量、线注记旋转角与边界保护）
- **QGIS 式图层体系**：注记按类别独立成层（河流注记/湖泊注记/水库注记/道路注记/山峰注记/政区名称标注…），图层按主题分组（底图/行政区划/水系/道路/轨道交通/地形地貌/注记/POI），支持整组显隐、拖拽排序、图层不透明度、竖排/横排注记、白描边等标注设置；自然语言可精确定位"湖泊注记"等注记图层
- **自动版式**：LayoutEngine（标题/图例/比例尺/指北针/来源/坐标/时间 + 冲突避免）
- **自动验收**：MapQAService 1000 分制（十项指标 A-J、Critical 门槛、四类地图专项权重）
- **16 组 Benchmark**：行政/交通/旅游/地势 × 1:500k/1:250k/1:100k/1:25k 全部 PASS（详见 docs/audit/FINAL_BENCHMARK_REPORT.md）
- **载负量控制**：按比例尺分级显隐图层、大图层要素抽稀
- **矢量编辑**：点/线/面绘制、节点拖拽、复制/简化、属性编辑、撤销重做、保存回写
- **多格式导出**：GeoJSON / SVG / PNG

## 地图质量与验收

```bash
# 16 组最终 Benchmark（行政/交通/旅游/地势 × 四尺度）
python tools/run_final_benchmark.py

# 从 Benchmark 输出评分汇总
python tools/audit.py --benchmark

# 单图专家验收（如交通图 1:100k）
python tools/audit.py --map traffic --scale 100000
```

当前 16 组结果：行政区划图 922-934、交通图 918-923、旅游图 926-929、
地势图 894-900，全部 PASS、Critical=0、核心要素 recall=1.0。

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
| `backend/data/dem/` | SRTM DEM（等高线生成，体积大、不入库，需 `tools/download_srtm_wuhan.ps1` 下载） |

## 前端说明

前端为 Vue 3（Vite）应用，位于 `frontend/vue-app/`：

- **开发模式**：`npm run dev`（默认 5173），`vite.config.ts` 将 `/api`、`/ws`
  代理到后端 8080。
- **做图渲染**：`LegacyMapPanel.vue` 复用 `public/legacy/` 下的经典 JS 做图模块
  （`MapPanel` + LOD + 编辑），这些模块在 `index.html` 中以全局脚本加载并暴露到
  `window.MapPanel / Utils / API / CONFIG`。
- **生产构建**：`npm run build` 生成 `frontend/vue-app/dist/`；后端若检测到该目录，
  会通过 `/app` 静态托管构建产物。
