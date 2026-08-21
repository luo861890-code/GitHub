# Phase 3.4 Pipeline Stability & Duplicate Convergence 报告

阶段结论：**PHASE_3_4_BLOCKED**（final exact/reverse duplicate 未收敛为 0，如实标记）。

## 1. 353 / 82 重复来源

- 82 条原始重复：wuhan_roads.geojson / LocalGeoService 道路图层中的 exact/reverse 重复（居民区街区、三级道路、次干道等）。
- 353 放大：map_service._connect_polylines_by_name（linemerge）对同名道路合并后产生重复段；displacement 位移对近距线产生近似重复。

## 2. 本阶段已完成（有证据）

- SourceRoadDeduplication：LocalGeoService._dedupe_road_layer 对道路图层 exact/reverse 去重并记录 provenance（removed/kept/reason/source）。实测 get_roads_layers 后道路 exact duplicate = 0。
- Displacement 回滚：resolve_parallel 改为候选位移 + 距离 QA（after_d > before_d+5m 才接受，否则回滚），记录 rollback_count。
- StageMetrics：engine 输出 raw_duplicate / final_exact_duplicate / rollbacks。
- canonical category recall：traffic category_recall=1.0、entity_recall=1.0（canonical_id 匹配）。

## 3. 每阶段 duplicate 数量（实测 1:100k）

- LocalGeoService 源层（去重后）：exact = 0
- engine 前（linemerge 后）：raw_duplicate ≈ 313（linemerge 重复未彻底清除）
- final：332（含位移后近似重复）

## 4. displacement rollback 次数

实测 0（位移后距离未触发回滚条件；重复主要来自 linemerge 而非位移）。

## 5. legitimate parallel

未建立独立计数（near/parallel 分类逻辑在 DuplicateDetector 中实现，未在最终输出汇总）。

## 6. 四尺度结果

未完成（本会话仅验证 1:100k；1:500k/1:250k/1:25k 未跑）。

## 7. 性能瓶颈

未完整统计；已知 displacement 为 O(n²)（近距线两两比较），是生成耗时的主要因素。

## 8. 测试

未新增独立测试文件（token 受限）；源层去重经脚本实测 exact=0。原 158 项未本会话全量验证。

## 9. 未解决问题（BLOCKED 原因）

1. linemerge 后重复未彻底清除（raw ≈ 313）：_dedupe_polyline_layers 已实现但未彻底生效（调用链/引用需进一步调试）。
2. final duplicate 332 未收敛为 0。
3. 四尺度 benchmark、性能分阶段统计、独立测试集未完成。

建议下一步：修 linemerge 输出的去重（在 _connect_polylines_by_name 内部去重，而非外部兜底），再跑四尺度验证与独立测试。
