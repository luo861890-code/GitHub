# 最终遗留问题

1. LabelEngine 曲线注记、feature-aware displacement：PARTIAL（线注记已实现）。
2. SymbolRegistry：已实现（15 类），未接入 map_service 渲染管线（PARTIAL）。
3. LayoutEngine：已实现版式规划与校验，未接入前端渲染（PARTIAL）。
4. 行政区划数据源 11 处微小 overlap（DataV 边界精度）：SOURCE_DATA_WARNING，未伪修复。
5. 四类×四尺度完整 benchmark：PARTIAL。
6. 独立测试集与全量 158 项回归：本会话未完成，需后续补跑。
7. 铁路 geometry_quality=approximate、source_confidence=unverified（未与官方核验）。

## 建议下一步

优先完成 LabelEngine 线注记与 SymbolRegistry，跑四类×四尺度完整 benchmark 与全量测试，再进入 AutoRepair 闭环。
