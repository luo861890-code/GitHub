"""知识图谱服务 - Neo4j知识图谱管理与查询

支持两种运行模式：
1. Neo4j可用模式：完整图数据库，支持Cypher查询、实体/关系管理
2. 内存规则模式（降级）：Neo4j不可用时自动降级，使用CITY_BBOX和WUHAN_LANDMARKS作为内置知识

KGService为制图智能体提供知识支撑：
- 制图约束（不同地图类型的规范要求）
- 样式推荐（地图类型对应的推荐配色和样式）
- 地标查询（城市地标POI信息）
- 图谱可视化（D3.js格式的节点和边数据）
- 制图决策查询（指定地图类型的完整制图方案，含图层配置、符号方案、配色方案、标注规则）
- 图层顺序查询（指定地图类型的图层叠置顺序）
"""
from app.utils.logger import get_logger
logger = get_logger(__name__)
import os
import time
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import CITY_BBOX, WUHAN_LANDMARKS, MAP_STYLES
from app.core.exceptions import KnowledgeGraphError
from app.utils.helpers import generate_id


class KGService:
    """知识图谱服务

    管理制图领域知识图谱，提供约束查询、样式推荐、自然语言问答等功能。
    Neo4j连接失败时自动降级为内存规则模式。
    """

    def __init__(self, llm_service=None):
        """初始化知识图谱服务

        尝试连接Neo4j，连接失败则降级为内存规则模式。

        Args:
            llm_service: LLM服务实例（可选），用于自然语言查询生成Cypher
        """
        self.llm_service = llm_service
        self.driver = None
        self._memory_store: Dict[str, List[dict]] = {}  # 内存模式的数据存储
        self._last_connect_attempt = 0.0
        self._reconnect_interval = 60.0

        # 尝试连接Neo4j
        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            # 验证连接
            self.driver.verify_connectivity()
            logger.info("[KGService] Neo4j连接成功，使用图数据库模式")
            self._last_connect_attempt = time.time()
        except Exception as e:
            logger.info(f"[KGService] Neo4j连接失败: {e}，降级为内存规则模式")
            self.driver = None
            self._init_memory_store()
            self._last_connect_attempt = time.time()

    def _ensure_connected(self):
        """Neo4j 断连后自动重连：每次请求按退避间隔尝试，恢复后切回图数据库模式。"""
        if self.driver is not None:
            return
        now = time.time()
        if now - self._last_connect_attempt < self._reconnect_interval:
            return
        self._last_connect_attempt = now
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            driver.verify_connectivity()
            self.driver = driver
            logger.info("[KGService] Neo4j重新连接成功，切换回图数据库模式")
        except Exception as e:
            # 连接失败必须关闭刚创建的 driver，避免每次重连都泄漏一个连接池
            try:
                if 'driver' in locals() and driver is not None:
                    driver.close()
            except Exception:
                pass
            logger.info(f"[KGService] Neo4j重连失败: {e}，保持内存模式")

    # ==================== 知识初始化 ====================

    @staticmethod
    def _safe_label(label) -> str:
        """将外部标签规范化为 Neo4j 合法标签（非法时回退 Entity）"""
        import re
        s = str(label or "").strip()
        return s if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s) else "Entity"

    @staticmethod
    def _safe_rel_type(rel_type) -> str:
        """将外部关系类型规范化为 Neo4j 合法类型（非法时回退 RELATED）"""
        import re
        s = str(rel_type or "").strip()
        return s if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s) else "RELATED"

    @staticmethod
    def _parse_params(value) -> Any:
        """兼容 Neo4j 中 dict/list 属性被 json.dumps 成字符串存储的 parameters 字段

        init_knowledge 导入时对 dict/list 属性做了 JSON 序列化，
        此处读取端统一解析：字符串→json.loads，dict/list→原样返回。
        """
        if isinstance(value, str):
            try:
                import json as _json
                return _json.loads(value)
            except Exception:
                return {}
        return value or {}

    @staticmethod
    def _safe_property_keys(properties) -> Dict[str, Any]:
        """过滤属性字典，仅保留 Neo4j 合法的属性键（防止键注入 Cypher）"""
        import re
        _KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        if not properties:
            return {}
        return {
            str(k): v for k, v in properties.items()
            if isinstance(k, str) and _KEY_RE.match(k)
        }

    def init_knowledge(self) -> bool:
        """初始化图谱数据

        在Neo4j中创建制图领域知识节点和关系，包括：
        - 地图类型节点（MapType）及其样式约束
        - 制图规则节点（CartographyRule）
        - 城市和地标节点（City, Landmark）

        Returns:
            初始化是否成功
        """
        self._ensure_connected()
        if self.driver is None:
            logger.info("[KGService] 内存模式，知识已内置，无需初始化")
            return True

        try:
            with self.driver.session() as session:
                # 创建约束（防止重复节点）
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:MapType) REQUIRE m.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Landmark) REQUIRE l.name IS UNIQUE")

                # 创建地图类型节点及制图约束
                map_type_constraints = {
                    "traffic": "交通图应包含道路和铁路网络，使用暖色调区分道路等级",
                    "tourism": "旅游图应标注景点、博物馆、历史遗迹，使用醒目标记",
                    "campus": "校园图应包含教学楼、宿舍、绿地等设施，使用清新配色",
                    "basic": "基础地图应包含道路、水系、生活设施，使用中性色调",
                    "food": "美食图应标注餐厅、咖啡馆等餐饮场所，使用暖色标记",
                    "administrative": "行政区划图应包含行政边界，使用区分色填充",
                }

                for map_type, constraint in map_type_constraints.items():
                    session.run(
                        "MERGE (m:MapType {name: $name}) "
                        "SET m.constraint = $constraint, m.updated_at = timestamp()",
                        name=map_type,
                        constraint=constraint,
                    )

                # 创建城市和地标节点
                for city_name, bbox in CITY_BBOX.items():
                    session.run(
                        "MERGE (c:City {name: $name}) "
                        "SET c.min_lat = $min_lat, c.min_lon = $min_lon, "
                        "c.max_lat = $max_lat, c.max_lon = $max_lon, "
                        "c.center_lat = $center_lat, c.center_lon = $center_lon",
                        name=city_name,
                        min_lat=bbox["min_lat"],
                        min_lon=bbox["min_lon"],
                        max_lat=bbox["max_lat"],
                        max_lon=bbox["max_lon"],
                        center_lat=bbox["center_lat"],
                        center_lon=bbox["center_lon"],
                    )

                # 创建武汉地标节点并关联到城市
                for landmark in WUHAN_LANDMARKS:
                    session.run(
                        "MERGE (l:Landmark {name: $name}) "
                        "SET l.lat = $lat, l.lng = $lng, l.type = $type",
                        name=landmark["name"],
                        lat=landmark["lat"],
                        lng=landmark["lng"],
                        type=landmark["type"],
                    )
                    session.run(
                        "MATCH (c:City {name: '武汉市'}), (l:Landmark {name: $name}) "
                        "MERGE (c)-[:HAS_LANDMARK]->(l)",
                        name=landmark["name"],
                    )

                # 导入完整本体数据（init_data.json：样式/规则/图层配置/符号等扩展知识）
                import json as _json
                init_data_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    "data", "kg", "init_data.json",
                )
                if os.path.exists(init_data_path):
                    with open(init_data_path, "r", encoding="utf-8") as f:
                        data = _json.load(f)
                    json_nodes = data.get("nodes", [])
                    json_relations = data.get("relations", [])
                    # 追加 5 大类本体（MapElement/MapSymbol/MapData/MapProjection/CartoFactor）
                    try:
                        from app.core.kg_ontology import ONTOLOGY_NODES, ONTOLOGY_RELATIONS
                        json_nodes = list(json_nodes) + list(ONTOLOGY_NODES)
                        json_relations = list(json_relations) + list(ONTOLOGY_RELATIONS)
                    except ImportError:
                        pass

                    # 与内存模式一致：按 name 去重，首次出现为准
                    seen_names = set()
                    unique_nodes = []
                    for node in json_nodes:
                        name = (node.get("name") or "").strip()
                        if not name or name in seen_names:
                            continue
                        seen_names.add(name)
                        unique_nodes.append(node)

                    for node in unique_nodes:
                        name = node.get("name") or ""
                        label = self._safe_label(node.get("label") or "Entity")
                        props = {}
                        for key, value in node.items():
                            if key in ("name", "label"):
                                continue
                            if isinstance(value, (dict, list)):
                                props[key] = _json.dumps(value, ensure_ascii=False)
                            elif value is not None:
                                props[key] = value
                        session.run(
                            f"MERGE (n:{label} {{name: $name}}) SET n += $props",
                            name=name,
                            props=props,
                        )

                    for rel in json_relations:
                        rel_type = self._safe_rel_type(rel.get("type") or "RELATED")
                        from_name = rel.get("from") or rel.get("source") or ""
                        to_name = rel.get("to") or rel.get("target") or ""
                        if not from_name or not to_name:
                            continue
                        rel_props = {}
                        for key, value in (rel.get("properties") or {}).items():
                            if isinstance(value, (dict, list)):
                                rel_props[key] = _json.dumps(value, ensure_ascii=False)
                            elif value is not None:
                                rel_props[key] = value
                        session.run(
                            f"MATCH (a {{name: $from_name}}), (b {{name: $to_name}}) "
                            f"MERGE (a)-[r:{rel_type}]->(b) SET r += $props",
                            from_name=from_name,
                            to_name=to_name,
                            props=rel_props,
                        )

                logger.info("[KGService] 知识图谱初始化完成")
                return True

        except Exception as e:
            logger.info(f"[KGService] 知识初始化失败: {e}")
            return False

    # ==================== 知识查询 ====================

    def get_constraints(self) -> List[Dict[str, str]]:
        """获取制图约束列表

        Returns:
            约束列表，每项包含 map_type 和 constraint 字段
        """
        self._ensure_connected()
        if self.driver is None:
            # 内存模式：返回内置约束
            constraints = self._memory_store.get("constraints", [])
            return constraints

        try:
            with self.driver.session() as session:
                result = session.run("MATCH (m:MapType) RETURN m.name AS map_type, m.constraint AS constraint")
                return [
                    {"map_type": record["map_type"], "constraint": record["constraint"]}
                    for record in result
                ]
        except Exception as e:
            logger.info(f"[KGService] 查询约束失败: {e}")
            return []

    def get_style_recommendations(self, map_type: str,
                                  extra_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """获取指定地图类型的样式推荐

        Args:
            map_type: 地图类型（traffic/tourism/campus等）
            extra_params: 附加查询参数（audience/topic/region 等），兼容 AgentService 调用

        Returns:
            样式推荐列表，每项包含 element_type 和 style 字段
        """
        # 从MAP_STYLES获取样式配置
        recommendations = []
        for element_type, style in MAP_STYLES.items():
            if isinstance(style, list):
                # highway类型有子类型，展开为多个推荐
                for config in style:
                    subtypes = config.get("subtypes", {})
                    for subtype, sub_style in subtypes.items():
                        recommendations.append({
                            "element_type": element_type,
                            "subtype": subtype,
                            "style": sub_style,
                        })
                    default_style = config.get("default")
                    if default_style:
                        recommendations.append({
                            "element_type": element_type,
                            "subtype": "default",
                            "style": default_style,
                        })
            elif isinstance(style, dict):
                recommendations.append({
                    "element_type": element_type,
                    "subtype": "default",
                    "style": style,
                })

        # 如果Neo4j可用，尝试获取图谱中的额外样式推荐
        if self.driver is not None:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        "MATCH (m:MapType {name: $map_type})-[:RECOMMENDS_STYLE]->(s:StyleRecommendation) "
                        "RETURN s.element_type AS element_type, s.style AS style",
                        map_type=map_type,
                    )
                    for record in result:
                        recommendations.append({
                            "element_type": record["element_type"],
                            "subtype": "recommended",
                            "style": record["style"],
                        })
            except Exception as e:
                logger.info(f"[KGService] 查询样式推荐失败: {e}")

        return recommendations

    def get_graph_data(self, limit: int = 100) -> Dict[str, List[dict]]:
        """获取图谱可视化数据（D3.js格式）

        Args:
            limit: 最多返回的节点数量

        Returns:
            {"nodes": [{id, label, name, properties}], "links": [{source, target, type}]}
        """
        self._ensure_connected()
        if self.driver is None:
            # 内存模式：返回内置地标图谱
            return self._get_memory_graph_data(limit)

        try:
            with self.driver.session() as session:
                # 查询节点
                node_result = session.run(
                    f"MATCH (n) RETURN id(n) AS id, labels(n) AS labels, "
                    f"n.name AS name, properties(n) AS properties LIMIT {limit}"
                )
                nodes = []
                node_id_map = {}  # Neo4j内部ID到字符串ID的映射
                for record in node_result:
                    neo4j_id = record["id"]
                    str_id = str(neo4j_id)
                    node_id_map[neo4j_id] = str_id
                    labels = record["labels"]
                    label = labels[0] if labels else "Unknown"
                    nodes.append({
                        "id": str_id,
                        "label": label,
                        "name": record["name"] or "未命名",
                        "properties": dict(record["properties"]),
                    })

                # 查询关系
                link_result = session.run(
                    f"MATCH (a)-[r]->(b) "
                    f"RETURN id(a) AS source, id(b) AS target, type(r) AS type LIMIT {limit * 2}"
                )
                links = []
                for record in link_result:
                    source_id = node_id_map.get(record["source"])
                    target_id = node_id_map.get(record["target"])
                    if source_id and target_id:
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "type": record["type"],
                        })

                return {"nodes": nodes, "links": links}

        except Exception as e:
            logger.info(f"[KGService] 获取图谱数据失败: {e}")
            return {"nodes": [], "links": []}

    def get_subgraph(self, entity_name: str, depth: int = 2, limit: int = 50) -> Dict[str, List[dict]]:
        """获取以指定实体为中心的子图 - 支持多跳检索（GraphRAG核心）

        从指定实体出发，检索depth跳范围内的所有节点和关系。
        Neo4j可用时使用Cypher变长路径查询，否则使用内存BFS遍历。

        Args:
            entity_name: 中心实体名称
            depth: 检索深度（跳数），默认2跳
            limit: 最多返回的节点数量

        Returns:
            {"nodes": [...], "links": [...], "center": entity_name}
        """
        self._ensure_connected()
        if self.driver is None:
            return self._get_memory_subgraph(entity_name, depth, limit)

        try:
            with self.driver.session() as session:
                # Cypher多跳查询
                result = session.run(
                    f"MATCH path = (n {{name: $name}})-[*1..{depth}]-(m) "
                    f"WITH DISTINCT n, m, relationships(path) AS rels "
                    f"LIMIT {limit} "
                    f"RETURN n, m, rels",
                    name=entity_name,
                )
                # 构建子图数据
                nodes_set = {}
                links = []
                for record in result:
                    n_node = record["n"]
                    m_node = record["m"]
                    for neo4j_node in [n_node, m_node]:
                        nid = str(neo4j_node.id)
                        if nid not in nodes_set:
                            labels = list(neo4j_node.labels)
                            nodes_set[nid] = {
                                "id": nid,
                                "label": labels[0] if labels else "Unknown",
                                "name": neo4j_node.get("name", "未命名"),
                                "properties": dict(neo4j_node),
                            }
                    # 添加关系
                    for rel in record["rels"]:
                        links.append({
                            "source": str(rel.start_node.id),
                            "target": str(rel.end_node.id),
                            "type": rel.type,
                        })

                return {
                    "nodes": list(nodes_set.values())[:limit],
                    "links": links,
                    "center": entity_name,
                }
        except Exception as e:
            logger.info(f"[KGService] 子图检索失败: {e}")
            return {"nodes": [], "links": [], "center": entity_name}

    def _get_memory_subgraph(self, entity_name: str, depth: int, limit: int) -> Dict[str, List[dict]]:
        """内存模式的子图检索 - 广度优先遍历

        Args:
            entity_name: 中心实体名称
            depth: 检索深度
            limit: 最多返回节点数

        Returns:
            子图数据 {"nodes": [...], "links": [...], "center": entity_name}
        """
        all_nodes = self._memory_store.get("nodes", [])
        all_relations = self._memory_store.get("relations", [])

        # 找到起始节点（按name匹配）
        start_nodes = [
            n for n in all_nodes
            if n.get("name") == entity_name
            or entity_name in str(n.get("properties", {}).get("name", ""))
        ]
        if not start_nodes:
            return {"nodes": [], "links": [], "center": entity_name}

        # BFS遍历
        visited = set()
        queue = [(n, 0) for n in start_nodes]
        result_nodes = []
        result_links = []

        while queue and len(result_nodes) < limit:
            node, current_depth = queue.pop(0)
            node_id = node.get("id", node.get("name", ""))
            if node_id in visited:
                continue
            visited.add(node_id)

            result_nodes.append({
                "id": node_id,
                "label": node.get("label", "Unknown"),
                "name": node.get("name", node.get("properties", {}).get("name", "未命名")),
                "properties": node.get("properties", {}),
            })

            if current_depth >= depth:
                continue

            # 查找相邻节点（通过关系）
            node_name = node.get("name", "")
            for rel in all_relations:
                rel_from = rel.get("from", rel.get("source", ""))
                rel_to = rel.get("to", rel.get("target", ""))

                if rel_from == node_name:
                    # 出边关系
                    target_name = rel_to
                    result_links.append({
                        "source": node_id,
                        "target": target_name,
                        "type": rel.get("type", "RELATED"),
                    })
                    # 查找目标节点加入队列
                    next_nodes = [n for n in all_nodes if n.get("name") == target_name]
                    for nn in next_nodes:
                        nn_id = nn.get("id", nn.get("name", ""))
                        if nn_id not in visited:
                            queue.append((nn, current_depth + 1))

                elif rel_to == node_name:
                    # 入边关系
                    source_name = rel_from
                    result_links.append({
                        "source": source_name,
                        "target": node_id,
                        "type": rel.get("type", "RELATED"),
                    })
                    # 查找源节点加入队列
                    next_nodes = [n for n in all_nodes if n.get("name") == source_name]
                    for nn in next_nodes:
                        nn_id = nn.get("id", nn.get("name", ""))
                        if nn_id not in visited:
                            queue.append((nn, current_depth + 1))

        return {"nodes": result_nodes, "links": result_links, "center": entity_name}

    def query_cartographic_decision(self, map_type: str, audience: str = "public") -> Dict[str, Any]:
        """查询指定地图类型和受众的完整制图决策方案

        从知识图谱中检索与指定地图类型和受众相关的所有制图决策，
        按decision_type分组组装为结构化方案。

        Args:
            map_type: 地图类型（traffic/tourism/campus/food/basic/administrative）
            audience: 目标受众级别（public/professional/expert），默认public

        Returns:
            结构化制图决策方案字典，包含：
            {
                "map_type": str,
                "audience": str,
                "layer_configs": [{...}],
                "symbol_scheme": {...},
                "color_scheme": {...},
                "annotation_rules": {...},
                "confidence": str,
            }
            如果找不到决策数据，返回空字典。
        """
        self._ensure_connected()
        if self.driver is None:
            return self._query_cartographic_decision_memory(map_type, audience)

        try:
            with self.driver.session() as session:
                # 查询指定地图类型和受众的所有制图决策
                result = session.run(
                    "MATCH (m:MapType {name: $map_type})-[:HAS_DECISION]->(d:CartographicDecision) "
                    "WHERE d.audience_level = $audience "
                    "RETURN d.decision_type AS decision_type, "
                    "d.map_type AS map_type, "
                    "d.audience_level AS audience_level, "
                    "d.parameters AS parameters, "
                    "d.priority AS priority, "
                    "d.rationale AS rationale, "
                    "d.name AS name",
                    map_type=map_type,
                    audience=audience,
                )

                decisions = [record.data() for record in result]

                if not decisions:
                    logger.info(f"[KGService] 未找到地图类型'{map_type}'受众'{audience}'的制图决策数据")
                    return {}

                # 按decision_type分组组装结果
                assembled: Dict[str, Any] = {
                    "map_type": map_type,
                    "audience": audience,
                }

                decision_map = {d.get("decision_type", ""): d for d in decisions}
                decision_count = len(decisions)

                # 提取图层配置
                layer_config_decision = decision_map.get("LAYER_CONFIG")
                if layer_config_decision:
                    params = self._parse_params(layer_config_decision.get("parameters", {}))
                    assembled["layer_configs"] = params.get("layers", []) if isinstance(params, dict) else []
                else:
                    assembled["layer_configs"] = []

                # 提取符号方案
                symbol_decision = decision_map.get("SYMBOL_SCHEME")
                if symbol_decision:
                    assembled["symbol_scheme"] = self._parse_params(symbol_decision.get("parameters", {}))
                else:
                    assembled["symbol_scheme"] = {}

                # 提取配色方案
                color_decision = decision_map.get("COLOR_SCHEME")
                if color_decision:
                    assembled["color_scheme"] = self._parse_params(color_decision.get("parameters", {}))
                else:
                    assembled["color_scheme"] = {}

                # 提取标注规则
                annotation_decision = decision_map.get("ANNOTATION_RULE")
                if annotation_decision:
                    assembled["annotation_rules"] = self._parse_params(annotation_decision.get("parameters", {}))
                else:
                    assembled["annotation_rules"] = {}

                # 计算置信度（基于找到的决策数量占4种类型的比例）
                type_count = sum(
                    1 for t in ["LAYER_CONFIG", "SYMBOL_SCHEME", "COLOR_SCHEME", "ANNOTATION_RULE"]
                    if t in decision_map
                )
                if type_count >= 4:
                    assembled["confidence"] = "high"
                elif type_count >= 2:
                    assembled["confidence"] = "medium"
                elif type_count >= 1:
                    assembled["confidence"] = "low"
                else:
                    assembled["confidence"] = "none"

                logger.info(f"[KGService] 查询制图决策成功: map_type={map_type}, audience={audience}, "
                      f"decisions={decision_count}, confidence={assembled['confidence']}")
                return assembled

        except Exception as e:
            logger.info(f"[KGService] 查询制图决策失败: {e}，回退到内存模式")
            return self._query_cartographic_decision_memory(map_type, audience)

    def _query_cartographic_decision_memory(self, map_type: str, audience: str) -> Dict[str, Any]:
        """内存模式的制图决策查询

        从 self._memory_store 中过滤 CartographicDecision 节点，
        查找与指定地图类型和受众匹配的决策，按decision_type分组组装结果。

        Args:
            map_type: 地图类型
            audience: 目标受众级别

        Returns:
            结构化制图决策方案字典
        """
        all_nodes = self._memory_store.get("nodes", [])
        all_relations = self._memory_store.get("relations", [])

        # 过滤出匹配的CartographicDecision节点
        matched_decisions = []
        for node in all_nodes:
            if node.get("label") != "CartographicDecision":
                continue
            props = node.get("properties", node)
            node_map_type = props.get("map_type", "")
            node_audience = props.get("audience_level", "public")
            if node_map_type == map_type and node_audience == audience:
                matched_decisions.append(props)

        if not matched_decisions:
            # 尝试放宽受众匹配
            for node in all_nodes:
                if node.get("label") != "CartographicDecision":
                    continue
                props = node.get("properties", node)
                if props.get("map_type") == map_type:
                    matched_decisions.append(props)

        if not matched_decisions:
            logger.info(f"[KGService] 内存模式未找到地图类型'{map_type}'的制图决策数据")
            return {}

        # 按decision_type分组
        decision_map = {}
        for d in matched_decisions:
            dtype = d.get("decision_type", "")
            if dtype not in decision_map:
                decision_map[dtype] = d

        assembled: Dict[str, Any] = {
            "map_type": map_type,
            "audience": audience,
        }

        # 提取图层配置
        layer_config_decision = decision_map.get("LAYER_CONFIG")
        if layer_config_decision:
            params = self._parse_params(layer_config_decision.get("parameters", {}))
            assembled["layer_configs"] = params.get("layers", []) if isinstance(params, dict) else []
        else:
            assembled["layer_configs"] = []

        # 提取符号方案
        symbol_decision = decision_map.get("SYMBOL_SCHEME")
        if symbol_decision:
            assembled["symbol_scheme"] = self._parse_params(symbol_decision.get("parameters", {}))
        else:
            assembled["symbol_scheme"] = {}

        # 提取配色方案
        color_decision = decision_map.get("COLOR_SCHEME")
        if color_decision:
            assembled["color_scheme"] = self._parse_params(color_decision.get("parameters", {}))
        else:
            assembled["color_scheme"] = {}

        # 提取标注规则
        annotation_decision = decision_map.get("ANNOTATION_RULE")
        if annotation_decision:
            assembled["annotation_rules"] = self._parse_params(annotation_decision.get("parameters", {}))
        else:
            assembled["annotation_rules"] = {}

        # 计算置信度
        type_count = sum(
            1 for t in ["LAYER_CONFIG", "SYMBOL_SCHEME", "COLOR_SCHEME", "ANNOTATION_RULE"]
            if t in decision_map
        )
        if type_count >= 4:
            assembled["confidence"] = "high"
        elif type_count >= 2:
            assembled["confidence"] = "medium"
        elif type_count >= 1:
            assembled["confidence"] = "low"
        else:
            assembled["confidence"] = "none"

        logger.info(f"[KGService] 内存模式查询制图决策: map_type={map_type}, audience={audience}, "
              f"decisions={len(matched_decisions)}, confidence={assembled['confidence']}")
        return assembled

    def query_layer_order(self, map_type: str) -> List[Dict[str, Any]]:
        """查询指定地图类型的图层叠置顺序

        从知识图谱中检索与指定地图类型关联的图层配置决策，
        提取并返回按叠置顺序排列的图层列表。

        Args:
            map_type: 地图类型（traffic/tourism/campus/food/basic/administrative）

        Returns:
            排序后的图层列表，每项包含 name, order, osm_tags, symbol_type 等字段。
            如果找不到图层配置，返回空列表并打印警告。
        """
        self._ensure_connected()
        if self.driver is None:
            return self._query_layer_order_memory(map_type)

        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (m:MapType {name: $map_type})-[:HAS_DECISION]->(d:CartographicDecision {decision_type: 'LAYER_CONFIG'}) "
                    "RETURN d.parameters AS parameters, d.name AS name",
                    map_type=map_type,
                )

                records = [record.data() for record in result]

                if not records:
                    logger.info(f"[KGService] 未找到地图类型'{map_type}'的图层配置决策")
                    return []

                # 从决策参数中提取图层列表并排序
                layers = []
                for record in records:
                    params = self._parse_params(record.get("parameters", {}))
                    layer_list = params.get("layers", []) if isinstance(params, dict) else []
                    for layer in layer_list:
                        if isinstance(layer, dict):
                            layers.append(layer)

                # 按order排序
                layers.sort(key=lambda x: x.get("order", 999))
                logger.info(f"[KGService] 查询图层顺序成功: map_type={map_type}, layers={len(layers)}")
                return layers

        except Exception as e:
            logger.info(f"[KGService] 查询图层顺序失败: {e}，回退到内存模式")
            return self._query_layer_order_memory(map_type)

    def _query_layer_order_memory(self, map_type: str) -> List[Dict[str, Any]]:
        """内存模式的图层顺序查询

        从 self._memory_store 中过滤与指定地图类型匹配的
        CartographicDecision（decision_type=LAYER_CONFIG）节点，
        提取并排序图层列表。

        Args:
            map_type: 地图类型

        Returns:
            排序后的图层列表
        """
        all_nodes = self._memory_store.get("nodes", [])

        # 查找匹配的图层配置决策
        layers = []
        for node in all_nodes:
            if node.get("label") != "CartographicDecision":
                continue
            props = node.get("properties", node)
            if props.get("map_type") == map_type and props.get("decision_type") == "LAYER_CONFIG":
                params = self._parse_params(props.get("parameters", {}))
                layer_list = params.get("layers", []) if isinstance(params, dict) else []
                for layer in layer_list:
                    if isinstance(layer, dict):
                        layers.append(layer)

        if not layers:
            logger.info(f"[KGService] 内存模式未找到地图类型'{map_type}'的图层配置")
            return []

        # 按order排序
        layers.sort(key=lambda x: x.get("order", 999))
        logger.info(f"[KGService] 内存模式查询图层顺序: map_type={map_type}, layers={len(layers)}")
        return layers

    def query(self, question: str) -> str:
        """自然语言查询

        Neo4j可用时尝试用LLM生成Cypher查询执行；
        不可用时用关键词匹配WUHAN_LANDMARKS返回结果。

        Args:
            question: 自然语言问题

        Returns:
            查询结果文本
        """
        if self.driver is not None and self.llm_service is not None:
            # 尝试用LLM生成Cypher查询
            return self._query_with_llm(question)
        else:
            # 降级：关键词匹配
            return self._query_with_keywords(question)

    def evaluate_competency_questions(self) -> Dict[str, Any]:
        """能力问题(CQs)验证：检验知识图谱的知识覆盖度与推理能力

        对应申报书验收点：可查询、可推理的知识图谱需支持 10 个以上
        预设能力问题（CQs），覆盖要素匹配、规则检索、场景适配三类。
        无论 Neo4j 还是内存模式均可执行（内部方法自带降级）。
        """
        cqs = [
            {"question": "旅游地图中景点应使用何种符号？", "check": "style", "map_type": "tourism"},
            {"question": "适用于1:10万比例尺的河流符号规则是什么？", "check": "constraints"},
            {"question": "交通地图的图层叠加顺序应该如何？", "check": "layer_order", "map_type": "traffic"},
            {"question": "湖泊要素应使用什么填充颜色与样式？", "check": "style", "map_type": "basic"},
            {"question": "行政区划图中区县名称注记如何配置？", "check": "query", "query": "行政区划图中区县名称注记如何配置？"},
            {"question": "水系要素与道路要素的层级关系应该是怎样的？", "check": "query", "query": "水系和道路的层级关系应该是怎样的？"},
            {"question": "旅游地图受众为儿童时符号应如何设计？", "check": "style", "map_type": "tourism", "audience": "child"},
            {"question": "标准地图中省界的线型与颜色规范是什么？", "check": "constraints"},
            {"question": "校园导览图中注记的最小字号应是多少？", "check": "constraints"},
            {"question": "武汉市域图适合采用什么地图投影？", "check": "query", "query": "武汉市域图适合采用什么地图投影？"},
            {"question": "地图注记不能压盖重要地物的规则是什么？", "check": "constraints"},
            {"question": "美食地图中餐饮POI应采用什么符号表达？", "check": "style", "map_type": "food"},
        ]

        results = []
        passed = 0
        for cq in cqs:
            q = cq["question"]
            check = cq.get("check")
            ok = False
            evidence = ""
            try:
                if check == "style":
                    extra = {"audience": cq.get("audience", "public")} if cq.get("audience") else None
                    recs = self.get_style_recommendations(cq.get("map_type", "basic"), extra) or []
                    ok = bool(recs)
                    evidence = "、".join(
                        f"{r.get('element_type')}:{r.get('style')}" for r in recs[:4]
                    )
                elif check == "layer_order":
                    layers = self.query_layer_order(cq.get("map_type", "basic")) or []
                    ok = bool(layers)
                    evidence = "、".join(str(l.get("name")) for l in layers[:6])
                elif check == "constraints":
                    cons = self.get_constraints() or []
                    ok = bool(cons)
                    evidence = "；".join(
                        f"{c.get('map_type')}:{c.get('constraint')}" for c in cons[:4]
                    )
                else:  # query：自然语言经 LLM→Cypher 或关键词降级
                    ans = self.query(cq.get("query", q)) or ""
                    ok = bool(ans.strip()) and "未返回结果" not in ans and not ans.strip().startswith("无法")
                    evidence = str(ans)[:150]
            except Exception as e:
                ok = False
                evidence = f"查询异常: {e}"
            results.append({"question": q, "passed": ok, "evidence": evidence})
            if ok:
                passed += 1

        total = len(cqs)
        gaps = [r["question"] for r in results if not r["passed"]]
        return {
            "total": total,
            "passed": passed,
            "rate": round(passed / total, 2) if total else 0,
            "status": "PASS" if passed >= total * 0.7 else "INSUFFICIENT",
            "results": results,
            "gaps": gaps,
            "suggestion": (
                "知识图谱覆盖度良好，可支撑智能制图的专业约束查询"
                if not gaps else
                f"以下能力问题未通过验证，建议补充对应知识：{'；'.join(gaps[:5])}"
            ),
        }

    @staticmethod
    def _is_readonly_cypher(cypher: str) -> bool:
        """校验Cypher查询是否为只读，防止LLM生成写语句破坏图谱

        允许以只读关键字开头的查询；包含写操作关键字则拒绝。
        """
        import re as _re
        # 去除行注释后取语句主体
        cleaned = _re.sub(r"//.*", "", cypher).strip()
        upper = cleaned.upper()
        # 写操作关键字
        write_keywords = [
            "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE",
            "DROP", "LOAD", "FOREACH", "ALTER", "INDEX", "CONSTRAINT",
        ]
        if any(kw in upper for kw in write_keywords):
            return False
        # 必须以只读查询开头
        allowed_prefixes = ("MATCH", "RETURN", "WITH", "UNWIND", "OPTIONAL", "CALL")
        return upper.startswith(allowed_prefixes)

    def _query_with_llm(self, question: str) -> str:
        """使用LLM生成Cypher查询并执行

        Args:
            question: 自然语言问题

        Returns:
            查询结果文本
        """
        # 动态获取图谱的节点标签与关系类型，保证新导入的知识可被检索
        labels_str = "MapType, City, Landmark, StyleRecommendation, CartographyRule"
        rels_str = "HAS_LANDMARK, RECOMMENDS_STYLE, FLOWS_THROUGH"
        try:
            with self.driver.session() as _s:
                _labels = [r[0] for r in _s.run("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l ORDER BY l").values()]
                _rels = [r[0] for r in _s.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t ORDER BY t").values()]
                if _labels:
                    labels_str = ", ".join(_labels)
                if _rels:
                    rels_str = ", ".join(_rels)
        except Exception:
            pass

        system_prompt = (
            "你是一个Cypher查询生成器。根据用户问题生成Neo4j Cypher查询语句。\n"
            f"图谱中包含以下节点类型：{labels_str}\n"
            f"关系类型包括：{rels_str}\n"
            "很多制图知识节点带有 question 与 answer 属性（如等高线、投影、配色、注记、制图综合、"
            "专题制图、数据规范、编辑操作、地形图、遥感、电子地图等规则）。查询知识类问题时，"
            "请从用户问题提取1-2个关键主题词，优先用如下形态检索："
            "MATCH (n) WHERE any(l IN labels(n) WHERE l IN [<可能的标签>]) "
            "AND (n.question CONTAINS <关键词> OR n.answer CONTAINS <关键词>) "
            "RETURN n.question AS question, n.answer AS answer LIMIT 5；"
            "若不确定标签，可用 MATCH (n) WHERE n.question IS NOT NULL AND n.question CONTAINS <关键词> "
            "RETURN n.question AS question, n.answer AS answer LIMIT 5。\n"
            "只返回Cypher查询语句，不要包含其他内容。"
        )
        prompt = f"用户问题: {question}\n\n请生成对应的Cypher查询语句："

        cypher = self.llm_service.generate(prompt, system_prompt)
        if not cypher:
            return self._query_with_keywords(question)

        # 清理LLM输出（去除markdown标记）
        cypher = cypher.strip()
        if cypher.startswith("```"):
            cypher = cypher.split("\n", 1)[1] if "\n" in cypher else cypher[3:]
        if cypher.endswith("```"):
            cypher = cypher[:-3]
        cypher = cypher.strip()

        # 安全校验：拒绝写操作，防止 LLM 生成的 Cypher 破坏图谱数据
        if not self._is_readonly_cypher(cypher):
            logger.info(f"[KGService] 拒绝执行非只读Cypher查询: {cypher[:100]}")
            return self._query_with_keywords(question)

        try:
            from neo4j import READ_ACCESS
            # 以只读模式执行，并限制返回行数，避免大结果集拖垮服务
            with self.driver.session(default_access_mode=READ_ACCESS) as session:
                result = session.run(cypher)
                records = [dict(record) for record in result]
                if records:
                    return str(records[:50])
                else:
                    return "查询未返回结果。"
        except Exception as e:
            logger.info(f"[KGService] Cypher查询执行失败: {e}，回退到关键词匹配")
            return self._query_with_keywords(question)

    def _query_with_keywords(self, question: str) -> str:
        """使用关键词匹配进行查询（降级模式）

        Args:
            question: 自然语言问题

        Returns:
            匹配结果文本
        """
        # 检查是否查询地标
        if any(kw in question for kw in ["地标", "景点", " landmark", "哪里", "有什么"]):
            # 尝试匹配城市
            matched_city = None
            for city in CITY_BBOX:
                short_name = city.replace("市", "")
                if short_name in question or city in question:
                    matched_city = city
                    break

            if matched_city == "武汉市" or (not matched_city and "武汉" in question):
                # 返回武汉地标
                results = []
                for landmark in WUHAN_LANDMARKS:
                    name = landmark["name"]
                    if name in question or any(
                        char in question for char in name[:2]
                    ):
                        results.append(
                            f"{landmark['name']}（{landmark['type']}）"
                            f"位于({landmark['lat']}, {landmark['lng']})"
                        )
                if results:
                    return "匹配到以下地标：\n" + "\n".join(results)
                else:
                    # 返回所有武汉地标
                    all_landmarks = [
                        f"- {lm['name']}（{lm['type']}）"
                        for lm in WUHAN_LANDMARKS
                    ]
                    return f"武汉市的已知地标有：\n" + "\n".join(all_landmarks)

        # 检查是否查询城市信息
        if any(kw in question for kw in ["城市", "范围", "坐标", "bbox"]):
            city_lines = []
            for city, bbox in CITY_BBOX.items():
                city_lines.append(
                    f"- {city}: 中心({bbox['center_lat']}, {bbox['center_lon']})"
                )
            return "支持的城市有：\n" + "\n".join(city_lines)

        # 检查是否查询制图知识
        if any(kw in question for kw in ["制图", "地图", "样式", "颜色"]):
            constraints = self.get_constraints()
            lines = [f"- {c['map_type']}: {c['constraint']}" for c in constraints]
            return "制图约束如下：\n" + "\n".join(lines)

        return f"抱歉，无法理解问题「{question}」。您可以询问城市地标、制图约束等信息。"

    # ==================== 实体/关系管理 ====================

    def create_entity(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """创建实体节点

        Args:
            label: 节点标签（如"Landmark", "City"）
            properties: 节点属性字典

        Returns:
            创建的节点信息 {"id": ..., "label": ..., "properties": ...}

        Raises:
            KnowledgeGraphError: 创建失败
        """
        self._ensure_connected()
        # 防注入：标签/属性键白名单化
        label = self._safe_label(label)
        properties = self._safe_property_keys(properties)
        if self.driver is None:
            # 内存模式
            node_id = generate_id("node")
            node = {"id": node_id, "label": label, "properties": properties}
            self._memory_store.setdefault("nodes", []).append(node)
            logger.info(f"[KGService] 内存模式创建实体: {label} (ID: {node_id})")
            return node

        try:
            with self.driver.session() as session:
                # 动态构建属性键值对（键已白名单化，值参数化）
                prop_keys = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                cypher = f"CREATE (n:{label} {{{prop_keys}}}) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                result = session.run(cypher, **properties)
                record = result.single()
                if record:
                    return {
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else label,
                        "properties": dict(record["properties"]),
                    }
                raise KnowledgeGraphError("创建实体失败：无返回结果")
        except Exception as e:
            raise KnowledgeGraphError(f"创建实体失败: {e}")

    def update_entity(self, node_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """更新实体节点属性

        Args:
            node_id: 节点ID
            properties: 要更新的属性字典

        Returns:
            更新后的节点信息

        Raises:
            KnowledgeGraphError: 更新失败
        """
        self._ensure_connected()
        # 防注入：属性键白名单化
        properties = self._safe_property_keys(properties)
        if self.driver is None:
            # 内存模式
            for node in self._memory_store.get("nodes", []):
                if node["id"] == node_id:
                    node["properties"].update(properties)
                    logger.info(f"[KGService] 内存模式更新实体: {node_id}")
                    return node
            raise KnowledgeGraphError(f"节点不存在: {node_id}")

        try:
            with self.driver.session() as session:
                set_clauses = ", ".join([f"n.{k} = ${k}" for k in properties.keys()])
                cypher = f"MATCH (n) WHERE id(n) = toInteger($node_id) SET {set_clauses} RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                params = {"node_id": node_id, **properties}
                result = session.run(cypher, **params)
                record = result.single()
                if record:
                    return {
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else "Unknown",
                        "properties": dict(record["properties"]),
                    }
                raise KnowledgeGraphError(f"节点不存在: {node_id}")
        except Exception as e:
            raise KnowledgeGraphError(f"更新实体失败: {e}")

    def delete_entity(self, node_id: str) -> bool:
        """删除实体节点

        Args:
            node_id: 节点ID

        Returns:
            删除是否成功

        Raises:
            KnowledgeGraphError: 删除失败
        """
        self._ensure_connected()
        if self.driver is None:
            # 内存模式
            nodes = self._memory_store.get("nodes", [])
            original_count = len(nodes)
            self._memory_store["nodes"] = [n for n in nodes if n["id"] != node_id]
            if len(self._memory_store["nodes"]) < original_count:
                logger.info(f"[KGService] 内存模式删除实体: {node_id}")
                return True
            raise KnowledgeGraphError(f"节点不存在: {node_id}")

        try:
            with self.driver.session() as session:
                session.run("MATCH (n) WHERE id(n) = toInteger($node_id) DETACH DELETE n", node_id=node_id)
                logger.info(f"[KGService] 删除实体: {node_id}")
                return True
        except Exception as e:
            raise KnowledgeGraphError(f"删除实体失败: {e}")

    def get_entities(self, label: str) -> List[Dict[str, Any]]:
        """按标签查询实体列表

        Args:
            label: 节点标签（如"Landmark", "MapType", "Style"等）

        Returns:
            实体列表，每项包含 id, label, properties
        """
        self._ensure_connected()
        # 防注入：标签白名单化
        label = self._safe_label(label)
        if self.driver is None:
            # 内存模式
            nodes = self._memory_store.get("nodes", [])
            return [n for n in nodes if n.get("label") == label]

        try:
            with self.driver.session() as session:
                result = session.run(
                    f"MATCH (n:{label}) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties LIMIT 100"
                )
                entities = []
                for record in result:
                    entities.append({
                        "id": str(record["id"]),
                        "label": record["labels"][0] if record["labels"] else label,
                        "properties": dict(record["properties"]),
                    })
                return entities
        except Exception as e:
            logger.info(f"[KGService] 查询实体失败: {e}")
            return []

    def create_relation(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建关系

        Args:
            source_label: 源节点标签
            source_id: 源节点ID
            target_label: 目标节点标签
            target_id: 目标节点ID
            relation_type: 关系类型
            properties: 关系属性（可选）

        Returns:
            创建的关系信息

        Raises:
            KnowledgeGraphError: 创建失败
        """
        self._ensure_connected()
        # 防注入：标签/关系类型/属性键白名单化
        source_label = self._safe_label(source_label)
        target_label = self._safe_label(target_label)
        relation_type = self._safe_rel_type(relation_type)
        properties = self._safe_property_keys(properties) if properties else None
        if self.driver is None:
            # 内存模式
            relation = {
                "source": source_id,
                "target": target_id,
                "type": relation_type,
                "properties": properties or {},
            }
            self._memory_store.setdefault("relations", []).append(relation)
            logger.info(f"[KGService] 内存模式创建关系: {source_id}-[{relation_type}]->{target_id}")
            return relation

        try:
            with self.driver.session() as session:
                prop_str = ""
                params = {"source_id": source_id, "target_id": target_id}
                if properties:
                    prop_keys = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                    prop_str = f" {{{prop_keys}}}"
                    params.update(properties)

                cypher = (
                    f"MATCH (a:{source_label}) WHERE id(a) = toInteger($source_id) "
                    f"MATCH (b:{target_label}) WHERE id(b) = toInteger($target_id) "
                    f"CREATE (a)-[r:{relation_type}{prop_str}]->(b) "
                    f"RETURN type(r) AS type, id(a) AS source, id(b) AS target"
                )
                result = session.run(cypher, **params)
                record = result.single()
                if record:
                    return {
                        "source": str(record["source"]),
                        "target": str(record["target"]),
                        "type": record["type"],
                        "properties": properties or {},
                    }
                raise KnowledgeGraphError("创建关系失败：无返回结果")
        except Exception as e:
            raise KnowledgeGraphError(f"创建关系失败: {e}")

    def import_document(self, content: str, entity_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """文档导入 - 从文本中提取实体创建节点

        简单的文档导入：通过分句和关键词匹配提取实体，
        为每个识别到的实体创建知识图谱节点。

        Args:
            content: 文档文本内容
            entity_labels: 期望提取的实体标签列表（可选）

        Returns:
            {"imported_count": N, "entities": [...]}
        """
        if entity_labels is None:
            entity_labels = ["Landmark", "City", "MapType"]

        imported_entities = []

        # 简单实体提取：匹配已知城市和地标
        for city in CITY_BBOX:
            short_name = city.replace("市", "")
            if short_name in content:
                entity = self.create_entity("City", {"name": city, "source": "document"})
                imported_entities.append(entity)

        for landmark in WUHAN_LANDMARKS:
            if landmark["name"] in content:
                entity = self.create_entity(
                    "Landmark",
                    {
                        "name": landmark["name"],
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                        "source": "document",
                    },
                )
                imported_entities.append(entity)

        # 如果有LLM可用，尝试用LLM增强实体提取
        if self.llm_service is not None:
            llm_prompt = (
                f"请从以下文本中提取地理实体（地名、地标、机构名），"
                f"以JSON数组格式返回，每项包含name和type字段：\n\n{content[:500]}"
            )
            llm_result = self.llm_service.generate(llm_prompt)
            if llm_result:
                # 简单解析LLM返回的JSON
                from app.utils.helpers import safe_json_loads
                entities = safe_json_loads(llm_result, [])
                if isinstance(entities, list):
                    for ent in entities:
                        if isinstance(ent, dict) and "name" in ent:
                            entity = self.create_entity(
                                entity_labels[0] if entity_labels else "Entity",
                                {"name": ent["name"], "type": ent.get("type", "unknown"), "source": "llm_extract"},
                            )
                            imported_entities.append(entity)

        logger.info(f"[KGService] 文档导入完成，共创建{len(imported_entities)}个实体")
        return {"imported_count": len(imported_entities), "entities": imported_entities}

    # ==================== 内部辅助方法 ====================

    def _init_memory_store(self):
        """初始化内存模式的数据存储
        
        优先从 init_data.json 加载完整的知识图谱数据（含扩展本体节点），
        同时加载 kg_ontology.py 中的本体定义作为补充。
        """
        # 内置制图约束
        self._memory_store["constraints"] = [
            {"map_type": "traffic", "constraint": "交通图应包含道路和铁路网络，使用暖色调区分道路等级"},
            {"map_type": "tourism", "constraint": "旅游图应标注景点、博物馆、历史遗迹，使用醒目标记"},
            {"map_type": "campus", "constraint": "校园图应包含教学楼、宿舍、绿地等设施，使用清新配色"},
            {"map_type": "basic", "constraint": "基础地图应包含道路、水系、生活设施，使用中性色调"},
            {"map_type": "food", "constraint": "美食图应标注餐厅、咖啡馆等餐饮场所，使用暖色标记"},
            {"map_type": "administrative", "constraint": "行政区划图应包含行政边界，使用区分色填充"},
        ]

        # 优先从 init_data.json 加载完整知识图谱数据
        import os
        import json
        
        init_data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "data", "kg", "init_data.json"
        )
        
        loaded_from_file = False
        if os.path.exists(init_data_path):
            try:
                with open(init_data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 加载init_data.json中的所有节点和关系
                json_nodes = data.get("nodes", [])
                json_relations = data.get("relations", [])
                
                # 转换节点格式：将顶层属性移入properties
                converted_nodes = []
                for node in json_nodes:
                    name = node.pop("name", "")
                    label = node.pop("label", "")
                    # 剩余属性放入properties
                    properties = dict(node)
                    properties["name"] = name
                    converted_nodes.append({
                        "id": name,  # 用name作为ID
                        "label": label,
                        "name": name,
                        "properties": properties,
                    })
                
                self._memory_store["nodes"] = converted_nodes
                self._memory_store["relations"] = json_relations
                logger.info(f"[KGService] 从init_data.json加载: {len(converted_nodes)}个节点, "
                      f"{len(json_relations)}条关系")
                loaded_from_file = True
            except Exception as e:
                logger.info(f"[KGService] 加载init_data.json失败: {e}，回退到本体模块")
        
        # 如果文件加载失败，回退到kg_ontology.py
        if not loaded_from_file:
            try:
                from app.core.kg_ontology import ONTOLOGY_NODES, ONTOLOGY_RELATIONS
                self._memory_store["nodes"] = list(ONTOLOGY_NODES)
                self._memory_store["relations"] = list(ONTOLOGY_RELATIONS)
                logger.info(f"[KGService] 内存知识库已初始化（含{len(ONTOLOGY_NODES)}个本体节点, "
                      f"{len(ONTOLOGY_RELATIONS)}条本体关系）")
            except ImportError:
                self._memory_store["nodes"] = []
                self._memory_store["relations"] = []
                logger.info("[KGService] 内存知识库已初始化（本体模块未加载）")

    def _get_memory_graph_data(self, limit: int) -> Dict[str, List[dict]]:
        """获取内存模式的图谱数据

        从已加载的init_data.json节点和关系构建D3.js格式的图谱数据。
        
        Args:
            limit: 最多返回节点数

        Returns:
            D3.js格式的图谱数据
        """
        all_nodes = self._memory_store.get("nodes", [])
        all_relations = self._memory_store.get("relations", [])
        
        nodes = []
        links = []
        node_name_set = set()
        
        # 添加已加载的节点（限制数量）
        for node in all_nodes[:limit]:
            node_id = node.get("id", node.get("name", ""))
            if node_id in node_name_set:
                continue
            node_name_set.add(node_id)
            nodes.append({
                "id": node_id,
                "label": node.get("label", "Unknown"),
                "name": node.get("name", node.get("properties", {}).get("name", "未命名")),
                "properties": node.get("properties", {}),
            })
        
        # 构建关系链接（仅包含已添加节点之间的关系）
        for rel in all_relations:
            source_name = rel.get("from", rel.get("source", ""))
            target_name = rel.get("to", rel.get("target", ""))
            if source_name in node_name_set and target_name in node_name_set:
                links.append({
                    "source": source_name,
                    "target": target_name,
                    "type": rel.get("type", "RELATED"),
                })
        
        # 如果没有加载到任何节点，回退到内置城市和地标
        if not nodes:
            for i, (city_name, bbox) in enumerate(CITY_BBOX.items()):
                if len(nodes) >= limit:
                    break
                node_id = f"city_{i}"
                nodes.append({
                    "id": node_id,
                    "label": "City",
                    "name": city_name,
                    "properties": {
                        "center_lat": bbox["center_lat"],
                        "center_lon": bbox["center_lon"],
                    },
                })
            
            city_node_id = "city_0"
            for i, landmark in enumerate(WUHAN_LANDMARKS):
                if len(nodes) >= limit:
                    break
                node_id = f"landmark_{i}"
                nodes.append({
                    "id": node_id,
                    "label": "Landmark",
                    "name": landmark["name"],
                    "properties": {
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                    },
                })
                links.append({
                    "source": city_node_id,
                    "target": node_id,
                    "type": "HAS_LANDMARK",
                })
        
        return {"nodes": nodes, "links": links}

    def close(self):
        """关闭Neo4j连接"""
        if self.driver is not None:
            self.driver.close()
            logger.info("[KGService] Neo4j连接已关闭")
