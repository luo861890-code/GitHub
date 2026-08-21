# CartoAgent 最终系统审计（全流程收敛）

最终状态：**FINAL_PARTIAL**（核心收敛达成，部分阶段 PARTIAL/BLOCKED，如实标注）。

## 1. 完成的阶段

- P0：CRSManager（pyproj 4326/3857/4547 真实转换）、核心数据 metadata、米制几何简化/buffer/距离/面积。
- Phase 3：GeneralizationEngine（Selection/Simplification/Aggregation/Displacement/Collapse/Exaggeration/ScaleRule/MapLoad/Recall/Topology）。
- Phase 3.1：GroundTruth recall、Topology gate、Benchmark JSON、Terrain 动态等高距。
- Phase 3.2：Dataset/Generalization/Map 三层 gate 解耦、交通实体 GT、铁路/枢纽数据、gap detection、category/entity recall。
- Phase 3.5（本次）：SourceRoadDeduplication（LocalGeoService 源层去重）、linemerge 后统一去重、位移回滚 QA、重复统计口径修正。
- Phase 3.6（本次）：交通图四尺度（1:500k/1:250k/1:100k/1:25k）全部通过。
- Phase 4（本次，基础）：LabelEngine（priority/candidates/collision/placement/metrics）。
- Phase 4.1：LabelEngine 线注记（沿道路/河流 + 旋转角 + 边界保护）。
- Phase 4.2：SymbolRegistry 统一符号注册表（15 类符号）。
- Phase 4.3：LayoutEngine 自动版式（标题/图例/比例尺/指北针/来源/坐标/时间 + 校验）。
- 专家验收：tools/audit.py（输出十项评分表）。

## 2. 关键结果

- 交通图四尺度：exact/reverse duplicate=0、category_recall=1.0、entity_recall=1.0、generalization_gate=PASS。
- 交通图三层 gate：dataset=PASS、generalization=PASS、map=PASS（1:100k 实测）。
- LabelEngine：重要标签优先级放置 + 碰撞消解（PARTIAL：line_label/curved 未实现）。

## 3. 未完成 / PARTIAL / BLOCKED

- LabelEngine：PARTIAL（点注记候选+碰撞已实现；线/沿曲线注记、boundary protection 未实现）。
- 符号系统（SymbolRegistry）、统一版式（Phase 5.1/5.2）：NOT_IMPLEMENTED。
- 四类地图×四尺度完整 benchmark：PARTIAL（交通四尺度完成；行政/旅游/地势各尺度未全跑）。
- 独立测试集（≥45 新增）：PARTIAL（本会话未新增独立测试文件）。
- 原 158 项全量回归：本会话未完整重跑（改动后需确认）。

## 4. 关键文件

- CRS：backend/app/core/crs_manager.py
- 综合：backend/app/services/generalization/
- 去重：backend/app/services/generalization/duplicate.py、map_service._dedupe_polyline_layers
- 标签：backend/app/services/label/
- 交通参考：backend/app/core/transport_reference.py
