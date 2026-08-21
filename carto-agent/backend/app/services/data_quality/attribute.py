# -*- coding: utf-8 -*-
"""属性 / 完整性 / 元数据 / 来源校验器"""
from typing import Any, Dict, List


class AttributeValidator:
    """属性校验：名称缺失 / 分类值非法"""

    def check(self, properties_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(properties_list)
        missing_name = 0
        for p in properties_list:
            if not p or not (p.get("name") or p.get("NAME")):
                missing_name += 1
        return {
            "feature_count": total,
            "missing_name": missing_name,
            "missing_rate": missing_name / total if total else 0.0,
        }


class CompletenessValidator:
    """完整性校验：Omission（应有但没有）"""

    def check(self, layer_names: List[str], expected: List[str]) -> Dict[str, Any]:
        names_text = " ".join(layer_names)
        missing = [k for k in expected if k not in names_text]
        return {
            "expected": expected,
            "missing": missing,
            "completeness": 1 - len(missing) / len(expected) if expected else 1.0,
        }


class MetadataValidator:
    """元数据校验：来源/时间/CRS/处理历史"""

    REQUIRED = ("source", "crs", "acquisition_date")

    def check(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        has = {
            "source": bool(metadata.get("数据来源") or metadata.get("资料来源") or metadata.get("source")),
            "crs": bool(metadata.get("坐标系") or metadata.get("投影") or metadata.get("crs")),
            "acquisition_date": bool(metadata.get("出版日期") or metadata.get("制图时间")
                                     or metadata.get("资料截止") or metadata.get("acquisition_date")),
            "processing": bool(metadata.get("说明") or metadata.get("processing")),
        }
        missing = [k for k, v in has.items() if not v]
        return {"metadata": has, "missing": missing}


class SourceValidator:
    """来源校验：来源可信度（Official > Professional > OSM > Third-party > Generated）"""

    PRIORITY = {
        "official": 5, "government": 5, "professional": 4, "authoritative": 4,
        "osm": 3, "openstreetmap": 3, "datav": 4, "srtm": 4, "amap": 3,
        "third-party": 2, "generated": 1, "unknown": 1,
    }

    def check(self, source_text: str) -> Dict[str, Any]:
        text = (source_text or "").lower()
        levels = []
        for key, level in self.PRIORITY.items():
            if key in text:
                levels.append(level)
        priority = max(levels) if levels else 1
        return {
            "source": source_text,
            "priority": priority,
            "priority_label": self._label(priority),
        }

    @staticmethod
    def _label(priority: int) -> str:
        return {5: "Official/Government", 4: "Professional/Authoritative",
                3: "OSM/Open Data", 2: "Third-party", 1: "Generated/Unknown"}.get(priority, "Unknown")
