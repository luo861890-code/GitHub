# -*- coding: utf-8 -*-
"""武汉交通基础数据与实体 Ground Truth（真实来源，未核验处如实标注）

数据来源：公开地理坐标（火车站/机场/城市节点）与公开铁路网走向。
verification_status 一律 unverified（未与官方测绘/运营数据核验），不虚构“官方精度”。
"""
from typing import Any, Dict, List


# 铁路线路：主要走向用真实节点坐标连线（[lat, lng]），非精确轨道中心线
RAILWAYS: List[Dict[str, Any]] = [
    {
        "name": "京广铁路", "category": "railway", "importance": 1.0,
        "source": "公开铁路网走向", "verification_status": "unverified",
        "geometry_quality": "approximate", "source_confidence": "unverified",
        "coords": [
            [31.02, 113.95], [30.72, 114.25], [30.6210, 114.2500],  # 孝感→汉口→汉口站
            [30.5850, 114.2950], [30.5492, 114.2981],  # 经长江大桥
            [30.5310, 114.3160], [29.85, 114.30],  # 武昌站→咸宁
        ],
    },
    {
        "name": "京广高铁", "category": "railway", "importance": 1.0,
        "source": "公开铁路网走向", "verification_status": "unverified",
        "geometry_quality": "approximate", "source_confidence": "unverified",
        "coords": [
            [31.10, 114.20], [30.70, 114.35], [30.6070, 114.4230],  # 武汉站
            [30.30, 114.40],
        ],
    },
    {
        "name": "汉丹铁路", "category": "railway", "importance": 0.9,
        "source": "公开铁路网走向", "verification_status": "unverified",
        "geometry_quality": "approximate", "source_confidence": "unverified",
        "coords": [
            [30.6210, 114.2500], [30.70, 114.10], [30.80, 113.90],  # 汉口→襄阳方向
        ],
    },
    {
        "name": "武九铁路", "category": "railway", "importance": 0.9,
        "source": "公开铁路网走向", "verification_status": "unverified",
        "geometry_quality": "approximate", "source_confidence": "unverified",
        "coords": [
            [30.5310, 114.3160], [30.55, 114.60], [30.40, 114.90],  # 武昌→鄂州→九江方向
        ],
    },
]


# 交通枢纽实体（真实坐标，公开已知）
HUBS: List[Dict[str, Any]] = [
    {"id": "hub_wuhan_station", "name": "武汉站", "category": "transport_hub",
     "importance": 1.0, "lat": 30.6070, "lng": 114.4230,
     "source": "公开坐标", "verification_status": "unverified"},
    {"id": "hub_hankou_station", "name": "汉口站", "category": "transport_hub",
     "importance": 1.0, "lat": 30.6210, "lng": 114.2500,
     "source": "公开坐标", "verification_status": "unverified"},
    {"id": "hub_wuchang_station", "name": "武昌站", "category": "transport_hub",
     "importance": 1.0, "lat": 30.5310, "lng": 114.3160,
     "source": "公开坐标", "verification_status": "unverified"},
    {"id": "hub_tianhe_airport", "name": "武汉天河国际机场", "category": "transport_hub",
     "importance": 1.0, "lat": 30.7838, "lng": 114.2081,
     "source": "公开坐标", "verification_status": "unverified"},
]


# 交通 Ground Truth：类别级 + 实体级
TRAFFIC_GT: Dict[str, Any] = {
    "categories": [
        {"id": "cat_motorway", "name": "高速公路", "canonical_id": "highway.motorway",
         "category": "highway", "importance": 1.0},
        {"id": "cat_trunk", "name": "主干道", "canonical_id": "highway.trunk",
         "category": "primary_road", "importance": 0.9},
        {"id": "cat_railway", "name": "铁路", "canonical_id": "railway.main",
         "category": "railway", "importance": 1.0},
        {"id": "cat_metro", "name": "轨道交通线路", "canonical_id": "metro.line",
         "category": "metro", "importance": 1.0},
        {"id": "cat_bridge", "name": "主要桥梁", "canonical_id": "bridge.major",
         "category": "bridge", "importance": 1.0},
    ],
    "entities": [
        {"id": "hub_wuhan_station", "name": "武汉站", "category": "transport_hub",
         "source": "公开坐标", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
        {"id": "hub_hankou_station", "name": "汉口站", "category": "transport_hub",
         "source": "公开坐标", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
        {"id": "hub_wuchang_station", "name": "武昌站", "category": "transport_hub",
         "source": "公开坐标", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
        {"id": "hub_tianhe_airport", "name": "武汉天河国际机场", "category": "transport_hub",
         "source": "公开坐标", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
        {"id": "railway_beijing_guangzhou", "name": "京广铁路", "category": "railway",
         "source": "公开铁路网", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
        {"id": "railway_beijing_guangzhou_hsr", "name": "京广高铁", "category": "railway",
         "source": "公开铁路网", "importance": 1.0,
         "expected_at_scales": ["1:500000", "1:250000", "1:100000"]},
    ],
}
