# -*- coding: utf-8 -*-
"""知识图谱第二轮扩充：制图综合/投影/符号/专题图/数据质量/编辑操作/出图 -> Neo4j（幂等 MERGE）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "whu-2401")
driver = GraphDatabase.driver(URI, auth=AUTH)

# (id, label, question, answer, [(rel_to_label, rel_type), ...])
RULES = [
    # ============ 制图综合 ============
    ("gen_selective", "GeneralizationRule",
     "制图综合的取舍原则",
     "制图综合按要素重要程度取舍：保留等级高、面积大、有代表性的要素，舍去次要、细小、密集的要素；取舍数量随比例尺缩小而减少，保证图面清晰均衡。",
     [("ScaleRule", "RELATES_TO"), ("CartographicDecision", "INFLUENCES")]),
    ("gen_simplify", "GeneralizationRule",
     "图形简化的原则",
     "图形简化保留要素基本形状特征（转折点、曲率关键点），去除微小弯曲与碎部；简化后不得改变要素拓扑关系与相对位置关系（Douglas-Peucker 等算法需设合理阈值）。",
     [("LinearElement", "REPRESENTS")]),
    ("gen_merge", "GeneralizationRule",
     "要素合并原则",
     "小面积同类要素可合并为较大单元表达（如小湖泊群合并为湖群），合并后属性取主要要素，名称注记保留主导名称；合并不得破坏语义分类。",
     [("ArealElement", "REPRESENTS")]),
    ("gen_displacement", "GeneralizationRule",
     "要素移位规则",
     "要素密集导致压盖时，低等级要素向两侧位移（位移量不超过图上 0.5mm），保持高等级要素位置准确；移位后不得与邻要素产生新冲突。",
     [("ConflictRule", "GOVERNS")]),
    # ============ 地图投影 ============
    ("proj_select", "MapProjection",
     "地图投影的选择依据",
     "投影选择取决于制图区域范围、形状与用途：中国全图常用等积/等角圆锥投影（Lambert/Albers），小区域大比例尺用高斯-克吕格或 UTM；专题图优先等积投影保证面积可比。",
     [("CartographicDecision", "DETERMINES")]),
    ("proj_distortion", "MapProjection",
     "投影变形控制",
     "大区域制图必须考虑投影变形：等角投影保角度变形但面积变形大，等积投影保面积变形但角度变形大；选择投影时优先控制制图区域主要变形量，并在图廓标注投影名称。",
     [("ScaleRule", "RELATES_TO")]),
    ("proj_scale_limit", "MapProjection",
     "比例尺与投影匹配",
     "大于 1:10000 的大比例尺图使用高斯-克吕格分带投影；中小比例尺全国图使用圆锥投影；经纬网按投影类型绘制并注记经纬度。",
     [("ScaleRule", "CONSTRAINS")]),
    # ============ 符号系统 ============
    ("symbol_point_levels", "SymbolRule",
     "点状符号分级表达",
     "点状符号尺寸反映要素等级（省级>市级>区县级），同级要素符号必须一致；符号颜色与要素类别语义一致，重要符号可加晕圈突出。",
     [("PointElement", "REPRESENTS")]),
    ("symbol_line_levels", "SymbolRule",
     "线状符号分级表达",
     "线状要素按等级分级设色与设宽：道路 高速>国道>省道>县道（GB/T 色别），河流 干流>支流>溪流；线型（实线/虚线）表达类别或虚拟边界。",
     [("LinearElement", "REPRESENTS")]),
    ("symbol_area_levels", "SymbolRule",
     "面状符号表达",
     "面状要素用填充色/晕线/网点表达类别与等级；同类面用统一色系，等级用深浅区分；面边界线宽 0.5~1.5px，不得压盖内部注记。",
     [("ArealElement", "REPRESENTS")]),
    # ============ 色彩设计 ============
    ("color_hierarchy", "ColorSchemeRule",
     "色彩层次表达",
     "地图色彩分三层：底图底色（浅、低饱和）→ 中间要素（中饱和）→ 重点要素（高饱和或强对比色），突出重点信息，避免所有要素同权重。",
     [("LayerConfig", "HAS_LAYER")]),
    ("color_visual_variable", "ColorSchemeRule",
     "视觉变量运用",
     "色彩与形状、尺寸、方向、纹理、明度共同构成视觉变量体系：定性数据用色相区分，定量数据用明度/饱和度渐变，避免同一数据同时用多个冲突变量。",
     [("CartographicDecision", "INFLUENCES")]),
    # ============ 专题制图 ============
    ("theme_choropleth", "MapType",
     "分级统计图法（面域）",
     "分级统计图法以行政/自然区域为单元，用深浅色阶表达数量差异；分级数 4~7 级，分级方法（等距/分位/自然断点）与数据分布匹配，需附图例说明分级。",
     [("CartographicDecision", "INFLUENCES")]),
    ("theme_isolines", "MapType",
     "等值线图法",
     "等值线法表达连续渐变现象（高程/气温/降水），等值线间隔均匀、注记断线放置、数值朝向高处；相邻等值线不得相交，首曲线与计曲线分级。",
     [("LinearElement", "REPRESENTS")]),
    ("theme_point_density", "MapType",
     "点值法",
     "点值法用点密度表示数量分布，每点代表固定数值；点均匀随机分布、大小一致、不重叠，点间距与图面协调，图例标注每点代表数值。",
     [("CartographicDecision", "INFLUENCES")]),
    ("theme_symbol_proportional", "MapType",
     "定点符号法",
     "定点符号法用符号大小表示数量值（分级符号或比例符号），符号面积与数值成比例（或按分级）；符号定位准确，图例说明换算关系。",
     [("MapSymbol", "VISUALIZES")]),
    ("theme_range", "MapType",
     "范围法",
     "范围法用面状符号表达现象的分布范围（如人口稠密区），范围边界清晰，内部可加晕线或网点，范围与行政边界可分离表达。",
     [("ArealElement", "REPRESENTS")]),
    ("theme_flow", "MapType",
     "动线法",
     "动线法表达流动现象（交通流/人口迁移），线宽或箭头表达流量大小，颜色表达方向或类别；动线不得过多交叉混乱。",
     [("LinearElement", "REPRESENTS")]),
    # ============ 数据质量 ============
    ("data_topo", "DataRule",
     "拓扑一致性要求",
     "面要素边界必须闭合、相邻面不重叠不裂缝；线要素不悬挂、不重复；要素编辑后应执行拓扑检查（节点/边/面关系），保证空间关系正确。",
     [("CartographicData", "REQUIRES")]),
    ("data_crs_epsg", "DataRule",
     "坐标系统与 EPSG 编码",
     "数据应记录 EPSG 编码：WGS84=EPSG:4326、CGCS2000=EPSG:4490、Web墨卡托=EPSG:3857；坐标系不一致的图层叠加前必须统一转换。",
     [("MapProjection", "CONSTRAINS")]),
    ("data_attribute_types", "DataRule",
     "属性字段类型规范",
     "属性表字段类型与语义匹配：名称用文本、面积用数值（km²）、等级用整型/枚举、注记样式字段（字号/颜色/旋转角）用规范数值；不得混用类型。",
     [("CartographicData", "DEFINES")]),
    # ============ 编辑操作 ============
    ("edit_snap", "EditRule",
     "要素捕捉规则",
     "绘制/编辑要素时启用捕捉：端点捕捉、中点捕捉、交点捕捉、垂足捕捉，捕捉容差 5~10px，保证要素精确衔接与拓扑正确。",
     [("Tool", "ENABLES")]),
    ("edit_vertex", "EditRule",
     "顶点编辑规则",
     "顶点编辑允许增删移顶点，移动顶点后自动更新边界与面积属性；删除顶点时避免要素自交；顶点密度与比例尺/符号宽度匹配。",
     [("Tool", "SUPPORTS")]),
    ("edit_merge_split", "EditRule",
     "要素合并与拆分",
     "合并要素时属性取主要素或求并集，拆分要素时沿分割线生成独立记录；合并/拆分后属性表记录同步更新，图例样式保持一致。",
     [("CartographicData", "STORES")]),
    # ============ 注记细节 ============
    ("label_wordspacing", "LabelRule",
     "注记字隔规则",
     "注记字隔按要素长度与字号调整：点状要素注记字隔为 0（连续），线状要素字隔可放大（字隔=字号×0.5~2），面状要素注记居中；长名称可分行。",
     [("AnnotationRuleDecision", "INFLUENCES")]),
    ("label_priority_chain", "LabelRule",
     "注记优先级链",
     "注记优先级：行政中心名>城市名>主要水系名>道路名>景点名>次要地物名；冲突时低级注记让位，同级按重要性（面积/流量/等级）取舍。",
     [("ConflictRule", "GOVERNS")]),
    ("label_rotation_line", "LabelRule",
     "线状注记旋转方向",
     "线状要素注记旋转角取沿线走向，但注记字符始终正立（不颠倒）；字向与线向一致，注记落在线上方 1~2mm 处，避免压线。",
     [("AnnotationRuleDecision", "INFLUENCES")]),
    # ============ 出图输出 ============
    ("output_resolution", "DataRule",
     "出图分辨率要求",
     "位图导出分辨率不小于 150dpi（打印 300dpi），矢量导出保持无损；图片格式 PNG（含透明）、JPEG（照片）、SVG/PDF（矢量）；长宽与比例尺匹配。",
     [("Tool", "SUPPORTS")]),
    ("output_layout", "LegendRule",
     "图面整饰布局",
     "图面整饰：图名置于上方居中、比例尺（数字+图形）置于下方、指北针置于右上、图例置于右下方空白区、经纬网注记沿图廓；图例与图内符号一一对应。",
     [("MapElement", "ORGANIZES")]),
    ("output_map_frame", "LegendRule",
     "图廓与经纬网",
     "图廓线内细外粗；经纬网注记（纬度/经度数值）标注于图廓内外；中小比例尺需绘制经纬网，大比例尺可用方里网（公里格网）。",
     [("MapProjection", "REFINES")]),
    # ============ 比例尺与内容 ============
    ("scale_detail_level", "ScaleRule",
     "比例尺与详细程度匹配",
     "比例尺决定要素选取与详细程度：小比例尺只表达主干要素，大比例尺表达细部；同一幅图内要素详略需一致，不得出现主干要素缺失而细部过度表达。",
     [("LayerConfig", "HAS_LAYER")]),
    ("scale_annotation_density", "ScaleRule",
     "注记密度随比例尺调整",
     "注记数量随比例尺缩小而减少，保证图面注记密度在合理范围（不重叠、可读）；按要素等级梯度保留注记，等级低者先舍去。",
     [("AnnotationRuleDecision", "INFLUENCES")]),
]

def run():
    with driver.session() as s:
        n = 0
        for rid, label, q, a, rels in RULES:
            props = {"question": q, "answer": a, "category": "制图学全面规范", "source": "carto-standards-2"}
            s.run(f"MERGE (n:{label} {{name:$name}}) SET n += $props", name=rid, props=props)
            for rel_to, rel_type in rels:
                s.run(
                    "MATCH (a:%s {name:$aname}) MATCH (b) "
                    "WHERE any(l IN labels(b) WHERE l=$blabel) "
                    "WITH a, b LIMIT 3 MERGE (a)-[r:%s]->(b) SET r.source='carto-standards-2'"
                    % (label, rel_type),
                    aname=rid, blabel=rel_to,
                )
            n += 1
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        rules = s.run("MATCH (n) WHERE n.question IS NOT NULL RETURN count(n) AS c").single()["c"]
        labels = s.run("MATCH (n) RETURN DISTINCT labels(n)[0] AS l ORDER BY l").values()
        print(f"新增规则={n}")
        print(f"图谱总计: nodes={nodes} relations={rels} 知识规则节点={rules}")
        print("标签:", ", ".join(str(x[0]) for x in labels))
    driver.close()

run()
