# 已知 Bug 清单（含已修复项）

## 已修复（2026-08 审计期）

1. **会话持久化丢失地图引用**（P0）：`session_service._save_sessions` 序列化消息时遗漏 `map_id/map_summary`，导致重启后历史消息无法显示地图与制图过程。已修复（补全字段）。
2. **快速路径跳过六维解析**（P1）：`agent_service.process_request` 快速路径直接以 `cartography_task=None` 进入制图流程，provenance.task 为空。已修复（快速路径保留六维解析）。
3. **App.vue 串行初始化阻塞会话加载**（P1）：`onMounted` 串行 `await loadLLMStatus` → `loadSessions`，LLM 状态检测慢时会话列表/地图长时间空白。已改为并行初始化 + 自动恢复最近会话。
4. **前端 TS 构建失败**（P1）：`chatStore.map_name` 不存在、`MapCanvas` 闭包变量推断为 never、`iconSize: null` 非法等 4 处类型错误导致 `npm run build` 失败。已修复。
5. **KG 自环关系**（P3）：`case_traffic_wuhan_public SIMILAR_TO 自身` 无意义。已删除。

## 现存问题（待处理）

6. **专题地图模拟数据**：`map_service._generate_thematic_layers` 使用随机数据，多次生成同一专题图结果不一致（缺随机种子）。
7. **Overpass 行政边界抓取超时**：`osm_service` 抓取 `boundary~administrative` 时镜像超时（curl exit 28），每次重试 90 秒；行政图已跳过该抓取，但其他依赖 OSM boundary 的场景仍受影响。
8. **`quality_service` 与 `cartography_validator` 双套校验**：两处质量体系并存，指标口径需统一（前端 QualityReport 使用 mapStore.quality，Trace 面板使用 validator 结果）。
9. **KGPanel 定位**：`right: var(--toolbar-width)`（56px）与实际工具栏宽度（50px）不一致，右侧面板位置偏差。

> 复现步骤与修复建议详见各文件内注释与对应 commit。
