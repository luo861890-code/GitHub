# -*- coding: utf-8 -*-
"""知识图谱全方面扩充：35条问答知识 + 制图学/编辑规范规则 -> Neo4j（幂等 MERGE）"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "whu-2401")
driver = GraphDatabase.driver(URI, auth=AUTH)

KB_PATH = "../data/kg/cartography_kb.json"

# ============ 1. 35 条问答知识 -> CartographyRule ============
kb = json.load(open(KB_PATH, encoding="utf-8"))
# 知识分类 -> 关联到的已有图谱标签（建立语义关系）
KB_REL = {
    "基础概念": [("MapType", "GOVERNS"), ("CartographyRule", "EXPLAINS")],
    "地图类型": [("MapType", "DESCRIBES")],
    "制图规范": [("MapSymbol", "GOVERNS"), ("CartographyRule", "SPECIFIES")],
    "地图要素": [("MapElement", "REPRESENTS"), ("MapSymbol", "GOVERNS")],
    "OSM数据": [("CartographicData", "SOURCES")],
    "地图可视化": [("MapSymbol", "VISUALIZES"), ("Tool", "USES")],
    "空间分析": [("Tool", "IMplements")],
}

# ============ 2. 补充制图学规则（含编辑模式规范）============
# (id, label, question, answer, [(rel_to_label, rel_type), ...])
EXTRA_RULES = [
    # ---- 注记规则 ----
    ("label_horizontal_primary", "LabelRule",
     "地图注记应以横向排布为主",
     "注记文字原则上横向（水平）排布，保证易读性。仅当要素走向（如河流、道路）导致横向严重压盖或歧义时，才允许沿要素走向旋转注记（旋转角一般不超过45°）。修改注记方向应优先调整到横向。",
     [("MapElement", "GOVERNS"), ("AnnotationRuleDecision", "INFLUENCES")]),
    ("label_placement_point", "LabelRule",
     "点状要素注记的放置规则",
     "点状要素注记一般置于符号右上方（第一优先）、右方、上方，注记与符号之间留 0.5~1mm 间隔；避免压盖符号本体；同名注记不得重复出现。",
     [("MapSymbol", "GOVERNS"), ("PointElement", "REPRESENTS")]),
    ("label_placement_line", "LabelRule",
     "线状要素注记的放置规则",
     "线状要素（河流、道路）注记应沿要素走向分布，文字方向与线状走向一致；较长线状要素可分段重复注记；注记不得横跨压盖线要素符号。",
     [("LinearElement", "REPRESENTS")]),
    ("label_placement_area", "LabelRule",
     "面状要素注记的放置规则",
     "面状要素注记应置于面域内部中心附近，字号与面域面积相匹配；面域过小时注记可置于面外并加引线。",
     [("ArealElement", "REPRESENTS")]),
    ("label_conflict_avoid", "LabelRule",
     "注记冲突的避让规则",
     "注记之间、注记与符号之间不得相互压盖；发生冲突时优先保留等级较高要素的注记，低等级注记移位或删除；同图注记密度受 LABEL_DENSITY_LIMIT 约束，超限时按等级舍去次要注记。",
     [("ConflictRule", "GOVERNS")]),
    ("label_size_by_level", "LabelRule",
     "注记字号按要素等级分级",
     "注记字号反映要素重要程度分级：城市名>区县名>乡镇名>地物名；系统按 LABEL_STYLE 的 city/district/town/water/landmark/poi 六级分别设定字号与颜色，不可随意混用。",
     [("ScaleRule", "RELATES_TO")]),
    ("label_color_contrast", "LabelRule",
     "注记颜色需与背景要素形成对比",
     "注记颜色与所在底图要素需保持足够对比度；水体注记常用蓝色系、行政区名用深色，注记不得与同色系符号混淆。",
     [("ColorSchemeRule", "GOVERNS")]),
    # ---- 配色规则 ----
    ("color_hue_harmony", "ColorSchemeRule",
     "地图配色的色相协调原则",
     "整幅地图色调需统一协调，避免大面积高饱和对比色并置；专题设色应语义关联（水系蓝、植被绿、交通橙/黄、行政区区分色），相邻区域用可区分色相。",
     [("InfluencingFactor", "DETERMINES")]),
    ("color_graduated", "ColorSchemeRule",
     "分级设色规则",
     "数量分级设色需按数据大小次序选用色阶（浅→深），级差与数值差成对应；相邻级别颜色过渡自然，避免跳色与级数过少或过多。",
     [("CartographicDecision", "INFLUENCES")]),
    ("color_land_water", "ColorSchemeRule",
     "水系与陆地配色规范",
     "水域用蓝色系（青蓝/深蓝），陆地底色用浅色（米白/浅灰绿）；水域面颜色与陆地形成明确区分，水系注记用与水体一致的蓝色系。",
     [("MapElement", "COLORS")]),
    ("color_district_fill", "ColorSchemeRule",
     "行政区划普染色配色规则",
     "行政区划图各政区用不同色相区分（普染色），相邻政区色相差异明显；同色相深浅仅用于表达隶属关系或分级，不可用于相邻平级政区。",
     [("BoundaryRule", "APPLIES_TO")]),
    ("color_transparency_range", "ColorSchemeRule",
     "填充透明度合理范围",
     "面要素填充透明度一般 0.2~0.9，透明度过低导致压盖底图要素不可读、过高则符号不清晰；透明图层面与下层面要素的叠压关系需保持可读。",
     [("Style", "GOVERNS")]),
    # ---- 符号规则 ----
    ("symbol_point_design", "SymbolRule",
     "点状符号设计规范",
     "点状符号形状与要素类别语义对应（行政中心用几何符号、POI用象形符号）；符号大小与地图比例尺、要素等级适配，同级要素符号统一；点符号不因缩放无限放大，需随比例尺分级。",
     [("PointSymbol", "DESIGNS")]),
    ("symbol_line_design", "SymbolRule",
     "线状符号设计规范",
     "线状符号以线宽、线型（实线/虚线/点线）、颜色区分等级：高等级道路线宽大颜色深，低等级细浅；道路用色遵循 GB_COLORS（高速/国道/省道/县道分级配色）。",
     [("LineSymbol", "DESIGNS")]),
    ("symbol_area_design", "SymbolRule",
     "面状符号设计规范",
     "面状要素用填充色/填充图案/边界线表达；面边界线宽与面积等级匹配；水面、绿地、居民地填充样式需与图例一致。",
     [("AreaSymbol", "DESIGNS")]),
    ("symbol_level_by_rank", "SymbolRule",
     "符号等级化设计",
     "同一图层内要素按等级（重要度/规模）分级设符号：重要要素大而醒目，次要要素小而淡；等级数一般 3~5 级，不宜过多。",
     [("ScaleRule", "RELATES_TO")]),
    # ---- 比例尺规则 ----
    ("scale_digital_represent", "ScaleRule",
     "数字比例尺的表示规则",
     "数字比例尺以 1:M 形式表示，分子恒为1，分母取整且为 10 的整倍数或常用值（1:5000/1:10000/1:25000/1:50000/1:100000…），图上 1cm 对应实地 M cm。",
     [("MapElement", "MEASURES")]),
    ("scale_graphic", "ScaleRule",
     "图解比例尺绘制规则",
     "图解（直线）比例尺分为主尺与辅尺，辅尺向右以整单位递增、主尺向左细分；比例尺长度一般 8~15cm，与图幅宽度协调，单位标注完整。",
     [("MapElement", "MEASURES")]),
    ("scale_by_zoom", "ScaleRule",
     "缩放级别与比例尺对应关系",
     "Web 地图按 SCALE_LEVELS/SCALE_MATRIX 将缩放级别映射为制图比例尺；缩放级别改变时要素显示分级随之变化，避免符号与注记比例失衡。",
     [("ScaleRule", "APPLIES_TO")]),
    # ---- 投影规则 ----
    ("projection_mercator", "MapProjection",
     "墨卡托投影特点与适用",
     "墨卡托投影为等角圆柱投影，等角航线为直线、方向正确但面积变形随纬度增大；适用于航海图与 Web 地图（Web Mercator/EPSG:3857）。",
     [("CartographicData", "REQUIRES")]),
    ("projection_gauss", "MapProjection",
     "高斯-克吕格投影特点与适用",
     "高斯-克吕格投影为等角横切椭圆柱投影，按 3°/6° 分带，中央经线无变形；适用于 1:500~1:100万国家基本比例尺地形图，我国采用 CGCS2000 椭球。",
     [("CartographicData", "REQUIRES")]),
    ("projection_selection", "MapProjection",
     "地图投影选择原则",
     "投影选择需兼顾：制图区域形状与位置（中纬地区用圆锥投影、低纬用圆柱、极地用方位）、用途（等积/等角/任意）、比例尺与变形允许值；小比例尺专题图需说明投影变形性质。",
     [("InfluencingFactor", "DETERMINES")]),
    # ---- 图层规则 ----
    ("layer_order_rule", "LayerConfig",
     "图层叠置顺序规则",
     "图层按要素性质自下而上叠置：底图（影像/晕渲）→面状（水体、绿地、居民地）→线状（道路、境界）→点状（居民点、POI）→注记层最上；点状符号不得被面状压盖。",
     [("MapType", "HAS_LAYER")]),
    ("layer_visibility_rule", "LayerConfig",
     "图层显示与比例尺联动",
     "各图层可见性随比例尺缩放级别联动（如小比例尺只显示主要道路与地名，大比例尺显示全部要素），遵循 SCALE_RANGE_BY_MIN_ZOOM。",
     [("ScaleRule", "APPLIES_TO")]),
    ("layer_grouping", "LayerConfig",
     "图层面板分类组织规则",
     "图层面板按语义分组组织（水系/交通/绿地/居民地/境界/注记等），同名图层避免重复；图层命名规范、可辨识。",
     [("Tool", "USES")]),
    # ---- 制图综合 ----
    ("generalization_simplify", "GeneralizationRule",
     "制图综合之简化",
     "简化（化简）：在保留要素基本轮廓特征前提下减少顶点数量（Douglas-Peucker），删除微小弯曲；简化程度随比例尺缩小增大，但不得改变要素拓扑关系。",
     [("MapElement", "SIMPLIFIES")]),
    ("generalization_merge", "GeneralizationRule",
     "制图综合之合并与选取",
     "合并：小比例尺下将邻近同类小面合并为更大面（如小块绿地合并）；选取：按最小尺寸阈值舍弃次要小要素（如极小面、短小地物）。",
     [("MapElement", "GENERALIZES")]),
    ("generalization_displacement", "GeneralizationRule",
     "制图综合之移位与位移",
     "当要素拥挤压盖时，将次要要素沿垂直于主要要素方向适度移位（一般不大于图上 0.5mm），保持要素间最小间距，避免破坏重要要素位置精度。",
     [("ConflictRule", "RESOLVES")]),
    # ---- 编辑模式规范（用户强调）----
    ("edit_select_feature", "EditRule",
     "要素选中规则",
     "编辑模式下应能通过点击/框选选中任意地理要素；选中态需高亮显示（描边/变色）；要素选中后可查看其属性并可修改样式。",
     [("Tool", "ENABLES")]),
    ("edit_modify_style", "EditRule",
     "要素样式修改需符合制图规范",
     "修改单个要素样式时应保持与所在图层整体规范一致：线状要素线宽取 1~8px、面要素填充透明度 0.2~0.9、注记字号与图层分级一致；不得随意破坏图例一致性。",
     [("Style", "GOVERNS"), ("MapSymbol", "GOVERNS")]),
    ("edit_attribute_table", "EditRule",
     "属性表编辑规则",
     "属性表应存储要素全部制图数据与属性字段；通过属性表选中行可联动高亮地图对应要素，通过地图选中要素可反查属性表记录；属性修改即时同步。",
     [("CartographicData", "STORES")]),
    ("edit_undo_redo", "EditRule",
     "编辑操作的撤销与恢复",
     "所有编辑操作（样式修改/注记调整/删除要素）均应支持撤销与恢复（undo/redo），操作历史按栈管理，防止误操作不可逆。",
     [("Tool", "SUPPORTS")]),
    ("edit_annotation_horizontal", "EditRule",
     "注记横向排布修改",
     "调整注记方向时以横向（水平）排布为默认；对倾斜注记可一键恢复为横向，保证版面整齐与易读。",
     [("AnnotationRuleDecision", "GOVERNS")]),
    ("edit_stroke_width", "EditRule",
     "线宽修改规范范围",
     "线状要素线宽一般 1~8px（0.3~2.5mm 图上线宽），超出范围导致过细不可见或过粗压盖；线宽修改后需检查与相邻要素的协调。",
     [("LineSymbol", "GOVERNS")]),
    # ---- 数据规范 ----
    ("data_shp_format", "DataRule",
     "Shapefile 文件组构成",
     "Shapefile 以 .shp（几何）+ .shx（索引）+ .dbf（属性表）+ .prj（投影）+ .cpg（字符编码）文件组形式存储；导出/导入时五件套缺一不可，编码统一 UTF-8 或 GBK。",
     [("CartographicData", "DEFINES")]),
    ("data_attribute_complete", "DataRule",
     "属性表数据完整性要求",
     "地图上每个可见要素都必须在属性表中存在对应记录，属性字段（名称/类别/等级/面积等）完整无缺；制图注记也应作为要素或字段存储在图层数据中。",
     [("CartographicData", "REQUIRES")]),
    ("data_projection_consistent", "DataRule",
     "数据投影一致性规则",
     "同一工程所有图层必须使用统一坐标系（建议 CGCS2000 或 WGS84），跨投影叠加前需先投影转换；导出 shp 时 .prj 必须写入正确坐标系统。",
     [("MapProjection", "CONSTRAINS")]),
    # ---- 地图整饰 ----
    ("legend_design", "LegendRule",
     "图例设计规范",
     "图例应完整覆盖图中所有符号类型，符号样式与图内一一对应；图例按类别分组排列，文字简洁；比例尺、指北针、图名、经纬网等整饰要素齐全。",
     [("MapElement", "ORGANIZES")]),
    ("north_arrow", "LegendRule",
     "指北针与经纬网规则",
     "地图需标注指北针（或图廓定向信息）；经纬网/方里网按比例尺与投影选择，经纬网注记（经纬度数值）完整，网格密度与图幅协调。",
     [("MapProjection", "REFINES")]),
    # ---- 专题地图规范 ----
    ("profile_traffic", "MapType",
     "交通图制图规范",
     "交通图突出道路等级体系：高速/国道/省道/县道按 GB 色别与线宽分级，路名注记沿走向分布，枢纽（立交/车站）重点表达，其他要素淡化。",
     [("LayerConfig", "HAS_LAYER")]),
    ("profile_tourism", "MapType",
     "旅游图制图规范",
     "旅游图突出景点/博物馆/历史遗迹等 POI 符号，景区范围用面状底色，配套标注交通可达信息；POI 按 TOURISM_POI_LEVELS 分级显示。",
     [("LayerConfig", "HAS_LAYER")]),
    ("profile_campus", "MapType",
     "校园图制图规范",
     "校园图清晰表达教学楼/宿舍/食堂/运动场/绿地等设施分区，道路网格完整，注记以横向为主，配色清新（浅绿底+深蓝道路）。",
     [("LayerConfig", "HAS_LAYER")]),
    ("profile_admin", "MapType",
     "行政区划图制图规范",
     "行政区划图以境界线为核心：省界/市界/区县界线型分级，各政区普染色填充，行政中心符号分级（省级/市级/区县级），注记按行政等级分级字号。",
     [("BoundaryRule", "GOVERNS")]),
    ("profile_water", "MapType",
     "水系图制图规范",
     "水系图突出江河湖库：主要河流线宽分级、湖泊面蓝色填充、水系注记用蓝色横向排布；河流名称沿走向注记。",
     [("MapElement", "HAS_LAYER")]),
]

# ============ 导入 ============
def run():
    with driver.session() as s:
        # 1) 导入 35 条问答知识
        n_kb = 0
        for k in kb:
            name = k["id"]
            props = {
                "question": k["question"],
                "answer": k["answer"],
                "category": k["category"],
                "source": "cartography_kb",
            }
            s.run("MERGE (n:CartographyRule {name:$name}) SET n += $props", name=name, props=props)
            # 关联关系（语义）
            for label, rel in KB_REL.get(k["category"], []):
                s.run(
                    "MATCH (a:CartographyRule {name:$aname}) "
                    "MATCH (b) WHERE any(l IN labels(b) WHERE l=$blabel) "
                    "WITH a, b LIMIT 2 MERGE (a)-[r:%s]->(b) SET r.source='kb'" % rel,
                    aname=name, blabel=label,
                )
            n_kb += 1

        # 2) 导入补充规则
        n_extra = 0
        for rid, label, q, a, rels in EXTRA_RULES:
            props = {"question": q, "answer": a, "category": "制图学扩展", "source": "carto-standards"}
            s.run(f"MERGE (n:{label} {{name:$name}}) SET n += $props", name=rid, props=props)
            for rel_to, rel_type in rels:
                s.run(
                    "MATCH (a:%s {name:$aname}) MATCH (b) "
                    "WHERE any(l IN labels(b) WHERE l=$blabel) "
                    "WITH a, b LIMIT 3 MERGE (a)-[r:%s]->(b) SET r.source='carto-standards'"
                    % (label, rel_type),
                    aname=rid, blabel=rel_to,
                )
            n_extra += 1

        # 统计
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        rules = s.run("MATCH (n) WHERE n.question IS NOT NULL RETURN count(n) AS c").single()["c"]
        print(f"导入 kb={n_kb} 补充规则={n_extra}")
        print(f"图谱总计: nodes={nodes} relations={rels} 知识规则节点={rules}")
    driver.close()

run()
