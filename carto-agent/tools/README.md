# CartoAgent 运维与开发工具

## 启动 / 停止 / 守护

- `python tools/start_all.py --watch`：一键启动后端（8080）+ 前端（5173），附带看门狗自动重启
- `python tools/stop_all.py`：停止后端 / 前端 / 看门狗（含子进程树）
- 单独启动：`python tools/start_server_noproxy.py`（后端，无代理直连外网）、`python tools/start_frontend.py`（前端）

## 测试

- `cd backend && python -m pytest`：单元测试（当前 194 项：意图/地图服务/导出/会话/KG/符号推荐/校验/工具/GeoToken/制图引擎/QA 精度）
- `python tools/test_api_flow.py`：25 项接口回归（隔离数据，不写生产文件）
- `python tools/test_network_flow.py`：9 项联网功能回归（LLM/OSM/OSRM/维基/GraphRAG，需外网）

## 质量验收 / Benchmark

- `python tools/run_final_benchmark.py`：16 组最终 Benchmark（行政/交通/旅游/地势 × 1:500k/1:250k/1:100k/1:25k），
  输出 `benchmarks/wuhan/final/`（before/after/metrics/qa/runtime + summary）
- `python tools/audit.py --benchmark`：从 Benchmark 输出评分汇总
- `python tools/audit.py --map traffic --scale 100000`：单图专家验收（十项指标评分表）
- `python tools/run_map_qa.py`：批量验收四类地图（输出 reports/）
- `python tools/run_generalization_benchmark.py`：制图综合 Benchmark（before/after/metrics/qa）

## 数据流水线

- `python tools/run_data_pipeline.py`：一键执行本地地理数据准备脚本（prepare_local_data → prepare_local_geo → clean_water_data → optimize_geo_data）
- `python tools/download_srtm_wuhan.ps1`：下载武汉 SRTM DEM（等高线/晕渲）
- `python tools/import_carto_knowledge.py`：导入制图知识语料到 Neo4j

## 数据迁移 / 修复

- `python tools/migrate_data.py`：地图/会话数据瘦身迁移与归档
- `python tools/migrate_metadata.py`：为数据集补写 `.metadata.json`
- `python tools/normalize_admin_maps.py`：行政区划数据规范化
- `python tools/compare_admin_maps.py`：对比行政图数据
- `python tools/fix_system.py`：系统修复脚本
- `python tools/patch_def.py`：一次性补丁

## 数据辅助

- `python tools/supplement_kg.py`：知识图谱补充
- `python tools/extract_samples.py`：样本提取
- `python tools/process_utils.py`：进程管理公共函数
- `python tools/test_map_gen.py`：地图生成接口冒烟测试

## 导出 / 验证

- `python tools/export_ontology.py`：导出 KG 本体
- `python tools/verify_lod.py`：验证 LOD 分级
- `python tools/evaluate_system.py`：系统整体评估
