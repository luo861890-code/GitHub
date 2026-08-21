# CartoAgent 运维与开发工具

## 启动 / 停止 / 守护

- `python tools/start_all.py --watch`：一键启动后端（8080）+ 前端（5173），附带看门狗自动重启
- `python tools/stop_all.py`：停止后端 / 前端 / 看门狗（含子进程树）
- 单独启动：`python tools/start_server_noproxy.py`（后端，无代理直连外网）、`python tools/start_frontend.py`（前端）

## 测试

- `cd backend && python -m pytest`：单元测试（意图/地图服务/导出/会话/KG/符号推荐/校验/工具/GeoToken）
- `python tools/test_api_flow.py`：25 项接口回归（隔离数据，不写生产文件）
- `python tools/test_network_flow.py`：9 项联网功能回归（LLM/OSM/OSRM/维基/GraphRAG，需外网）

## 数据流水线

- `python tools/run_data_pipeline.py`：一键执行本地地理数据准备脚本（prepare_local_data → prepare_local_geo → clean_water_data → optimize_geo_data）
- `python tools/download_srtm_wuhan.ps1`：下载武汉 SRTM DEM（等高线/晕渲）
- `python tools/import_carto_knowledge.py`：导入制图知识语料到 Neo4j

## 数据迁移 / 修复

- `python tools/migrate_data.py`：地图/会话数据瘦身迁移与归档
- `python tools/fix_system.py`：系统修复脚本
- `python tools/compare_admin_maps.py`：对比行政图数据

## 导出 / 验证

- `python tools/export_ontology.py`：导出 KG 本体
- `python tools/verify_lod.py`：验证 LOD 分级
- `python tools/evaluate_system.py`：系统整体评估
