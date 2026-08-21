# -*- coding: utf-8 -*-
"""四类武汉地图“应有核心要素集合”（Ground Truth）+ 真实 recall 计算

来源：
  - 行政区 13 区：app.core.constants.WUHAN_DISTRICTS（民政部现状）
  - 旅游核心：app.core.constants.WUHAN_LANDMARKS / WUHAN_GIS_POI
  - 交通核心：武汉公开交通骨架（高速公路/铁路/地铁/跨江桥梁/枢纽）
  - 地势核心：计曲线（100m 间隔等高线）
recall = |intersection(expected, generated)| / |expected|，不做“骨架全保留”式推断。
"""
from typing import Any, Dict, List

from app.core.constants import WUHAN_DISTRICTS, WUHAN_LANDMARKS


# 核心要素清单（真实来源）
EXPECTED_FEATURES: Dict[str, Dict[str, List[str]]] = {
    "administrative": {
        "districts": [d["name"] for d in WUHAN_DISTRICTS],  # 13 区
        "city_boundary": ["武汉市域边界"],
    },
    "traffic": {
        "core_highways": ["高速公路", "主干道"],           # 类别级（数据无稳定具体路名）
        "railways": ["铁路"],
        "metros": ["轨道交通线路"],
        "bridges": ["主要桥梁"],
        "hubs": ["武汉站", "汉口站", "武昌站", "武汉天河国际机场"],
    },
    "tourism": {
        "core_attractions": ["黄鹤楼", "东湖", "湖北省博物馆", "武汉大学", "户部巷",
                             "古琴台", "晴川阁", "归元寺", "东湖绿道", "木兰文化生态旅游区"],
    },
    "terrain": {
        "index_contours": ["等高线（计曲线）"],  # 100m 间隔计曲线
    },
}


def compute_recall(map_type: str, layers: List[Dict], category: str, expected: List[str]) -> Dict[str, Any]:
    """真实 recall：generated 中出现的 expected 要素 / expected 总数"""
    if not expected:
        return {"expected_count": 0, "matched_count": 0, "missed": [], "recall": 1.0}

    generated_names = _collect_names(layers)
    matched = [e for e in expected if e in generated_names]
    missed = [e for e in expected if e not in generated_names]
    return {
        "expected_count": len(expected),
        "matched_count": len(matched),
        "missed": missed,
        "recall": round(len(matched) / len(expected), 4),
    }


def compute_all_recall(map_type: str, layers: List[Dict]) -> Dict[str, Any]:
    """四类地图各核心要素类别的 recall 汇总"""
    spec = EXPECTED_FEATURES.get(map_type, {})
    result: Dict[str, Any] = {}
    for category, expected in spec.items():
        result[category] = compute_recall(map_type, layers, category, expected)
    # 总 recall（跨类别平均）
    recalls = [r["recall"] for r in result.values()]
    result["overall_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else 1.0
    return result


def _collect_names(layers: List[Dict]) -> List[str]:
    """收集 generated 图层中的要素名（图层名 + properties.name）"""
    names: List[str] = []
    for l in layers:
        names.append(l.get("name", ""))
        for p in (l.get("properties") or []):
            if isinstance(p, dict) and p.get("name"):
                names.append(str(p["name"]))
        for f in (l.get("features") or []):
            prop = f.get("properties") or {}
            if prop.get("name"):
                names.append(str(prop["name"]))
    return names
