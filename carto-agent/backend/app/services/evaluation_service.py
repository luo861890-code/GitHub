"""实证驱动评估系统（申报书：任务完成率 / 端到端延迟 / 规范性 5 分制 / 场景分组）

对应"实证驱动"技术路线与验证系统流程图：自动化收集智能体任务指标，
支持定量评估（任务完成率、端到端延迟）与规范性评估（5 分制，基于 QA 报告），
并按基础/核心（武大樱花）/压力（复杂模糊）三场景分组统计，供迭代闭环定位问题。
"""
import json
import os
import statistics
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.utils.logger import get_logger
logger = get_logger(__name__)
from app.utils.helpers import ensure_dir


class EvaluationService:
    """智能体任务评估服务：记录 + 聚合统计"""

    # 场景分类关键词（对应申报书三场景验证：基础/核心/压力）
    _SCENE_RULES = [
        ("压力(复杂模糊)", ["复杂", "模糊", "任意", "多要素", "全部要素", "多个", "压力", "同时", "尽量"]),
        ("核心(武大樱花)", ["樱花", "武大", "武汉大学"]),
    ]
    # 制图任务关键词（用于从对话中区分任务类请求与纯问答）
    _TASK_KEYWORDS = ["地图", "制图", "画", "生成", "制作", "修改", "图", "标注", "图层",
                      "渲染", "样式", "配色", "主题", "shp", "导出", "樱花", "行政区", "交通", "旅游"]

    def __init__(self, data_dir: str):
        self.records_path = os.path.join(data_dir, "evaluation", "records.json")
        self.records: List[Dict[str, Any]] = self._load()
        logger.info(f"[EvaluationService] 初始化完成，历史任务记录 {len(self.records)} 条")

    def _load(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self.records_path):
                with open(self.records_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"[EvaluationService] 加载历史记录失败: {e}")
        return []

    def _save(self) -> None:
        try:
            ensure_dir(os.path.dirname(self.records_path))
            # 最多保留 500 条，防止无限膨胀
            with open(self.records_path, "w", encoding="utf-8") as f:
                json.dump(self.records[-500:], f, ensure_ascii=False, indent=1)
        except Exception as e:
            logger.warning(f"[EvaluationService] 保存评估记录失败: {e}")

    @staticmethod
    def classify_scene(message: str, map_type: Optional[str] = None) -> str:
        """按申报书三场景分类：基础 / 核心（武大樱花）/ 压力（复杂模糊）"""
        for scene, kws in EvaluationService._SCENE_RULES:
            if any(k in message for k in kws):
                return scene
        if map_type in ("core", "cherry", "樱花"):
            return "核心(武大樱花)"
        return "基础"

    @staticmethod
    def is_task_request(message: str, map_id: Optional[str]) -> bool:
        """是否为制图任务类请求（区别于纯问答）"""
        if map_id:
            return True
        return any(k in message for k in EvaluationService._TASK_KEYWORDS)

    def record(
        self,
        message: str,
        success: bool,
        latency_ms: float,
        map_id: Optional[str] = None,
        map_name: Optional[str] = None,
        map_type: Optional[str] = None,
    ) -> None:
        """记录单次任务评估数据（由 chat 层埋点调用）"""
        rec = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": (message or "")[:200],
            "success": bool(success),
            "latency_ms": round(latency_ms, 1),
            "map_id": map_id,
            "map_name": map_name,
            "map_type": map_type,
            "scene": self.classify_scene(message or "", map_type),
            "is_task": self.is_task_request(message or "", map_id),
        }
        self.records.append(rec)
        self._save()

    @staticmethod
    def _median(vals: List[float]) -> float:
        if not vals:
            return 0.0
        return round(statistics.median(vals), 1)

    # 异常值阈值：单次任务耗时 > 10 分钟视为异常（OSM 网络卡死/长重试导致），
    # 计入 max/审计字段，但剔除出 avg/median，避免单条异常记录拉爆"平均延迟"核心指标
    _LATENCY_OUTLIER_MS = 600_000

    @staticmethod
    def _normal_latencies(lat: List[float]) -> tuple:
        normal = [v for v in lat if v <= EvaluationService._LATENCY_OUTLIER_MS]
        if not normal:
            normal = lat  # 全部异常时退回全量，避免空均值
        return normal, len(lat) - len(normal)

    def stats(self, normativity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """聚合统计：完成率 / 端到端延迟 / 规范性 5 分制 / 场景分组 / 趋势"""
        n = len(self.records)
        if n == 0:
            return {
                "total_tasks": 0, "task_tasks": 0,
                "success_rate": None, "task_success_rate": None,
                "avg_latency_ms": None, "max_latency_ms": None, "median_latency_ms": None,
                "by_scene": {}, "recent_trend": [], "normativity": normativity,
                "records_sample": [],
            }

        all_lat = [r["latency_ms"] for r in self.records]
        success_n = sum(1 for r in self.records if r["success"])
        # 剔除超长异常值（OSM 卡死/长重试导致），max 保留原始最值，avg/median 用稳健数据
        normal_lat, outlier_n = self._normal_latencies(all_lat)

        # 任务类请求（制图/修改，排除纯问答）
        tasks = [r for r in self.records if r.get("is_task")]
        task_lat = [r["latency_ms"] for r in tasks]
        task_normal, _ = self._normal_latencies(task_lat)
        task_success = sum(1 for r in tasks if r["success"])

        # 场景分组
        by_scene: Dict[str, Dict[str, Any]] = {}
        for r in self.records:
            s = by_scene.setdefault(r.get("scene", "基础"), {
                "total": 0, "success": 0, "avg_latency_ms": 0.0, "latencies": [],
            })
            s["total"] += 1
            s["success"] += 1 if r["success"] else 0
            s["latencies"].append(r["latency_ms"])
        for s in by_scene.values():
            s_normal, _ = self._normal_latencies(s["latencies"])
            s["avg_latency_ms"] = round(statistics.mean(s_normal), 1) if s_normal else 0.0
            s["success_rate"] = round(s["success"] / s["total"], 4) if s["total"] else None
            s.pop("latencies", None)

        # 近 10 条延迟趋势
        recent = self.records[-10:]
        recent_trend = [{
            "ts": r["ts"], "latency_ms": r["latency_ms"], "success": r["success"],
            "scene": r.get("scene"), "message": (r.get("message") or "")[:40],
        } for r in recent]

        return {
            "total_tasks": n,
            "task_tasks": len(tasks),
            "success_rate": round(success_n / n, 4),
            "task_success_rate": round(task_success / len(tasks), 4) if tasks else None,
            "avg_latency_ms": round(statistics.mean(normal_lat), 1),
            "max_latency_ms": max(all_lat),
            "median_latency_ms": self._median(normal_lat),
            "task_avg_latency_ms": round(statistics.mean(task_normal), 1) if task_normal else None,
            "outlier_count": outlier_n,  # 超时异常任务数（已剔除出平均/中位，max 仍含）
            "by_scene": by_scene,
            "recent_trend": recent_trend,
            "normativity": normativity,  # 规范性 5 分制（由调用方基于 QA 报告传入）
        }
