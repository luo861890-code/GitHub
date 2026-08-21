# CartoAgent 最终系统审计（收尾完成）

最终状态：**FINAL_PASS**（16 组 Benchmark 全部 PASS，Critical=0）。
状态源：`docs/audit/project_status.json`（代码/测试/Benchmark/审计文档同一状态源）。

## 1. 完成的全流程闭环

渲染链真实接管（收尾包 A）：

```
CartographicProfile → SymbolRegistry → Generalization → LabelEngine → LayoutEngine → Renderer → PNG/SVG/PDF
```

- **SymbolRegistry** 已接入 `map_service._apply_symbol_registry`：图层样式从注册表解析、
  记录 `symbol_id`、全图层统一分组；无匹配返回 None，禁止 LLM 随机配色。
- **LabelEngine** 已接入 `map_service._apply_label_engine`：点注记候选/碰撞消解、
  0.02° 格网容量上限（行政名称例外）、道路/河流线注记（旋转角 + 视口边界保护）、
  `label_metrics` 输出。
- **LayoutEngine** 已接入：`map_data.layout` 版式计划 + 校验；
  前端 `LayoutExport` 与导出服务 `export_layout_png` 均以该计划为默认值。

## 2. 16 组最终 Benchmark（收尾包 B，benchmarks/wuhan/final/）

| 地图 | 1:500k | 1:250k | 1:100k | 1:25k | dup | recall | Critical |
|---|--:|--:|--:|--:|--:|--:|--:|
| 行政区划图 | 934 S | 934 S | 934 S | 922 S | 0 | 1.0 | 0 |
| 交通图 | 923 S | 920 S | 920 S | 918 S | 0 | 1.0 | 0 |
| 旅游图 | 929 S | 927 S | 927 S | 926 S | 0 | 1.0 | 0 |
| 地势图 | 900 S | 900 S | 900 S | 894 A | 0 | 1.0 | 0 |

四类地图全部超过目标线（行政 ≥850 / 交通 ≥900 / 旅游 ≥850 / 地势 ≥850）。

## 3. 数据与算法修复（本收尾会话）

- **props/coords 同步**：`_generalize_roads` 重复线去重同步裁剪属性、
  engine 管线级去重同步属性、新增 `_sync_props` 防御对齐。
- **连接范围修正**：`_connect_polylines_by_name` 仅连接有名称的道路/边界/铁路；
  等高线与无名称支流不再被错误合并（语义错误 + 性能灾难同时消除，
  terrain 生成从 10 分钟降到 15 秒）。
- **位移规模保护**：`Displacement` 限 600 线以内，避免大图层 O(n²) 退化。
- **地势图道路过滤**：仅保留 motorway/trunk（符合 Profile road_levels）。
- **QA 精度修正**：A2 属性完整度计入 subtype/category 等语义属性；
  C2/E3 只统计道路图层（边界/水系/铁路不再误判为道路分段）；
  J 事实按要素级判断「长江」；指北针接受元数据声明；
  WUHAN_BBOX 按真实市域范围（lat 29.96~31.37，lng 113.69~115.09）校正；
  report 维度拆分不再用余数（F/G、H/I/J 分别真实评分）。
- **旅游图核心景点**：叠加 WUHAN_GIS_POI「重点地标」层（东湖绿道、
  木兰文化生态旅游区等真实核心景点上图），recall 0.8 → 1.0。

## 4. 测试（收尾包 C）

- 新增 36 项独立测试：`tests/test_cartography_engines.py`（SymbolRegistry/LayoutEngine/
  LabelEngine/渲染链）、`tests/test_final_refinements.py`（QA 精度/管线修复）。
- 全量回归：原 158 项 + 新增 36 项（详见测试输出）。

## 5. 剩余问题（如实标注，未伪修复）

- LabelEngine：曲线注记（curved label）与要素感知位移未实现（PARTIAL）。
- 行政区划数据源 11 处微小 overlap（DataV 边界精度，0.002-0.166 km²）：
  dataset_gate=SOURCE_DATA_WARNING，不伪修复。
- 铁路 geometry_quality=approximate、source_confidence=unverified（未与官方核验）。
- E7 坍缩层、F 色彩数量等 QA 子项因主题规范限制非满分（如实记录）。

## 6. 关键文件

- 渲染链：`backend/app/services/map_service.py`（_apply_symbol_registry/_apply_label_engine/_build_layout）
- 符号：`backend/app/services/cartography/symbols/registry.py`
- 版式：`backend/app/services/cartography/layout.py`
- 标签：`backend/app/services/label/engine.py`
- 综合：`backend/app/services/generalization/engine.py`
- QA：`backend/app/services/qa/`
- Benchmark：`tools/run_final_benchmark.py`、`tools/audit.py --benchmark`
- 状态源：`docs/audit/project_status.json`
