"""QGIS 式图层目录（Layer Catalog）

carto-agent 的图层体系参照 QGIS 图层面板组织：

1. 每个图层都是独立的一行（含注记图层）：河流注记 / 湖泊注记 / 水库注记 /
   道路注记 / 轨道注记 / 山峰注记 / 区县名称标注 / 市级名称标注 / 地标名称 等
   各注记类别都有自己的图层，不再合并进一个笼统的"水系注记"。
2. 图层按主题分组（group），图层面板以分组树形式展示，支持整组显隐。
3. 提供自然语言 → 图层 / 注记类别的解析（别名表），供 LLM 与关键词匹配使用，
   避免出现"找不到'湖泊注记'图层，只能退而求其次改'水系注记'"的情况。
"""
from typing import Dict, List, Optional, Tuple

# ============ 一、标准分组（QGIS 图层树，按绘制顺序自下而上） ============
LAYER_GROUP_ORDER: List[str] = [
    "底图",          # 陆地底图 / 省域 / 周边地市 / DEM晕渲
    "行政区划",      # 区县政区 / 区县界 / 市界 / 省界 / 行政中心
    "水系",          # 大江大河 / 主要河流 / 支流溪流 / 河流水面 / 湖泊 / 水库 / 河流中心线
    "居民地",        # 居民地街区
    "地形地貌",      # 等高线 / 山峰 / 山体阴影
    "道路",          # 道路-*
    "轨道交通",      # 铁路 / 轨道 / 地铁 / 轻轨
    "注记",          # 各注记图层（河流注记/湖泊注记/道路注记/山峰注记/政区名称标注…）
    "POI/符号",      # 景点 / 重点地标 / 汇入口 / 河源 / 公交站 …
    "其他",
]

# 注记图层统一分组（QGIS 中注记通常是独立图层，可单独显隐/改样式）
ANNOTATION_GROUP = "注记"

# ============ 二、注记图层定义 ============
# 每个注记类别 → (规范图层名, 别名列表, 要素类型 feature_type)
# feature_type 取值与 label_spec 一致：admin / water / transport / poi / peak
ANNOTATION_LAYERS: Dict[str, dict] = {
    "湖泊注记": {
        "name": "湖泊注记",
        "aliases": ["湖泊注记", "湖注记", "湖泊名", "湖名", "湖泊标注", "lake annotation"],
        "feature_type": "water",
        "category": "lake",
    },
    "河流注记": {
        "name": "河流注记",
        "aliases": ["河流注记", "河注记", "河流名", "江名", "河道注记", "river annotation"],
        "feature_type": "water",
        "category": "river",
    },
    "水库注记": {
        "name": "水库注记",
        "aliases": ["水库注记", "库名", "reservoir annotation"],
        "feature_type": "water",
        "category": "reservoir",
    },
    "水系注记": {  # 兼容层：合并水系注记（旧数据/兜底）
        "name": "水系注记",
        "aliases": ["水系注记", "水体注记", "water annotation"],
        "feature_type": "water",
        "category": "water",
    },
    "道路注记": {
        "name": "道路注记",
        "aliases": ["道路注记", "路名注记", "路名", "道路名", "road annotation", "街道名"],
        "feature_type": "transport",
        "category": "road",
    },
    "轨道注记": {
        "name": "轨道注记",
        "aliases": ["轨道注记", "铁路注记", "地铁注记", "轻轨注记", "rail annotation"],
        "feature_type": "transport",
        "category": "rail",
    },
    "山峰注记": {
        "name": "山峰注记",
        "aliases": ["山峰注记", "山名注记", "高程注记", "peak annotation"],
        "feature_type": "peak",
        "category": "peak",
    },
    "区县名称标注": {
        "name": "区县名称标注",
        "aliases": ["区县名称标注", "区县注记", "区名标注", "区名注记", "district label"],
        "feature_type": "admin",
        "category": "admin",
    },
    "市级名称标注": {
        "name": "市级名称标注",
        "aliases": ["市级名称标注", "市名标注", "市名注记", "city label"],
        "feature_type": "admin",
        "category": "admin",
    },
    "地标名称": {
        "name": "地标名称",
        "aliases": ["地标名称", "地标注记", "景点名称", "landmark label"],
        "feature_type": "poi",
        "category": "landmark",
    },
}

