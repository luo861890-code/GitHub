// ========== 会话类型 ==========
export interface Session {
  session_id: string
  title: string
  created_at?: number
  updated_at?: number
}

// ========== 消息类型 ==========
export interface Message {
  id?: string
  session_id?: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  steps?: Step[]
  map_id?: string
  map_summary?: MapSummary | null
  map_data?: MapData | null
  geotoken_info?: GeoTokenInfo | null
  rag_sources?: RagSource[]
  graphrag_entities?: string[]
  graphrag_chain?: GraphragChainHop[]
  knowledge_sources?: KnowledgeSources
  quality?: QualityReport | null
  timestamp?: number
  provider?: string
  model?: string
  created_at?: string
}

export interface Step {
  step_id?: string
  name?: string
  status: 'pending' | 'running' | 'success' | 'failed'
  description?: string
}

// ========== 地图数据类型 ==========
export interface MapData {
  map_id?: string
  name?: string
  map_type?: string
  center?: [number, number]
  zoom?: number
  theme?: string
  layers?: MapLayer[]
  legend?: LegendData
  quality?: QualityReport
  metadata?: Record<string, string>
  layout?: any
  label_metrics?: any
  generalization_metrics?: any
}

export interface MapSummary {
  name?: string
  map_type?: string
  region?: string
  center?: [number, number]
  zoom?: number
  theme?: string
}

export interface MapLayer {
  id: string
  type: LayerType
  name: string
  /** QGIS 式图层分组名（底图/行政区划/水系/道路/轨道交通/地形地貌/注记/POI…） */
  group?: string
  /** 图层级不透明度（QGIS 图层透明度，0-1） */
  opacity?: number
  /** 坐标系（如 EPSG:4326），QGIS 图层属性 */
  crs?: string
  /** 比例尺显示范围（zoom 档位），QGIS 比例尺依赖显示 */
  min_zoom?: number
  max_zoom?: number
  /** QGIS 式标注配置（独立于要素样式的注记设置） */
  label?: LabelConfig
  coordinates?: any
  data?: any
  features?: MapFeature[]
  properties?: Record<string, any>[]
  style?: LayerStyle
  popup?: string
  radius?: number
  visible?: boolean
  metadata?: Record<string, any>
  _lodVisible?: boolean
}

/** QGIS 式标注（Labeling）配置：挂载在图层上，控制该图层注记的渲染 */
export interface LabelConfig {
  enabled?: boolean
  /** 注记字段（properties 中的字段名） */
  field?: string
  /** 字体族：song(宋体)/hei(黑体)/kai(楷体)/bold/italic/normal */
  font?: string
  fontSize?: number
  color?: string
  /** 文字描边（白边） */
  halo?: boolean
  /** 文字方向：horizontal 水平横排 / vertical 竖排 */
  textDirection?: 'horizontal' | 'vertical'
  /** 字头朝向：up / auto */
  orientation?: string
  /** 旋转角度 */
  rotation?: number
  /** 放置方式：point(点位) / along(沿要素) / area(面内居中) */
  placement?: 'point' | 'along' | 'area'
}

export interface MapFeature {
  type: string
  coordinates: any
  style?: LayerStyle
  properties?: Record<string, any>
  geometry?: any
}

export type LayerType =
  | 'polyline' | 'line'
  | 'polygon' | 'area'
  | 'circleMarker' | 'marker' | 'point'
  | 'textLabel' | 'label' | 'text'
  | 'heatmap'
  | 'circle'
  | 'geojson'
  | 'imageOverlay' | 'raster'

export interface LayerStyle {
  color?: string
  borderColor?: string
  fillColor?: string
  weight?: number
  opacity?: number
  fillOpacity?: number
  dashArray?: string | null
  radius?: number
  fontSize?: number
  font?: string
  rotation?: number
  center?: boolean
  icon?: string
  iconClass?: string
  kind?: string
  blur?: number
  maxZoom?: number
  minOpacity?: number
  color_scheme?: string[]
  featureColors?: string[]
  labelsEnabled?: boolean
  labelFontSize?: number
  labelColor?: string
  labelPosition?: string
  /** 注记文字方向：horizontal 水平横排 / vertical 竖排 */
  textDirection?: 'horizontal' | 'vertical'
  /** 白描边（文字外围白色描边） */
  halo?: boolean
  /** 文字样式：italic 斜体 / bold 粗体 / normal */
  fontWeight?: string | number
  /** 注记放置：along 沿要素 / point 点位 */
  placement?: string
}

// ========== 知识图谱类型 ==========
export interface KGNode {
  id: string
  name?: string
  label: string
  properties?: Record<string, any>
  connections?: number
  degree?: number
  radius?: number
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

export interface KGLink {
  source: string | KGNode
  target: string | KGNode
  type?: string
  relation_type?: string
  value?: number
}

export interface KGGraphData {
  nodes: KGNode[]
  links: KGLink[]
}

// ========== 知识来源类型 ==========
export interface RagSource {
  title: string
  score?: number
}

export interface KnowledgeSources {
  rag?: RagSource[]
  graphrag?: {
    entities?: string[]
  }
  kg_answer?: string
}

export interface GraphragChainHop {
  hop?: number
  entities?: string[]
  confidence?: string
}

// ========== GeoToken类型 ==========
export interface GeoTokenInfo {
  layer_count: number
  total_elements: number
  total_area_km2?: number
  layer_details?: GeoTokenLayerDetail[]
}

export interface GeoTokenLayerDetail {
  name: string
  type: string
  element_count: number
}

// ========== 图例类型 ==========
export interface LegendData {
  title?: string
  items: LegendItem[]
}

export interface LegendItem {
  label: string
  type?: string
  color?: string
  fillColor?: string
  fillOpacity?: number
  weight?: number
  dashArray?: string
  group?: string
  icon?: string
  iconClass?: string
}

// ========== 质量报告类型 ==========
export interface QualityReport {
  summary: { passed_all?: boolean; failed?: number }
  items: QualityItem[]
  warnings?: string[]
}

export interface QualityItem {
  check: string
  passed: boolean
  count?: number
  message?: string
  positions?: [number, number][]
}

// ========== 路径规划类型 ==========
export interface RouteData {
  coordinates: [number, number][]
  distance: number
  duration: number
  profile?: string
  profile_name?: string
  source?: string
  steps?: RouteStep[]
}

export interface RouteStep {
  instruction: string
  distance: number
}

// ========== LLM设置类型 ==========
export interface LLMProvider {
  id: string
  name: string
  models: string[]
  configured?: boolean
  masked_key?: string
}

export interface LLMProvidersData {
  current?: string
  current_provider?: string
  provider?: string
  current_model?: string
  model?: string
  providers?: LLMProvider[]
  available?: LLMProvider[]
}

// ========== SSE流式回调类型 ==========
export interface StreamCallbacks {
  onThinking?: (text: string) => void
  onChunk?: (chunk: string) => void
  onMap?: (data: MapData) => void
  onSteps?: (steps: Step[]) => void
  onRag?: (sources: RagSource[]) => void
  onGraphrag?: (data: { entities?: string[] }) => void
  onGraphragChain?: (chain: GraphragChainHop[]) => void
  onGeotoken?: (info: GeoTokenInfo) => void
  onKnowledgeSources?: (sources: KnowledgeSources) => void
  onDone?: (data: { provider?: string; model?: string }) => void
  onError?: (msg: string) => void
}
