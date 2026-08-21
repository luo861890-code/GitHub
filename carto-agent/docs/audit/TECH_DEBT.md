# 技术债清单（2026-08 审计）

## P1（建议近期处理）

1. **MapCanvas.vue 遗留组件**：已不被任何视图引用（主视图/编辑视图均用 LegacyMapPanel），约 87KB 源码 + 相关类型逻辑冗余。建议删除或标注 deprecated。
2. **专题地图数据为模拟**：`map_service._generate_thematic_layers` 中 population/economic/climate 等使用 `random.uniform` 生成模拟要素，非真实统计数据，论文/科研场景不可用。
3. **前端 `MapData` 类型缺 provenance 字段**：`types/index.ts` 的 MapData 未声明 `provenance/task`，前端访问需 `(msg.map_data as any)` 绕过（ChatPanel/AgentTracePanel 已用断言）。
4. **`_handle_map_generation` 方法过长**：约 470 行，含 6 个步骤内联；provenance 已抽出为 `_build_provenance`，其余步骤可继续拆分。
5. **依赖版本偏旧**：FastAPI 0.115.0 / Pydantic 2.9.0 / Vue 3.4.x / Vite 5.x；升级前需按计划 §35-36 走 Context7 官方文档兼容分析。

## P2（可择机处理）

6. `tool_registry` 中部分工具（fetch_boundary/fetch_road 等）未填 preconditions/postconditions（默认空），契约不完整。
7. `cartography_validator` 的 schema/geometry/task_compliance 层暂无独立检查项（六层评估中这三层 score=0）。
8. KG 本体 `ONTOLOGY_NODES` 与 `init_data.json` 可能存在重复/不一致，Neo4j 导入依赖 `tools/import_carto_knowledge.py` 的幂等性。
9. 前端 `KGPanel` 使用 `right: var(--toolbar-width)` 绝对定位，与工具栏实际宽度（50px）存在历史不一致。
10. 会话 JSON 手动序列化（`_save_sessions`）而非 `model_dump`，字段增删易遗漏（历史上漏过 map_id/map_summary，已修复）。

## 建议暂缓

- PostGIS/Neon 正式数据层（计划 §19）：当前 JSON 文件对原型可用，进入 Benchmark 阶段再迁移。
- GeoToken/MapGPT 训练（计划 §31）：缺语料与评测，先积累 provenance 数据。
- VLM Judge（计划 §23）：依赖外部视觉模型接入，先完善程序规则验证。
