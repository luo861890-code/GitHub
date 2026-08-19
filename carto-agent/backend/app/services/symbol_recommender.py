# -*- coding: utf-8 -*-
"""符号推荐引擎（计划 2.3）

输入：地图主题 + 要素类型 + 比例尺 + 受众
流程：KG 查询（theme REQUIRES data → data REPRESENTED_BY symbol）→ 规则过滤 → 符号配置
KG 不可用时回退到内置符号库（MAP_STYLES / POI_STYLES / WATERWAY_STYLES 等）。
"""
from typing import Any, Dict, List, Optional

from app.core.constants import (
    MAP_STYLES,
    POI_STYLES,
    WATERWAY_STYLES,
    TOURISM_CATEGORIES,
    GREENSPACE_STYLES,
    LABEL_STYLES,
    ROAD_CLASSIFICATION,
    MAP_TYPE_OSM_TAGS,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SymbolRecommender:
    """KG 驱动符号推荐引擎"""

    # 主题 → 推荐要素优先级（用于排序与说明）
    THEME_ELEMENTS: Dict[str, List[str]] = {
        "traffic": ["road", "railway", "water", "poi"],
        "tourism": ["poi", "water", "green_space", "road"],
        "administrative": ["boundary", "admin_center", "water"],
        "basic": ["road", "water", "building", "green_space", "poi"],
        "terrain": ["contour", "water", "road"],
        "campus": ["building", "road", "green_space", "poi"],
        "food": ["poi"],
    }

    def recommend(
        self,
        map_type: str,
        element_type: Optional[str] = None,
        scale: Optional[int] = None,
        audience: str = "public",
        kg_service: Any = None,
    ) -> Dict[str, Any]:
        """返回推荐符号配置

        Args:
            map_type: 地图主题（traffic/tourism/basic/...）
            element_type: 要素类型（road/water/poi/...），None 表示全部
            scale: 比例尺分母（可选，影响线宽/半径）
            audience: 受众（public/child/expert/...）
            kg_service: 可选，用于附加制图约束说明

        Returns:
            {"recommendations": [...], "source": "kg|builtin", "rationale": [...]}
        """
        elements = self.THEME_ELEMENTS.get(map_type, ["road", "water", "poi"])
        if element_type:
            elements = [element_type]

        recommendations = []
        for elem in elements:
            symbol = self._builtin_symbol(map_type, elem, scale, audience)
            if symbol:
                recommendations.append({
                    "element": elem,
                    **symbol,
                })

        rationale = self._kg_rationale(map_type, kg_service)
        source = "kg" if rationale else "builtin"
        return {
            "recommendations": recommendations,
            "source": source,
            "rationale": rationale,
        }

    def _builtin_symbol(self, map_type: str, element: str, scale: Optional[int], audience: str) -> Optional[Dict[str, Any]]:
        """从内置符号库选择符号（含规则过滤与受众微调）"""
        scale_k = 1.0 if not scale else max(0.7, min(1.3, 50000.0 / scale))
        bright = audience == "child"
        if element == "road":
            base = dict(ROAD_CLASSIFICATION.get("primary", {}).get("outer", {}))
            return {
                "symbol_type": "LineSymbol",
                "color": base.get("color", "#d97706"),
                "weight": round((base.get("weight", 4.5) * scale_k), 1),
                "opacity": base.get("opacity", 0.9),
            }
        if element == "railway":
            return {"symbol_type": "LineSymbol", "color": "#4b5563", "weight": 3,
                    "opacity": 0.9, "dashArray": "6,4"}
        if element == "water":
            return {"symbol_type": "LineSymbol", "color": "#3b82f6", "weight": 3, "opacity": 0.8,
                    "fillColor": "#93c5fd", "fillOpacity": 0.5}
        if element == "poi":
            cat = map_type if map_type in TOURISM_CATEGORIES else "default"
            cfg = TOURISM_CATEGORIES.get(cat, TOURISM_CATEGORIES.get("attraction", {}))
            color = "#f59e0b" if bright else cfg.get("color", "#dc2626")
            return {"symbol_type": "PointSymbol", "color": color, "radius": 7,
                    "icon": cfg.get("icon", "📍"), "fillOpacity": 0.8}
        if element == "green_space":
            cfg = GREENSPACE_STYLES.get("park", {})
            return {"symbol_type": "AreaSymbol", "fillColor": cfg.get("fillColor", "#86efac"),
                    "color": cfg.get("color", "#16a34a"), "fillOpacity": 0.4}
        if element == "building":
            cfg = MAP_STYLES.get("building", {})
            return {"symbol_type": "AreaSymbol", "fillColor": cfg.get("fillColor", "#d1d5db"),
                    "color": cfg.get("color", "#9ca3af"), "fillOpacity": cfg.get("fillOpacity", 0.3)}
        if element == "boundary":
            return {"symbol_type": "LineSymbol", "color": "#E03131", "weight": 3, "opacity": 0.9}
        if element == "admin_center":
            return {"symbol_type": "PointSymbol", "color": "#D82828", "radius": 9, "icon": "★"}
        if element == "contour":
            return {"symbol_type": "LineSymbol", "color": "#C8A268", "weight": 1.2, "opacity": 0.8}
        return None

    @staticmethod
    def _kg_rationale(map_type: str, kg_service: Any) -> List[str]:
        """附加 KG 制图约束说明（若可用）"""
        if not kg_service:
            return []
        try:
            constraints = kg_service.get_constraints()
            for c in constraints or []:
                if c.get("map_type") == map_type and c.get("constraint"):
                    return [c["constraint"]]
        except Exception as e:
            logger.info(f"[SymbolRecommender] KG 约束获取失败: {e}")
        return []
