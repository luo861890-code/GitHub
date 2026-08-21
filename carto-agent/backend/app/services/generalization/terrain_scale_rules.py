# -*- coding: utf-8 -*-
"""地势图动态等高距：contour_interval = f(scale, DEM resolution, terrain relief)

确定性规则（不引入 AI）：
  等高距 = 图上 1mm 折算实地米数，按地形起伏调整，取整到 DEM 可表达的 20m 倍数。
  武汉 DEM resolution=30m、等高线间隔 20m，故可用等高距为 20m 的整数倍。
"""
from typing import List, Tuple


def contour_interval(scale: int, resolution_m: float, relief_m: float) -> int:
    """确定性等高距（米）：按比例尺基础档位，地形起伏放大，取整到 20m 倍数。

    基础等高距（图上 0.2mm）：
      1:500K → 100m，1:250K → 40m，1:100K → 20m
    起伏放大：relief 越大等高距越大，但封顶 100m（避免武汉低起伏被放大成高山错觉）。
    """
    base_by_scale = {500_000: 100, 250_000: 40, 100_000: 20}
    base = base_by_scale.get(scale, 20)
    # relief 用分位数（调用方传入的 relief_m 已是整体起伏，这里做放大）
    if relief_m > 500:
        base = min(100, base * 2)
    elif relief_m > 200:
        base = min(100, round(base * 1.5 / 20) * 20)
    # 取整到 20m 倍数，最小 20m
    interval = max(20, int(round(base / 20.0)) * 20)
    return interval


def select_contours(
    elevations: List[float],
    interval: int,
) -> Tuple[List[float], List[float], str]:
    """按等高距选取：保留 elevation % interval == 0，删除其余，返回 (kept, removed, reason)"""
    kept = [e for e in elevations if abs(e) % interval < 1e-9]
    removed = [e for e in elevations if abs(e) % interval >= 1e-9]
    reason = (
        f"等高距 {interval}m：保留 {len(kept)} 条、删除 {len(removed)} 条"
        f"（DEM 30m / 起伏 {round(max(elevations) - min(elevations), 0) if elevations else 0}m）"
    )
    return kept, removed, reason
