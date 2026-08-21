# Phase 3.3 Generalization 结果质量收敛报告

阶段结论：**PHASE_3_3_BLOCKED**（final duplicate 未收敛为 0，如实标记，不降阈值伪装 PASS）。

## 1. 重复线来源定位

诊断（diag_dup2/diag_dup3）：

- LocalGeoService 原始道路图层即含 exact/reverse 重复（居民区街区 13、三级道路 28、次干道 13、主干道 5 等，累计约 82 条多余）。
- engine 的 _generalize_roads（selection/simplification/displacement）前后重复数不变，未新增 exact 重复。
- 最终 generate_map 输出重复（topology check_duplicate_lines）约 246-353，含位移阶段 resolve_parallel 对近距线产生的近似重复。

## 2. 每阶段 duplicate 数量

- raw（LocalGeoService）：约 82 条多余
- after selection/simplification：不变（82）
- after displacement：重复数增加（位移复制产生近似重复）
- final：未收敛（实测 final_duplicate_count=353）

分类：exact（约 82 原始）+ near/位移近似（位移后新增）。

## 3. Duplicate Detection Engine

新增 backend/app/services/generalization/duplicate.py：DuplicateDetector（exact/reverse/near 分类，保留 legitimate_parallel）。engine 已在 simplification 后、displacement 前调用去重，并在输出前统一去重 exact/reverse。

未收敛原因：displacement 的 resolve_parallel 对近距线产生近似重复，exact 去重无法消除近似重复；且 LocalGeoService 原始重复未在数据源层修复（仅在 pipeline 内去重，仍可能被位移重新引入）。

## 4. canonical category ID

transport_reference.TRAFFIC_GT categories 已加 canonical_id（highway.motorway / highway.trunk / railway.main / metro.line / bridge.major）；ground_truth.compute_all_recall 改用 canonical_id 匹配。

实测：traffic category_recall=1.0、entity_recall=1.0、overall=1.0。

## 5. traffic recall

category_recall=1.0（5/5）、entity_recall=1.0（6/6）。

## 6. 铁路 confidence

铁路/枢纽 metadata 增加 geometry_quality（approximate/reference_point）与 source_confidence（unverified）；recall 输出 geometry_verified（当前 0，因全部 unverified，如实）。

## 7. topology

traffic generalization_gate=BLOCKED_BY_GENERALIZATION（重复线未清零）；行政 dataset_gate/generalization_gate/map_gate 均 PASS。

## 8. 四尺度结果

本会话未完成 1:500k/1:250k/1:100k/1:25k 四尺度完整验证（测试耗时超限中断），仅验证 1:100k：final_duplicate=353、category_recall=1.0、entity_recall=1.0。

## 9. 测试

新增测试未完成（本会话 token 不足，未新增独立测试文件；原 158 项需后续补跑确认）。

## 10. 未解决问题（BLOCKED 原因）

1. final duplicate 未收敛为 0（当前 353）：位移产生近似重复 + LocalGeoService 原始重复未在数据源层修复。
2. 全量 158 项测试本会话未完成验证（耗时超限）。
3. 四尺度 benchmark 未完整运行。

建议下一步：修复 LocalGeoService 道路数据源重复（数据层），调整 displacement 去重策略（位移后 near-duplicate 检测），再跑四尺度验证。
