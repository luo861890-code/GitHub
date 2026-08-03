import os
import time
import re
import requests
import folium
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_neo4j import Neo4jGraph
from langchain_ollama import ChatOllama
from langchain_neo4j import GraphCypherQAChain
from typing import Optional

# 加载环境变量（Neo4j 密码等）
load_dotenv()

# ================== 连接 Neo4j 知识图谱 ==================
graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password=os.getenv("NEO4J_PASSWORD"),
    database="neo4j"
)

# ================== 初始化 Ollama 模型 ==================
llm = ChatOllama(
    model="llama3",          # 确保已下载该模型
    temperature=0,
)

# ================== 定义问答链的示例（可选） ==================
examples = [
    {
        "question": "武汉市有哪些主要河流？",
        "query": """
        MATCH (c:AdministrativeRegion {name:'武汉市'})
        CALL spatial.withinDistance('rivers', c.geometry, 1.0) YIELD node, distance
        WHERE node.name IS NOT NULL
        RETURN node.name AS riverName, distance
        """
    },
    {
        "question": "长江流经哪些省份？",
        "query": """
        MATCH (r:LineEntity {name:'长江'})-[:FLOWS_THROUGH]->(p:AdministrativeRegion)
        WHERE p.level = '省'
        RETURN p.name AS province
        """
    }
]

# 创建问答链（用于 /ask 接口）
qa_chain = GraphCypherQAChain.from_llm(
    graph=graph,
    cypher_llm=llm,
    qa_llm=llm,
    examples=examples,
    allow_dangerous_requests=True,
    verbose=True,
    return_direct=False,
    top_k=10
)

# ================== 创建 FastAPI 应用 ==================
app = FastAPI(title="地图知识图谱智能体 API")

# 添加 CORS 中间件（允许所有来源，开发环境使用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== 请求体模型定义 ==================
class Query(BaseModel):
    question: str

class MapRequest(BaseModel):
    map_type: str          # 地图类型，如 "交通图"
    region: str             # 区域，如 "武汉市"
    scale: str = "1:100000" # 可选，比例尺
    format: str = "html"    # 输出格式，支持 "html"

class AgentRequest(BaseModel):
    message: str

class AgentResponse(BaseModel):
    type: str  # 'text' 或 'map'
    text: Optional[str] = None
    map_html: Optional[str] = None
    error: Optional[str] = None

# ================== 地图生成相关函数 ==================

def get_region_bbox(region_name):
    """
    从图谱获取区域的边界框（暂用硬编码，后续可从数据库获取）
    """
    # 这里仅以武汉市为例
    bbox = {
        "min_lon": 114.0,
        "min_lat": 30.4,
        "max_lon": 114.6,
        "max_lat": 30.7
    }
    return bbox

