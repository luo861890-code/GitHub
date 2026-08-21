# -*- coding: utf-8 -*-
"""核心 GeoJSON 元数据迁移：生成 manifest 与逐文件 .metadata.json（可重复执行）

用法:
    python tools/migrate_metadata.py

输出:
    backend/data/metadata/datasets.json   统一 manifest（含真实 feature_count/geometry_type）
    backend/data/metadata/schema.json     metadata schema
    backend/data/geo/<name>.metadata.json  每个数据文件旁的元数据
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.core.dataset_metadata import METADATA_SCHEMA, get_manifest  # noqa: E402

GEO_DIR = os.path.join(ROOT, "backend", "data", "geo")
META_DIR = os.path.join(ROOT, "backend", "data", "metadata")

# dataset_id -> 文件名
FILE_MAP = {
    "wuhan_roads": "wuhan_roads.geojson",
    "wuhan_water": "wuhan_water.geojson",
    "wuhan_transit": "wuhan_transit.geojson",
    "wuhan_tourism": "wuhan_tourism.geojson",
    "wuhan_builtup": "wuhan_builtup.geojson",
    "hubei_cities": "hubei_cities.geojson",
    "hubei_province": "hubei_province.geojson",
    "wuhan_districts": "wuhan_districts.geojson",
    "wuhan_contours": "wuhan_contours.geojson",
}


def detect_geometry_type(features: list) -> str:
    types = {}
    for f in features:
        g = (f.get("geometry") or {}).get("type")
        if g:
            types[g] = types.get(g, 0) + 1
    if not types:
        return "Unknown"
    return "/".join(sorted(types, key=types.get, reverse=True))


def main():
    os.makedirs(META_DIR, exist_ok=True)
    manifest = get_manifest()
    migrated = []
    for entry in manifest:
        dsid = entry["dataset_id"]
        fname = FILE_MAP.get(dsid)
        if not fname:
            migrated.append(entry)
            continue
        path = os.path.join(GEO_DIR, fname)
        feature_count = 0
        geometry_type = entry.get("geometry_type", "Unknown")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])
            feature_count = len(features)
            geometry_type = detect_geometry_type(features) or entry.get("geometry_type", "Unknown")
            # 写入逐文件 metadata
            per_file = dict(entry)
            per_file["feature_count"] = feature_count
            per_file["geometry_type"] = geometry_type
            with open(path.replace(".geojson", ".metadata.json"), "w", encoding="utf-8") as f:
                json.dump(per_file, f, ensure_ascii=False, indent=1)
        entry["feature_count"] = feature_count
        entry["geometry_type"] = geometry_type
        migrated.append(entry)

    # manifest
    with open(os.path.join(META_DIR, "datasets.json"), "w", encoding="utf-8") as f:
        json.dump({"datasets": migrated}, f, ensure_ascii=False, indent=1)
    # schema
    with open(os.path.join(META_DIR, "schema.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata_schema": METADATA_SCHEMA}, f, ensure_ascii=False, indent=1)

    print(f"[metadata] 已迁移 {len(migrated)} 个数据集")
    for e in migrated:
        print(f"  {e['dataset_id']:<16} features={e['feature_count']:<6} type={e['geometry_type']}")


if __name__ == "__main__":
    main()
