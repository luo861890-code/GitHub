# CartoAgent 系统架构（2026-08 审计版）

> 本文件基于实际代码审计生成，所有结论均可在对应源码路径验证。

## 1. 总体架构

CartoAgent 是一个「LLM + 知识图谱 + WebGIS」的智能制图系统，采用
FastAPI（后端）+ Vue3/Pinia/Leaflet（前端）+ Neo4j/内存KG（知识层）三层架构：

```
用户（自然语言）
    │
    ▼
ChatPanel (Vue) ──SSE──▶ /api/chat/sessions/{id}/stream
    │                          │
    │                          ▼
    │              AgentService.process_request
    │              ├─ 意图检测（快速路径/LLM意图）
    │              ├─ SixDimParser 六维任务解析 → CartographyTask
    │              ├─ RAG / GraphRAG 知识检索
    │              ├─ KGPriorPlanner 规划（KG优先 + LLM补充）
    │              ├─ ToolRegistry 工具链执行
│              └─ CartographyValidator 质量校验
│                          │
│                          ▼
│              MapService.generate_map（OSM/高德/本地DataV/DEM）
│                ├─ DataQuality（数据质量引擎：几何/拓扑/属性/元数据）
│                ├─ CartographicProfile（主题-数据-尺度约束矩阵）
│                ├─ GeneralizationEngine（选取/简化/聚合/位移/坍缩/夸张 + Topology gate）
│                ├─ SymbolRegistry（统一符号）
│                ├─ LabelEngine（点/线注记碰撞消解）
│                ├─ LayoutEngine（标题/图例/比例尺/指北针/来源）
│                └─ MapQAService（1000 分制验收 A-J）
│                          │
    ▼                          ▼
LegacyMapPanel/MapCanvas  ◀── 地图 JSON（layers/legend/quality/provenance）
（Leaflet 渲染 + LOD 分级 + QGIS式编辑）
```

## 2. 核心模块与职责

| 层 | 模块 | 职责 |
|---|---|---|
| 编排 | `backend/app/services/agent_service.py` | ReAct 流程编排：意图检测、六维解析、RAG/GraphRAG、规划、工具、生成、校验、provenance |
| 任务理解 | `task_parser.py` | 六维制图任务书（theme/region/temporal/method/audience/symbol），LLM+规则降级 |
| 规划 | `cartographic_planner.py` | KG 优先规划：data/style/render + projection/generalization/layout/validation/export 完整结构 |
| 知识 | `kg_service.py` / `kg_ontology.py` | Neo4j/内存双模式 KG，制图决策查询，8 类本体（MapElement/MapSymbol/CartographicData/MapProjection/InfluencingFactor/CartographicDecision/LayerConfig/MapCase/Dataset） |
| 知识增强 | `graphrag_service.py` / `rag_service.py` | GraphRAG 多跳推理、RAG 检索 |
| 工具 | `tool_registry.py` | 21 个标准化工具（含契约：preconditions/postconditions/cost/retryable） |
| 数据 | `map_service.py` / `osm_service.py` / `amap_service.py` / `local_geo_service.py` / `geo_service.py` / `data_source_adapter.py` / `data_fusion.py` / `crs_manager.py` | 多源数据（OSM/高德/DataV/本地 GeoJSON/DEM）融合、CRS 归一与地图生成 |
| 数据质量 | `services/data_quality/` | 几何/拓扑/位置/属性/完整性/元数据校验，输出 DataQualityReport |
| 制图综合 | `services/generalization/` | Selection/Simplification/Aggregation/Displacement/Collapse/Exaggeration + GroundTruth recall + 动态等高距 |
| 符号 | `services/cartography/symbols/registry.py` | 15 类统一符号注册表，禁止 LLM 随机配色 |
| 注记 | `services/label/` | 点/线注记候选与碰撞消解、格网容量、线注记旋转角与边界保护 |
| 版式 | `services/cartography/layout.py` | 标题/图例/比例尺/指北针/来源/坐标/时间自动布局 + 校验 |
| 验收 | `services/qa/` + `map_qa_service.py` | 1000 分制十项指标（A-J）、Critical 门槛、四类地图专项权重 |
| 渲染 | `frontend/.../LegacyMapPanel.vue` + `public/legacy/map*.js` | Leaflet 渲染、LOD 分级、制图整饰 |
| 编辑 | `QgisEditor.vue` / `MapCanvas.vue` / `map-edit.js` | QGIS 式矢量编辑 |
| 校验 | `cartography_validator.py` / `quality_service.py` | 7 维评分 + 六层评估（schema/geometry/spatial/cartography/visual/task） |
| 导出 | `export_service.py` | PNG/SVG/GeoJSON/布局导出 |
| 会话 | `session_service.py` | 会话管理、消息持久化（轻量地图引用） |
| 前端状态 | `stores/{app,chat,map,edit,kg}Store.ts` | Pinia 全局状态 |

## 3. 完整可跑通的用户路径

1. 打开主界面 → `App.vue onMounted` 并行加载 LLM 状态与会话列表，自动恢复最近会话
2. 对话输入"生成武汉市交通图" → `ChatPanel → chatStore.sendMessage`（SSE）
3. 后端：快速路径意图识别 → 六维解析 → KG 决策 → 规划 → 工具匹配 → `generate_map` → 校验 → provenance
4. 前端：`map` SSE 事件 → `mapStore.setMapData` → `LegacyMapPanel` 渲染 → 顶栏/底栏/图层面板联动
5. 缩放地图 → `map-lod.js refreshLabels` 按比例尺分级显示（重要要素优先）
6. 进入编辑模式 → QgisEditor 编辑 → 保存/导出
7. 消息卡片可点击"查看制图过程" → `AgentTracePanel` 展示任务书/规划/工具/步骤

## 4. 当前不能跑通的路径 / 限制

- `MapCanvas.vue` 已不再被引用（主视图与编辑视图均使用 `LegacyMapPanel`），属于遗留组件
- 专题统计图（population/economic/climate 等）走 `_generate_thematic_layers` 随机模拟数据，非真实数据；
  四类核心专题（行政区划/交通/旅游/地势）均为真实数据
- 行政区划数据源存在 11 处微小 overlap（DataV 边界精度，0.002-0.166 km²），
  dataset_gate=SOURCE_DATA_WARNING，未伪修复
- 铁路几何为公开走向近似线（geometry_quality=approximate、source_confidence=unverified）
- LabelEngine 曲线注记（curved label）与要素感知位移未实现（PARTIAL）
- VLM 视觉验证（计划 §23）未实现
- PostGIS/Neon 数据层（计划 §19）未实现，空间数据仍存 JSON 文件
