# 制图综合实现审计（第三阶段前置）

只读审计，追踪当前真实综合操作，区分“真实几何操作”与“显示层 LOD”。

## 1. 当前综合操作

- 湖泊多尺度选取：local_geo_service.py:346-358，按 LAKE_BANDS 面积阈值分档（真实几何）。
- 湖泊同名/湖群合并：local_geo_service.py:381-415，CRSManager.buffer_shapely_meters + unary_union（真实几何）。
- 湖泊化简：local_geo_service.py:433-439，g.simplify(tol) 在米制投影（真实几何）。
- 湖泊降维（面→点）：local_geo_service.py:454+，载负量 max_count 截取，小湖转点（真实几何）。
- 居民地选取/概括：local_geo_service.py:672+，面积分档 + 合并 + simplify + Chaikin 平滑（真实几何）。
- 河流长度选取：local_geo_service.py:606，长度 >25000m 阈值（米制）。
- 河流简化：local_geo_service.py:635，CRSManager.simplify_shapely_meters（真实几何）。
- 道路连通合并：map_service.py:2289 _connect_polylines_by_name（同名 linemerge，真实几何）。
- 图层显隐 LOD：map-lod.js:310 _lodVisible（显示层，按 zoom 档）。
- 要素抽稀预算：map-lod.js:141 _applyLoadControl（显示层，按 zoom 预算保留）。
- POI 分级保留：map-lod.js:61 _rebuildPoiKeep（显示层，全局 POI 预算 + 重要性排序）。

## 2. 真实几何 vs 显示隐藏

真实几何操作（后端、离线、改变几何）：湖泊/居民地/河流的选取、合并、化简、降维，道路 linemerge。
显示层（前端、运行时、不改存储几何）：_lodVisible、_applyLoadControl、_rebuildPoiKeep。
关键缺口：道路 selection/simplification、POI 聚类、位移、小行政区夸张在后端无独立引擎，依赖前端运行时 LOD。

## 3. scale 参数 vs 固定参数

湖泊 LAKE_BANDS 按 4 档面积阈值（有尺度含义，非显式比例尺）；简化 tolerance 固定 13m（SIMPLIFY_TOLERANCE_M），未按 1:1M/1:250K/1:100K 分级；前端 LOD 用 zoom 档而非严格比例尺。结论：无统一 ScaleRule。

## 4. 会造成数据丢失的操作

湖泊 max_count 截取（超上限按面积截断）；前端 _applyLoadControl 抽稀（不显示但原始数据仍在 store，非物理删除）；专题图 _generate_thematic_layers 用 random 模拟（非真实，见 PROJECT_AUDIT.md）。

## 5. 四类地图分别缺什么

行政区划：缺小行政区面积夸张/最小面积保护、区名冲突位移。交通：缺道路重要性选择、道路等级综合、平行道路/铁路位移、跨江冲突消解。旅游：缺 POI 聚类与展开、景点权威分级、旅游区域。地势：缺等高距按 scale/relief 动态推导（现固定 20m/100m）、等高线抽稀。

## 6. 结论

当前“综合”能力分散在 local_geo_service（真实几何）与前端 map-lod（显示层）。缺少统一 GeneralizationEngine、ScaleRule、道路/POI 的 selection 与 displacement、召回率/数据损失/拓扑校验、MapLoadMetrics。下一步按此建立。