def fetch_osm_elements(bbox, element_types, max_retries=3):
    """
    从 Overpass API 获取 OSM 要素，支持超时和重试
    """
    servers = [
        "https://overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter"
    ]
    
    # 定义每种要素类型对应的 Overpass 查询语句
    type_query_map = {
        "highway": 'way["highway"~"motorway|trunk"]',
        "railway": 'way["railway"]',
        "waterway": 'way["waterway"]',
        # 可根据需要继续添加
    }
    
    # 构造 Overpass 查询
    queries = []
    for typ in element_types:
        if typ in type_query_map:
            query_part = type_query_map[typ]
            queries.append(f"""
                {query_part}({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
                out geom;
            """)
        else:
            print(f"未知要素类型: {typ}，已跳过")
    
    # 如果没有有效查询，返回空
    if not queries:
        return {}
    
    query = "[out:json];" + "".join(queries)
    
    for attempt in range(max_retries):
        for server in servers:
            try:
                print(f"尝试从 {server} 获取数据 (尝试 {attempt+1}/{max_retries})")
                response = requests.get(
                    server,
                    params={'data': query},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                # 按类型分组
                elements_by_type = {}
                for elem in data.get('elements', []):
                    if 'tags' in elem:
                        # 判断主要类型
                        for typ in element_types:
                            if typ in elem['tags']:
                                elements_by_type.setdefault(typ, []).append(elem)
                                break
                return elements_by_type
            except requests.exceptions.RequestException as e:
                print(f"请求失败: {e}")
                continue
        # 所有服务器失败，等待后重试
        if attempt < max_retries - 1:
            time.sleep(2)
    
    print("所有 Overpass 服务器均失败，返回空数据。")
    return {}

def style_for_type(element_type):
    """根据要素类型返回 folium 样式"""
    styles = {
        "highway": {"color": "blue", "weight": 3, "opacity": 0.7},
        "railway": {"color": "red", "weight": 2, "opacity": 0.8},
        "waterway": {"color": "cyan", "weight": 4, "opacity": 0.6},
    }
    return styles.get(element_type, {"color": "gray", "weight": 1, "opacity": 0.5})

def generate_folium_map(region_name, map_type):
    """
    生成 folium 地图对象并返回完整的 HTML 字符串
    从知识图谱中读取地图类型对应的样式配置，支持子类型和多层样式
    """
    # 1. 从知识图谱查询样式配置
    styles_config = None
    try:
        query = "MATCH (m:MapType {name: $map_type}) RETURN m.feature_styles AS styles"
        # 如果 graph.query 支持参数，否则用字符串拼接
        result = graph.query(query, params={"map_type": map_type})
        if result and result[0].get('styles'):
            import json
            styles_config = json.loads(result[0]['styles'])
            print(f"从图谱读取样式配置: {styles_config}")
    except Exception as e:
        print(f"查询样式配置失败: {e}")

    # 如果没有获取到配置，使用默认配置（仅 highway 蓝色）
    if not styles_config:
        styles_config = {
            "highway": [{"color": "blue", "weight": 3, "opacity": 0.7}]
        }
        print("使用默认样式配置")

    # 2. 根据样式配置确定需要的要素类型
    element_types = list(styles_config.keys())

    # 3. 获取区域边界框（目前硬编码为武汉市）
    bbox = get_region_bbox(region_name)
    center_lat = (bbox['min_lat'] + bbox['max_lat']) / 2
    center_lon = (bbox['min_lon'] + bbox['max_lon']) / 2

    # 4. 从 OSM 获取数据
    elements_by_type = fetch_osm_elements(bbox, element_types)

    # 5. 创建 folium 地图
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')

    # 6. 添加要素到地图，按照样式配置绘制（支持子类型和多层）
    for typ, elements in elements_by_type.items():
        if typ not in styles_config:
            continue
        style_def = styles_config[typ]
        
        for elem in elements:
            if 'geometry' not in elem or 'tags' not in elem:
                continue
            
            # 获取子类型
            subtype = None
            if typ == 'highway':
                subtype = elem['tags'].get('highway')
            elif typ == 'railway':
                subtype = elem['tags'].get('railway')
            elif typ == 'waterway':
                subtype = elem['tags'].get('waterway')
            
            # 确定当前要素的样式
            if isinstance(style_def, dict):
                # 如果 style_def 是字典，可能包含子类型
                if subtype and subtype in style_def:
                    layer_styles = style_def[subtype]
                else:
                    # 没有子类型匹配，使用顶层样式（可能是单层或多层）
                    layer_styles = style_def.get('*', style_def)  # 如果存在 '*' 通配符则使用，否则整个 style_def 作为单层
            else:
                layer_styles = style_def  # 列表或单层

            # 确保 layer_styles 是列表
            if not isinstance(layer_styles, list):
                layer_styles = [layer_styles]
            
            # 逐层绘制
            for layer in layer_styles:
                color = layer.get('color', 'gray')
                weight = layer.get('weight', 2)
                opacity = layer.get('opacity', 0.5)
                dash_array = layer.get('dashArray')
                coords = [(pt['lat'], pt['lon']) for pt in elem['geometry']]
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=weight,
                    opacity=opacity,
                    dashArray=dash_array
                ).add_to(m)

    # 7. 生成原始 HTML
    html = m.get_root().render()
    # 强制替换标题
    html = re.sub(r'<title>.*?</title>', f'<title>{region_name}{map_type}</title>', html, flags=re.IGNORECASE)

    # 确保页面编码正确
    if '<meta charset=' not in html.lower():
        html = html.replace('<head>', '<head><meta charset="UTF-8">')

    # 8. 替换 CDN 链接为国内镜像（保持不变）
    # ...（你的 CDN 替换代码）
    html = re.sub(r'https://cdn\.jsdelivr\.net/npm/leaflet@([^/]+)/dist/leaflet\.css',
                  r'https://cdn.bootcdn.net/ajax/libs/leaflet/\1/leaflet.css', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/npm/leaflet@([^/]+)/dist/leaflet\.js',
                  r'https://cdn.bootcdn.net/ajax/libs/leaflet/\1/leaflet.js', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/npm/bootstrap@([^/]+)/dist/css/bootstrap\.min\.css',
                  r'https://cdn.bootcdn.net/ajax/libs/bootstrap/\1/css/bootstrap.min.css', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/npm/bootstrap@([^/]+)/dist/js/bootstrap\.bundle\.min\.js',
                  r'https://cdn.bootcdn.net/ajax/libs/bootstrap/\1/js/bootstrap.bundle.min.js', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/npm/@fortawesome/fontawesome-free@([^/]+)/css/all\.min\.css',
                  r'https://cdn.bootcdn.net/ajax/libs/font-awesome/\1/css/all.min.css', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/gb/python-visualization/folium/folium/templates/leaflet\.awesome-markers\.css',
                  r'https://cdnjs.cloudflare.com/ajax/libs/leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css', html)
    html = re.sub(r'https://cdn\.jsdelivr\.net/gb/python-visualization/folium/folium/templates/leaflet\.awesome-markers\.js',
                  r'https://cdnjs.cloudflare.com/ajax/libs/leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js', html)

    return html

    
