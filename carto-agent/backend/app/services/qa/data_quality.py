# -*- coding: utf-8 -*-
"""A. 地理数据质量（200 分）：位置精度/属性精度/几何质量/完整性/元数据"""
from typing import Any, Dict, List, Tuple

from .metrics import WUHAN_DISTRICT_COUNT, WUHAN_DISTRICTS, point_in_bbox, valid_pt


class DataQuality:
    """A 项：地理数据质量 200 分"""

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        layers = map_data.get("layers", [])
        meta = map_data.get("metadata") or {}
        detail: List[str] = []
        total = 0

        # ---- A1 位置精度 50：非法坐标 + CRS 缺失 ----
        invalid = 0
        total_pts = 0
        for l in layers:
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                    total_pts += 1
                    if not valid_pt(c):
                        invalid += 1
        position = 50
        if total_pts:
            rate = invalid / total_pts
            position = max(0, round(50 * (1 - rate * 5)))
            if rate > 0.01:
                issues["C1"].append(f"A1 位置精度：{invalid}/{total_pts} 个非法坐标")
        else:
            position = 0
            issues["C1"].append("A1 位置精度：无可解析坐标")
        # CRS 缺失 → Critical（规范 A1 自动规则）
        if not (meta.get("坐标系") or meta.get("投影")):
            issues["C0"].append("A1 位置精度：CRS 缺失（致命错误）")
        total += position

        # ---- A2 属性精度 40：按要素类型检查名称/等级/高程 ----
        attr = self._attribute_score(map_data, issues)
        total += attr

        # ---- A3 几何质量 30：自相交/重复几何（简化检测） ----
        geo, geo_issues = self._geometry_score(layers)
        total += geo
        for i in geo_issues:
            issues["C1"].append(f"A3 几何质量：{i}")

        # ---- A4 完整性 40：空图层 + 行政期望 ----
        complete = self._completeness_score(map_data, issues)
        total += complete

        # ---- A5 元数据 20：来源/坐标系/时间/许可 ----
        meta_score = 0
        if meta.get("数据来源") or meta.get("资料来源"):
            meta_score += 6
        if meta.get("坐标系") or meta.get("投影"):
            meta_score += 6
        if meta.get("出版日期") or meta.get("制图时间") or meta.get("资料截止"):
            meta_score += 4
        if meta.get("审图号") or meta.get("版权"):
            meta_score += 4
        else:
            issues["C2"].append("A5 元数据：缺少许可/审图信息")
        total += meta_score

        detail.append(f"A1位置 {position}/50 · A2属性 {attr}/40 · A3几何 {geo}/30 · "
                      f"A4完整 {complete}/40 · A5元数据 {meta_score}/20")
        return min(total, 200), detail

    def _attribute_score(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> int:
        """属性精度：名称缺失率 + 类型相关属性"""
        layers = map_data.get("layers", [])
        total_feats = 0
        no_name = 0
        for l in layers:
            props = l.get("properties") or []
            if not props:
                continue
            total_feats += len(props)
            no_name += sum(1 for p in props if not (p.get("name") or ""))
        if total_feats == 0:
            return 20
        missing_rate = no_name / total_feats
        attr = max(0, round(40 * (1 - missing_rate * 3)))
        if missing_rate > 0.1:
            issues["C1"].append(f"A2 属性精度：{no_name}/{total_feats} 个要素缺少名称")
        return attr

    def _geometry_score(self, layers: List[Dict]) -> Tuple[int, List[str]]:
        seen = set()
        dup = 0
        for l in layers:
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and c and isinstance(c[0], (int, float)):
                    key = repr([round(float(x), 6) for x in c[:2]])
                    if key in seen:
                        dup += 1
                    else:
                        seen.add(key)
        score = max(0, 30 - 5 * dup)
        return score, ([f"{dup} 组重复点坐标"] if dup else [])

    def _completeness_score(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> int:
        layers = map_data.get("layers", [])
        empty = [l.get("name", "未命名") for l in layers
                 if not (l.get("coordinates") or l.get("features"))]
        score = 40 if not empty else max(0, 40 - 8 * len(empty))
        if empty:
            issues["C1"].append(f"A4 完整性：{len(empty)} 个空图层 {empty[:3]}")
        # 行政图区县唯一名核对（遗漏/多余）
        if map_data.get("map_type") == "administrative":
            district = next((l for l in layers if l.get("name") == "区县政区"), None)
            if district:
                names = {(f.get("properties") or {}).get("name", "")
                         for f in (district.get("features") or []) if (f.get("properties") or {}).get("name")}
                extra = names - WUHAN_DISTRICTS
                miss = WUHAN_DISTRICTS - names
                if extra or miss:
                    issues["C0"].append(
                        f"A4 完整性：行政区事实错误（多余 {sorted(extra)[:3]}，缺失 {sorted(miss)[:3]}）"
                    )
                    score = min(score, 10)
                elif len(names) == WUHAN_DISTRICT_COUNT:
                    score = 40
        return score
