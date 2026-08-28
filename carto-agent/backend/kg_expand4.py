# -*- coding: utf-8 -*-
"""知识图谱第四轮扩充：投影数学/制图自动化算法/地图阅读/数据模型/统计地图/质量评价 等 -> Neo4j（幂等 MERGE）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "whu-2401")
driver = GraphDatabase.driver(URI, auth=AUTH)

RULES = [
    # ============ 投影数学基础 ============
    ("proj_axes", "MapProjection",
     "地图投影的轴分类",
     "地图投影按投影轴方位分：正轴投影（投影轴与地轴重合）、横轴投影（投影轴垂直于地轴，如高斯-克吕格）、斜轴投影（投影轴与地轴斜交，如斜轴方位投影）；按变形性质分等角、等积、等距、任意。",
     [("CartographicDecision", "INFLUENCES")]),
    ("proj_tangent", "MapProjection",
     "投影面与投影方式",
     "地图投影按投影面分平面（方位投影）、圆柱面（墨卡托/高斯）、圆锥面（兰伯特/阿尔伯斯）；按投影面与球面的关系分切投影（相切一条线/一点）与割投影（相割两条线，割线处无变形）；割投影可减小变形范围。",
     [("MapProjection", "REFINES")]),
    ("proj_mercator", "MapProjection",
     "墨卡托投影特性",
     "墨卡托投影是正轴等角圆柱投影，等角航线（恒向线）为直线、适合航海导航，但面积变形随纬度增大（高纬地区面积严重放大）；Web墨卡托（EPSG:3857）用球体近似，是网络地图标准。",
     [("MapProjection", "CONSTRAINS")]),
    # ============ 制图自动化算法 ============
    ("algo_generalize", "GeneralizationRule",
     "制图综合的常用算法",
     "制图综合算法：Douglas-Peucker（线状简化，保留关键点）、Ramer 简化、凸包/凹包（面聚合）、Douglas 曲线综合、Liang-Barsky；面合并用多边形布尔运算（union/difference）；要素移位用位移场模型。",
     [("Tool", "SUPPORTS"), ("CartographicDecision", "INFLUENCES")]),
    ("algo_interp", "MapUseRule",
     "空间插值方法",
     "空间插值用于由离散点生成连续面：IDW（反距离加权）、克里金（Kriging，考虑空间自相关）、样条插值（Spline）、TIN 三角网插值；方法选择取决于数据分布与现象类型，插值结果需交叉验证精度。",
     [("CartographicData", "SOURCES"), ("Tool", "SUPPORTS")]),
    ("algo_voronoi", "MapUseRule",
     "Voronoi 与 Delaunay",
     "Voronoi 图将平面划分为距离最近生成点的区域，用于邻近分析、设施服务区划分；Delaunay 三角网是 Voronoi 对偶，用于构建 TIN、地形建模、空间关系分析。",
     [("Tool", "SUPPORTS")]),
    # ============ 数据模型 ============
    ("data_model_vector_raster", "DataRule",
     "矢量与栅格数据模型",
     "矢量模型以点线面几何+属性表表达离散要素（精确、可量算、小数据量），栅格模型以像元网格表达连续面（简单、利于叠置分析，但分辨率决定精度）；两者可互转（矢栅转换）。",
     [("CartographicData", "DEFINES"), ("Tool", "SUPPORTS")]),
    ("data_format_geojson", "DataRule",
     "常见空间数据格式",
     "常见空间格式：GeoJSON（矢量，Web 标准）、Shapefile（shp/shx/dbf/prj/cpg 五件套）、GeoPackage（SQLite 容器，可含矢量栅格）、KML/KMZ（Google Earth）、GeoTIFF（栅格带坐标）；格式选择考虑平台兼容与数据量。",
     [("CartographicData", "DEFINES")]),
    ("data_topology_model", "DataRule",
     "拓扑数据模型",
     "拓扑数据模型存储节点-弧段-面片的拓扑关系（共享边界、连通性、邻接性），支持网络分析（路径/流）与拓扑查询；编辑时维护拓扑一致性，防止悬挂、伪节点、面裂缝。",
     [("CartographicData", "REQUIRES")]),
    # ============ 统计地图 ============
    ("theme_chart_local", "MapType",
     "图表定位法（柱状/饼图）",
     "图表定位法在要素点位放置统计图表（柱状图、饼图、玫瑰图）表达数量构成；图表尺寸按比例分级、颜色分类目；图表不重叠、注记清晰，图例说明单位与比例。",
     [("MapSymbol", "VISUALIZES"), ("CartographicDecision", "INFLUENCES")]),
    ("theme_classification_methods", "MapType",
     "专题数据分级方法",
     "数据分级方法：等间距（等差分级）、等频（分位，每级数量相近）、自然断点（Jenks，组内方差最小）、标准差分级、几何间隔（适应偏态分布）；分级数一般 4-7 级，方法与数据分布匹配。",
     [("CartographicDecision", "INFLUENCES")]),
    ("theme_normalize", "MapType",
     "专题统计的归一化",
     "分级统计前对数据进行归一化：总量除以面积（密度）、除以人口（人均）等，避免面积大区域天然数值高导致的视觉误导；归一化后分级更反映真实空间差异。",
     [("CartographicDecision", "INFLUENCES")]),
    # ============ 地图阅读 ============
    ("reading_map_reading", "MapUseRule",
     "地图阅读的基本方法",
     "地图阅读按序：图名与比例尺确定范围与精度 → 图例理解符号 → 经纬网/指北针定向 → 分层判读要素（水系/地貌/居民地/交通）→ 量算（距离/面积/方位）→ 综合分析空间关系；读图需结合地图投影与坐标系知识。",
     [("MapElement", "ORGANIZES"), ("MapProjection", "REFINES")]),
    ("reading_navigation", "MapUseRule",
     "地图导航与方位",
     "地图方位：图上北向（指北针）对应实地北向，方位角从北起算顺时针；实际导航需考虑磁偏角（磁北-真北差值，随地区与时间变化）；电子地图 GPS 定位用 WGS84 坐标。",
     [("MapProjection", "REFINES")]),
    # ============ 质量评价 ============
    ("quality_eval_system", "MapUseRule",
     "地图质量评价体系",
     "地图质量评价维度：数学基础（投影/坐标正确性）、内容完整性（要素无缺漏）、几何精度（位置中误差）、属性准确性、现势性（数据时效）、易读性（符号/注记/配色清晰）、艺术性（整饰美观）；评价用检查点抽样与专家评图结合。",
     [("CartographicData", "REQUIRES")]),
    ("quality_error_sources", "MapUseRule",
     "制图误差来源",
     "制图误差来源：数据源误差（测量/遥感分辨率）、投影与坐标转换误差、制图综合误差（取舍/简化）、符号化误差（定位/尺寸）、数字化与编辑误差；误差分析帮助控制成图质量。",
     [("CartographicData", "REQUIRES")]),
    # ============ 制图规范细节 ============
    ("spec_layer_naming", "MapCompilationRule",
     "图层命名与组织规范",
     "图层命名规范：类型前缀（水系/道路/居民地/境界/注记/底图）+ 等级后缀（概览/市域/城区/详图）；图层按空间关系分层（底图-水系-道路-注记），同一图层内要素类型统一；命名清晰便于管理检索。",
     [("LayerConfig", "HAS_LAYER")]),
    ("spec_annotation_levels", "LabelRule",
     "注记分级与抽稀",
     "注记按要素等级分级显示：高等级（城市/主要水系）常显，低等级（次要街道/小地物）按缩放级别与密度抽稀；抽稀保证注记不重叠、图面清晰，重要注记优先级最高。",
     [("AnnotationRuleDecision", "INFLUENCES"), ("ScaleRule", "RELATES_TO")]),
    ("spec_web_interaction", "DigitalMap",
     "Web 地图交互规范",
     "Web 地图交互：滚轮/双指缩放、拖拽平移、点击查询（popup）、图层切换、测距测面工具；交互反馈及时（加载态/悬停高亮）；缩放级别限制（min/maxZoom）防止过度放大失真。",
     [("Tool", "ENABLES")]),
    # ============ 制图专家流程细节 ============
    ("expert_data_check", "CartographicExpert",
     "制图前数据检查",
     "制图前检查：数据格式与坐标系统一、几何有效性（自交/闭合/重复点）、属性字段完整（必填字段无空值）、要素完整性（关键要素无缺失）、数据现势性；数据检查可提前发现并规避制图错误。",
     [("CartographicData", "REQUIRES"), ("Tool", "SUPPORTS")]),
    ("expert_annotation_placement", "CartographicExpert",
     "注记配置的整体流程",
     "注记配置流程：定注记分级（按要素等级）→ 定字体字号配色 → 初始放置（点右上方/线沿线/面居中）→ 冲突检测与避让 → 密度控制（抽稀/合并）→ 检查横向优先与可读性；注记完成后再检查压盖。",
     [("AnnotationRuleDecision", "INFLUENCES"), ("ConflictRule", "GOVERNS")]),
]

def run():
    with driver.session() as s:
        n = 0
        for rid, label, q, a, rels in RULES:
            props = {"question": q, "answer": a, "category": "地图学进阶", "source": "carto-science-4"}
            s.run(f"MERGE (n:{label} {{name:$name}}) SET n += $props", name=rid, props=props)
            for rel_to, rel_type in rels:
                s.run(
                    "MATCH (a:%s {name:$aname}) MATCH (b) "
                    "WHERE any(l IN labels(b) WHERE l=$blabel) "
                    "WITH a, b LIMIT 3 MERGE (a)-[r:%s]->(b) SET r.source='carto-science-4'"
                    % (label, rel_type),
                    aname=rid, blabel=rel_to,
                )
            n += 1
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        rules = s.run("MATCH (n) WHERE n.question IS NOT NULL RETURN count(n) AS c").single()["c"]
        print(f"本轮新增规则={n}")
        print(f"图谱总计: nodes={nodes} relations={rels} 知识规则节点={rules}")
    driver.close()

run()
