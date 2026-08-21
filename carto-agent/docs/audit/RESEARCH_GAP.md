# 研究实验缺口（2026-08）

对照《CartoAgent 长期优化完善计划》与研究材料，当前系统已具备：
- 六维任务书（带 confidence/inferred）✅
- KG 驱动规划 + 完整规划结构 ✅
- 21 个带契约的工具 ✅
- 七维校验 + 六层评估框架 ✅
- 地图 provenance（可追溯"为什么这样画"）✅
- 前端 Agent Trace 面板 ✅
- 1000 分制自动地图验收（MapQAService：六级评分 + 致命错误门槛 + 问题/缺失清单 + 修改优先级）✅
- 四类武汉地图批量验收（tools/run_map_qa.py → outputs/reports/）✅

## 尚未建立（下一阶段研究重点）

1. **Baseline 固化（计划 §2-3）**：未创建 `baseline/v1.0` tag、未记录版本矩阵（Python/Node/FastAPI/LLM/KG 节点数等）。
2. **CartoAgentBench（计划 §24-26）**：无 benchmark 任务集（50+ 任务按行政/交通/旅游/地形/专题分类），无评价指标脚本（Task Success Rate/Tool Accuracy/Plan Efficiency/Auto Correction Rate 等）。
3. **消融实验（计划 §28）**：LLM vs +RAG vs +KG vs +Tool vs +Validator 未做实验矩阵；KG 简单 vs 分层未对比。
4. **VLM Judge（计划 §23）**：已有程序规则六层评估（MapQAService），尚缺视觉验证（地图 PNG → VLM 评估标题/图例/比例尺/指北针/符号一致性/任务符合度）。
5. **错误恢复闭环（计划 §17-18）**：无 Error Log Parser → 分类器 → 修复 → 重试机制。
6. **GeoToken 语料（计划 §30-31）**：`geotoken_service` 已能提取 token，但无训练语料/评测。
7. **实验记录**：provenance 已逐图记录，但缺"一次实验批量运行 + metrics_schema + 统计检验"的模块。

## 建议路径

按计划 §50 顺序：① 审计文档（本目录）→ ② Baseline 固化 → ③ Benchmark 任务集 → ④ 消融实验脚本 → ⑤ VLM Judge → ⑥ 论文。
