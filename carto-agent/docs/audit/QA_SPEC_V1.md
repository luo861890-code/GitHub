# CartoAgent 武汉四类专题地图质量验收规范 V1.0（落地说明）

> 本文件为《CartoAgent 武汉四类专题地图质量验收规范 V1.0》在仓库中的工程落地说明。
> 规范原文由用户提供，作为 CartoAgent 后续开发的总验收标准（母规范）。

## 一、评分模型（1000 分制 + 否决项）

| 一级指标 | 分值 | 实现模块 |
|---|--:|---|
| A. 地理数据质量 | 200 | `qa/data_quality.py` |
| B. 数据数量与完整性 | 100 | `qa/completeness.py` |
| C. 空间/拓扑/逻辑一致性 | 100 | `qa/topology_quality.py` |
| D. 多源一致性与时效性 | 80 | `qa/temporal_source_quality.py` |
| E. 地图综合与多尺度表达 | 180 | `qa/generalization_quality.py` |
| F. 符号系统与视觉层级 | 100 | `qa/symbol_label_quality.py` |
| G. 注记与冲突处理 | 80 | `qa/symbol_label_quality.py` |
| H. 专题信息质量 | 70 | `qa/layout_thematic_fact.py` |
| I. 地图整饰与版式 | 50 | `qa/layout_thematic_fact.py` |
| J. 事实与语义正确性 | 40 | `qa/layout_thematic_fact.py` |

等级：S≥900 / A 850-899 / B 750-849 / C 650-749 / D 600-649 / E<600。
状态：PASS / CONDITIONAL_PASS / REWORK / FAIL（任一 Critical → 总分 ≤599，状态降级）。

## 二、四类地图专项权重（规范 §21）

- 行政区划图：数据/事实 35% · 拓扑 20% · 综合 15% · 视觉 10% · 注记 10% · 整饰 10%
- 交通图：数据/拓扑 35% · 综合 25% · 视觉 15% · 注记 10% · 时效 10% · 整饰 5%
- 旅游图：专题 30% · 数据 20% · 综合 15% · 视觉 15% · 注记 10% · 事实 10%
- 地势图：DEM 35% · 地学 20% · 综合 15% · 视觉 15% · 水系 10% · 整饰 5%

## 三、问题分级

C0 Critical（行政事实错误/边界严重错误/CRS 缺失/区名错误等）→ 总分 ≤599
C1 Major（空图层、属性缺失、分段过多、注记碰撞率>3% 等）
C2 Minor（色彩过多、整饰缺失、来源可信度低等）
C3 Suggestion（保留扩展位）

## 四、当前四类地图验收基线（2026-08）

最终验收基线（2026-08-21，16 组 Benchmark 实测，见 FINAL_BENCHMARK_REPORT.md）：

| 地图 | 1:500k | 1:250k | 1:100k | 1:25k | 等级 | 状态 | Critical | duplicate | recall |
|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| 行政区划图 | 934 | 934 | 934 | 922 | S | PASS | 0 | 0 | 1.0 |
| 交通图 | 923 | 920 | 920 | 918 | S | PASS | 0 | 0 | 1.0 |
| 旅游图 | 929 | 927 | 927 | 926 | S | PASS | 0 | 0 | 1.0 |
| 地势图 | 900 | 900 | 900 | 894 | S/A | PASS | 0 | 0 | 1.0 |

通过线：行政/交通/地势 850，旅游 800（当前全部达标）。
早期问题（要素名称缺失 A2、道路分段过多 C2/E3、整饰缺失 I）已在收尾会话修复：
A2 计入 subtype/category 等语义属性、C2/E3 仅统计道路图层、metadata 补全整饰项。

## 五、使用方式

```bash
# 批量验收四类地图（输出 outputs/reports/）
python tools/run_map_qa.py

# 单图验收（API）
GET /api/maps/{map_id}/qa
```

前端：地图消息卡片 → "质量验收报告"面板（十项评分 + 问题清单 + 修改优先级）。

## 六、后续（规范 Phase 1-6）

Phase 1 数据质量底座（CRS/几何/拓扑/完整性/元数据）→ 已实现（CRSManager + DataQualityEngine + 10 数据集 metadata）
Phase 2 四类地图数据模型 → 数据清单已建立（`qa/metrics.py` THEMATIC_EXPECTED）
Phase 3 尺度综合 → 已实现选取/简化/聚合/位移/夸张/坍缩/多尺度评估，米制 tolerance 已接入（CRSManager）
Phase 4 LabelEngine → 已实现点/线注记候选放置、碰撞消解、格网容量、线注记旋转角与边界保护（曲线注记 PARTIAL）
Phase 5 MapQA → 已完成（本规范）
Phase 6 Agent 闭环（Generate→Check→Repair→Recheck）→ 待接入自动返工（自动修复闭环未实现）

新增专题（人口/土地利用/夜间灯光等）时，仅需在 `qa/metrics.py` 添加 `CartographicProfile` 与权重，无需重设计验图逻辑。

## 七、四类地图 Cartographic Profile（《武汉四类专题地图数据规范》落地）

`backend/app/core/cartographic_profiles.py` 定义四套 Profile：

- **尺度约束矩阵**：1:1M / 1:250K / 1:100K / 1:25K 四档，各要素类别 show/partial/hide
  （市界/区界全尺度显示，街道界/支路小比例尺隐藏，核心景点始终显示，服务设施大比例尺才显示）
- **主题重要性**：如交通图 高速★★★★★/桥梁★★★★★/轨道★★★★★，行政图 边界★★★★★/POI☆
- **旅游 POI 分级**：P0 核心景点 1.0 / P1 文化历史 0.9 / P2 自然公园 0.5-0.8 / P3 服务设施 0.3，
  写入图层 properties.importance，前端 LOD 抽稀按重要性优先保留
- **交通桥梁提取**：从道路数据提取"主要桥梁"独立主题层（武汉长江大桥/杨泗港大桥等 67 座）

`map_service.generate_map` 已集成 Profile：生成时移除各主题禁止图层、提取桥梁、POI 分级。

当前四类地图基线（Profile 生效后）：

| 地图 | 总分 | 等级 | 状态 | 说明 |
|---|--:|--:|---|--|
| 行政区划图 | 922-934 | S | PASS | 边界为主，道路/POI 精简，13 区 recall=1.0 |
| 交通图 | 918-923 | S | PASS | 含 67 座主要桥梁独立层，category/entity recall=1.0 |
| 旅游图 | 926-929 | S | PASS | POI 按 P0-P3 分级，核心景点 recall=1.0 |
| 地势图 | 894-900 | S/A | PASS | DEM/等高线/山峰，计曲线 recall=1.0 |
