# 制图综合引擎（GeneralizationEngine）阶段报告

阶段：第三阶段。已建立真实 GeneralizationEngine 并接入四类武汉地图。未完成项如实标注。

## 1. 修改文件与新增模块

新增 backend/app/services/generalization/：models.py（输入/输出模型）、scale_rules.py（ScaleRule 6 档，tolerance=0.2mm×scale/1000 按要素类别加权）、selection.py（道路重要性=class+length+connectivity、POI 分级选择、尺度预算）、simplification.py（米制 DP）、aggregation.py（linemerge + POI 聚类）、displacement.py（投影坐标垂直位移）、collapse.py（小面→点）、exaggeration.py（小面保护）、metrics.py（MapLoad/召回/损失/拓扑）、engine.py（统一入口）。

修改：backend/app/services/map_service.py（generate_map 调用 _apply_generalization，metrics 写入 map_data.generalization_metrics）；backend/tests/test_generalization.py（新增 34 项测试）。

## 2. 调用链

MapService.generate_map → _apply_cartographic_profile → _apply_generalization（GeneralizationEngine.generalize，scale=zoom→比例尺）→ 图层几何真实改变 + generalization_metrics。

## 3. 算法与参数

简化容差：图上 0.2mm 折算实地米（1:1M→200m 到 1:25K→5m），按要素类别加权（motorway 0.5、contour_minor 1.5、riverline 0.4）。道路重要性=class×0.5 + min(length/50km,0.3) + min(connectivity/20,0.3)。尺度预算：骨架不裁，支路 1:1M→0、1:500K→10%、1:250K→40%、1:100K→70%、1:25K→100%。位移距离=图上 0.3mm。POI 聚类距离=图上 0.5mm。

## 4. 四类地图测试结果（真实武汉数据，1:100k）

- 行政区划：28 层，MapLoad 30.1，feature_loss 0.0004，vertex_loss 0.1398，length_change -0.1211
- 交通：26 层，MapLoad 30.1，feature_loss 0.0，vertex_loss 0.2697，length_change -0.2314
- 旅游：34 层，MapLoad 30.4，feature_loss 0.0，vertex_loss 0.3094，length_change -0.1915
- 地势：35 层，MapLoad 30.8，feature_loss 0.1455，vertex_loss 0.7063，length_change -0.402

feature_loss 仅统计 selection 真实移除数（聚合/坍缩不计入）。

## 5. before/after 数值

等高线 104→76 顶点（-26.9%），长度 10613.1m→10534.7m（-0.739%）。道路简化端点保持、长度变化 <5%。行政 13 区综合后 recall=1.0（13/13）。

## 6. 测试结果

新增 34 项（ScaleRule 5、Selection 4、Simplification 4、Aggregation 3、Displacement 3、Collapse/Exaggeration 3、Metrics 4、Engine 集成 4、负例 4）。全量 123 项通过（原 89 + 新 34）。

## 7. 未解决问题（如实标注）

- 交通核心要素召回率：PARTIAL（骨架全保留，但未建立“应有核心要素清单”做 98%/100% 显式对比）。
- 旅游核心 POI 召回率：PARTIAL（分级选择已实现，未做权威清单显式 recall）。
- 支路 scale-aware 在交通图上的覆盖：PARTIAL（预算逻辑已实现且有单测，但交通图 minor_road 在 CartographicProfile 阶段被主题过滤，图层已不存在）。
- 拓扑线连通性接入输出：PARTIAL（TopologyCheck 有实现，engine 未在 metrics 输出调用 check_line_connectivity）。
- Smoothing：PARTIAL（Chaikin 存在于 local_geo_service，未在 GeneralizationEngine 单独封装）。
- Benchmark（before/after/metrics/qa JSON）：NOT_IMPLEMENTED。
- 地势等高距动态推导：NOT_IMPLEMENTED（等高距仍由 contour_service 固定 20m/100m）。

## 8. 下一阶段建议

补四类地图核心要素清单与显式召回率；接入线连通性到 metrics；封装 Smoothing；生成 benchmark；地势等高距动态推导。
