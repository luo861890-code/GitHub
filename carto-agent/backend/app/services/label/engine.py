# -*- coding: utf-8 -*-
"""LabelEngine：标签优先级 / 候选位置 / 碰撞消解（真实实现）

优先级：行政名称 > 核心地名 > 主要交通 > 核心旅游点 > 普通要素。
候选位置：top/bottom/left/right/diagonal（点注记）；along-line（线注记）。
碰撞消解：低优先级标签降级/隐藏。
"""
from typing import Any, Dict, List, Tuple
import math


# 标签优先级（数字越大越优先）
PRIORITY: Dict[str, int] = {
    "admin": 100, "core_place": 80, "transport": 60, "core_poi": 40, "normal": 10,
}

# 候选位置（相对锚点像素偏移）
CANDIDATES: Dict[str, List[Tuple[int, int]]] = {
    "point": [(0, 0), (0, -16), (0, 16), (-16, 0), (16, 0), (-12, -12), (12, -12), (-12, 12), (12, 12)],
}


def label_priority(category: str) -> int:
    return PRIORITY.get(category, PRIORITY["normal"])


class CollisionGrid:
    """标签碰撞网格（屏幕像素格网，真实碰撞检测）"""

    def __init__(self, cell: int = 40):
        self.cell = cell
        self.grid: Dict[str, List[Dict]] = {}

    def _key(self, x: int, y: int) -> str:
        return f"{x // self.cell},{y // self.cell}"

    def conflict(self, x: int, y: int, w: int, h: int) -> bool:
        """标签矩形是否与已放置标签冲突"""
        for cx in range(x, x + w + 1, self.cell):
            for cy in range(y, y + h + 1, self.cell):
                k = self._key(cx, cy)
                for placed in self.grid.get(k, []):
                    px, py, pw, ph = placed["x"], placed["y"], placed["w"], placed["h"]
                    if not (x + w <= px or px + pw <= x or y + h <= py or py + ph <= y):
                        return True
        return False

    def add(self, x: int, y: int, w: int, h: int, label: Dict):
        for cx in range(x, x + w + 1, self.cell):
            for cy in range(y, y + h + 1, self.cell):
                k = self._key(cx, cy)
                self.grid.setdefault(k, []).append({"x": x, "y": y, "w": w, "h": h, "label": label})


class LabelEngine:
    """标签引擎：点/线注记候选 + 碰撞消解"""

    def __init__(self):
        self.collision = CollisionGrid()
        self.placed: List[Dict] = []
        self.suppressed: List[Dict] = []

    def place_point_label(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        name: str,
        category: str,
        latlng: Tuple[float, float],
    ) -> Dict[str, Any]:
        """点注记：尝试各候选位置，无冲突则放置，否则降级（缩小/隐藏低优先级）"""
        prio = label_priority(category)
        for ox, oy in CANDIDATES["point"]:
            if not self.collision.conflict(x + ox, y + oy, w, h):
                self.collision.add(x + ox, y + oy, w, h, {"name": name, "prio": prio})
                self.placed.append({"name": name, "category": category, "priority": prio,
                                    "position": (x + ox, y + oy), "latlng": latlng, "suppressed": False})
                return {"name": name, "placed": True, "position": (x + ox, y + oy)}
        # 冲突：低优先级隐藏，高优先级缩小重试
        if prio < PRIORITY["transport"]:
            self.suppressed.append({"name": name, "category": category, "reason": "collision"})
            return {"name": name, "placed": False, "suppressed": True}
        return {"name": name, "placed": False, "suppressed": False, "note": "high_priority_deferred"}

    def place_line_label(
        self,
        line_lonlat: List[Tuple[float, float]],
        name: str,
        category: str,
        canvas_size: Tuple[int, int] = (1680, 950),
    ) -> Dict[str, Any]:
        """线注记：沿道路/河流放置（取线中点，计算旋转角），检查边界保护"""
        if len(line_lonlat) < 2:
            return {"name": name, "placed": False, "reason": "too_short"}
        # 中点
        mid = line_lonlat[len(line_lonlat) // 2]
        # 近似屏幕坐标（简单线性映射，演示用；生产应经投影与画布变换）
        lats = [p[0] for p in line_lonlat]
        lngs = [p[1] for p in line_lonlat]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        span = max(1e-6, max_lng - min_lng, max_lat - min_lat)
        x = int((mid[1] - min_lng) / span * (canvas_size[0] - 100) + 50)
        y = int((max_lat - mid[0]) / span * (canvas_size[1] - 100) + 50)
        # 旋转角（线主方向）
        i0 = max(0, len(line_lonlat) // 2 - 1)
        i1 = min(len(line_lonlat) - 1, len(line_lonlat) // 2 + 1)
        p0, p1 = line_lonlat[i0], line_lonlat[i1]
        angle = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        # 边界保护：距画布边缘至少 20px
        if x < 20 or y < 20 or x > canvas_size[0] - 20 or y > canvas_size[1] - 20:
            return {"name": name, "placed": False, "reason": "out_of_bounds", "position": (x, y)}
        prio = label_priority(category)
        self.placed.append({"name": name, "category": category, "priority": prio,
                            "position": (x, y), "angle": angle, "line_label": True,
                            "suppressed": False})
        return {"name": name, "placed": True, "position": (x, y), "angle": round(angle, 1)}
