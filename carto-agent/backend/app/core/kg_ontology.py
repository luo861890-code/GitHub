"""制图知识图谱本体定义 - 基于LLM-KG-Carto框架

定义论文核心的7类概念本体，构建制图领域知识图谱的概念层次结构：
1. MapElement: 地图要素（道路、建筑、水系等地理实体）
2. MapSymbol: 地图符号（点状/线状/面状符号的设计规范）
3. CartographicData: 制图数据（OSM/遥感/矢量等数据源）
4. MapProjection: 地图投影（坐标系、投影方式）
5. InfluencingFactor: 影响因素（比例尺、用途、受众等制图决策因素）
6. CartographicDecision: 制图行为决策（特定条件下的制图方案选择，如图层配置、符号方案、配色方案、标注规则）
7. LayerConfig: 图层配置（地图类型对应的图层叠置方案，定义图层名称、顺序、可见性、数据源等）

本体关系推理链：
    MapType → CONTAINS_ELEMENT → MapElement
    MapElement → REPRESENTED_BY → MapSymbol
    MapElement → SOURCED_FROM → CartographicData
    MapSymbol → GOVERNED_BY → CartographyRule
    CartographicData → REQUIRES → MapProjection
    InfluencingFactor → INFLUENCES → MapElement
    InfluencingFactor → DETERMINES → MapSymbol
    MapType → HAS_DECISION → CartographicDecision → HAS_LAYER → LayerConfig
    InfluencingFactor → INFLUENCES → CartographicDecision
"""
from typing import Dict, List, Any


# ========== 7类核心概念本体定义 ==========

ONTOLOGY_CLASSES: Dict[str, Dict[str, Any]] = {
    "MapElement": {
        "description": "地图要素 - 地理实体在地图上的抽象表示",
        "color": "#3b82f6",  # 蓝色
        "subtypes": ["PointElement", "LinearElement", "ArealElement", "NetworkElement"],
        "properties": ["element_type", "osm_tag", "geometry_type", "rendering_priority"],
    },
    "MapSymbol": {
        "description": "地图符号 - 地图要素的视觉表达规范",
        "color": "#a855f7",  # 紫色
        "subtypes": ["PointSymbol", "LineSymbol", "AreaSymbol", "TextSymbol"],
        "properties": ["symbol_type", "color", "size", "style", "opacity"],
    },
    "CartographicData": {
        "description": "制图数据 - 地图制作的数据来源与格式",
        "color": "#22c55e",  # 绿色
        "subtypes": ["OSMData", "RemoteSensingData", "VectorData", "RasterData"],
        "properties": ["data_source", "data_format", "update_frequency", "coverage", "license"],
    },
    "MapProjection": {
        "description": "地图投影 - 地理坐标系与投影方式",
        "color": "#f97316",  # 橙色
        "subtypes": ["GeographicCRS", "ProjectedCRS", "CustomCRS"],
        "properties": ["crs_code", "projection_method", "unit", "accuracy"],
    },
    "InfluencingFactor": {
        "description": "影响因素 - 影响制图决策的各种因素",
        "color": "#ef4444",  # 红色
        "subtypes": ["Scale", "MapPurpose", "TargetAudience", "VisualConstraint"],
        "properties": ["factor_type", "value_range", "priority", "description"],
    },
    "CartographicDecision": {
        "description": "制图行为决策 - 特定条件下的制图方案选择",
        "color": "#f59e0b",
        "subtypes": ["LayerConfigDecision", "SymbolSchemeDecision", "ColorSchemeDecision", "AnnotationRuleDecision"],
        "properties": ["decision_id", "decision_type", "map_type", "audience_level", "parameters", "priority", "rationale"],
    },
    "LayerConfig": {
        "description": "图层配置 - 地图类型对应的图层叠置方案",
        "color": "#06b6d4",
        "subtypes": ["BaseLayer", "ThematicLayer", "AnnotationLayer"],
        "properties": ["layer_name", "layer_order", "visibility_default", "min_zoom", "max_zoom", "data_source", "osm_tags", "symbol_type"],
    },
    "MapCase": {
        "description": "地图案例 - 已完成的地图作品/任务（相似案例检索，支持 MapCase similar_to MapCase）",
        "color": "#ec4899",
        "subtypes": ["AdministrativeCase", "TrafficCase", "TourismCase", "TerrainCase"],
        "properties": ["case_id", "map_type", "region", "audience", "page_size", "task_summary", "artifact_ref"],
    },
    "Dataset": {
        "description": "数据集 - 可用的制图数据资源（Theme requires Dataset / Dataset suitable_for Symbol）",
        "color": "#14b8a6",
        "subtypes": ["VectorDataset", "RasterDataset", "POIDataset", "DEMDataset"],
        "properties": ["dataset_name", "data_source", "format", "coverage", "license", "resolution"],
    },
}


