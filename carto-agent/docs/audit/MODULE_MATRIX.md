# 模块输入/输出矩阵（基于实际代码）

## 后端服务

| 模块 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| `agent_service.process_request` | message, session_id | {success, response, map_data, steps, thinking} | task_parser/planner/tool_registry/map_service/validator |
| `task_parser.SixDimParser.parse` | user_input | CartographyTask（六维+confidence/inferred） | llm_service（可选） |
| `cartographic_planner.plan` | CartographyTask, map_type, city | ExecutionPlan（14 键规划结构） | kg_service, llm_service |
| `crs_manager.CRSManager` | lonlat/latlng + CRS | 4326/3857/4547 投影转换、米制 simplify/buffer/area/distance | pyproj |
| `data_fusion.DataFusionEngine` | 多源图层 | CRS/schema/name/class 归一 + confidence 赋值 | crs_manager |
| `generalization.GeneralizationEngine.generalize` | map_type, layers, scale | {layers, metrics(recall/topology/gates/dup)} | crs_manager, profiles |
| `label.LabelEngine` | 标签坐标/名称/优先级 | 放置/抑制/线注记 + label_metrics | 无 |
| `cartography.symbols.SymbolRegistry.resolve_symbol` | category, feature_class | 统一符号（symbol_id/color/width/priority） | 无 |
| `cartography.layout.LayoutEngine.plan` | map_name, map_type | 版式槽位（title/legend/scale_bar/north/source/crs/made_at）+ 校验 | 无 |
| `map_qa_service.MapQAService.generate_report` | map_data | 1000 分制报告（十项维度/等级/状态/C0-C2） | qa/* |
| `kg_service.query_cartographic_decision` | map_type, audience | {layer_configs, symbol_scheme, color_scheme, annotation_rules, confidence} | Neo4j / 内存规则 |
| `tool_registry.execute_plan` | ExecutionPlan | {success, results, errors} | 已注册工具 |
| `map_service.generate_map` | map_type, region, zoom | map_data（layers/legend/quality/metadata/layout/label_metrics/generalization_metrics） | osm/amap/local_geo/geo_service/generalization/label/cartography |
| `cartography_validator.validate` | map_data | {score, issues, check_scores, dimensions} | kg_service（可选） |
| `export_service` | map_id, format | 文件/数据 URL | map_service |
| `session_service.add_message` | session_id, role, content, map_data | SessionMessage（map_id+map_summary 轻量） | 无 |

## 前端状态

| Store | 关键状态 | 关键动作 |
|---|---|---|
| `appStore` | showLayerPanel/showChatPanel/currentView/showTracePanel/traceData | toggle*、openTracePanel |
| `chatStore` | sessions/currentSessionId/messages | loadSessions（自动恢复最近会话）、sendMessage、switchSession |
| `mapStore` | currentMapData/layerGroups/quality/theme/layout | setMapData、sortedLayers、updateLayerStyle |
| `editStore` | active/drawTool/undoStack | setDrawTool、pushUndo/popUndo |
| `kgStore` | graph 数据 | loadGraph |

## 数据流关键链路

1. 六维任务书：`CartographyTask.to_task_book()` → `provenance.task`（每维 value/confidence/inferred）
2. 规划：`ExecutionPlan.to_dict()` → `provenance.plan`（14 键）
3. 工具：`ToolRegistry.get_tool_provenance_summary()` → `provenance.tools`
4. 地图持久化：`map_service._schedule_save` → `data/maps/{map_id}.json`（含 provenance）
5. 会话持久化：`session_service._save_sessions` → `data/sessions.json`（map_id/map_summary）
6. 制图管线：generate_map 内部按 CartographicProfile → SymbolRegistry → Generalization →
   LabelEngine → LayoutEngine 顺序产出 map_data，MapQAService 验收后写入
   `generalization_metrics` / `label_metrics` / `layout` 字段
