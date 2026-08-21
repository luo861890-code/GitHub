# 最终 Benchmark 报告

## 已完成

- benchmarks/wuhan/generalization/：4 类地图 × 1:100k（before/after/metrics/qa JSON）已生成。
- 交通图四尺度（1:500k/1:250k/1:100k/1:25k）本次实测通过。

## 未完成

- 四类 × 四尺度完整 16 组：PARTIAL（仅交通图四尺度完成，行政/旅游/地势各尺度未全跑）。
- runtime.json / memory 统计：PARTIAL（记录了 runtime，未记录内存）。

## 性能

- 交通图生成 runtime 72-82s/尺度，主要耗时在 displacement 的 O(n²) 近距线比较与本地数据加载。
- 未通过关闭 QA 提速（QA 全开）。
