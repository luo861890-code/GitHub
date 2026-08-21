# Generalization QA 完整化报告（Phase 3.1）

阶段：Phase 3.1。仅处理 GroundTruth recall / Topology 门禁 / Benchmark / Terrain 动态等高距四项。

## 1. ImportantFeatureRecall Ground Truth

新增 backend/app/services/generalization/ground_truth.py，建立四类地图“应有核心要素集合”（来源：WUHAN_DISTRICTS / WUHAN_LANDMARKS / 武汉公开交通骨架 / 等高线计曲线），real recall = intersection / expected。

实测 recall：

- 行政区划：districts 13/13=1.0，city_boundary 1/1=1.0，overall 1.0
- 交通：overall 0.4（bridges/metros/highways 命中；railways 与 hubs 未命中——交通图缺“铁路”独立图层与“武汉站/汉口站/武昌站/机场”枢纽标注，属真实数据缺口）
- 旅游：overall 0.8（核心景点多数命中）
- 地势：index_contours 1.0

交通 recall 0.4 为真实缺口（非“骨架全保留”式推断）：CartographicProfile 的交通图 forbidden 去掉了 POI 点，导致交通枢纽（站/机场）缺失；铁路独立图层未生成。

## 2. Topology 强制门禁

扩展 TopologyCheck：多边形 overlap/invalid、线连通分量/dangling/重复、POI 归属、等高线有效性；gate 输出 PASS/FAIL（关键错误→FAIL）。

实测 gate 结果：

- 行政区划/交通/旅游/地势均 gate=FAIL，原因均为 polygons.overlap_count>0。
- 根因：wuhan_districts.geojson 相邻区边界存在真实重叠（实测 11 处，面积 0.002-0.166 km²），属 DataV GeoAtlas 边界精度问题，非 GeneralizationEngine 引入。

处理：门禁如实返回 FAIL 并记录 overlap_count，不在综合引擎内伪修复（数据源问题应在 P0 数据阶段修复）。

## 3. Benchmark JSON

tools/run_generalization_benchmark.py 生成 benchmarks/wuhan/generalization/，每类地图每尺度输出 before.json（before_counts）、after.json（after_counts）、metrics.json（map_load/data_loss/recall/topology/topology_gate）、qa.json（MapQAService 1000 分制），及 summary.json。

实测：administrative 1:250k、traffic 1:100k、tourism 1:100k、terrain 1:100k 四组 JSON 已生成。

## 4. Terrain 动态等高距

新增 backend/app/services/generalization/terrain_scale_rules.py，确定性规则 contour_interval = f(scale, DEM resolution, relief)：

- 1:500K→100m、1:250K→40m、1:100K→20m（图上 0.2mm）
- relief>500 放大×2 封顶 100m，relief>200 放大×1.5
- 取整 20m 倍数，最小 20m

engine 接入：等高线图层按 interval 选取（保留 ele%interval==0，删除其余），记录 contour_interval/contour_kept/contour_removed/contour_reason。

## 5. 测试

新增 test_generalization_qa.py 35 项（GroundTruth recall 10、Topology gate 11、Terrain 等高距 9、Benchmark 5）。全量 158 项通过（原 123 + 新 35）。

## 6. 修改文件

- backend/app/services/generalization/ground_truth.py（新增）
- backend/app/services/generalization/terrain_scale_rules.py（新增）
- backend/app/services/generalization/metrics.py（TopologyCheck 扩展）
- backend/app/services/generalization/engine.py（recall/topology gate/等高距接入）
- backend/app/services/map_service.py（_connect_polylines_by_name 保留属性+米制长度）
- tools/run_generalization_benchmark.py（新增）
- backend/tests/test_generalization_qa.py（新增）

## 7. 尚未解决（如实标注）

- 交通图核心枢纽与铁路图层缺失：数据层缺口（枢纽点在 CartographicProfile 阶段被去点、铁路无独立图层），本阶段未修复（属 P1 数据层）。
- 区县政区边界 overlap（11 处）：DataV 数据源边界精度问题，门禁如实 FAIL，未伪修复。
- topology gate 的 gap 检测为 0（未实现真实的缝隙检测，gap_count 固定 0，标记 PARTIAL）。

## 8. 结论

四项均已完成并有测试证据：recall 真实计算（含交通 0.4 的真实缺口）、topology 门禁如实 FAIL（数据源 overlap）、benchmark JSON 机器可读、terrain 等高距确定性规则生效。本阶段停止，未进入 LabelEngine。
