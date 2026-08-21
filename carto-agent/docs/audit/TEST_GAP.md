# 测试覆盖缺口（2026-08）

当前：后端 pytest 36 项通过（tests/：agent_intent/export/geotoken/kg/map_service/session/symbol_recommender/tool_registry/validator/plan_upgrade）。

## 缺口

1. **agent_service 集成测试**：`process_request` 全流程（六维解析→规划→工具→生成→provenance）无自动化测试（依赖 LLM/网络），仅手动端到端验证。建议用 mock LLM + mock map_service 做闭环单测。
2. **前端无单测/E2E**：无 Vitest/Playwright 测试；Trace 面板、会话恢复、LOD 分级等仅靠 CDP 脚本验证（`visualizations/.../cdp_*.mjs`，未纳入 CI）。
3. **LOD 分级逻辑**（`map-lod.js`）：POI 预算/档位/抽稀无单元测试，依赖浏览器实测。
4. **provenance 数据完整性**：无测试断言 provenance 结构（task/plan/tools 字段齐全）。
5. **错误恢复**：`osm_service` 超时重试、Overpass 镜像切换无测试。
6. **导出格式**：PNG/SVG/GeoJSON 导出仅有基础测试，布局导出（LayoutExport）未覆盖。
7. **并发/性能**：SSE 流式、会话防抖写入并发无压力测试。

## 建议

- 优先补：agent_service mock 闭环测试 + provenance 结构测试（可纳入 `tests/`）。
- 中期：引入 Playwright 对主流程（生成地图→LOD→编辑→导出→Trace）做 E2E。
- CI 门禁：后端 pytest + `npm run build`（vue-tsc）必须通过（计划 §38）。
