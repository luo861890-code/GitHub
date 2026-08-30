# CartoAgent 架构设计

## 1. 系统概览

CartoAgent 是一个基于大语言模型（LLM）和知识图谱（KG）的在线地图制图智能体系统。系统采用前后端分离架构，后端基于 FastAPI 提供 RESTful API 和 SSE 流式接口，前端基于 Vue 3 + Leaflet 提供地图渲染和编辑能力。

## 2. 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                      前端层 (Vue 3)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 地图画布  │ │ 图层面板  │ │ 智能体聊天│ │ 编辑工具  │  │
│  │ (Leaflet)│ │ (Pinia)  │ │ (SSE)    │ │ (矢量编辑)│  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP / SSE / WebSocket
┌──────────────────────────▼──────────────────────────────┐
│                    API 网关层 (FastAPI)                    │
│  /api/chat  /api/maps  /api/knowledge  /api/settings    │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   业务服务层 (Services)                    │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │ AgentService │ │ MapService  │ │ KnowledgeService │  │
│  │ (智能体核心)  │ │ (地图生成)  │ │ (知识图谱)       │  │
│  └─────────────┘ └─────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │ OSMService   │ │ GeoService  │ │ LLMService       │  │
│  │ (OSM数据)    │ │ (行政区划)  │ │ (大模型调用)     │  │
│  └─────────────┘ └─────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │ QAService    │ │ LabelService│ │ Generalization   │  │
│  │ (质量评估)    │ │ (注记放置)  │ │ (地图综合)       │  │
│  └─────────────┘ └─────────────┘ └──────────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    数据层 (Data)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 地图存储  │ │ 会话存储  │ │ OSM缓存  │ │ 知识图谱  │  │
│  │ (JSON)    │ │ (JSON)    │ │ (JSON)   │ │ (Neo4j)  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 3. 核心模块详解

### 3.1 AgentService（智能体核心）

智能体采用 ReAct（Reasoning + Acting）+ KG（Knowledge Graph）决策架构：

**工作流程**：
1. **需求解析**：LLM 解析用户自然语言，提取城市、地图类型、特殊要求
2. **知识检索**：从 KG 获取制图约束、符号规范、配色方案
3. **KG 决策查询**：查询图层配置、注记规则、载负量阈值
4. **工具匹配**：根据 KG 决策自动推荐工具链
5. **任务规划**：制定数据获取和地图生成计划
6. **地图生成**：调用 MapService 生成地图
7. **质量评估**：调用 QAService 评估地图质量
8. **输出**：返回地图数据和制图过程

**SSE 流式输出**：
- 每个步骤通过 SSE 事件推送到前端
- 支持思考过程（thinking）透明展示
- 支持心跳保活（heartbeat）防止连接超时

### 3.2 MapService（地图生成与管理）

**职责**：
- 根据地图类型和区域生成结构化地图数据
- 管理地图的 CRUD 操作
- 地图数据持久化（按 map_id 独立存储）

**地图生成流程**：
1. 获取区域边界框（CITY_BBOX）
2. 从 OSM/DataV 获取地理数据
3. 按图层类型构建结构化数据（点/线/面/注记）
4. 应用制图样式（颜色/宽度/透明度）
5. 注记自动放置（LabelService）
6. 地图综合（GeneralizationService）
7. 质量检查（QAService）

**地图存储**：
- 索引文件：`data/users/<uid>/maps.json`
- 完整地图：`data/users/<uid>/maps/<map_id>.json`
- 归档地图：`data/users/<uid>/archive/maps/<map_id>.json`

### 3.3 OSMService（OSM 数据获取）

**职责**：
- 通过 Overpass API 获取 OpenStreetMap 数据
- 数据缓存（内存 + 磁盘）
- 数据预处理（坐标校验/去重/裁剪）

**缓存机制**：
- 内存缓存：LRU，最多 20 条，TTL 30 分钟
- 磁盘缓存：`backend/runtime/osm_cache.json`，TTL 24 小时
- 缓存 key：`(region, element_type)`，如 `("武汉市", "highway")`

**数据类型**：
- highway：道路（motorway/trunk/primary/secondary/tertiary/residential）
- railway：铁路/地铁/轻轨
- waterway：河流/溪流/运河
- natural：湖泊/森林/草地
- place：城市/区县/居民地
- amenity/shop/tourism：POI

### 3.4 KnowledgeService（知识图谱）

**职责**：
- 制图学知识存储与查询
- 智能体制图决策支持
- 知识图谱可视化

