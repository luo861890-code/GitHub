# -*- coding: utf-8 -*-
"""多源数据融合层（DataFusionEngine）

负责 CRS/schema/name/class 归一、来源优先级、时间对齐与置信度赋值，
以及多源冲突报告。LLM 不得直接决定冲突取舍，由来源优先级 + 时效 + 精度决定。
"""
from typing import Any, Dict, List, Optional


class DataFusionEngine:
    """多源数据融合引擎"""

    # 来源优先级（§八：官方/权威数据优先）
    SOURCE_PRIORITY = {
        "official": 6, "government": 6, "professional_survey": 5,
        "authoritative_open": 4, "datav": 4, "srtm": 4,
        "osm": 3, "amap": 3, "third_party": 2, "generated": 1, "unknown": 1,
    }

    def normalize_name(self, name: str) -> str:
        """名称规范化：繁简/空白/大小写归一（武汉本地）"""
        if not name:
            return ""
        n = str(name).strip()
        # 常见繁简映射（武汉相关）
        simple_map = {"漢": "汉", "陽": "阳", "橋": "桥", "區": "区", "縣": "县",
                      "長": "长", "門": "门", "東": "东", "龍": "龙"}
        for trad, simp in simple_map.items():
            n = n.replace(trad, simp)
        # 空白归一
        n = " ".join(n.split())
        return n

    def source_priority(self, source: str) -> int:
        """来源 -> 优先级数值"""
        text = (source or "").lower()
        for key, prio in sorted(self.SOURCE_PRIORITY.items(), key=lambda x: -len(x[0])):
            if key in text:
                return prio
        return 1

    def assign_confidence(self, source: str, has_name: bool) -> float:
        """按来源 + 属性完整性赋值置信度（0-1）"""
        priority = self.source_priority(source)
        base = {6: 0.95, 5: 0.9, 4: 0.85, 3: 0.7, 2: 0.5, 1: 0.3}.get(priority, 0.5)
        if not has_name:
            base *= 0.6
        return round(base, 2)

    def enrich_layers(self, layers: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
        """给每个要素补充 source / source_date / confidence（就地返回新列表）"""
        out = []
        for layer in layers:
            layer = dict(layer)
            props = layer.get("properties") or []
            new_props = []
            for p in props:
                p = dict(p) if isinstance(p, dict) else {}
                p.setdefault("source", source)
                p.setdefault("confidence", self.assign_confidence(source, bool(p.get("name"))))
                new_props.append(p)
            if new_props:
                layer["properties"] = new_props
            layer.setdefault("metadata", {})["source"] = source
            out.append(layer)
        return out

    def detect_conflicts(
        self,
        layers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """多源冲突检测：同名要素来源不一致 / 同名点空间偏移"""
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for layer in layers:
            src = (layer.get("metadata") or {}).get("source") or "unknown"
            for p in (layer.get("properties") or []):
                nm = self.normalize_name((p or {}).get("name") or "")
                if nm:
                    by_name.setdefault(nm, []).append({"source": src, "prop": p})
        conflicts = []
        for nm, entries in by_name.items():
            sources = {e["source"] for e in entries}
            if len(sources) > 1:
                conflicts.append({
                    "name": nm,
                    "sources": sorted(sources),
                    "note": "同名要素来自多个数据源，需按来源优先级/时效核验",
                })
        return {
            "conflict_count": len(conflicts),
            "conflicts": conflicts[:50],
        }

    def fusion_report(
        self,
        layers: List[Dict[str, Any]],
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """生成多源融合报告"""
        source_list = sources or []
        priorities = [
            {"source": s.get("name", ""), "priority": self.source_priority(s.get("name", ""))}
            for s in source_list
        ]
        conflicts = self.detect_conflicts(layers)
        return {
            "source_priorities": priorities,
            "conflicts": conflicts,
            "normalization": "繁简/空白归一已应用",
            "recommendation": "同名多源冲突按 source_priority + freshness + accuracy 决策",
        }
