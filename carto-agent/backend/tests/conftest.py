# -*- coding: utf-8 -*-
import json
import os
import shutil

import pytest

from app.services.map_service import MapService


@pytest.fixture()
def work_tmp_dir():
    """工作区内可写的临时目录（沙箱不允许写系统 %TEMP%）。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tmp = os.path.join(root, "data", "test_pytest_tmp")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def map_service(work_tmp_dir):
    ms = MapService(persist_path=os.path.join(work_tmp_dir, "maps.json"))
    ms.put_map("map_test_0001", {
        "map_id": "map_test_0001",
        "name": "测试地图",
        "map_type": "traffic",
        "region": "武汉市",
        "center": [30.5928, 114.3055],
        "zoom": 12,
        "theme": "amap_normal",
        "created_at": 1700000000,
        "metadata": {"数据来源": "测试"},
        "layers": [
            {
                "id": "layer_road",
                "type": "polyline",
                "name": "道路",
                "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
                "properties": [{"name": "路1", "subtype": "primary"}],
                "style": {"color": "#3388ff", "weight": 3},
            },
            {
                "id": "layer_lake",
                "type": "polygon",
                "name": "湖泊",
                "coordinates": [[[30.58, 114.28], [30.58, 114.29], [30.59, 114.29], [30.59, 114.28]]],
                "properties": [{"name": "湖1"}],
                "style": {"fillColor": "#60a5fa", "fillOpacity": 0.6},
            },
        ],
    })
    yield ms
    ms.flush()