# ================== API 路由 ==================

@app.get("/")
def root():
    return {"message": "地图知识图谱智能体 API 已启动"}

@app.post("/ask")
async def ask(query: Query):
    question = query.question
    # 针对“武汉市河流”的特定问题（硬编码，确保准确）
    if "武汉市" in question and "河流" in question:
        cypher = """
        MATCH (c:AdministrativeRegion {name:'武汉市'})
        CALL spatial.withinDistance('rivers', c.geometry, 1.0) YIELD node, distance
        WHERE node.name IS NOT NULL
        RETURN node.name AS riverName, distance
        """
        try:
            result = graph.query(cypher)
            if result:
                rivers = [r['riverName'] for r in result]
                return {"answer": f"武汉市附近的主要河流有：{', '.join(rivers)}"}
            else:
                return {"answer": "未找到武汉市附近的河流数据。"}
        except Exception as e:
            return {"error": f"查询失败: {str(e)}"}
    else:
        # 其他问题使用问答链
        try:
            result = qa_chain.invoke(question)
            return {"answer": result['result']}
        except Exception as e:
            return {"error": str(e)}

@app.post("/generate_map")
async def generate_map(req: MapRequest):
    """
    生成交互式地图，返回 HTML 字符串
    """
    try:
        html = generate_folium_map(req.region, req.map_type)
        return {"map_html": html}
    except Exception as e:
        return {"error": str(e)}

# 可选：空间查询接口（查找城市附近的河流）
@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(req: AgentRequest):
    """
    统一智能体接口：根据用户输入自动判断是问答还是制图
    """
    msg = req.message.strip()
    if not msg:
        return AgentResponse(type='text', error='输入不能为空')

    # 简单的意图识别规则
    # 如果消息包含“画”、“制图”、“地图”、“生成”等词，并且包含城市名，则尝试制图
    city_match = re.search(r'([\u4e00-\u9fa5]{2,}?(?:市|区|县)?)', msg)
    city = city_match.group(1) if city_match else None

    # 制图关键词
    map_keywords = ['画', '制图', '地图', '生成', '给我画', '绘制', '做个']
    is_map_request = any(kw in msg for kw in map_keywords) and city is not None

    if is_map_request:
        # 尝试生成地图，默认地图类型为交通图
        try:
            map_type = "交通图"
            region = city
            html = generate_folium_map(region, map_type)
            return AgentResponse(type='map', text=f'为您生成{region}{map_type}', map_html=html)
        except Exception as e:
            return AgentResponse(type='text', error=f'地图生成失败: {str(e)}')
    else:
        # 否则当作问答处理
        try:
            result = qa_chain.invoke(msg)
            return AgentResponse(type='text', text=result['result'])
        except Exception as e:
            return AgentResponse(type='text', error=f'问答失败: {str(e)}')
@app.post("/nearby_rivers")
async def nearby_rivers(city: str, distance: float = 1.0):
    query = f"""
    MATCH (c:AdministrativeRegion {{name: '{city}'}})
    CALL spatial.withinDistance('rivers', c.geometry, {distance}) YIELD node, distance
    WHERE node.name IS NOT NULL
    RETURN node.name AS riverName, distance
    """
    try:
        result = graph.query(query)
        return {"city": city, "rivers": result}
    except Exception as e:
        return {"error": str(e)}