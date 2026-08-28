# -*- coding: utf-8 -*-
"""知识图谱第三轮扩充：地形图/地貌/遥感/电子地图/分幅编号/坐标基准/地图设计/注记字体/量算精度 等地图学知识 -> Neo4j（幂等 MERGE）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "whu-2401")
driver = GraphDatabase.driver(URI, auth=AUTH)

# (id, label, question, answer, [(rel_to_label, rel_type), ...])
RULES = [
    # ============ 地形图与地貌 ============
    ("topo_contour", "TopographicMap",
     "等高线表示地貌的规则",
     "等高线是连接高程相等点的闭合曲线，等高距按比例尺与地貌特征确定（地形图有标准等高距系列）；计曲线（每5条首曲线加粗）与首曲线（细线）分级；等高线密集表示坡度陡、稀疏表示坡度缓；等高线注记数字朝向高处（上坡方向）；陡崖用示坡线/陡崖符号表达。",
     [("MapElement", "REPRESENTS"), ("ScaleRule", "RELATES_TO")]),
    ("topo_hypsometric", "TopographicMap",
     "分层设色法表示地貌",
     "分层设色法按高程带分层设色（低地绿→高原黄→山地棕→雪线白），层间颜色过渡自然、色带反映高程梯度；分层设色常与等高线配合，图例必须列出各色带高程范围。",
     [("ColorSchemeRule", "GOVERNS"), ("MapElement", "REPRESENTS")]),
    ("topo_shading", "TopographicMap",
     "晕渲法表示地貌",
     "晕渲法（山影法）用阴影表达地形起伏，光源通常来自西北方向，受光面亮、背光面暗；晕渲强度与坡度相关，可与分层设色/等高线叠置表达立体感；图面保持清晰不过暗。",
     [("MapElement", "REPRESENTS"), ("Style", "GOVERNS")]),
    ("topo_dem", "TopographicMap",
     "DEM与数字地形分析",
     "数字高程模型（DEM）是规则格网存储的高程数据，可派生坡度、坡向、山体阴影、等高线；分析用 DEM 分辨率需与比例尺匹配（格网大小对应地面分辨率）；DEM 精度取决于数据源（SRTM/ASTER/LiDAR）。",
     [("CartographicData", "SOURCES"), ("Tool", "SUPPORTS")]),
    ("topo_relief_types", "TopographicMap",
     "基本地貌类型与表示",
     "基本地貌类型：平原（高程低、等高线稀疏）、丘陵（相对高差小）、山地（等高线密集）、高原（顶面平坦边缘陡）；不同地貌用不同等高线形态与地貌符号组合表达。",
     [("MapElement", "REPRESENTS")]),
    # ============ 遥感制图 ============
    ("remote_image_map", "RemoteSensingMap",
     "影像地图的制作要点",
     "影像地图以遥感影像为底图叠加矢量要素与注记；影像需经几何校正（配准到目标坐标系）、辐射增强；影像分辨率与比例尺匹配，重要地物叠加线划符号突出；影像需注记成像时间与波段。",
     [("MapType", "DESCRIBES"), ("CartographicData", "SOURCES")]),
    ("remote_interpretation", "RemoteSensingMap",
     "遥感影像地物判读要素",
     "影像判读依据色调、形状、大小、纹理、阴影、位置、相关关系七要素识别地物：水体深色光滑、植被红绿波段特征、道路线状规则；判读需结合实地与已有资料验证。",
     [("CartographicData", "SOURCES")]),
    ("remote_landcover", "RemoteSensingMap",
     "遥感专题信息提取",
     "利用遥感数据提取土地利用/植被/水体等专题信息：监督分类需样本、非监督分类需后处理，分类精度需混淆矩阵评价；专题成果需与制图综合结合。",
     [("MapType", "DESCRIBES"), ("Tool", "SUPPORTS")]),
    # ============ 电子地图 ============
    ("digital_webgis", "DigitalMap",
     "电子地图/WebGIS 的特点",
     "电子地图基于屏幕显示、可交互（缩放/平移/查询），数据组织为矢量或栅格瓦片；WebGIS 采用分层渲染与符号化，矢量瓦片支持动态样式；电子地图需考虑屏幕分辨率与显示层级。",
     [("Tool", "ENABLES"), ("LayerConfig", "HAS_LAYER")]),
    ("digital_tiles", "DigitalMap",
     "地图瓦片与 LOD",
     "地图瓦片按金字塔结构分级切分（Web墨卡托 3857 标准 256px 瓦片），缩放级别对应 LOD（Level of Detail）；矢量瓦片按要素几何与层级抽稀（重要要素高层级保留），瓦片命名遵循 z/x/y 规则。",
     [("ScaleRule", "RELATES_TO"), ("LayerConfig", "HAS_LAYER")]),
    ("digital_render", "DigitalMap",
     "屏幕地图渲染规范",
     "屏幕地图符号尺寸需考虑像素密度（普通屏/高分屏），最小可点选目标不小于 22px；线宽与注记字号随缩放自适应；渲染层级（z-index）决定要素压盖关系，重要要素置顶。",
     [("MapSymbol", "GOVERNS"), ("Style", "GOVERNS")]),
    # ============ 地图分幅与编号 ============
    ("sheet_division", "MapCompilationRule",
     "地图分幅方法",
     "地图分幅分矩形分幅与经纬线（梯形）分幅：大比例尺图用矩形分幅（按坐标格网），中小比例尺国家基本比例尺地形图用经纬线分幅；分幅使相邻图幅拼接无缝、便于检索。",
     [("ScaleRule", "RELATES_TO")]),
    ("sheet_number", "MapCompilationRule",
     "地形图图幅编号规则",
     "国家基本比例尺地形图按行列编号（如 1:100万 图幅按经差6°纬差4°分带编号，再按 2^n 倍率细分到 1:50万/1:25万/1:10万/1:5万/1:1万等）；编号反映图幅位置与比例尺。",
     [("MapProjection", "REFINES")]),
    ("sheet_legend_spec", "MapCompilationRule",
     "地形图图式规范",
     "地形图图式（图例规范）规定各要素的符号、线型、颜色、注记字体标准（如 GB 图式）；制图必须遵循图式，保证同图幅内符号统一、图幅间可拼接。",
     [("MapSymbol", "GOVERNS")]),
    # ============ 坐标基准 ============
    ("datum_ellipsoid", "MapProjection",
     "地球椭球与坐标系基准",
     "地球形状用椭球近似（我国常用 CGCS2000 椭球，国际上 WGS84 椭球）；坐标系基准（datum）定义椭球与大地水准面的关系，不同基准坐标有系统差；跨基准数据需转换（如 WGS84 与 CGCS2000 相差约几十厘米）。",
     [("CartographicData", "DEFINES")]),
    ("datum_gauss_zone", "MapProjection",
     "高斯-克吕格投影分带",
     "高斯-克吕格投影按经差 6°或 3°分带（6°带用于 1:2.5万-1:50万，3°带用于 1:1万及更大比例尺）；中央经线为 X 轴、赤道为 Y 轴；带号与中央经线按 L0=6n-3（6°带）计算；跨带拼接需坐标转换。",
     [("ScaleRule", "CONSTRAINS")]),
    # ============ 地图设计原理 ============
    ("design_visual_variables", "MapDesignRule",
     "地图视觉变量体系",
     "视觉变量：形状、尺寸、方向、颜色（色相/明度/饱和度）、纹理、位置；定性数据用形状与色相区分，定量数据用尺寸与明度渐变；视觉变量选择需符合数据特性与知觉习惯。",
     [("MapSymbol", "GOVERNS"), ("CartographicDecision", "INFLUENCES")]),
    ("design_semiotics", "MapDesignRule",
     "地图符号学（地图语言）",
     "地图语言由符号系统、注记系统与色彩系统构成，遵循『约定俗成』原则：符号应直观、可联想（蓝色水系、绿色植被）、规范统一；地图符号学（Bertin 符号学）研究符号与地理信息对应关系。",
     [("MapSymbol", "REPRESENTS"), ("CartographicDecision", "INFLUENCES")]),
    ("design_perception", "MapDesignRule",
     "视知觉与格式塔原则",
     "地图设计遵循视知觉规律：接近性（邻近要素成组）、相似性（相似符号成类）、连续性（线状要素连贯）、闭合性（完整图形优先）、图底关系（主体与背景区分）；设计时避免视觉混乱。",
     [("CartographicDecision", "INFLUENCES")]),
    ("design_layout_balance", "MapDesignRule",
     "图面配置与平衡",
     "图面配置遵循平衡、对比、统一原则：主图置于中央视觉焦点，附图/图例/比例尺/指北针分区布置不压主图；注记不跨图廓；整幅图视觉重心稳定、主次分明。",
     [("MapElement", "ORGANIZES")]),
    # ============ 注记字体 ============
    ("annotation_font_rule", "LabelRule",
     "注记字体与字号规范",
     "注记字体按要素类别分级（水系斜体、山峰等线体、行政名称宋体/黑体）；字号反映等级（城市名>区县名>乡镇名>地物名），一般 8-20px；注记字体清晰易读、笔画不粘连、方向横向为主。",
     [("AnnotationRuleDecision", "INFLUENCES"), ("ScaleRule", "RELATES_TO")]),
    # ============ 地图定向 ============
    ("orientation_true_mag", "MapCompilationRule",
     "地图定向与磁偏角",
     "地图定向分真北定向、磁北定向、坐标北定向；需标注指北针与磁偏角（磁北与真北夹角）；地形图图廓标注磁偏角数值，供方位换算；大比例尺图必须标注三北方向。",
     [("MapProjection", "REFINES"), ("MapElement", "ORGANIZES")]),
    # ============ 地图集 ============
    ("atlas_structure", "MapCompilationRule",
     "地图集的编制原则",
     "地图集按统一设计编制：图组结构（序图组/专题图组/区域图组）、统一比例尺体系、统一符号与配色、统一图例与整饰；各图幅内容协调不重复，反映区域全貌与专题规律。",
     [("MapType", "DESCRIBES"), ("MapElement", "ORGANIZES")]),
    # ============ 地图量算与应用 ============
    ("measure_distance_area", "MapUseRule",
     "地图量算方法",
     "地图量算：距离量算（比例尺换算，曲折线用曲线计/分段量算）、面积量算（方格法/求积仪/积分法）、坡度量算（等高线间高差与平距）；量算精度取决于比例尺与量算工具。",
     [("ScaleRule", "RELATES_TO"), ("Tool", "SUPPORTS")]),
    ("measure_slope", "MapUseRule",
     "坡度与坡向量算",
     "坡度由等高线间距与高差计算（tanθ=高差/平距）；坡向为坡面朝向（影响光照/水文）；数字环境下用 DEM 计算坡度坡向栅格，结果需平滑去噪。",
     [("CartographicData", "SOURCES"), ("Tool", "SUPPORTS")]),
    # ============ 地图精度与质量 ============
    ("quality_position_accuracy", "MapUseRule",
     "地图位置精度要求",
     "地图位置精度（中误差）与比例尺相关：1:1万图上点位中误差一般不超过图上0.1mm；精度评价用检查点对比（RMSE）；数字地图需满足矢量数据几何精度要求。",
     [("CartographicData", "REQUIRES")]),
    ("quality_currency", "MapUseRule",
     "地图现势性与内容精度",
     "地图现势性指数据时效，内容精度包括要素完整性、属性准确性、注记正确性；制图完成后需质检（要素有无缺漏、属性是否对应、图例是否一致、注记是否压盖）。",
     [("CartographicData", "REQUIRES"), ("Tool", "SUPPORTS")]),
    # ============ 制图专家整体知识 ============
    ("expert_workflow", "CartographicExpert",
     "地图制图的完整流程",
     "制图流程：需求分析（用途/比例尺/区域）→ 数据收集（矢量/栅格/属性）→ 坐标统一与投影选择 → 要素分层与数据整理 → 符号化与配色 → 注记配置 → 制图综合（取舍/简化）→ 图面整饰（图名/图例/比例尺/指北针）→ 质量检查 → 输出交付；各环节遵循对应制图规范。",
     [("CartographicDecision", "DETERMINES"), ("MapType", "GOVERNS")]),
    ("expert_decision_chain", "CartographicExpert",
     "制图决策的考虑维度",
     "制图决策综合考虑六维：用途（地图类型）、比例尺、区域特征、数据可用性、受众、表达方法；先定地图类型与比例尺，再定投影、要素分层、符号与配色，最后注记与整饰。",
     [("CartographicDecision", "INFLUENCES"), ("InfluencingFactor", "DETERMINES")]),
    ("expert_quality_check", "CartographicExpert",
     "制图质量检查清单",
     "质量检查清单：1)要素完整性（无缺漏）；2)属性与几何对应；3)注记无压盖、横向为主；4)图例与图内符号一致；5)投影与坐标统一；6)配色协调可读；7)比例尺/指北针/图名齐全；8)拓扑无错误。",
     [("Tool", "SUPPORTS"), ("CartographicData", "REQUIRES")]),
    ("expert_thematic_suitability", "CartographicExpert",
     "专题图方法适用性选择",
     "按数据与现象选择表达方法：面域统计用分级统计图法、连续分布用等值线法、离散点数量用点值法、点状要素数值用定点符号法、流动现象用动线法、分布范围用范围法；方法选择影响信息传达。",
     [("MapType", "DESCRIBES"), ("CartographicDecision", "INFLUENCES")]),
]

def run():
    with driver.session() as s:
        n = 0
        for rid, label, q, a, rels in RULES:
            props = {"question": q, "answer": a, "category": "地图学理论", "source": "carto-science-3"}
            s.run(f"MERGE (n:{label} {{name:$name}}) SET n += $props", name=rid, props=props)
            for rel_to, rel_type in rels:
                s.run(
                    "MATCH (a:%s {name:$aname}) MATCH (b) "
                    "WHERE any(l IN labels(b) WHERE l=$blabel) "
                    "WITH a, b LIMIT 3 MERGE (a)-[r:%s]->(b) SET r.source='carto-science-3'"
                    % (label, rel_type),
                    aname=rid, blabel=rel_to,
                )
            n += 1
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        rules = s.run("MATCH (n) WHERE n.question IS NOT NULL RETURN count(n) AS c").single()["c"]
        labels = s.run("MATCH (n) RETURN DISTINCT labels(n)[0] AS l ORDER BY l").values()
        print(f"本轮新增规则={n}")
        print(f"图谱总计: nodes={nodes} relations={rels} 知识规则节点={rules}")
        print("标签:", ", ".join(str(x[0]) for x in labels))
    driver.close()

run()