# 关键词类别 → 应优先命中的注记图层名（用于"改注记"意图解析）
# 例：用户说"把湖泊注记改成竖排" → 优先找"湖泊注记"图层。
# 由 ANNOTATION_LAYERS 的别名自动生成，长词优先（先匹配"湖泊注记"再匹配"湖名"）。
ANNOTATION_KEYWORD_TARGETS: List[Tuple[str, str]] = []
for _ann_cfg in ANNOTATION_LAYERS.values():
    for _alias in _ann_cfg["aliases"]:
        ANNOTATION_KEYWORD_TARGETS.append((_alias, _ann_cfg["name"]))
# 补充跨类别别名（旧图层命名兼容）
ANNOTATION_KEYWORD_TARGETS += [
    ("区县注记", "区县名称标注"),
    ("市级注记", "市级名称标注"),
    ("地标注记", "地标名称"),
    ("水体注记", "水系注记"),
    ("铁路注记", "轨道注记"),
]
ANNOTATION_KEYWORD_TARGETS.sort(key=lambda _t: -len(_t[0]))


def annotation_category(layer_name: str) -> Optional[str]:
    """从图层名推断注记类别（lake/river/reservoir/road/rail/peak/admin/landmark/water）。"""
    if not layer_name:
        return None
    for cfg in ANNOTATION_LAYERS.values():
        if cfg["name"] in layer_name:
            return cfg["category"]
    return None


def annotation_feature_type(layer_name: str) -> Optional[str]:
    """从图层名推断注记要素类型（water/transport/admin/poi/peak）。"""
    if not layer_name:
        return None
    for cfg in ANNOTATION_LAYERS.values():
        if cfg["name"] in layer_name:
            return cfg["feature_type"]
    return None


def is_annotation_layer(layer: dict) -> bool:
    """图层是否为注记图层（类型 textLabel/label 或名称含注记/标注）。"""
    ltype = (layer.get("type") or "").lower()
    name = layer.get("name") or ""
    if ltype in ("textlabel", "label", "text"):
        return True
    return ("注记" in name) or ("标注" in name)


def resolve_annotation_target(text: str) -> Optional[str]:
    """把自然语言中的注记类别词解析为规范图层名。

    例：
      "湖泊注记" -> "湖泊注记"
      "湖注记"   -> "湖泊注记"
      "道路名"   -> "道路注记"
    未命中返回 None。
    """
    if not text:
        return None
    # 精确包含匹配优先
    for kw, target in ANNOTATION_KEYWORD_TARGETS:
        if kw in text:
            return target
    return None


# ============ 三、要素图层分组判定 ============
# 与 map_service._classify_layer_group 对齐，但更完整、更 QGIS 化
_GROUP_RULES: List[Tuple[str, List[str]]] = [
    ("底图", ["陆地底图", "湖北省域", "周边地市", "市域底图", "省域", "晕渲", "山体阴影"]),
    ("行政区划", ["区县政区", "区县界", "市界", "省界", "境界", "边界", "行政中心", "乡镇界", "乡镇边界"]),
    ("水系", ["大江", "河流", "水系", "河道", "支流", "溪流", "水面", "中心线", "运河",
              "水涯", "湖岸", "湖泊", "湖面", "湖体", "水库", "水体符号"]),
    ("居民地", ["居民地", "居民区", "建成区", "街区", "住宅区"]),
    ("地形地貌", ["等高线", "山峰", "山体", "地貌", "计曲线", "首曲线"]),
    ("道路", ["道路", "高速", "公路", "国道", "省道", "干道", "主干道", "次干道", "支路",
              "匝道", "环线", "街巷", "街道", "连接线"]),
    ("轨道交通", ["铁路", "轨道", "地铁", "轻轨", "高铁", "城际"]),
    ("桥梁", ["桥梁", "大桥", "立交", "天桥"]),
    ("交通枢纽", ["枢纽", "机场", "车站", "火车站", "公交", "码头", "客运站"]),
    ("POI/符号", ["景点", "旅游", "公园", "博物馆", "文化", "历史", "宗教", "自然",
                  "地标", "名胜", "古迹", "美食", "餐厅", "酒店", "学校", "大学", "医院",
                  "商业", "商场", "汇入口", "河源", "公交站", "POI", "兴趣点", "重点"]),
]


