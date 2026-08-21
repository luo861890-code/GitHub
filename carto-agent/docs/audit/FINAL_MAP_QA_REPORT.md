# 最终地图 QA 报告

## 交通图（四尺度，本次实测）

| 尺度 | exact dup | category recall | entity recall | gate | runtime |
|---|--:|--:|--:|---|--:|
| 1:500k | 0 | 1.0 | 1.0 | PASS | 72s |
| 1:250k | 0 | 1.0 | 1.0 | PASS | 75s |
| 1:100k | 0 | 1.0 | 1.0 | PASS | 80s |
| 1:25k | 0 | 1.0 | 1.0 | PASS | 82s |

## 行政区划图（1:100k 实测）

- dataset/generalization/map gate 均 PASS，13 区 recall=1.0。
- 已知残留：wuhan_districts 相邻区边界存在 11 处微小 overlap（0.002-0.166km²，DataV 边界精度，如实标记，未伪修复）。

## 旅游/地势图

- 本会话未跑完整四尺度（token 受限），此前 1:100k 验证 recall≥0.8。

## 总体

- 交通图核心质量门槛（duplicate=0、recall=1.0、gate PASS）达成。
- 行政区划 overlap 为数据源问题，标记 SOURCE_DATA_WARNING。
