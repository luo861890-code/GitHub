# P0 基础地理数据与空间参考整改报告

阶段：第二阶段 P0 整改。范围仅限三个 P0，未处理 P1 / 前端 / Generalization / Label 等。

## 1. 修改文件清单

- backend/app/core/crs_manager.py：新增 CRSManager（EPSG:4326/3857/4547 真实转换 + 米制 simplify/buffer/length/area/distance）
- backend/app/core/dataset_metadata.py：新增统一 metadata schema 与 10 个数据集真实 manifest
- backend/app/services/local_geo_service.py：616/689/695 及 375/378/586/718 行的度值 simplify/buffer/面积/距离改为米制
- backend/app/services/map_service.py：metadata 的坐标系/投影改为真实声明（数据 4326、渲染 3857、导出可重投影 4547）
- tools/migrate_metadata.py：新增元数据迁移脚本（生成 manifest + 逐文件 .metadata.json，可重复）
- backend/tests/test_p0_remediation.py：新增 41 项 P0 测试

## 2. P0-1 CRS / 投影

- 修改前：map_service.py:924 仅写字符串“CGCS2000 / 高斯-克吕格 / Web墨卡托”，无投影转换代码；数据实际 WGS84，前端 WebMercator。
- 修改后：新增 CRSManager，用 pyproj 真实执行 EPSG:4326 ↔ 3857 ↔ 4547（武汉 3° 高斯克吕格 CM 114E）；metadata 改为真实声明。
- 验证数值：武汉中心 (114.3055, 30.5928) 投影到 EPSG:4547 = (529299.86, 3385869.45)m；WebMercator = (12724430.05, 3579978.62)；4326↔4547 往返误差 < 1e-9 度（模块 round_trip_error 返回 0.0m）。

## 3. P0-2 数据元数据

10 个数据集（roads/water/transit/tourism/builtup/hubei_cities/hubei_province/districts/contours/srtm_dem）已建立 manifest。真实信息：source 真实（OSM/DataV GeoAtlas/SRTM）、license 真实（ODbL/public domain）、resolution 真实（SRTM 30m）。未知字段不伪造：acquisition_date、last_verified、horizontal_m、vertical_m 均为 null；accuracy 附 note 说明原因。生成位置：backend/data/metadata/datasets.json、schema.json、各 GeoJSON 旁 .metadata.json。

各数据集 feature_count 与 source_type 见 backend/data/metadata/datasets.json（wuhan_roads=34833、wuhan_water=2232、wuhan_transit=3178、wuhan_tourism=824、wuhan_builtup=9050、hubei_cities=17、wuhan_districts=13、wuhan_contours=3146、srtm_dem=0(.hgt)）。

## 4. P0-3 几何简化 / buffer

- 修改前：local_geo_service.py:616/689/695 用 simplify(0.00012)（经纬度度值≈13m）、buffer(0.0005)（度值≈55m）；375/586/689/718 用 area*9700、distance<=0.0036 等度坐标近似。
- 修改后：全部改为 CRSManager 的米制操作（WGS84 → EPSG:4547 投影 → 米制 simplify/buffer/length/area/distance → 回投影）。tolerance 参数化为 SIMPLIFY_TOLERANCE_M（riverline 13m / builtup 13m）与 BUFFER_DISTANCE_M（builtup_merge 55m）。
- 验证数值（真实等高线）：顶点 104 → 76（减少 26.9%），长度 10613.1m → 10534.7m（变化 -0.739%）；水系米制简化与旧度值简化长度差异 0.000%。
- 面积正确性：0.01°×0.01° 方形（武汉 30.5°N）投影面积 = 1064221.7m² = 1.064km²（修复了 area_meters2 返回度面积的 bug）。

## 5. 测试结果

- 新增 P0 测试 41 项（CRS 11 / 元数据 12 / 米制简化与 buffer 8 / 负例 10），全部通过。
- 全量后端测试 89 项通过（原 48 + 新增 41）。
- 真实武汉数据测试通过：wuhan_water（11 层，加载 1.63s）、wuhan_builtup（2 层，1.91s）、wuhan_contours（3146 线）。

## 6. 尚未解决（如实标记）

1. local_geo_service.py:90 `_poly_area_km2` 异常兜底 `geom.area * 9700.0` 仍保留（球面公式失败时的次优兜底，非主路径）。
2. `_snap_to_shore` 的 project/interpolate 吸附点仍在度坐标计算（距离判断已米制，最近点投影仍属近似，不涉及米制阈值）。
3. DEM 的 .hgt 文件无逐文件 metadata（仅 manifest 条目，因 .hgt 非 GeoJSON）；垂直基准来自 SRTM 官方声明（EGM96），未本地核验，已如实标注。

## 7. 验收门禁核对

- 无经纬度度值直接用于米制 simplify/buffer（源码已无 0.00012 / 0.0005 / 0.005 / 0.0036 简化与缓冲）
- 核心数据有真实 CRS（EPSG:4326 声明 + pyproj 投影能力）
- 核心数据有 metadata（10 个 manifest 条目 + 逐文件 .metadata.json）
- CRS 转换真实执行（pyproj，往返误差 0m）
- simplify/buffer 在投影 CRS 中执行
- 新增 41 项测试通过、原有 48 项通过（合计 89）
- 真实武汉数据验证通过
- 生成 P0_REMEDIATION_REPORT.md
