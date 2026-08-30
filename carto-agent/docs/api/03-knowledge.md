# 知识图谱 API

> 前缀：`/api/knowledge`
> 源码：`backend/app/api/knowledge.py`

## 端点列表

### 实体管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/entities` | 创建实体 |
| GET | `/entities/{label}` | 获取实体列表 |
| PUT | `/entities/{node_id}` | 更新实体 |
| DELETE | `/entities/{node_id}` | 删除实体 |

### 关系管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/relations` | 创建关系 |

### 图谱查询
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/graph` | 获取完整图谱 |
| POST | `/query` | Cypher 查询 |
| GET | `/subgraph/{entity_name}` | 获取子图 |
| GET | `/ontology` | 获取本体定义 |

### 数据管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/import` | 导入数据 |
| POST | `/init` | 初始化图谱 |
| GET | `/constraints` | 获取约束 |

### 制图知识
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/styles/{map_type}` | 获取地图样式 |
| GET | `/cqs` | 获取制图质量标准 |
| POST | `/symbol-recommend` | 符号推荐 |

### 智能检索
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/rag-search` | RAG 检索 |
| POST | `/graphrag` | GraphRAG 检索 |

---

## 1. 创建实体

**POST** `/api/knowledge/entities`

### 请求体

```json
{
  "label": "MapType",
  "name": "交通图",
  "properties": {
    "description": "展示道路、铁路等交通要素的地图",
    "primary_layers": ["道路", "铁路", "交通枢纽"]
  }
}
```

---

## 2. 获取实体列表

**GET** `/api/knowledge/entities/{label}`

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| label | string | 实体类型（MapType/Layer/Symbol/...） |
| limit | int | 返回数量 |
| offset | int | 偏移量 |

---

## 3. 更新实体

**PUT** `/api/knowledge/entities/{node_id}`

---

## 4. 删除实体

**DELETE** `/api/knowledge/entities/{node_id}`

---

## 5. 创建关系

**POST** `/api/knowledge/relations`

### 请求体

```json
{
  "source": "实体A_ID",
  "target": "实体B_ID",
  "type": "USES_SYMBOL",
  "properties": {"condition": "高速公路"}
}
```

---

## 6. 获取完整图谱

**GET** `/api/knowledge/graph`

返回所有节点和关系，用于图谱可视化。

### 响应

```json
{
  "code": 0,
  "data": {
    "nodes": [
      {"id": "n1", "label": "MapType", "name": "交通图"},
      {"id": "n2", "label": "Layer", "name": "道路"}
    ],
    "relations": [
      {"source": "n1", "target": "n2", "type": "INCLUDES"}
    ]
  }
}
```

---

## 7. Cypher 查询

**POST** `/api/knowledge/query`

执行自定义 Cypher 查询（Neo4j 模式下）。

### 请求体

```json
{
  "cypher": "MATCH (m:MapType)-[:INCLUDES]->(l:Layer) WHERE m.name = '交通图' RETURN l",
  "params": {}
}
```

---

## 8. 获取子图

**GET** `/api/knowledge/subgraph/{entity_name}`

获取指定实体的关联子图。

---

## 9. 获取本体定义

**GET** `/api/knowledge/ontology`

返回知识图谱的本体 schema（节点类型、关系类型、属性定义）。

---

## 10. 导入数据

**POST** `/api/knowledge/import`

从 JSON/CSV 文件批量导入知识图谱数据。

### 请求体（multipart/form-data）

| 字段 | 类型 | 说明 |
|------|------|------|
| file | file | 数据文件 |
| format | string | 格式：json/csv |
| merge | boolean | 是否合并到现有图谱 |

---

## 11. 初始化图谱

**POST** `/api/knowledge/init`

初始化制图知识图谱（加载内置本体和基础数据）。

### 响应

```json
{
  "code": 0,
  "data": {
    "nodes_created": 150,
    "relations_created": 300,
    "message": "制图知识图谱初始化完成"
  }
}
```

---

## 12. 获取约束

**GET** `/api/knowledge/constraints`

获取图谱中的约束条件（唯一性约束、属性约束等）。

---

## 13. 获取地图样式

**GET** `/api/knowledge/styles/{map_type}`

从知识图谱获取指定地图类型的推荐样式配置。

### 路径参数

| 参数 | 说明 |
|------|------|
| map_type | 地图类型：admin/traffic/water/tour/... |

### 响应

```json
{
  "code": 0,
  "data": {
    "map_type": "traffic",
    "background": "#F0F0F0",
    "layers": [
      {"name": "高速公路", "color": "#FF0000", "weight": 4},
      {"name": "主干道", "color": "#FFA500", "weight": 3},
      {"name": "次干道", "color": "#FFFF00", "weight": 2}
    ],
    "annotation": {"direction": "horizontal", "font_size": 12}
  }
}
```

---

## 14. 获取制图质量标准

**GET** `/api/knowledge/cqs`

获取 Cartographic Quality Standards（制图质量标准）。

---

## 15. 符号推荐

**POST** `/api/knowledge/symbol-recommend`

根据要素类型和地图类型推荐合适的符号样式。

### 请求体

```json
{
  "feature_type": "station",
  "map_type": "traffic",
  "scale": "1:100000"
}
```

### 响应

```json
{
  "code": 0,
  "data": {
    "symbol": {
      "type": "circle",
      "color": "#FFFFFF",
      "borderColor": "#000000",
      "borderWidth": 2,
      "radius": 6
    },
    "alternatives": [...],
    "reason": "车站在交通图中通常使用白色圆形加黑色边框"
  }
}
```

---

## 16. RAG 检索

**POST** `/api/knowledge/rag-search`

基于检索增强生成（RAG）查询制图知识。

### 请求体

```json
{
  "query": "交通图中道路应该如何分级配色",
  "top_k": 5
}
```

### 响应

```json
{
  "code": 0,
  "data": {
    "answer": "交通图中道路通常按等级配色：高速公路红色、主干道橙色、次干道黄色...",
    "sources": [
      {"node": "道路分级", "relevance": 0.95},
      {"node": "交通图配色方案", "relevance": 0.88}
    ]
  }
}
```

---

## 17. GraphRAG 检索

**POST** `/api/knowledge/graphrag`

基于图结构的 RAG 检索，结合实体关系推理。

### 请求体

```json
{
  "query": "武汉市交通图需要哪些图层和符号",
  "depth": 2,
  "top_k": 10
}
```

---

## 知识图谱本体

### 节点类型

| 类型 | 说明 | 示例 |
|------|------|------|
| MapType | 地图类型 | 交通图、行政区划图、水系图 |
| Layer | 图层 | 道路、湖泊、行政边界 |
| Symbol | 符号 | 红色实线、蓝色面填充 |
| ColorScheme | 配色方案 | 色盲友好、打印友好 |
| AnnotationRule | 注记规则 | 横向、字号、避让 |
| DataSource | 数据源 | OSM、DataV、SRTM |
| QualityStandard | 质量标准 | 数据完整性、拓扑连接 |

### 关系类型

| 类型 | 说明 |
|------|------|
| INCLUDES | 地图类型包含图层 |
| USES_SYMBOL | 图层使用符号 |
| USES_COLOR | 图层使用配色 |
| HAS_ANNOTATION | 图层有注记规则 |
| SOURCED_FROM | 数据来源于 |
| RELATED_TO | 相关 |
| CONTRASTS_WITH | 对比 |
