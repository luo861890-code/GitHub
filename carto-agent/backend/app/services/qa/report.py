# -*- coding: utf-8 -*-
"""验收报告输出：JSON 结构 + 文本模板（规范 §三十）"""
from typing import Any, Dict


def to_text(report: Dict[str, Any]) -> str:
    """生成人类可读的验收报告文本（规范模板）"""
    lines = [
        "=" * 60,
        "CartoAgent Map Quality Assessment",
        f"{report.get('map_name', '未命名地图')}（{report.get('map_type', '')}）",
        "=" * 60,
        f"总体得分：{report.get('total_score', 0)} / 1000",
        f"等级：{report.get('grade', '')}",
        f"状态：{report.get('status', '')}",
        "",
    ]
    for dim, cfg in (report.get("dimensions") or {}).items():
        lines.append(f"{cfg['name']:<18} {cfg['score']:>4} / {cfg['max']}")
    lines += [
        "",
        f"Critical：{report.get('critical_errors', 0)}",
        f"Major：{report.get('major_errors', 0)}",
        f"Minor：{report.get('minor_errors', 0)}",
    ]
    issues = report.get("issues") or {}
    all_issues = (
        [f"C0 {i}" for i in issues.get("critical", [])]
        + [f"C1 {i}" for i in issues.get("major", [])]
        + [f"C2 {i}" for i in issues.get("minor", [])]
    )
    if all_issues:
        lines += ["", "主要问题："]
        lines += [f"{i + 1}. {txt}" for i, txt in enumerate(all_issues[:12])]
    if report.get("missing_features"):
        lines += ["", "缺失要素："]
        lines += [f"- {m}" for m in report["missing_features"]]
    if report.get("priority"):
        lines += ["", "修改优先级："]
        lines += [f"{i + 1}. {p}" for i, p in enumerate(report["priority"][:8])]
    lines += ["", "=" * 60]
    return "\n".join(lines)
