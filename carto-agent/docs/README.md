# CartoAgent 文档索引

本文档为 `docs/` 目录的唯一入口，按用途组织。历史阶段报告、过程性方案
与被取代的缺口分析已清理；当前状态以 `audit/project_status.json` 为准。

## 入门

| 文档 | 用途 |
|---|---|
| [项目结构说明.md](项目结构说明.md) | 代码组织、模块职责、数据存储、启动方式（README 主入口） |
| [地理数据准备说明.md](地理数据准备说明.md) | 本地 GeoJSON / DEM 数据来源与准备流程 |

## 规划与规范

| 文档 | 用途 |
|---|---|
| [CartoAgent长期优化完善计划.md](CartoAgent长期优化完善计划.md) | 长期优化完善主计划（需求与阶段路线） |
| [audit/QA_SPEC_V1.md](audit/QA_SPEC_V1.md) | 武汉四类专题地图质量验收规范 V1.0（1000 分制） |

## 当前状态与验收

| 文档 | 用途 |
|---|---|
| [audit/project_status.json](audit/project_status.json) | 单一状态源：模块状态 / 接入标记 / Benchmark 结果 / 性能修复 |
| [audit/FINAL_SYSTEM_AUDIT.md](audit/FINAL_SYSTEM_AUDIT.md) | 最终系统审计（渲染链闭环、16 组评分、修复清单） |
| [audit/FINAL_BENCHMARK_REPORT.md](audit/FINAL_BENCHMARK_REPORT.md) | 16 组最终 Benchmark 明细 |
| [audit/FINAL_MAP_QA_REPORT.md](audit/FINAL_MAP_QA_REPORT.md) | 四类地图 QA 门槛与维度分 |
| [audit/FINAL_REMAINING_ISSUES.md](audit/FINAL_REMAINING_ISSUES.md) | 剩余问题（PARTIAL / 数据源限制，如实标注） |
| [audit/LABEL_SPEC_IMPLEMENTATION.md](audit/LABEL_SPEC_IMPLEMENTATION.md) | 地图注记规范落地说明（优先级/字体字号字色/字向/尺度范围） |

## 架构参考

| 文档 | 用途 |
|---|---|
| [audit/ARCHITECTURE.md](audit/ARCHITECTURE.md) | 系统架构与数据流 |
| [audit/MODULE_MATRIX.md](audit/MODULE_MATRIX.md) | 模块-能力矩阵 |

## 工具

运维与开发工具说明见 [../tools/README.md](../tools/README.md)。
