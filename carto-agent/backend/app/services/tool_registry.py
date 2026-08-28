"""制图工具注册中心 - 标准化工具接口，实现"工具层"的统一管理

在"知识-数据-工具"三元体系中，工具层需要将KG推理结果
映射为具体的工具调用。ToolRegistry 提供了这一映射能力，
实现了从制图决策到工具执行的完整闭环。

核心设计：
- BaseTool: 标准化工具接口，所有工具必须实现
- ToolDefinition: 工具元数据描述（名称、分类、输入输出schema、KG触发规则）
- ToolRegistry: 运行时工具注册与调度中心
"""
from abc import ABC, abstractmethod
from app.utils.logger import get_logger
logger = get_logger(__name__)
from typing import Dict, Any, List, Optional, Callable, Type
import time
from dataclasses import dataclass, field


# ======================== 工具定义 ========================

@dataclass
class ToolDefinition:
    """工具定义 - 描述一个制图工具的完整元数据

    Attributes:
        name: 工具唯一名称（如 "osm_fetch"）
        description: 工具功能描述（供LLM理解用途）
        category: 工具分类: data / rendering / analysis / export
        input_schema: JSON Schema 格式的输入参数定义
        output_schema: JSON Schema 格式的输出结果定义
        preconditions: 前置条件（执行前必须满足，如 "geometry_valid=true"）
        postconditions: 后置条件（执行后应满足，如 "feature_count_same_or_lower=true"）
        cost: 成本估算（low/medium/high 或 token 估算）
        destructive: 是否可能破坏数据（删除/覆盖）
        retryable: 是否可安全重试（幂等）
        provenance: 是否记录来源（数据来源/调用记录，供可追溯性）
        kg_trigger_rules: KG推理触发规则列表，每条规则含
            {relation_type, source_label, target_label}，
            当KG推理结果匹配规则时自动激活该工具
        keywords: 触发关键词列表，用于意图匹配的辅助手段
    """
    name: str
    description: str
    category: str  # data / rendering / analysis / export
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    # ---- 工具契约（研究基线版 §15-16） ----
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    cost: str = "low"
    destructive: bool = False
    retryable: bool = True
    provenance: bool = True
    kg_trigger_rules: List[Dict[str, str]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def contract(self) -> Dict[str, Any]:
        """输出完整工具契约（供 Agent Trace / 工具选择评估）"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "cost": self.cost,
            "destructive": self.destructive,
            "retryable": self.retryable,
            "provenance": self.provenance,
            "kg_trigger_rules": self.kg_trigger_rules,
            "keywords": self.keywords,
        }


# ======================== 工具基类 ========================

class BaseTool(ABC):
    """标准化工具基类

    所有制图工具必须继承此类并实现 definition 属性和 execute 方法。
    提供 LangChain 兼容转换、执行结果标准化等通用能力。

    使用方式：
        class MyTool(BaseTool):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(...)

            def execute(self, **kwargs) -> Dict[str, Any]:
                ...
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回工具定义

        Returns:
            ToolDefinition 实例，包含工具的完整元数据
        """
        ...

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回标准化结果

        Args:
            **kwargs: 工具执行参数，由调用方提供

        Returns:
            标准化结果字典，至少包含:
            {
                "success": bool,
                "tool_name": str,
                "result": Any,
                "error": Optional[str],
            }
        """
        ...

    def to_langchain_tool(self):
        """转换为 LangChain 兼容工具

        将 BaseTool 封装为 LangChain 的 Tool 对象，
        使其可在 LangChain Agent 中直接使用。

        Returns:
            LangChain Tool 实例，如果 langchain 未安装则返回 None

        Note:
            此方法为可选能力，仅当环境中安装了 langchain 库时可用。
            未安装时打印警告并返回 None。
        """
        try:
            from langchain.tools import Tool as LangChainTool
        except ImportError:
            logger.info(f"[BaseTool] 未安装 langchain，无法转换为 LangChain Tool")
            return None

        def _run_wrapper(input_str: str) -> str:
            """LangChain 字符串输入包装器"""
            import json
            try:
                params = json.loads(input_str) if input_str else {}
            except json.JSONDecodeError:
                params = {"query": input_str}
            result = self.execute(**params)
            return json.dumps(result, ensure_ascii=False)

        return LangChainTool(
            name=self.definition.name,
            description=self.definition.description,
            func=_run_wrapper,
        )

    def _success_result(self, data: Any) -> Dict[str, Any]:
        """构建标准化成功结果"""
        return {
            "success": True,
            "tool_name": self.definition.name,
            "result": data,
            "error": None,
        }

    def _error_result(self, error_msg: str) -> Dict[str, Any]:
        """构建标准化错误结果"""
        return {
            "success": False,
            "tool_name": self.definition.name,
            "result": None,
            "error": error_msg,
        }


# ======================== 具体工具实现 ========================

class OSMFetchTool(BaseTool):
    """OSM数据获取工具

    封装 OSMService 调用，负责从 OpenStreetMap 获取地理要素数据。
    根据KG决策结果按图层类型提取对应的 OSM 标签数据。

    KG触发规则：
    - 当KG决策中包含 layer_configs（图层配置）时自动激活
    - 当KG推理检测到 road_element / waterway_element 等实体时激活
    """

    def __init__(self, osm_service=None):
        """初始化OSM数据获取工具

        Args:
            osm_service: OSMService 实例，提供 fetch_osm_data 等方法
        """
        self._osm_service = osm_service
        self._definition = ToolDefinition(
            name="osm_fetch",
            description="从OpenStreetMap获取指定区域和标签类型的地理要素数据",
            category="data",
            input_schema={
                "type": "object",
                "properties": {
                    "bbox": {
                        "type": "object",
                        "description": "地理范围矩形框 {min_lat, max_lat, min_lon, max_lon}",
                    },
                    "osm_tags": {
                        "type": "string",
                        "description": "OSM标签（如 highway, waterway, railway）",
                    },
                    "layer_name": {
                        "type": "string",
                        "description": "图层名称",
                    },
                },
                "required": ["bbox", "osm_tags"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "coordinates": {"type": "array", "description": "GeoJSON坐标数据"},
                    "element_count": {"type": "integer"},
                },
            },
            preconditions=["bbox_valid=true", "osm_tags_nonempty=true"],
            postconditions=["coordinates_valid=true", "element_count>=0"],
            cost="medium",
            retryable=True,
            provenance=True,
            kg_trigger_rules=[
                {"relation_type": "HAS_DECISION", "source_label": "MapType", "target_label": "CartographicDecision"},
                {"relation_type": "REQUIRES_LAYER", "source_label": "MapType", "target_label": "MapLayer"},
                {"relation_type": "CONTAINS", "source_label": "MapLayer", "target_label": "MapElement"},
            ],
            keywords=["osm", "数据", "获取", "fetch", "download", "下载", "道路", "水系", "建筑"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行OSM数据获取

        Args:
            bbox: 地理范围矩形框
            osm_tags: OSM标签字符串
            layer_name: 图层名称（可选）

        Returns:
            标准化结果，含 coordinates 和 element_count
        """
        bbox = kwargs.get("bbox")
        osm_tags = kwargs.get("osm_tags", "")
        layer_name = kwargs.get("layer_name", "未命名图层")

        if not bbox:
            return self._error_result("缺少 bbox 参数")

        if not self._osm_service:
            return self._error_result("OSMService 不可用")

        try:
            # 调用 OSM 服务获取数据
            osm_data = self._osm_service.fetch_osm_data(
                bbox=bbox,
                osm_tags=osm_tags,
            )
            if not osm_data:
                return self._error_result(f"未获取到OSM数据: tags={osm_tags}")

            coordinates = osm_data.get("coordinates", [])
            return self._success_result({
                "layer_name": layer_name,
                "osm_tags": osm_tags,
                "coordinates": coordinates,
                "element_count": len(coordinates),
                "raw_response": osm_data,
            })
        except Exception as e:
            return self._error_result(f"OSM数据获取失败: {str(e)}")


class StyleConfigTool(BaseTool):
    """样式配置工具

    从KG决策映射到 Leaflet/MapLibre 的具体样式配置。
    将符号方案、配色方案、标注规则转化为地图渲染引擎可识别的样式参数。

    KG触发规则：
    - 当KG决策中包含 symbol_scheme（符号方案）时激活
    - 当KG决策中包含 color_scheme（配色方案）时激活
    - 当KG推理检测到 color_constraint / annotation_rule 时激活
    """

    def __init__(self, kg_service=None):
        """初始化样式配置工具

        Args:
            kg_service: KGService 实例，提供 query_cartographic_decision 等方法
        """
        self._kg_service = kg_service
        self._definition = ToolDefinition(
            name="style_config",
            description="将知识图谱的制图决策转换为Leaflet/MapLibre样式配置",
            category="rendering",
            input_schema={
                "type": "object",
                "properties": {
                    "map_type": {
                        "type": "string",
                        "description": "地图类型（traffic/tourism/campus/food/basic/administrative）",
                    },
                    "element_type": {
                        "type": "string",
                        "description": "要素类型（road_element/waterway_element等）",
                    },
                    "kg_style": {
                        "type": "object",
                        "description": "KG推导的样式参数 {color, weight, opacity, ...}",
                    },
                },
                "required": ["map_type"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "leaflet_style": {"type": "object", "description": "Leaflet兼容样式"},
                    "maplibre_style": {"type": "object", "description": "MapLibre兼容样式"},
                },
            },
            kg_trigger_rules=[
                {"relation_type": "HAS_SYMBOL", "source_label": "MapLayer", "target_label": "Symbol"},
                {"relation_type": "USES_COLOR", "source_label": "MapType", "target_label": "ColorConstraint"},
                {"relation_type": "APPLIES_TO", "source_label": "AnnotationRule", "target_label": "MapLayer"},
                {"relation_type": "CONSTRAINED_BY", "source_label": "Symbol", "target_label": "ScaleFactor"},
            ],
            keywords=["样式", "配色", "颜色", "符号", "style", "color", "symbol", "标注"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行样式配置

        将KG决策参数转换为地图渲染引擎可用的样式配置。

        Args:
            map_type: 地图类型
            element_type: 要素类型（可选）
            kg_style: KG推导的原始样式参数（可选）

        Returns:
            标准化结果，含 leaflet_style 和 maplibre_style
        """
        map_type = kwargs.get("map_type", "basic")
        element_type = kwargs.get("element_type", "")
        kg_style = kwargs.get("kg_style", {})

        # 默认样式映射表
        default_styles = {
            "road_element": {"color": "#333333", "weight": 2.5, "opacity": 0.9},
            "railway_element": {"color": "#666666", "weight": 2.0, "opacity": 0.85, "dashArray": "8,4"},
            "waterway_element": {"color": "#3388ff", "weight": 2.0, "opacity": 0.8},
            "building_element": {"color": "#d4a574", "weight": 1.0, "opacity": 0.7, "fillOpacity": 0.3},
            "poi_element": {"color": "#ff6600", "weight": 1.0, "radius": 6, "opacity": 0.9},
            "green_space_element": {"color": "#66aa33", "weight": 1.0, "opacity": 0.6, "fillOpacity": 0.25},
            "boundary_element": {"color": "#cc3333", "weight": 1.5, "opacity": 0.7, "dashArray": "4,4"},
        }

        # 合并KG样式和默认样式
        base_style = default_styles.get(element_type, {"color": "#555555", "weight": 1.5, "opacity": 0.8})
        merged_style = {**base_style, **kg_style}

        # 构建 Leaflet 兼容样式
        leaflet_style = {
            "color": merged_style.get("color", "#555555"),
            "weight": merged_style.get("weight", 1.5),
            "opacity": merged_style.get("opacity", 0.8),
        }
        if "dashArray" in merged_style:
            leaflet_style["dashArray"] = merged_style["dashArray"]
        if "fillOpacity" in merged_style:
            leaflet_style["fillOpacity"] = merged_style["fillOpacity"]
        if "radius" in merged_style:
            leaflet_style["radius"] = merged_style["radius"]

        # 构建 MapLibre 兼容样式
        maplibre_style = {
            "type": "line" if element_type in ("road_element", "railway_element", "waterway_element", "boundary_element")
                    else "fill" if element_type in ("building_element", "green_space_element")
                    else "circle",
            "paint": {
                "line-color": merged_style.get("color", "#555555"),
                "line-width": merged_style.get("weight", 1.5),
                "line-opacity": merged_style.get("opacity", 0.8),
            } if element_type not in ("poi_element",)
            else {
                "circle-color": merged_style.get("color", "#ff6600"),
                "circle-radius": merged_style.get("radius", 6),
                "circle-opacity": merged_style.get("opacity", 0.9),
            },
        }

        return self._success_result({
            "map_type": map_type,
            "element_type": element_type,
            "leaflet_style": leaflet_style,
            "maplibre_style": maplibre_style,
            "raw_kg_style": kg_style,
        })


class MapRenderTool(BaseTool):
    """地图渲染工具

    调用 MapService 生成地图，将数据图层和样式配置组合为最终的地图可视化结果。

    KG触发规则：
    - 当 KG 决策包含完整的三要素（图层配置 + 符号方案 + 配色方案）时激活
    """

    def __init__(self, map_service=None):
        """初始化地图渲染工具

        Args:
            map_service: MapService 实例，提供 generate_map 等方法
        """
        self._map_service = map_service
        self._definition = ToolDefinition(
            name="map_render",
            description="调用地图渲染引擎生成可视化地图",
            category="rendering",
            input_schema={
                "type": "object",
                "properties": {
                    "map_type": {
                        "type": "string",
                        "description": "地图类型",
                    },
                    "region": {
                        "type": "string",
                        "description": "区域名称（城市名）",
                    },
                    "layers": {
                        "type": "array",
                        "description": "图层数据列表",
                    },
                    "render_options": {
                        "type": "object",
                        "description": "渲染选项 {center, zoom, background, primary_color}",
                    },
                },
                "required": ["map_type", "region"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "map_id": {"type": "string"},
                    "layer_count": {"type": "integer"},
                    "center": {"type": "array"},
                    "zoom": {"type": "integer"},
                },
            },
            preconditions=["map_type_in_known_types=true", "region_resolvable=true"],
            postconditions=["map_id_generated=true", "layer_count>=1"],
            cost="high",
            retryable=False,
            provenance=True,
            kg_trigger_rules=[
                {"relation_type": "HAS_DECISION", "source_label": "MapType", "target_label": "CartographicDecision"},
                {"relation_type": "USES_COLOR", "source_label": "MapType", "target_label": "ColorConstraint"},
                {"relation_type": "REQUIRES_LAYER", "source_label": "MapType", "target_label": "MapLayer"},
            ],
            keywords=["生成", "渲染", "绘制", "生成地图", "render", "generate", "画"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行地图渲染

        Args:
            map_type: 地图类型
            region: 区域名称
            layers: 图层数据列表（可选，如不传则由 map_service 自行获取）
            render_options: 渲染选项（可选）

        Returns:
            标准化结果，含 map_id, layer_count 等
        """
        map_type = kwargs.get("map_type", "basic")
        region = kwargs.get("region", "武汉市")
        render_options = kwargs.get("render_options", {})

        if not self._map_service:
            return self._error_result("MapService 不可用")

        try:
            map_data = self._map_service.generate_map(
                map_type=map_type,
                region=region,
            )
            layer_count = len(map_data.get("layers", []))
            return self._success_result({
                "map_id": map_data.get("map_id", ""),
                "layer_count": layer_count,
                "center": map_data.get("center", []),
                "zoom": map_data.get("zoom", 12),
                "layer_names": [ly.get("name", "") for ly in map_data.get("layers", [])],
            })
        except Exception as e:
            return self._error_result(f"地图渲染失败: {str(e)}")


class QualityCheckTool(BaseTool):
    """质量校验工具

    调用 CartographyValidator 对生成的地图进行多维度质量校验，
    检测图层完整性、符号规范性和配色协调性。

    KG触发规则：
    - 地图生成后自动触发（作为渲染步骤的后置校验）
    """

    def __init__(self, cartography_validator=None, kg_service=None):
        """初始化质量校验工具

        Args:
            cartography_validator: CartographyValidator 实例
            kg_service: KGService 实例（用于参考规范校验）
        """
        self._validator = cartography_validator
        self._kg_service = kg_service
        self._definition = ToolDefinition(
            name="quality_check",
            description="对生成的地图进行多维度质量校验（图层完整性、符号规范性、配色协调性）",
            category="analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "map_data": {
                        "type": "object",
                        "description": "地图数据字典，需包含 layers 等字段",
                    },
                },
                "required": ["map_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "description": "0-100 综合质量分"},
                    "issues": {"type": "array", "description": "质量问题列表"},
                    "passed_checks": {"type": "array"},
                    "failed_checks": {"type": "array"},
                },
            },
            preconditions=["map_data_nonempty=true", "layers_present=true"],
            postconditions=["score_0_100=true", "dimensions_reported=true"],
            cost="low",
            retryable=True,
            provenance=True,
            kg_trigger_rules=[
                {"relation_type": "CONSTRAINED_BY", "source_label": "Symbol", "target_label": "ScaleFactor"},
                {"relation_type": "APPLIES_TO", "source_label": "AnnotationRule", "target_label": "MapLayer"},
            ],
            keywords=["质量", "校验", "检查", "验证", "quality", "check", "validate"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行质量校验

        Args:
            map_data: 地图数据字典

        Returns:
            标准化结果，含 score, issues, passed_checks, failed_checks
        """
        map_data = kwargs.get("map_data", {})

        if not map_data:
            return self._error_result("缺少 map_data 参数")

        if not self._validator:
            return self._error_result("CartographyValidator 不可用")

        try:
            validation_result = self._validator.validate(
                map_data, kg_service=self._kg_service
            )
            return self._success_result(validation_result)
        except Exception as e:
            return self._error_result(f"质量校验失败: {str(e)}")


class ExportTool(BaseTool):
    """地图导出工具

    将生成的地图导出为 GeoJSON / PNG / SVG 等格式。

    KG触发规则：
    - 用户请求中包含导出意图时激活
    """

    def __init__(self, export_service=None):
        """初始化地图导出工具

        Args:
            export_service: ExportService 实例，提供 export_map 等方法
        """
        self._export_service = export_service
        self._definition = ToolDefinition(
            name="map_export",
            description="将地图导出为GeoJSON/PNG/SVG等格式",
            category="export",
            input_schema={
                "type": "object",
                "properties": {
                    "map_id": {
                        "type": "string",
                        "description": "地图ID",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["geojson", "png", "svg"],
                        "description": "导出格式",
                    },
                    "options": {
                        "type": "object",
                        "description": "导出选项（分辨率、图层筛选等）",
                    },
                },
                "required": ["map_id", "format"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "format": {"type": "string"},
                    "file_size": {"type": "integer"},
                },
            },
            preconditions=["map_id_exists=true", "format_supported=true"],
            postconditions=["file_created=true", "file_size>0"],
            cost="low",
            retryable=True,
            provenance=True,
            kg_trigger_rules=[],
            keywords=["导出", "下载", "保存", "export", "download", "save", "geojson", "png", "svg"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行地图导出

        Args:
            map_id: 地图ID
            format: 导出格式
            options: 导出选项（可选）

        Returns:
            标准化结果，含 file_path, format, file_size
        """
        map_id = kwargs.get("map_id", "")
        export_format = kwargs.get("format", "geojson")
        options = kwargs.get("options", {})

        if not map_id:
            return self._error_result("缺少 map_id 参数")

        if not self._export_service:
            return self._error_result("ExportService 不可用")

        try:
            export_result = self._export_service.export_map(
                map_id=map_id,
                format=export_format,
                **options,
            )
            return self._success_result(export_result)
        except Exception as e:
            return self._error_result(f"地图导出失败: {str(e)}")


# ======================== 扩展工具生态（计划 2.5） ========================

class OSMTypeFetchTool(BaseTool):
    """按要素类型获取 OSM 数据（boundary/road/water/poi）"""

    def __init__(self, osm_service, element_type: str):
        self._osm_service = osm_service
        self._element_type = element_type
        name_map = {
            "boundary~administrative": ("fetch_boundary", "获取行政区划边界数据"),
            "highway": ("fetch_road", "获取道路网络数据"),
            "waterway": ("fetch_water", "获取水系数据"),
            "amenity": ("fetch_poi", "获取POI兴趣点数据"),
        }
        name, desc = name_map.get(element_type, (f"fetch_{element_type}", f"获取{element_type}数据"))
        self._definition = ToolDefinition(
            name=name,
            description=desc,
            category="data",
            input_schema={
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "城市名，如 武汉市"},
                    "element_type": {"type": "string", "description": "要素类型，默认 " + element_type},
                },
                "required": ["region"],
            },
            keywords=["边界", "道路", "水系", "POI", "数据", name],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        region = kwargs.get("region", "")
        element_type = kwargs.get("element_type", self._element_type)
        if not region:
            return self._error_result("缺少 region 参数")
        if not self._osm_service:
            return self._error_result("OSMService 不可用")
        try:
            data = self._osm_service.fetch_by_region(region, [element_type])
            return self._success_result({
                "region": region,
                "element_type": element_type,
                "count": sum(len(v) for v in data.values()),
                "data": data,
            })
        except Exception as e:
            return self._error_result(f"数据获取失败: {e}")


class SimplifyGeometryTool(BaseTool):
    """几何简化（Douglas-Peucker，shapely）"""

    def __init__(self):
        self._definition = ToolDefinition(
            name="simplify_geometry",
            description="对线/面坐标做几何简化，降低数据量与渲染压力",
            category="processing",
            input_schema={
                "type": "object",
                "properties": {
                    "coordinates": {"type": "array", "description": "线/面坐标（[lat,lng] 点列表）"},
                    "tolerance": {"type": "number", "description": "简化容差（米），默认 20"},
                },
                "required": ["coordinates"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "simplified_coordinates": {"type": "array"},
                    "original_points": {"type": "integer"},
                    "simplified_points": {"type": "integer"},
                },
            },
            preconditions=["coordinates_valid=true", "tolerance>0"],
            postconditions=["feature_count_same_or_lower=true", "geometry_valid=true"],
            cost="low",
            retryable=True,
            provenance=True,
            keywords=["简化", "抽稀", "简化几何", "simplify", "Douglas"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        coords = kwargs.get("coordinates") or []
        tolerance_m = float(kwargs.get("tolerance", 20.0))
        if not coords:
            return self._error_result("缺少 coordinates 参数")
        try:
            from app.utils.geo_simplify import simplify_coords_meters
            def _simplify_line(pts):
                if len(pts) < 3:
                    return pts
                # 输入 [lat,lng] -> [lng,lat] -> 米制简化 -> [lat,lng]
                lonlat = [(p[1], p[0]) for p in pts]
                simple = simplify_coords_meters(lonlat, tolerance_m, preserve_topology=True)
                return [[y, x] for x, y in simple]
            result = [_simplify_line(pts) for pts in coords if isinstance(pts, list) and len(pts) > 1]
            return self._success_result({"coordinates": result, "simplified": True})
        except Exception as e:
            return self._error_result(f"简化失败: {e}")


class GenerateLegendTool(BaseTool):
    """自动生成图例"""

    def __init__(self, map_service):
        self._map_service = map_service
        self._definition = ToolDefinition(
            name="generate_legend",
            description="根据地图图层自动生成图例数据",
            category="rendering",
            input_schema={
                "type": "object",
                "properties": {
                    "map_type": {"type": "string"},
                    "layers": {"type": "array"},
                },
                "required": ["map_type", "layers"],
            },
            keywords=["图例", "legend"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        map_type = kwargs.get("map_type", "basic")
        layers = kwargs.get("layers") or []
        if not self._map_service:
            return self._error_result("MapService 不可用")
        try:
            legend = self._map_service._generate_legend(map_type, layers)
            return self._success_result(legend)
        except Exception as e:
            return self._error_result(f"图例生成失败: {e}")


class DecorationTool(BaseTool):
    """地图整饰元素（图名/比例尺/指北针/附图）"""

    def __init__(self, kind: str):
        self._kind = kind
        specs = {
            "add_title": {"name": "add_title", "desc": "添加图名（{区域}{主题}图，居中上方黑体）",
                          "keywords": ["图名", "标题", "title"]},
            "add_scalebar": {"name": "add_scalebar", "desc": "添加比例尺（随缩放计算，下方居中）",
                             "keywords": ["比例尺", "scalebar", "scale"]},
            "add_north_arrow": {"name": "add_north_arrow", "desc": "添加指北针（右上角）",
                                "keywords": ["指北针", "north", "北"]},
            "add_inset": {"name": "add_inset", "desc": "添加附图（全国/全省位置示意图，左上角）",
                          "keywords": ["附图", "位置图", "inset"]},
        }
        spec = specs.get(kind, specs["add_title"])
        self._definition = ToolDefinition(
            name=spec["name"],
            description=spec["desc"],
            category="rendering",
            input_schema={
                "type": "object",
                "properties": {"map_id": {"type": "string"}, "text": {"type": "string"}},
            },
            keywords=spec["keywords"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        return self._success_result({
            "decoration": self._kind,
            "text": kwargs.get("text", ""),
            "applied": True,
        })


class BufferAnalysisTool(BaseTool):
    """缓冲区分析（shapely）"""

    def __init__(self):
        self._definition = ToolDefinition(
            name="buffer_analysis",
            description="对点/线要素做缓冲区分析",
            category="analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "coordinates": {"type": "array"},
                    "distance_km": {"type": "number", "description": "缓冲距离（公里）"},
                },
                "required": ["coordinates", "distance_km"],
            },
            keywords=["缓冲区", "buffer", "缓冲"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        coords = kwargs.get("coordinates") or []
        distance_km = float(kwargs.get("distance_km", 1))
        if not coords:
            return self._error_result("缺少 coordinates")
        try:
            from shapely.geometry import Point, LineString
            from shapely.ops import unary_union
            shapes = []
            for c in coords:
                if isinstance(c[0], (int, float)):
                    shapes.append(Point(c[1], c[0]))
                else:
                    shapes.append(LineString([(p[1], p[0]) for p in c]))
            # 1 度纬度约 111km，简化近似
            deg = distance_km / 111.0
            buf = unary_union([s.buffer(deg) for s in shapes])
            ring = list(buf.exterior.coords) if buf and not buf.is_empty else []
            return self._success_result({"buffer_coords": [[y, x] for x, y in ring]})
        except Exception as e:
            return self._error_result(f"缓冲区分析失败: {e}")


class OverlayAnalysisTool(BaseTool):
    """叠加分析（点与面相交）"""

    def __init__(self):
        self._definition = ToolDefinition(
            name="overlay_analysis",
            description="叠加分析：判断点是否落在面内",
            category="analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "points": {"type": "array", "description": "点列表 [[lat,lng],...]"},
                    "rings": {"type": "array", "description": "面环列表"},
                },
                "required": ["points", "rings"],
            },
            keywords=["叠加", "相交", "overlay", "intersect"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        points = kwargs.get("points") or []
        rings = kwargs.get("rings") or []
        if not points or not rings:
            return self._error_result("缺少 points/rings")
        try:
            from shapely.geometry import Point, Polygon
            polys = [Polygon([(p[1], p[0]) for p in ring]) for ring in rings if len(ring) >= 3]
            kept = [p for p in points if any(poly.contains(Point(p[1], p[0])) for poly in polys)]
            return self._success_result({"kept_points": kept, "count": len(kept)})
        except Exception as e:
            return self._error_result(f"叠加分析失败: {e}")


class ValidateCartographyTool(BaseTool):
    """制图质量校验（7维评分）"""

    def __init__(self, validator=None, kg_service=None):
        self._validator = validator
        self._kg_service = kg_service
        self._definition = ToolDefinition(
            name="validate_cartography",
            description="对地图做制图规范校验与质量评分",
            category="analysis",
            input_schema={
                "type": "object",
                "properties": {"map_data": {"type": "object"}},
                "required": ["map_data"],
            },
            keywords=["质检", "校验", "评分", "validate", "quality"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        map_data = kwargs.get("map_data")
        if not map_data:
            return self._error_result("缺少 map_data")
        try:
            validator = self._validator
            if validator is None:
                from app.services.cartography_validator import CartographyValidator
                validator = CartographyValidator()
            report = validator.validate(map_data, kg_service=self._kg_service)
            return self._success_result(report)
        except Exception as e:
            return self._error_result(f"校验失败: {e}")


class ExportFormatTool(BaseTool):
    """按格式导出地图数据（geojson/svg/png）"""

    def __init__(self, export_service, fmt: str):
        self._export_service = export_service
        self._fmt = fmt
        self._definition = ToolDefinition(
            name=f"export_{fmt}",
            description=f"将地图导出为 {fmt.upper()} 格式",
            category="export",
            input_schema={
                "type": "object",
                "properties": {"map_data": {"type": "object"}},
                "required": ["map_data"],
            },
            keywords=[fmt, "导出", "export"],
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, **kwargs) -> Dict[str, Any]:
        map_data = kwargs.get("map_data")
        if not map_data:
            return self._error_result("缺少 map_data")
        if not self._export_service:
            return self._error_result("ExportService 不可用")
        try:
            if self._fmt == "geojson":
                data = self._export_service.export_geojson(map_data)
            elif self._fmt == "svg":
                data = self._export_service.export_svg(map_data)
            else:
                data = self._export_service.export_png(map_data)
            return self._success_result({"format": self._fmt, "data_length": len(str(data))})
        except Exception as e:
            return self._error_result(f"导出失败: {e}")


# ======================== 工具注册中心 ========================

class ToolRegistry:
    """工具注册中心 - 运行时工具注册、分类和调度

    作为"知识-数据-工具"三元体系的核心调度层，提供：
    1. 运行时动态注册/移除工具
    2. 按分类查询工具
    3. 根据KG决策结果自动推导需要的工具
    4. 生成LLM function calling格式的工具描述
    5. 根据执行计划依次调用工具

    使用方式：
        registry = ToolRegistry()
        registry.register(OSMFetchTool(osm_service))
        registry.register(StyleConfigTool(kg_service))
        tools = registry.get_tools_for_decision(kg_decision)
        result = registry.execute_plan(execution_plan)
    """

    def __init__(self):
        """初始化工具注册中心"""
        self._tools: Dict[str, BaseTool] = {}
        logger.info("[ToolRegistry] 初始化完成")

    # ======================== 注册管理 ========================

    def register(self, tool: BaseTool) -> None:
        """注册工具

        如果工具名称已存在，会覆盖旧注册（支持热更新）。

        Args:
            tool: 实现了 BaseTool 接口的工具实例
        """
        name = tool.definition.name
        self._tools[name] = tool
        logger.info(f"[ToolRegistry] 注册工具: {name} (category={tool.definition.category})")

    def unregister(self, tool_name: str) -> bool:
        """移除已注册的工具

        Args:
            tool_name: 工具名称

        Returns:
            是否成功移除
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"[ToolRegistry] 移除工具: {tool_name}")
            return True
        return False

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取指定名称的工具

        Args:
            tool_name: 工具名称

        Returns:
            工具实例，不存在时返回 None
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> List[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        """已注册工具数量"""
        return len(self._tools)

    # ======================== 分类查询 ========================

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """按分类获取工具

        Args:
            category: 工具分类: data / rendering / analysis / export

        Returns:
            匹配分类的工具列表
        """
        return [
            tool for tool in self._tools.values()
            if tool.definition.category == category
        ]

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有已注册工具"""
        return list(self._tools.values())

    # ======================== KG决策映射 ========================

    def get_tools_for_decision(self, kg_decision: Dict[str, Any]) -> List[BaseTool]:
        """根据KG决策结果自动选择需要的工具

        分析KG决策中的图层配置、符号方案、配色方案等字段，
        匹配每个工具的 kg_trigger_rules，自动推导出需要的工具集合。

        推导逻辑：
        - 如果存在 layer_configs > 激活 data 类工具（OSMFetchTool）
        - 如果存在 symbol_scheme / color_scheme > 激活 rendering 类工具（StyleConfigTool, MapRenderTool）
        - 所有情况都会激活 QualityCheckTool（作为后置校验）

        Args:
            kg_decision: KG决策结果字典，包含 layer_configs, symbol_scheme, color_scheme 等

        Returns:
            匹配的工具列表，按推荐执行顺序排列
        """
        if not kg_decision:
            return list(self._tools.values())

        selected: List[BaseTool] = []
        selected_names: set = set()

        # 检测KG决策中的关键信号字段
        has_layer_configs = bool(kg_decision.get("layer_configs"))
        has_symbol_scheme = bool(kg_decision.get("symbol_scheme"))
        has_color_scheme = bool(kg_decision.get("color_scheme"))
        has_annotation_rules = bool(kg_decision.get("annotation_rules"))

        # 获取决策中涉及的实体和关系类型
        decision_types = set()
        if has_layer_configs:
            decision_types.add("LAYER_CONFIG")
        if has_symbol_scheme:
            decision_types.add("SYMBOL_SCHEME")
        if has_color_scheme:
            decision_types.add("COLOR_SCHEME")
        if has_annotation_rules:
            decision_types.add("ANNOTATION_RULE")

        # 遍历所有工具，匹配KG触发规则
        for tool in self._tools.values():
            tool_def = tool.definition

            # 方式1: 基于决策类型匹配工具分类
            if tool_def.category == "data" and has_layer_configs:
                if tool_def.name not in selected_names:
                    selected.append(tool)
                    selected_names.add(tool_def.name)
            elif tool_def.category == "rendering" and (has_symbol_scheme or has_color_scheme):
                if tool_def.name not in selected_names:
                    selected.append(tool)
                    selected_names.add(tool_def.name)
            elif tool_def.category == "analysis":
                # 质量校验工具总是被激活（作为后置校验）
                if tool_def.name not in selected_names:
                    selected.append(tool)
                    selected_names.add(tool_def.name)
            elif tool_def.category == "export":
                # 导出工具仅在用户明确请求时激活，不自动匹配
                pass

        # 如果没有任何工具被选中（KG决策为空或不完整），返回所有data和rendering类工具
        if not selected:
            selected = self.get_tools_by_category("data") + self.get_tools_by_category("rendering")
            # 后置校验仍然添加
            for tool in self._tools.values():
                if tool.definition.category == "analysis" and tool.definition.name not in {t.definition.name for t in selected}:
                    selected.append(tool)

        # 按执行顺序排列: data -> rendering -> analysis -> export
        category_order = {"data": 0, "rendering": 1, "analysis": 2, "export": 3}
        selected.sort(key=lambda t: category_order.get(t.definition.category, 99))

        names = [t.definition.name for t in selected]
        logger.info(f"[ToolRegistry] KG决策工具匹配: {names}, decision_types={decision_types}")
        return selected

    # ======================== LLM集成 ========================

    def get_tool_definitions_for_llm(self) -> List[Dict[str, Any]]:
        """生成供LLM使用的工具描述（LangChain function calling格式）

        将所有已注册工具的定义转换为LLM可理解的function calling schema，
        用于 ReAct Agent 或 LangChain 的 tool_choice 参数。

        Returns:
            工具描述列表，每项包含 name, description, parameters(input_schema)
        """
        definitions = []
        for tool in self._tools.values():
            tool_def = tool.definition
            definitions.append({
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.input_schema,
                "category": tool_def.category,
                "preconditions": tool_def.preconditions,
                "postconditions": tool_def.postconditions,
                "cost": tool_def.cost,
                "destructive": tool_def.destructive,
                "retryable": tool_def.retryable,
            })
        return definitions

    def list_tool_contracts(self) -> List[Dict[str, Any]]:
        """输出全部工具契约（Agent Trace / 实验记录用，研究基线版 §15-16）"""
        return [tool.definition.contract() for tool in self._tools.values()]

    def get_tool_provenance_summary(self) -> List[Dict[str, Any]]:
        """输出精简工具契约摘要（地图 provenance 记录用，避免全量 schema 冗余）"""
        summary = []
        for tool in self._tools.values():
            d = tool.definition
            summary.append({
                "name": d.name,
                "category": d.category,
                "preconditions": d.preconditions,
                "postconditions": d.postconditions,
                "destructive": d.destructive,
                "retryable": d.retryable,
            })
        return summary

    # ======================== 计划执行 ========================

    def execute_plan(self, execution_plan) -> Dict[str, Any]:
        """根据执行计划依次调用工具

        将 KGPriorPlanner 产生的 ExecutionPlan 映射为具体的工具调用序列，
        按 data_steps > style_steps > render_steps 的顺序依次执行各工具。

        Args:
            execution_plan: ExecutionPlan 实例，包含 data_steps, style_steps, render_steps

        Returns:
            {
                "success": bool,
                "results": Dict[str, Any],   # 各步骤的执行结果
                "errors": List[str],          # 错误信息列表
                "execution_summary": str,     # 执行摘要
            }
        """
        results = {}
        errors = []
        retries = []

        def _run(tool_name: str, kwargs: Dict[str, Any], step_desc: str) -> None:
            """带重试的工具调用：retryable 工具失败后自动重试一次（短暂退避）

            对应申报书执行驱动"状态管理与错误处理（重试/切换备用接口/瓶颈回退）"。
            """
            tool = self._tools.get(tool_name)
            if not tool:
                errors.append(f"工具未注册: {tool_name}")
                return
            try:
                retryable = bool(tool.definition.retryable)
            except Exception:
                retryable = True
            max_attempts = 2 if retryable else 1
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = tool.execute(**kwargs)
                    results[step_desc] = result
                    return
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts:
                        retries.append(f"{tool_name}[{step_desc}] 第{attempt}次失败，自动重试: {str(e)[:60]}")
                        logger.info(f"[ToolRegistry] {tool_name} 执行失败，自动重试: {str(e)[:60]}")
                        time.sleep(0.5)
            errors.append(f"{step_desc}失败: {str(last_err)}")

        # 步骤1: 执行数据获取步骤
        for step in execution_plan.data_steps:
            _run("osm_fetch", {
                "bbox": step.get("bbox_city"),
                "osm_tags": step.get("osm_tags", ""),
                "layer_name": step.get("layer_name", ""),
            }, f"data:{step.get('layer_name', 'unknown')}")

        # 步骤2: 执行样式配置步骤
        for step in execution_plan.style_steps:
            _run("style_config", {
                "element_type": step.get("element_type", ""),
                "kg_style": step.get("style", {}),
            }, f"style:{step.get('element_type', 'unknown')}")

        # 步骤3: 执行渲染步骤
        for step in execution_plan.render_steps:
            _run("map_render", {
                "render_options": step,
            }, f"render:{step.get('step', 'unknown')}")

        success = len(errors) == 0
        summary = (
            f"执行计划完成: {len(results)}个步骤成功, {len(errors)}个错误, {len(retries)}次自动重试"
            if success else
            f"执行计划部分失败: {len(results)}个步骤成功, {len(errors)}个错误, {len(retries)}次自动重试"
        )

        logger.info(f"[ToolRegistry] execute_plan: {summary}")
        return {
            "success": success,
            "results": results,
            "errors": errors,
            "retries": retries,
            "execution_summary": summary,
        }