# ========== 本体节点初始数据（用于扩展init_data.json和内存模式） ==========

ONTOLOGY_NODES: List[Dict[str, Any]] = [
    # --- MapElement 实例 ---
    {"label": "MapElement", "name": "road_element", "element_type": "linear", "osm_tag": "highway",
     "geometry_type": "line", "rendering_priority": 5,
     "description": "道路要素，包括高速公路、主干道、次干道等"},
    {"label": "MapElement", "name": "building_element", "element_type": "areal", "osm_tag": "building",
     "geometry_type": "polygon", "rendering_priority": 2,
     "description": "建筑要素，包括住宅、商业、工业建筑等"},
    {"label": "MapElement", "name": "waterway_element", "element_type": "linear", "osm_tag": "waterway",
     "geometry_type": "line", "rendering_priority": 4,
     "description": "水系要素，包括河流、运河、溪流等"},
    {"label": "MapElement", "name": "poi_element", "element_type": "point", "osm_tag": "tourism|amenity",
     "geometry_type": "point", "rendering_priority": 6,
     "description": "兴趣点要素，包括景点、餐厅、医院等"},
    {"label": "MapElement", "name": "railway_element", "element_type": "linear", "osm_tag": "railway",
     "geometry_type": "line", "rendering_priority": 5,
     "description": "铁路要素，包括高铁、地铁、轻轨等"},

    # --- MapSymbol 实例 ---
    {"label": "MapSymbol", "name": "highway_symbol", "symbol_type": "LineSymbol",
     "color": "#e892a2", "size": 5, "style": "solid", "opacity": 0.9,
     "description": "高速公路符号，粗线红色"},
    {"label": "MapSymbol", "name": "railway_symbol", "symbol_type": "LineSymbol",
     "color": "#555555", "size": 3, "style": "dashed", "opacity": 0.8,
     "description": "铁路符号，灰色虚线"},
    {"label": "MapSymbol", "name": "waterway_symbol", "symbol_type": "LineSymbol",
     "color": "#7dd3fc", "size": 3, "style": "solid", "opacity": 0.8,
     "description": "水系符号，蓝色实线"},
    {"label": "MapSymbol", "name": "building_symbol", "symbol_type": "AreaSymbol",
     "color": "#d1d5db", "size": 1, "style": "fill", "opacity": 0.3,
     "description": "建筑符号，浅灰填充"},
    {"label": "MapSymbol", "name": "poi_symbol", "symbol_type": "PointSymbol",
     "color": "#dc2626", "size": 8, "style": "circle", "opacity": 1.0,
     "description": "兴趣点符号，红色圆形标记"},

    # --- CartographicData 实例 ---
    {"label": "CartographicData", "name": "osm_data", "data_source": "OpenStreetMap",
     "data_format": "Overpass JSON", "update_frequency": "实时", "coverage": "全球",
     "license": "ODbL", "description": "OpenStreetMap开放数据，通过Overpass API获取"},
    {"label": "CartographicData", "name": "local_landmark_data", "data_source": "内置知识库",
     "data_format": "JSON", "update_frequency": "手动", "coverage": "武汉",
     "license": "自有", "description": "内置武汉地标数据，OSM不可用时降级使用"},

    # --- MapProjection 实例 ---
    {"label": "MapProjection", "name": "wgs84", "crs_code": "EPSG:4326",
     "projection_method": "地理坐标系", "unit": "度", "accuracy": "高",
     "description": "WGS84地理坐标系，GPS标准坐标系"},
    {"label": "MapProjection", "name": "web_mercator", "crs_code": "EPSG:3857",
     "projection_method": "Web墨卡托投影", "unit": "米", "accuracy": "中",
     "description": "Web墨卡托投影，在线地图标准投影"},

    # --- InfluencingFactor 实例 ---
    {"label": "InfluencingFactor", "name": "scale_factor", "factor_type": "Scale",
     "value_range": "zoom 8-19", "priority": "high",
     "description": "比例尺因素，决定地图详细程度和要素选择"},
    {"label": "InfluencingFactor", "name": "purpose_factor", "factor_type": "MapPurpose",
     "value_range": "traffic/tourism/campus/food/basic", "priority": "high",
     "description": "地图用途因素，决定图层选择和样式配置"},
    {"label": "InfluencingFactor", "name": "color_constraint", "factor_type": "VisualConstraint",
     "value_range": "主色不超过5种", "priority": "medium",
     "description": "色彩约束因素，确保视觉层次和信息可读性"},

    # --- CartographicDecision 实例 ---
    {"label": "CartographicDecision", "name": "traffic_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "traffic", "audience_level": "public", "priority": "high",
     "parameters": {
         "layers": [
             {"name": "道路", "order": 1, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "铁路", "order": 2, "osm_tags": "railway=*", "symbol_type": "LineSymbol"},
             {"name": "地铁", "order": 3, "osm_tags": "railway=subway", "symbol_type": "LineSymbol"},
             {"name": "公交站", "order": 4, "osm_tags": "highway=bus_stop", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "交通图需展示道路网络层次，按道路等级和交通工具类型分层",
     "description": "交通图的图层配置决策"},
    {"label": "CartographicDecision", "name": "tourism_color_scheme", "decision_type": "COLOR_SCHEME",
     "map_type": "tourism", "audience_level": "public", "priority": "high",
     "parameters": {
         "palette": {"primary": "#dc2626", "secondary": "#f97316", "accent": "#eab308", "background": "#fef3c7"},
         "rules": ["POI使用暖色系突出标注", "水域保持蓝色基准", "背景使用浅暖色提高对比度"]
     },
     "rationale": "旅游图需要醒目配色吸引注意力，暖色系激发探索欲望",
     "description": "旅游图的配色方案决策"},
    {"label": "CartographicDecision", "name": "campus_symbol_scheme", "decision_type": "SYMBOL_SCHEME",
     "map_type": "campus", "audience_level": "public", "priority": "medium",
     "parameters": {
         "building": {"type": "AreaSymbol", "color": "#bfdbfe", "border": "#3b82f6", "opacity": 0.4},
         "road": {"type": "LineSymbol", "color": "#94a3b8", "weight": 2, "style": "solid"},
         "green_space": {"type": "AreaSymbol", "color": "#bbf7d0", "opacity": 0.3},
         "facility": {"type": "PointSymbol", "color": "#6366f1", "size": 6, "style": "circle"},
     },
     "rationale": "校园图使用清新配色和简洁符号，区分教学区与生活区",
     "description": "校园图的符号方案决策"},
    {"label": "CartographicDecision", "name": "food_annotation_rule", "decision_type": "ANNOTATION_RULE",
     "map_type": "food", "audience_level": "public", "priority": "medium",
     "parameters": {
         "font_family": "sans-serif",
         "title_size": 16,
         "label_size": 11,
         "label_color": "#1e293b",
         "halo_color": "#ffffff",
         "halo_width": 1.5,
         "placement": "offset_right",
         "collision_rule": "hide_overflow",
     },
     "rationale": "美食图标注需清晰可读，标注框有明显光晕确保在各种底色上可见",
     "description": "美食图的标注规则决策"},
    {"label": "CartographicDecision", "name": "basic_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "basic", "audience_level": "public", "priority": "medium",
     "parameters": {
         "layers": [
             {"name": "水系", "order": 1, "osm_tags": "waterway=*|natural=water", "symbol_type": "AreaSymbol"},
             {"name": "绿地", "order": 2, "osm_tags": "landuse=grass|leisure=park", "symbol_type": "AreaSymbol"},
             {"name": "道路", "order": 3, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "建筑", "order": 4, "osm_tags": "building=*", "symbol_type": "AreaSymbol"},
             {"name": "生活设施", "order": 5, "osm_tags": "amenity=*|shop=*", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "基础地图按自然-人工层次叠置，先自然地理后人工设施",
     "description": "基础地图的图层配置决策"},
    {"label": "CartographicDecision", "name": "administrative_color_scheme", "decision_type": "COLOR_SCHEME",
     "map_type": "administrative", "audience_level": "professional", "priority": "high",
     "parameters": {
         "palette": {"primary": "#1e40af", "secondary": "#7c3aed", "tertiary": "#db2777", "background": "#f8fafc"},
         "rules": ["行政边界用深色实线", "各级行政区使用区分色填充", "标注行政名称置于区域中心"]
     },
     "rationale": "行政区划图需要清晰的边界区分和层级色彩编码",
     "description": "行政区划图的配色方案决策"},
    {"label": "CartographicDecision", "name": "traffic_symbol_scheme", "decision_type": "SYMBOL_SCHEME",
     "map_type": "traffic", "audience_level": "public", "priority": "high",
     "parameters": {
         "motorway": {"type": "LineSymbol", "color": "#e892a2", "weight": 5, "style": "solid"},
         "trunk": {"type": "LineSymbol", "color": "#fbb38c", "weight": 4, "style": "solid"},
         "primary": {"type": "LineSymbol", "color": "#fcd69b", "weight": 3, "style": "solid"},
         "railway": {"type": "LineSymbol", "color": "#555555", "weight": 2, "style": "dashed"},
         "station": {"type": "PointSymbol", "color": "#dc2626", "size": 7, "style": "square"},
     },
     "rationale": "交通图使用暖色调区分道路等级，铁路用灰色虚线区分",
     "description": "交通图的符号方案决策"},
    {"label": "CartographicDecision", "name": "tourism_annotation_rule", "decision_type": "ANNOTATION_RULE",
     "map_type": "tourism", "audience_level": "public", "priority": "medium",
     "parameters": {
         "font_family": "serif",
         "title_size": 18,
         "label_size": 12,
         "label_color": "#1e3a5f",
         "halo_color": "#fef3c7",
         "halo_width": 2,
         "placement": "top_center",
         "collision_rule": "prioritize_high_rank",
     },
     "rationale": "旅游图标注需美观大方，衬线字体提升文化感，按景点热度决定显示优先级",
     "description": "旅游图的标注规则决策"},
    {"label": "CartographicDecision", "name": "campus_layer_config", "decision_type": "LAYER_CONFIG",
     "map_type": "campus", "audience_level": "public", "priority": "medium",
     "parameters": {
         "layers": [
             {"name": "绿地水体", "order": 1, "osm_tags": "landuse=grass|natural=water", "symbol_type": "AreaSymbol"},
             {"name": "道路", "order": 2, "osm_tags": "highway=*", "symbol_type": "LineSymbol"},
             {"name": "教学楼", "order": 3, "osm_tags": "building=university|building=school", "symbol_type": "AreaSymbol"},
             {"name": "宿舍", "order": 4, "osm_tags": "building=dormitory", "symbol_type": "AreaSymbol"},
             {"name": "服务设施", "order": 5, "osm_tags": "amenity=*", "symbol_type": "PointSymbol"},
         ]
     },
     "rationale": "校园图优先展示绿地与教学设施，按校园功能区层次叠置",
     "description": "校园图的图层配置决策"},

    # --- LayerConfig 实例 ---
    {"label": "LayerConfig", "name": "road_base_layer", "layer_name": "道路基层",
     "layer_order": 1, "visibility_default": True, "min_zoom": 8, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "highway=*", "symbol_type": "LineSymbol",
     "description": "道路网络基层，包含各级道路"},
    {"label": "LayerConfig", "name": "water_base_layer", "layer_name": "水域基层",
     "layer_order": 0, "visibility_default": True, "min_zoom": 6, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "natural=water|waterway=*", "symbol_type": "AreaSymbol",
     "description": "水域基层，位于所有图层最下方"},
    {"label": "LayerConfig", "name": "railway_thematic_layer", "layer_name": "铁路专题层",
     "layer_order": 2, "visibility_default": True, "min_zoom": 9, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "railway=*", "symbol_type": "LineSymbol",
     "description": "铁路专题层，交通图中覆盖在道路层之上"},
    {"label": "LayerConfig", "name": "poi_annotation_layer", "layer_name": "POI标注层",
     "layer_order": 10, "visibility_default": True, "min_zoom": 13, "max_zoom": 19,
     "data_source": "OpenStreetMap", "osm_tags": "tourism=*|amenity=*", "symbol_type": "PointSymbol",
     "description": "POI标注层，位于所有专题层之上，展示兴趣点标注"},
    # ===== 5大类本体扩展：地图整饰 / 主题 / 区域 / 媒介 / 受众 =====
    {"label": "MapElement", "name": "main_map", "element_type": "frame",
     "description": "主图（地图主体）"},
    {"label": "MapElement", "name": "inset_map", "element_type": "frame",
     "description": "附图（全国/全省位置示意图，小比例尺）"},
    {"label": "MapElement", "name": "title_decoration", "element_type": "decoration",
     "description": "图名：{区域}{主题}图，居中上方，黑体"},
    {"label": "MapElement", "name": "legend_decoration", "element_type": "decoration",
     "description": "图例：按图层符号自动生成，右下/左下"},
    {"label": "MapElement", "name": "scalebar_decoration", "element_type": "decoration",
     "description": "比例尺：按当前比例尺计算，下方居中"},
    {"label": "MapElement", "name": "northarrow_decoration", "element_type": "decoration",
     "description": "指北针：右上角"},
    {"label": "MapElement", "name": "annotation_decoration", "element_type": "decoration",
     "description": "附加文字说明（数据来源/制图时间/制图者）"},
    {"label": "MapSymbol", "name": "annotation_text_symbol", "symbol_type": "TextSymbol",
     "color": "#333333", "size": 12, "description": "注记文本符号"},
    {"label": "MapTheme", "name": "theme_traffic", "theme": "traffic", "description": "交通图主题"},
    {"label": "MapTheme", "name": "theme_tourism", "theme": "tourism", "description": "旅游图主题"},
    {"label": "MapTheme", "name": "theme_administrative", "theme": "administrative",
     "description": "行政区划图主题"},
    {"label": "MapTheme", "name": "theme_basic", "theme": "basic", "description": "基础地图主题"},
    {"label": "MapTheme", "name": "theme_terrain", "theme": "terrain", "description": "地形图主题"},
    {"label": "CartoRegion", "name": "region_city", "region_level": "市", "description": "市级制图区域"},
    {"label": "CartoRegion", "name": "region_province", "region_level": "省",
     "description": "省级制图区域"},
    {"label": "CartoRegion", "name": "region_nation", "region_level": "国家",
     "description": "国家级制图区域"},
    {"label": "DisplayMedia", "name": "media_print", "media": "纸质印刷", "description": "纸质印刷媒介"},
    {"label": "DisplayMedia", "name": "media_screen", "media": "电子屏幕", "description": "电子屏幕媒介"},
    {"label": "TargetAudience", "name": "audience_public", "audience": "公众", "description": "公众受众"},
    {"label": "TargetAudience", "name": "audience_expert", "audience": "专家", "description": "专家受众"},
    {"label": "TargetAudience", "name": "audience_student", "audience": "学生", "description": "学生受众"},
    {"label": "TargetAudience", "name": "audience_child", "audience": "儿童", "description": "儿童受众"},
    {"label": "MapProjection", "name": "gauss_kruger", "crs_code": "CGCS2000_GK", "surface": "圆柱",
     "deformation": "等角", "description": "高斯-克吕格投影（城市级）"},
    {"label": "MapProjection", "name": "lambert_conformal", "crs_code": "LCC", "surface": "圆锥",
     "deformation": "等角", "description": "兰伯特等角圆锥投影（省级）"},
    {"label": "MapProjection", "name": "albers_equal_area", "crs_code": "AEA", "surface": "圆锥",
     "deformation": "等积", "description": "阿尔伯斯等积圆锥投影（国家级）"},
    {"label": "CartographicData", "name": "dem_data", "data_source": "SRTM",
     "description": "DEM高程数据（等高线/晕渲）"},
    {"label": "CartographicData", "name": "admin_data", "data_source": "DataV GeoAtlas",
     "description": "行政区划边界数据"},
    # ---- Dataset 数据集（Theme requires / Data suitable_for） ----
    {"label": "Dataset", "name": "osm_vector_dataset", "dataset_name": "OSM矢量数据",
     "data_source": "OpenStreetMap Overpass", "format": "GeoJSON", "coverage": "全球",
     "license": "ODbL", "description": "道路/水系/POI等矢量要素数据源"},
    {"label": "Dataset", "name": "amap_poi_dataset", "dataset_name": "高德POI数据",
     "data_source": "高德地图API", "format": "JSON", "coverage": "中国",
     "license": "高德开放平台", "description": "餐厅/银行/医院等兴趣点数据源"},
    {"label": "Dataset", "name": "srtm_dem_dataset", "dataset_name": "SRTM DEM",
     "data_source": "NASA SRTM 30m", "format": "GeoTIFF", "coverage": "全球",
     "license": "公有领域", "resolution": "30m", "description": "高程模型数据源（等高线/山体阴影）"},
    {"label": "Dataset", "name": "datav_admin_dataset", "dataset_name": "DataV行政区划",
     "data_source": "DataV GeoAtlas", "format": "GeoJSON", "coverage": "中国",
     "license": "DataV", "description": "省/市/县行政边界数据源"},
    # ---- MapCase 地图案例（相似案例检索） ----
    {"label": "MapCase", "name": "case_traffic_wuhan_public", "case_id": "case_traffic_001",
     "map_type": "traffic", "region": "武汉市", "audience": "公众", "page_size": "A4 横向",
     "task_summary": "武汉市交通图，面向公众，突出道路与轨道交通",
     "artifact_ref": "map_1506ba8fca8b", "description": "武汉公众交通图案例"},
    {"label": "MapCase", "name": "case_admin_wuhan", "case_id": "case_admin_001",
     "map_type": "administrative", "region": "武汉市", "audience": "公众", "page_size": "A4 横向",
     "task_summary": "武汉市行政区划图，边界为主、水系道路为辅",
     "artifact_ref": "map_22e0541ef5d9", "description": "武汉行政区划图案例"},
    {"label": "MapCase", "name": "case_terrain_wuhan", "case_id": "case_terrain_001",
     "map_type": "terrain", "region": "武汉市", "audience": "公众", "page_size": "A4 横向",
     "task_summary": "武汉市地势图，DEM山体阴影+等高线",
     "artifact_ref": "map_af99c7bdbd01", "description": "武汉地势图案例"},
]


# ========== 本体关系初始数据 ==========

ONTOLOGY_RELATIONS: List[Dict[str, Any]] = [
    # MapElement → REPRESENTED_BY → MapSymbol
    {"from": "road_element", "to": "highway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "道路要素由高速公路符号表示"}},
    {"from": "railway_element", "to": "railway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "铁路要素由铁路符号表示"}},
    {"from": "waterway_element", "to": "waterway_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "水系要素由水系符号表示"}},
    {"from": "building_element", "to": "building_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "建筑要素由建筑符号表示"}},
    {"from": "poi_element", "to": "poi_symbol", "type": "REPRESENTED_BY",
     "properties": {"description": "兴趣点要素由POI符号表示"}},

    # MapElement → SOURCED_FROM → CartographicData
    {"from": "road_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "道路数据来源于OSM"}},
    {"from": "building_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "建筑数据来源于OSM"}},
    {"from": "poi_element", "to": "osm_data", "type": "SOURCED_FROM",
     "properties": {"description": "POI数据来源于OSM"}},
    {"from": "poi_element", "to": "local_landmark_data", "type": "SOURCED_FROM",
     "properties": {"description": "POI数据降级来源于本地地标库"}},

    # MapElement → INFLUENCED_BY → InfluencingFactor
    {"from": "road_element", "to": "scale_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "道路要素的显示受比例尺影响"}},
    {"from": "road_element", "to": "purpose_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "道路要素的选取受地图用途影响"}},
    {"from": "poi_element", "to": "purpose_factor", "type": "INFLUENCED_BY",
     "properties": {"description": "POI要素的选取受地图用途影响"}},

    # InfluencingFactor → DETERMINES → MapSymbol
    {"from": "color_constraint", "to": "poi_symbol", "type": "DETERMINES",
     "properties": {"description": "色彩约束决定POI符号的颜色选择"}},
    {"from": "purpose_factor", "to": "highway_symbol", "type": "DETERMINES",
     "properties": {"description": "地图用途决定道路符号的样式"}},

    # CartographicData → REQUIRES → MapProjection
    {"from": "osm_data", "to": "wgs84", "type": "REQUIRES",
     "properties": {"description": "OSM数据使用WGS84坐标系"}},
    {"from": "osm_data", "to": "web_mercator", "type": "REQUIRES",
     "properties": {"description": "OSM数据在Web展示时转换为Web墨卡托投影"}},

    # 连接新本体与现有MapType节点
    {"from": "traffic", "to": "road_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "交通图包含道路要素"}},
    {"from": "traffic", "to": "railway_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "交通图包含铁路要素"}},
    {"from": "tourism", "to": "poi_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "旅游图包含POI要素"}},
    {"from": "campus", "to": "building_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "校园图包含建筑要素"}},
    {"from": "basic", "to": "waterway_element", "type": "CONTAINS_ELEMENT",
     "properties": {"description": "基础图包含水系要素"}},

    # --- 决策关系链：MapType → HAS_DECISION → CartographicDecision ---
    {"from": "traffic", "to": "traffic_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "交通图关联图层配置决策"}},
    {"from": "traffic", "to": "traffic_symbol_scheme", "type": "HAS_DECISION",
     "properties": {"description": "交通图关联符号方案决策"}},
    {"from": "tourism", "to": "tourism_color_scheme", "type": "HAS_DECISION",
     "properties": {"description": "旅游图关联配色方案决策"}},
    {"from": "tourism", "to": "tourism_annotation_rule", "type": "HAS_DECISION",
     "properties": {"description": "旅游图关联标注规则决策"}},
    {"from": "campus", "to": "campus_symbol_scheme", "type": "HAS_DECISION",
     "properties": {"description": "校园图关联符号方案决策"}},
    {"from": "campus", "to": "campus_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "校园图关联图层配置决策"}},
    {"from": "food", "to": "food_annotation_rule", "type": "HAS_DECISION",
     "properties": {"description": "美食图关联标注规则决策"}},
    {"from": "basic", "to": "basic_layer_config", "type": "HAS_DECISION",
     "properties": {"description": "基础地图关联图层配置决策"}},
    {"from": "administrative", "to": "administrative_color_scheme", "type": "HAS_DECISION",
     "properties": {"description": "行政区划图关联配色方案决策"}},

    # --- 决策 → HAS_LAYER → LayerConfig ---
    {"from": "traffic_layer_config", "to": "road_base_layer", "type": "HAS_LAYER",
     "properties": {"description": "交通图图层配置包含道路基层"}},
    {"from": "traffic_layer_config", "to": "railway_thematic_layer", "type": "HAS_LAYER",
     "properties": {"description": "交通图图层配置包含铁路专题层"}},
    {"from": "basic_layer_config", "to": "water_base_layer", "type": "HAS_LAYER",
     "properties": {"description": "基础地图图层配置包含水域基层"}},
    {"from": "basic_layer_config", "to": "poi_annotation_layer", "type": "HAS_LAYER",
     "properties": {"description": "基础地图图层配置包含POI标注层"}},

    # --- InfluencingFactor → INFLUENCES → CartographicDecision ---
    {"from": "purpose_factor", "to": "traffic_layer_config", "type": "INFLUENCES",
     "properties": {"description": "地图用途因素影响交通图层配置决策"}},
    {"from": "purpose_factor", "to": "campus_symbol_scheme", "type": "INFLUENCES",
     "properties": {"description": "地图用途因素影响校园图符号方案决策"}},
    {"from": "color_constraint", "to": "tourism_color_scheme", "type": "INFLUENCES",
     "properties": {"description": "色彩约束因素影响旅游图配色方案决策"}},
    {"from": "color_constraint", "to": "administrative_color_scheme", "type": "INFLUENCES",
     "properties": {"description": "色彩约束因素影响行政区划图配色方案决策"}},
    {"from": "scale_factor", "to": "basic_layer_config", "type": "INFLUENCES",
     "properties": {"description": "比例尺因素影响基础地图图层配置的缩放范围"}},
    # ===== 5大类本体关系：主题-数据 / 区域-投影 / 整饰 / 符号冲突 / 影响因素 =====
    {"from": "theme_traffic", "to": "road_element", "type": "REQUIRES",
     "properties": {"description": "交通图需要道路要素"}},
    {"from": "theme_traffic", "to": "railway_element", "type": "REQUIRES",
     "properties": {"description": "交通图需要铁路要素"}},
    {"from": "theme_traffic", "to": "waterway_element", "type": "REQUIRES",
     "properties": {"description": "交通图需要水系作底图要素"}},
    {"from": "theme_tourism", "to": "poi_element", "type": "REQUIRES",
     "properties": {"description": "旅游图需要旅游/设施POI要素"}},
    {"from": "theme_tourism", "to": "waterway_element", "type": "REQUIRES",
     "properties": {"description": "旅游图需要水系作底图要素"}},
    {"from": "theme_administrative", "to": "admin_data", "type": "REQUIRES",
     "properties": {"description": "行政区划图需要区划边界数据"}},
    {"from": "theme_terrain", "to": "dem_data", "type": "REQUIRES",
     "properties": {"description": "地形图需要DEM高程数据"}},
    {"from": "region_city", "to": "gauss_kruger", "type": "SUITABLE_FOR",
     "properties": {"description": "市级区域适配高斯-克吕格/UTM投影"}},
    {"from": "region_city", "to": "web_mercator", "type": "SUITABLE_FOR",
     "properties": {"description": "市级区域亦适配Web墨卡托（网页显示）"}},
    {"from": "region_province", "to": "lambert_conformal", "type": "SUITABLE_FOR",
     "properties": {"description": "省级区域适配兰伯特等角圆锥投影"}},
    {"from": "region_nation", "to": "albers_equal_area", "type": "SUITABLE_FOR",
     "properties": {"description": "国家级区域适配阿尔伯斯等积投影"}},
    {"from": "main_map", "to": "title_decoration", "type": "HAS_DECORATION",
     "properties": {"description": "主图包含图名"}},
    {"from": "main_map", "to": "legend_decoration", "type": "HAS_DECORATION",
     "properties": {"description": "主图包含图例"}},
    {"from": "main_map", "to": "scalebar_decoration", "type": "HAS_DECORATION",
     "properties": {"description": "主图包含比例尺"}},
    {"from": "main_map", "to": "northarrow_decoration", "type": "HAS_DECORATION",
     "properties": {"description": "主图包含指北针"}},
    {"from": "poi_symbol", "to": "annotation_text_symbol", "type": "CONFLICT_WITH",
     "properties": {"description": "POI符号与注记文本存在压盖冲突，需避让"}},
    {"from": "highway_symbol", "to": "annotation_text_symbol", "type": "CONFLICT_WITH",
     "properties": {"description": "道路符号与注记文本存在压盖冲突，需避让"}},
    {"from": "theme_traffic", "to": "scale_factor", "type": "AFFECTS",
     "properties": {"description": "交通图主题影响比例尺选择"}},
    {"from": "theme_tourism", "to": "purpose_factor", "type": "AFFECTS",
     "properties": {"description": "旅游图主题影响用途因素"}},
    {"from": "audience_public", "to": "purpose_factor", "type": "AFFECTS",
     "properties": {"description": "公众受众影响制图用途"}},
    {"from": "audience_child", "to": "color_constraint", "type": "AFFECTS",
     "properties": {"description": "儿童受众影响配色（更鲜艳明快）"}},
    {"from": "media_print", "to": "color_constraint", "type": "AFFECTS",
     "properties": {"description": "纸质印刷影响色彩规范"}},
    # ---- 决策关系补充（研究基线版 §6：KG 不仅存知识，还要能“做决策”） ----
    {"from": "scale_factor", "to": "road_element", "type": "CONTROLS",
     "properties": {"description": "比例尺控制要素选取（制图综合：小比例尺只保留主干要素）"}},
    {"from": "scale_factor", "to": "poi_element", "type": "CONTROLS",
     "properties": {"description": "比例尺控制POI数量（缩小后先保留重要地标，其次次要）"}},
    {"from": "theme_traffic", "to": "osm_vector_dataset", "type": "REQUIRES",
     "properties": {"description": "交通图需要OSM矢量数据（道路/轨道）"}},
    {"from": "theme_terrain", "to": "srtm_dem_dataset", "type": "REQUIRES",
     "properties": {"description": "地势图需要SRTM DEM数据"}},
    {"from": "theme_administrative", "to": "datav_admin_dataset", "type": "REQUIRES",
     "properties": {"description": "行政区划图需要DataV行政边界数据"}},
    {"from": "theme_tourism", "to": "amap_poi_dataset", "type": "REQUIRES",
     "properties": {"description": "旅游图需要POI数据（景点/设施）"}},
    {"from": "osm_vector_dataset", "to": "highway_symbol", "type": "SUITABLE_FOR",
     "properties": {"description": "OSM道路数据适配线状道路符号"}},
    {"from": "amap_poi_dataset", "to": "poi_symbol", "type": "SUITABLE_FOR",
     "properties": {"description": "POI数据适配点状兴趣点符号"}},
    {"from": "srtm_dem_dataset", "to": "contour_symbol", "type": "SUITABLE_FOR",
     "properties": {"description": "DEM数据适配等高线符号"}},
    {"from": "audience_public", "to": "poi_symbol", "type": "AFFECTS",
     "properties": {"description": "公众受众影响兴趣点符号（更直观的象形符号）"}},
    {"from": "audience_child", "to": "poi_symbol", "type": "AFFECTS",
     "properties": {"description": "儿童受众影响符号（鲜艳象形）"}},
    {"from": "case_traffic_wuhan_public", "to": "case_admin_wuhan", "type": "SIMILAR_TO",
     "properties": {"description": "交通图案例与行政图案例区域相似"}},
]


def get_ontology_summary() -> Dict[str, Any]:
    """获取本体概要信息

    Returns:
        包含类别数量、节点数量、关系数量和类别详情的字典
    """
    return {
        "class_count": len(ONTOLOGY_CLASSES),
        "classes": list(ONTOLOGY_CLASSES.keys()),
        "node_count": len(ONTOLOGY_NODES),
        "relation_count": len(ONTOLOGY_RELATIONS),
        "class_details": {
            k: {
                "description": v["description"],
                "color": v["color"],
                "subtypes": v["subtypes"],
            }
            for k, v in ONTOLOGY_CLASSES.items()
        }
    }