**知识本体**：
- 地图类型（行政图/交通图/水系图/旅游图...）
- 图层配置（每个地图类型包含哪些图层）
- 符号规范（点/线/面符号样式）
- 配色方案（色盲友好/打印友好/屏幕友好）
- 注记规则（字体/字号/方向/避让）
- 载负量阈值（不同比例尺的要素密度上限）

**存储后端**：
- Neo4j（推荐，支持复杂图查询）
- 本地 JSON 文件（兜底，无需额外服务）

### 3.5 QAService（质量评估）

**评估维度**：
1. **数据完整性**：坐标有效性、要素数量、属性完整性
2. **拓扑连接性**：道路端点连接率、网络连通性
3. **注记质量**：注记密度、重叠率、方向规范性
4. **符号规范**：颜色/宽度/样式符合制图规范
5. **载负量**：要素密度在阈值范围内

**输出**：
- 质量评分（0-100）
- 问题清单（位置/类型/建议）
- 质检报告（JSON）

## 4. 前端架构

### 4.1 技术栈
- Vue 3（Composition API）
- Vite（构建工具）
- TypeScript
- Leaflet（地图渲染）
- Pinia（状态管理）
- vue-router（路由）
- D3（数据可视化）

### 4.2 核心组件
- `LegacyMapPanel.vue`：地图画布（封装 legacy map.js）
- `LayerPanel.vue`：图层面板（显隐/排序/样式）
- `ChatPanel.vue`：智能体聊天（SSE 流式）
- `QgisEditor.vue`：矢量编辑器（节点编辑/属性编辑）
- `StylePanel.vue`：样式面板（颜色/宽度/符号）
- `AttributeTable.vue`：属性表

### 4.3 状态管理（Pinia）
- `appStore`：应用全局状态
- `mapStore`：地图数据和状态
- `chatStore`：聊天会话和消息
- `kgStore`：知识图谱数据
- `editStore`：编辑状态

### 4.4 地图渲染（legacy map.js）
- 基于 Leaflet 的自研 MapPanel
- 支持点/线/面/注记图层
- 支持载负量 LOD（分级显示）
- 支持矢量编辑（leaflet-editable）
- 支持注记自动避让

## 5. 数据流

### 5.1 地图生成数据流
```
用户输入 → ChatPanel → SSE → /api/chat
  → AgentService.process()
    → LLMService.chat()（需求解析）
    → KnowledgeService.query()（知识检索）
    → MapService.generate()（地图生成）
      → OSMService.fetch()（OSM数据）
      → GeoService.build()（行政区划）
      → LabelService.place()（注记放置）
      → GeneralizationService.simplify()（地图综合）
    → QAService.evaluate()（质量评估）
  → SSE 事件流 → ChatPanel（进度展示）
  → 地图数据 → mapStore → LegacyMapPanel（渲染）
```

### 5.2 地图编辑数据流
```
用户操作 → QgisEditor → editStore
  → /api/maps/{id}（保存）
  → MapService.update()
  → 地图文件更新
  → LegacyMapPanel 重新渲染
```

## 6. 扩展性设计

### 6.1 新增地图类型
1. 在 `constants.py` 的 `MAP_TYPE_OSM_TAGS` 中添加数据类型配置
2. 在 `map_service.py` 中添加图层构建逻辑
3. 在 KG 中添加该类型的制图知识
4. 在前端添加快捷指令按钮

### 6.2 新增 LLM 提供商
1. 在 `llm_service.py` 中添加新的 Provider 类
2. 实现统一的 `chat()` 接口
3. 在配置中添加 API Key 和 Base URL

### 6.3 新增数据源
1. 在 `services/` 中添加新的 Service 类
2. 实现统一的数据获取接口
3. 在 `map_service.py` 中集成新数据源

## 7. 性能优化

### 7.1 OSM 数据缓存
- 内存缓存（LRU，30分钟 TTL）
- 磁盘缓存（JSON，24小时 TTL）
- 避免重复请求 Overpass API

### 7.2 地图综合
- 道格拉斯-普克算法（线要素化简）
- 要素合并（相邻同属性要素合并）
- 载负量控制（按比例尺分级显示）

### 7.3 前端渲染
- Leaflet Canvas 渲染（大量要素）
- LOD 分级显示（按缩放级别显示不同细节）
- 注记避让（避免重叠）

### 7.4 SSE 流式
- 心跳保活（每15秒）
- 分块传输（避免单次响应过大）
- 进度透明（每个步骤实时推送）
