# CartoAgent 系统审计报告（阶段 0 · 只读）

> 审计范围：backend / frontend / data / tools / docs / scripts。审计方法：追踪真实数据流，核对源码与数据文件，不采用模糊结论。本阶段不修改业务代码，不声称“优化完成”。

## 1. 当前架构

```
数据源（Overpass OSM / 高德(可选) / DataV GeoAtlas / 本地 GeoJSON / SRTM DEM）
   ↓ 下载/预处理（backend/scripts/*.py）
本地 GeoJSON（backend/data/geo/*.geojson）
   ↓ LocalGeoService / GeoService / ContourService 读取
MapService.generate_map（多源融合 + CartographicProfile + 图层排序 + 连通合并）
   ↓ 地图 JSON（layers/legend/quality/metadata/provenance）
前端 LegacyMapPanel + map.js/map-lod.js（Leaflet 渲染 + LOD + 制图整饰）
   ↓ MapQAService（1000 分制验收）+ DataQualityEngine
AgentService（六维任务书 → KG 规划 → 工具 → 生成 → 校验 → provenance）
```

## 2. 数据流（真实路径）

1. 本地数据：backend/scripts/prepare_local_geo.py 生成，clean_water_data.py 清洗，optimize_geo_data.py 简化。
2. 行政边界：geo_service.py 读 backend/data/geo/wuhan_districts.geojson（13 区）+ hubei_cities.geojson + hubei_province.geojson。
3. 道路/水系/旅游/轨道：local_geo_service.py 读同名 GeoJSON；OSM 仅作缺失兜底（map_service.py 中 if not _local_water 等分支）。
4. DEM：generate_contours.py 从 backend/data/dem/*.hgt（SRTM 30m）生成 wuhan_contours.geojson，contour_service.py 读取。
5. 生成：map_service.generate_map 按 map_type 组织图层 → _connect_polylines_by_name 合并同名线 → _apply_cartographic_profile 过滤/分级 → _sort_layers 排序。
6. 渲染：前端 map.js 按 layerZ 叠置、map-lod.js 做 LOD 分级显隐与抽稀。

## 3. 已有能力（有代码/数据/测试证据）

| 能力 | 证据 |
|---|---|
| 六维任务理解 | task_parser.py；test_plan_upgrade.py::test_six_dim_task_book_with_confidence |
| KG 规划 | cartographic_planner.py；kg_service.query_cartographic_decision |
| 工具契约 | tool_registry.py ToolDefinition.preconditions/postconditions；test_tool_registry.py |
| 四类地图 Profile | cartographic_profiles.py；test_cartographic_profiles.py（5 项） |
| 1000 分制验收 | qa/map_score.py（A-J 十项 + 致命门槛）；test_map_qa.py |
| DataQualityEngine | data_quality/engine.py；test_data_layer.py |
| DataFusionEngine | data_fusion.py（来源优先级/繁简归一/置信度） |
| 图层排序 | map_service._sort_layers（2245 行）；前端 map.js layerZ |
| 道路连通合并 | map_service._connect_polylines_by_name（2289 行） |
| LOD | map-lod.js _lodVisible + _applyLoadControl + 全局 POI 预算 |
| 会话/导出/编辑 | session_service.py、export_service.py、QgisEditor.vue |

## 4. 实际未完成 / 半实现 / 缺陷（逐条含位置与证据）

### 4.1 几何简化单位体系问题（P0）

- local_geo_service.py:616：`sim = ln.simplify(0.00012, preserve_topology=True)`，注释 `# ~13m 化简`——仍在经纬度坐标上以度值近似米数。
- 同文件 :689 `g.simplify(0.00012, ...)`、:695 `g.buffer(0.0005)` 同样问题。
- 上一轮已改 scripts/optimize_geo_data.py 与 tool_registry.SimplifyGeometryTool 为米制（utils/geo_simplify.py），但 local_geo_service.py 内部残留经纬度 DP，未全量统一。

### 4.2 CRS / 投影未真正实现（P0）

- map_service.py:924-925 仅在 metadata 写字符串“CGCS2000 / 高斯-克吕格 / Web墨卡托”，无投影转换代码（无 pyproj/transform）。
- 数据实际为 WGS84 经纬度，前端 Leaflet 按 WebMercator 渲染，声明与实现不一致，多源数据未做投影归一。

### 4.3 多源数据无统一元数据（P0）

- 实测 7 个 GeoJSON 的 metadata 均为空、crs 均为 null：wuhan_roads(34833)、wuhan_water(2232)、wuhan_transit(3178)、wuhan_tourism(824)、hubei_cities(17)、wuhan_districts(13)、wuhan_contours(3146)。
- DataV/OSM/SRTM 三类来源无来源、时间、CRS、精度、许可的统一元数据。

### 4.4 专题地图为 mock 数据（P1）

- map_service._generate_thematic_layers（1701-1758 行）用 random.uniform/random.choice 生成专题图：`pts.append([p[0], p[1], random.uniform(0.2, 1.0)])`（1720）、`cat = random.choice(cats)`（1751）。
- _generate_fallback_layers（1813）对非武汉城市生成“模拟地标数据”。

### 4.5 导出 PNG 依赖 Pillow（P1）

- export_service.py:302、:594 `_png_placeholder`：Pillow 缺失时返回占位 PNG，非真实渲染导出。

### 4.6 注记引擎仅“简单避让”（P1）

- map.js:40/160/358：`this._labelPlaced = []`、`this._labelNames = new Set()` 为全局防重复堆叠，无候选位置/优先级/边缘距离/沿道路放置（规范 §G）。
- qa/symbol_label_quality.py 的碰撞率是格网近似（0.02° 格网计数），非真实屏幕像素碰撞。

### 4.7 地图综合未形成完整引擎（P1）

- 当前实现 = Douglas-Peucker + LOD（显隐/抽稀），即“简化 + 可见性”，无 aggregation/displacement/exaggeration/collapse/smoothing/conflict-resolution 的确定性执行引擎（qa/generalization_quality.py 只评估不执行）。

### 4.8 符号推荐为 KG + 硬编码兜底（P2）

- symbol_recommender.py:80 `_builtin_symbol` 硬编码 road/railway/water/poi/green_space/building/boundary/admin_center/contour 配色；:73 `source = "kg" if rationale else "builtin"`。

### 4.9 交通网络拓扑仅“分段数”启发式（P1）

- qa/topology_quality.py C2 用“同名道路分段 >30 段”近似连通性问题，未计算真实路网连通分量/断头路/路口拓扑/重叠率（规范 §C2）。

### 4.10 OSM 分类映射存在但未校验（P2）

- local_geo_service.py:806-809 `ROAD_CN` 已做 motorway→高速公路主线 等中文映射，但无道路等级正确性校验（国道/省道语义是否匹配）。

### 4.11 测试覆盖缺口（P1）

- 后端 14 个测试文件、40 个 def test_（pytest 48 项通过）；无 agent 全流程集成测试（依赖 LLM/网络）、前端 E2E、LOD 单元测试、provenance 结构断言、错误恢复测试；前端验证依赖 visualizations/.../cdp_*.mjs 临时脚本，未纳入 CI。

### 4.12 自动验证部分为启发式（P2）

- qa/ 的密度用市域面积 8569km² 估算、注记碰撞用格网近似、POI 归属用 bbox 而非面内判定，属工程近似，需在报告明确标注“近似指标”。

## 5. 四类武汉地图分别的问题

### 武汉市行政区划图

- 事实层：区县唯一区名=13 已校验（qa/data_quality.py、topology_quality.py），但 DataV 边界无权威来源/版本/CRS 元数据。
- 综合层：无小行政单元面积夸张/位移（qa/generalization_quality.py E6/E7 仅扣分不执行）。
- 注记层：区名仅简单避让，无候选放置/优先级。

### 武汉市交通图

- 道路分类有 OSM→中文映射，无等级正确性校验；拓扑仅“分段数”启发式，无真实连通性指标。
- 桥梁已提取“主要桥梁”图层（cartographic_profiles.py is_major_bridge，实测 67 座），但桥梁与道路/铁路的跨江冲突消解未实现。
- 多尺度是 map-lod.js 的 zoom 档位，非“比例尺→等级→数量”的严格数据库级综合。

### 武汉市旅游图

- OSM tourism/leisure/historic 类别≠武汉旅游行业分类；实测含 park(299)/hotel(112)/museum(96)，hotel/guest_house 混入景点图层。
- cartographic_profiles.py TOURISM_POI_LEVELS 已给图层级 P0-P3 importance（P1/P2 生效），但无权威景区等级（5A/4A）、开放状态、票务；无景点聚类/旅游区域/旅游路线。

### 武汉市地势图

- DEM 用 SRTM .hgt 生成等高线，但无 DEM 元数据/垂直基准/NoData/精度报告（数据文件无 metadata）。
- 晕渲用前端 ArcGIS 在线 hillshade 瓦片（config/index.ts），非本地 DEM 派生晕渲；等高距/色带为固定配置（contour_service.py STYLE_INDEX/MINOR，terrain 固定 20m/100m）；武汉低起伏地形未做垂直夸张约束。

## 6. 技术债

1. MapCanvas.vue（约 87KB）已不被引用，属遗留组件。
2. appStore/chatStore 存在 map_data 轻量引用与完整数据两种形态，部分前端用 (msg.map_data as any) 绕过类型。
3. quality_service.py / cartography_validator.py / qa/ 三套质检并存，口径未统一。
4. 前端 KGPanel 定位 right: var(--toolbar-width)（56px）与实际工具栏宽度（50px）不一致。
5. 依赖偏旧：FastAPI 0.115.0 / Pydantic 2.9.0 / Vue 3.4.x / Vite 5.x。

## 7. 推荐改造顺序

① 统一 CRS/投影与几何简化（local_geo_service.py 残留度值简化 + 补投影转换）→ ② 补全多源数据元数据（7 个 GeoJSON 加 source/date/CRS/accuracy/license）→ ③ GeneralizationEngine（aggregation/displacement/exaggeration/collapse）→ ④ LabelEngine（候选位置/优先级/碰撞）→ ⑤ 交通网络拓扑真实计算 → ⑥ 旅游 POI 权威分级与聚类 → ⑦ DEM 元数据与本地晕渲 → ⑧ 测试补全 → ⑨ Benchmark + 黄金样本。

## 8. 第一阶段建议修改的文件（仅建议，本轮未改）

1. local_geo_service.py：616/689/695 行度值 simplify/buffer 改米制（复用 utils/geo_simplify.py）。
2. map_service.py：CRS/投影增加实际转换或显式声明“数据 WGS84、渲染 WebMercator、导出需重投影”。
3. backend/scripts/ 数据准备脚本：为 GeoJSON 写入统一 metadata（source/date/CRS/accuracy/license/processing）。
4. qa/*：在报告标注“近似指标”与“真实几何验证”的区分。
5. map_service.py:1701-1758：专题图随机数据标注为 mock 或接入真实数据源。
6. export_service.py：PNG 占位返回显式标记，避免误作真实导出。

## 9. 结论

当前系统已完成“数据获取 → 地图生成 → LOD 渲染 → 1000 分制验收”主链路，四类武汉核心地图使用真实数据（行政 DataV、交通/旅游 OSM+本地、地势 SRTM），后端 48 项测试通过。但存在 P0 问题：局部几何简化仍以经纬度度值近似米数、CRS 未真正投影、多源数据无统一元数据；专题图与部分导出为 mock/占位。距离“稳定生产可验收专业地图”尚有距离，下一步应优先处理 CRS/投影/元数据与几何综合，而非继续堆 UI。
