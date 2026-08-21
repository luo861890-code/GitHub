# 最终地图 QA 报告（四类 × 四尺度）

## 核心质量门槛（全部达成）

| 指标 | 行政 | 交通 | 旅游 | 地势 |
|---|--:|--:|--:|--:|
| 13 区 recall | 1.0 | - | - | - |
| category/entity recall | - | 1.0 / 1.0 | - | - |
| 核心景点 recall | - | - | 1.0 | - |
| 计曲线 recall | - | - | - | 1.0 |
| exact/reverse duplicate | 0 | 0 | 0 | 0 |
| Critical | 0 | 0 | 0 | 0 |
| generalization_gate | PASS | PASS | PASS | PASS |

## 十项维度（1:100k 代表值）

| 维度 | 行政 | 交通 | 旅游 | 地势 |
|---|--:|--:|--:|--:|
| A 数据质量 200 | 180 | 180 | 180 | 150 |
| B 完整性 100 | 100 | 94 | 94 | 100 |
| C 拓扑 100 | 92 | 86 | 86 | 95 |
| D 多源 80 | 80 | 80 | 80 | 80 |
| E 综合 180 | 172 | 162 | 162 | 180 |
| F 符号 100 | 100 | 100 | 100 | 100 |
| G 注记 80 | 62 | 57 | 62 | 56 |
| H 专题 70 | 70 | 70 | 70 | 70 |
| I 整饰 50 | 50 | 50 | 50 | 50 |
| J 事实 40 | 40 | 39 | 40 | 40 |

注：B/C/E/G 分项为通用框架指标，部分子项（如 E7 坍缩层、
F 色彩数量、C3 点归属）受主题规范或要素类型限制而非满分，已如实记录，
非数据错误。

## 已知数据源问题

- 行政区划图：wuhan_districts.geojson 相邻区边界存在 11 处微小 overlap
  （0.002-0.166 km²，DataV 边界精度）→ dataset_gate=SOURCE_DATA_WARNING，
  未伪修复（不修改阈值、不删除数据）。
- 铁路几何为公开走向近似线（geometry_quality=approximate、
  source_confidence=unverified），feature_presence 与 geometry_verified 分开统计。
