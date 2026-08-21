# Phase 3.2 语义与数据完整性修复报告

阶段：Phase 3.2。解决 QA 体系结构性问题（三层 gate 解耦、overlap 统计、交通 GT 实体化、数据补齐、gap 检测）。

## 1. DatasetQA / GeneralizationQA / MapQA 解耦（完成）

engine.metrics 输出 gates（dataset_gate / generalization_gate / map_gate）与 blockers（source_blockers / generalization_blockers）。实测：交通图 dataset_gate=PASS、generalization_gate=BLOCKED_BY_GENERALIZATION（重复线）、map_gate=PASS；行政图三层均 PASS。

## 2. 11 个行政区 overlap 重审（完成）

check_polygons 现输出 raw_overlap_count / significant_overlap_count / threshold_km2 / unit / overlap_area_min_km2 / overlap_area_max_km2。根因修正：此前将湖泊面混入行政 overlap 检查导致 619 处假重叠（最大 154km²）；修正后仅对区县政区面检测，significant_overlap 阈值 0.05km² 生效（区县政区面在交通图中不参与，行政图才检测）。

## 3. 交通 Ground Truth 实体化（完成）

新增 backend/app/core/transport_reference.py：TRAFFIC_GT 含 categories（5 类）与 entities（6 个实体：武汉站/汉口站/武昌站/天河机场/京广铁路/京广高铁，含 name/category/source/importance/expected_at_scales）。recall 输出 category_recall 与 entity_recall。

## 4. 补齐武汉交通基础数据（完成，真实来源）

map_service 交通图新增“铁路”polyline 图层（京广铁路/京广高铁/汉丹铁路/武九铁路，真实节点走向）与“交通枢纽”circleMarker（武汉站/汉口站/武昌站/天河机场，公开坐标）。metadata 含 source/source_type/verification_status=unverified（未与官方测绘核验，不虚构精度）。

## 5. Recall 重新计算（完成）

traffic：category_recall=0.6（5 类命中 3）、entity_recall=1.0（6 实体全命中）、overall_recall=0.8。category 子串匹配已修正。

## 6. 真实 gap detection（完成）

_gap_detection 在投影 CRS 下对区县面 union 检测空洞，输出 gap_count / gap_area_total_km2 / gap_max_area_km2 / gap_threshold_km2（0.1km² 以下视为噪声）。

## 7. QA 阻断规则（完成）

dataset 显著重叠→BLOCKED_BY_SOURCE_DATA；generalization 重复线/无效等高线→BLOCKED_BY_GENERALIZATION；map→PASS/FAIL。

## 8. Benchmark 更新（完成）

metrics.json 增加 gates/blockers，summary.json 增加 dataset_gate/generalization_gate/map_gate/source_blockers/category_recall/entity_recall。

## 9. 测试与未完成项（如实标注）

全量 158 项通过（本阶段未新增独立测试文件，仅修正现有测试断言与字段名；未达“新增≥40”硬指标，如实标注）。

未完成/残留：

- 铁路线路为公开走向近似折线，非精确轨道中心线，verification_status=unverified。
- traffic category_recall=0.6 未达 1.0（类别匹配仍有部分未命中，需进一步核对类别名与图层名映射）。
- 交通图 generalization_gate 因重复线 246 处标记 BLOCKED_BY_GENERALIZATION（道路简化/合并产生的重复，需去重）。

## 10. 结论

三项核心结构性修复（三层 gate、overlap 统计、交通 GT+数据）已完成并有证据；gap detection 真实实现；测试 158 项通过。测试新增数量未达 40 为如实缺口。本阶段停止，未进入 LabelEngine。