def layer_group(layer: dict) -> str:
    """QGIS 式图层分组：给任意图层返回其所属分组名。

    注记图层（textLabel/label 或名称含注记/标注）统一归入"注记"组；
    其余按名称关键词判定，保证同一类要素（含其注记）分层清晰。
    """
    name = layer.get("name") or ""
    ltype = (layer.get("type") or "").lower()
    if is_annotation_layer(layer):
        return ANNOTATION_GROUP
    for group, kws in _GROUP_RULES:
        if any(k in name for k in kws):
            return group
    # 点状符号兜底
    if ltype in ("circlemarker", "marker", "point", "circle"):
        return "POI/符号"
    return "其他"


# ============ 四、标准注记图层样式（与 label_spec 一致的默认值） ============
ANNOTATION_STYLE_DEFAULTS: Dict[str, dict] = {
    "湖泊注记": {"color": "#2E6FA3", "fontSize": 12, "weight": 2, "font": "song"},
    "河流注记": {"color": "#2E6FA3", "fontSize": 12, "weight": 2, "font": "song", "italic": True},
    "水库注记": {"color": "#2E6FA3", "fontSize": 11, "weight": 2, "font": "song"},
    "水系注记": {"color": "#1e3a8a", "fontSize": 12, "weight": 2, "font": "song"},
    "道路注记": {"color": "#374151", "fontSize": 11, "weight": 2, "font": "song"},
    "轨道注记": {"color": "#6b21a8", "fontSize": 11, "weight": 2, "font": "song"},
    "山峰注记": {"color": "#7A5230", "fontSize": 11, "weight": 2, "font": "song"},
    "区县名称标注": {"color": "#1F2937", "fontSize": 15, "weight": 3, "font": "song"},
    "市级名称标注": {"color": "#1F2937", "fontSize": 22, "weight": 4, "font": "song"},
    "地标名称": {"color": "#0f3d91", "fontSize": 13, "weight": 3, "font": "bold"},
}


def annotation_style_default(layer_name: str) -> dict:
    """注记图层默认样式（缺失时给一个安全兜底）。"""
    for name, style in ANNOTATION_STYLE_DEFAULTS.items():
        if name in layer_name:
            return dict(style)
    return {"color": "#1a1a1a", "fontSize": 12, "weight": 2, "font": "song"}


def split_water_labels(labels: List[dict]) -> Dict[str, List[dict]]:
    """把合并的水系注记列表拆分为 河流/湖泊/水库 三类。

    判定规则：
      - 名称以 江/河/渠/港/溪/河 结尾 → 河流注记
      - 名称含 水库/坝 → 水库注记
      - 名称含 湖/泊/池/塘/荡/淀/泽 → 湖泊注记
      - 带 area_km2 的注记（面状水体）→ 湖泊注记
    返回 {"river": [...], "lake": [...], "reservoir": [...], "other": [...]}
    """
    out: Dict[str, List[dict]] = {"river": [], "lake": [], "reservoir": [], "other": []}
    for lb in labels:
        name = (lb.get("name") or "") if isinstance(lb, dict) else ""
        if not name:
            # 无名面状水体（带面积）按湖泊处理；其余归"其他"
            if lb.get("area_km2") is not None:
                out["lake"].append(lb)
            else:
                out["other"].append(lb)
            continue
        if any(k in name for k in ("水库", "坝")):
            out["reservoir"].append(lb)
        elif name.endswith(("江", "河", "渠", "港", "溪", "川", "水")) or "河流" in name:
            out["river"].append(lb)
        elif any(k in name for k in ("湖", "泊", "池", "塘", "荡", "淀", "泽", "漾")):
            out["lake"].append(lb)
        elif lb.get("area_km2") is not None:
            out["lake"].append(lb)
        else:
            out["other"].append(lb)
    return out
