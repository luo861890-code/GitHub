<template>
  <div class="legacy-map-panel" :class="{ 'with-chrome': showChrome }">
    <!-- 地图顶栏：图名 / 底图 / 数字比例尺 / 投影 / 撤销重做 / 清除 / 北方向 / 经纬网 -->
    <MapTopBar v-if="showChrome" />

    <div id="map-container" ref="mapEl" class="legacy-map-container"></div>

    <!-- 标准制图整饰（图名/指北针/比例尺/审图落款） -->
    <template v-if="mapStore.currentMapData">
      <div class="map-decoration-title">{{ mapStore.mapName || '未命名地图' }}</div>
      <div class="map-decoration-north">
        <span class="north-arrow">↑</span>
        <span class="north-text">N</span>
      </div>
      <div class="map-decoration-scale">
        <div class="scale-bar">
          <span v-for="i in 4" :key="i" class="scale-seg" :class="{ dark: i % 2 === 1 }"></span>
        </div>
        <div class="scale-label">0 <span class="scale-value">{{ scaleLabel }}</span></div>
      </div>
      <div class="map-decoration-attribution">
        编制单位：地图制图智能体 CartoAgent | 资料来源：DataV GeoAtlas / OSM | 制图时间：{{ today }}
      </div>
    </template>

    <!-- 测量结果提示 -->
    <div v-if="measureMode" class="measure-tooltip">
      <i class="fa-solid fa-ruler"></i>
      <span>{{ measureResult }}</span>
    </div>

    <!-- 底部状态栏：坐标 / 缩放 / 图层数 / 质检 / 编辑状态 -->
    <div v-if="showChrome" class="map-status-bar">
      <div class="map-status-item">
        <i class="fa-solid fa-location-crosshairs"></i>
        <span>{{ statusLat }} · {{ statusLng }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-magnifying-glass"></i>
        <span>缩放 {{ statusZoom }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-layer-group"></i>
        <span>{{ mapStore.sortedLayers.length }} 图层</span>
      </div>
      <div class="map-status-item">
        <span
          class="status-quality"
          :class="qualityClass"
          :title="qualityTitle"
          @click="appStore.toggleLayerPanel()"
        >
          {{ qualityText }}
        </span>
      </div>
      <div class="map-status-item">
        <span class="status-edit" :class="{ editing: appStore.showEditPanel }">
          {{ appStore.showEditPanel ? '编辑中' : '未编辑' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useMapStore } from '@/stores/mapStore'
import { useAppStore } from '@/stores/appStore'
import type { MapData } from '@/types'
import api from '@/services/api'
import { showInputDialog } from '@/utils/dialog'
import MapTopBar from './MapTopBar.vue'

/** 是否显示地图顶栏/底栏（主界面默认显示；QGIS 编辑界面自身已有菜单栏与状态栏，传入 false 避免重复） */
const props = withDefaults(defineProps<{ showChrome?: boolean }>(), {
  showChrome: true,
})

/**
 * 经典 JS 做图模块（MapPanel）集成层。
 *
 * 背景：后端生成的行政区划图等制图逻辑原先由经典前端（8080/app）的 MapPanel 类
 * 负责渲染。本组件用 window 上动态加载的 MapPanel（见 public/legacy/map*.js）
 * 取代原 Vue 侧的 MapCanvas.vue，仅复用其「做图渲染」能力，图层面板/图例/状态栏
 * 等经典 UI 仍由 Vue 侧组件接管（对应 MapPanel 的 headless 模式）。
 *
 * 同时本组件作为主视图的「地图事件总线」：左侧工具栏 / 图层面板 / 浮动面板
 * 通过 `#map-container` 派发 `map-*` 自定义事件，本组件统一监听并转发到
 * Leaflet 地图（panel.map）与 mapStore，保证主视图所有按钮都有实际响应。
 */

/** MapPanel 实例的最小类型描述（完整类定义见 public/legacy/map.js） */
interface MapPanelInstance {
  _headless: boolean
  map: any // Leaflet L.Map 实例
  mapCrsKey: string
  currentTheme: string
  currentMapType: string | null
  currentMapId: string | null
  currentMapData: MapData | null
  tileLayer: any
  layerGroups: Record<string, any>
  _layerOrder: string[]
  _lockedGroups: Record<string, any>
  _labelPlaced: any[]
  _labelNames: Set<string>
  _poiMarkers: any[]
  layerControl: any
  _initEditable?: () => void
  startDraw?: (type: string) => void
  deleteSelectedFeature?: () => void
  undoEdit?: () => void
  redoEdit?: () => void
  copySelectedFeature?: () => void
  simplifySelectedFeature?: () => void
  saveEdits?: () => Promise<void>
  setTheme: (theme: string) => void
  exportMap?: (format: string) => Promise<void>
  refreshLabels(): void
  renderMap(data: MapData): void
  _fitAdministrativeBounds(data: MapData): void
}

const mapStore = useMapStore()
const appStore = useAppStore()
const mapEl = ref<HTMLDivElement | null>(null)

/** 经典 JS MapPanel 实例；由 setupPanel 创建，onBeforeUnmount 销毁 */
let panel: MapPanelInstance | null = null

// ===== 测量工具状态 =====
const measureMode = ref<'distance' | 'area' | null>(null)
const measurePoints = ref<[number, number][]>([])
const measureResult = ref('')
let measureLayer: any = null

/** 路径规划渲染图层 */
let routeLayerGroup: any = null

/** 比例尺/落款状态 */
const scaleLabel = ref('')
const today = new Date().toLocaleDateString('zh-CN')

/** 底部状态栏状态 */
const statusLat = ref('30.5928°')
const statusLng = ref('114.3055°')
const statusZoom = ref('12')

const qualityText = computed(() => {
  const q = mapStore.quality
  if (!q) return '质检中…'
  const fail = q.summary?.failed || 0
  return q.summary?.passed_all ? '质检 ✓ 全部通过' : `质检 ⚠ ${fail} 项异常`
})

const qualityClass = computed(() => {
  const q = mapStore.quality
  if (!q) return ''
  return q.summary?.passed_all ? 'ok' : 'warn'
})

const qualityTitle = computed(() => {
  const q = mapStore.quality
  if (!q) return '数据质量检测（点击图层面板查看）'
  const items = q.items || []
  const failed = items.filter((i: any) => !i.passed)
  return failed.map((i: any) => i.check + (i.message ? ': ' + i.message : '')).join('\n') || '全部通过'
})

/** 底图中文名 → 主题 key 映射（用于任务参数面板） */
const BASEMAP_TO_THEME: Record<string, string> = {
  '高德地图': 'amap_normal',
  '高德卫星': 'amap_satellite',
  '天地图矢量': 'tianditu_vec',
  '天地图影像': 'tianditu_img',
  'OSM标准': 'standard',
  'OSM暗色': 'dark',
  '纯色底图': 'plain',
}

/** 渲染地图数据，并保证容器尺寸正确后再取景 */
function renderMapData(data: MapData) {
  if (!panel?.map) return
  clearRouteLayer()
  // 校准容器尺寸：Vue 挂载/流式渲染初期容器可能为 0，直接 renderMap 会导致
  // 行政图 fitBounds 取景失效（地图停在默认中心，周边地市不可见）
  panel.map.invalidateSize()
  panel.currentMapId = data.map_id || null
  panel.currentMapData = data
  panel.renderMap(data)
  syncPanelVisibility()
  // 流式渲染会多次触发 renderMap，布局仍可能抖动；下一帧再强制取景一次，
  // 确保行政图最终视图正确（显示完整"武汉全域 + 周边地市"范围）
  requestAnimationFrame(() => {
    if (panel?.map && panel._fitAdministrativeBounds) {
      panel.map.invalidateSize()
      panel._fitAdministrativeBounds(data)
    }
    syncPanelVisibility()
  })
}

/** 依据 mapStore 当前图层状态重建地图数据并重渲染（样式/显隐/排序/分析结果即时生效） */
function rebuildFromStore() {
  if (!panel?.map) return
  const base = mapStore.currentMapData || {}
  // 直接复用 mapStore 的原始 data 引用（不做浅拷贝），保证经典 MapPanel 编辑与
  // mapStore 共享同一对象，实现主界面与编辑界面实时同步
  const layers = mapStore.sortedLayers.map((item) => item.data)
  const data: MapData = { ...(base as MapData), layers }
  renderMapData(data)
}

/** 按 mapStore 的显隐状态同步经典 MapPanel 图层（直接操作 Leaflet，不触发后端持久化） */
function syncPanelVisibility() {
  if (!panel?.map) return
  mapStore.sortedLayers.forEach((item) => {
    const cItem = panel?.layerGroups?.[item.id]
    if (!cItem) return
    const onMap = panel!.map.hasLayer(cItem.layer)
    if (item.visible && !onMap) cItem.layer.addTo(panel!.map)
    if (!item.visible && onMap) panel!.map.removeLayer(cItem.layer)
  })
}

// ===== 视图历史（上一视图 / 下一视图） =====
const viewHistory: { center: [number, number]; zoom: number }[] = []
let viewHistoryIndex = -1
let viewHistoryLock = false

function recordView() {
  if (!panel?.map || viewHistoryLock) return
  const c = panel.map.getCenter()
  const v = { center: [c.lat, c.lng] as [number, number], zoom: panel.map.getZoom() }
  const last = viewHistory[viewHistoryIndex]
  if (last && last.center[0] === v.center[0] && last.center[1] === v.center[1] && last.zoom === v.zoom) return
  viewHistory.splice(viewHistoryIndex + 1)
  viewHistory.push(v)
  viewHistoryIndex = viewHistory.length - 1
  if (viewHistory.length > 50) { viewHistory.shift(); viewHistoryIndex-- }
}

function prevView() {
  if (!panel?.map || viewHistoryIndex <= 0) return
  viewHistoryIndex--
  const v = viewHistory[viewHistoryIndex]
  viewHistoryLock = true
  panel.map.setView(v.center, v.zoom)
  setTimeout(() => { viewHistoryLock = false }, 300)
}

function nextView() {
  if (!panel?.map || viewHistoryIndex >= viewHistory.length - 1) return
  viewHistoryIndex++
  const v = viewHistory[viewHistoryIndex]
  viewHistoryLock = true
  panel.map.setView(v.center, v.zoom)
  setTimeout(() => { viewHistoryLock = false }, 300)
}

// ===== 密度分析（点图层 → 热力密度图层） =====
function generateDensityLayer() {
  let targetLayer: any = null
  for (const item of Object.values(mapStore.layerGroups)) {
    const t = item.data?.type
    if (t === 'circleMarker' || t === 'marker' || t === 'point') { targetLayer = item.data; break }
  }
  if (!targetLayer) { (window as any).Utils?.showToast?.('没有点状图层，无法做密度分析', 'warning'); return }
  const points = (targetLayer.coordinates || []).map((c: any) => {
    if (Array.isArray(c) && c.length >= 2 && isFinite(c[0]) && isFinite(c[1])) return [c[0], c[1], 1]
    return null
  }).filter(Boolean)
  if (points.length === 0) { (window as any).Utils?.showToast?.('点图层无有效坐标', 'warning'); return }
  const heatLayer: any = {
    id: 'density_' + Date.now(),
    type: 'heatmap',
    name: `密度分析（${targetLayer.name || '点图层'}）`,
    coordinates: points,
    style: { radius: 25, blur: 15 },
    group: '分析结果',
  }
  const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l) => l.order))
  mapStore.layerGroups[heatLayer.id] = { visible: true, data: heatLayer, order: maxOrder + 1 }
  rebuildFromStore()
  ;(window as any).Utils?.showToast?.(`已生成密度热力图（${points.length} 个点）`, 'success')
}

/** 清除经典 MapPanel 的 Leaflet 图层（headless 安全版，避免触发 DOM 耦合的 updateLayerPanel） */
function clearPanelLayers() {
  if (!panel) return
  Object.values(panel.layerGroups).forEach((item: any) => {
    if (item?.layer) panel!.map.removeLayer(item.layer)
  })
  panel.layerGroups = {}
  panel._layerOrder = []
  panel._labelPlaced = []
  panel._labelNames = new Set()
  panel._poiMarkers = []
}

/** 缩放至指定图层 */
function zoomToLayer(layerId: string) {
  if (!panel?.map) return
  const item = panel.layerGroups[layerId]
  const leafletLayer = item?.layer
  const bounds = leafletLayer?.getBounds?.()
  if (bounds && bounds.isValid()) {
    panel.map.fitBounds(bounds, { padding: [50, 50] })
  }
}

/** 计算并回传地图统计数据（供 ChatPanel 的「地图统计数据」面板显示） */
function emitStats() {
  if (!panel?.map) return
  let totalFeatures = 0
  let pointLayers = 0
  let lineLayers = 0
  let polygonLayers = 0
  let pointFeatures = 0
  let lineFeatures = 0
  let polygonFeatures = 0
  Object.values(mapStore.layerGroups).forEach((item: any) => {
    const d = item.data
    if (!d) return
    const t = d.type || ''
    let count = 0
    if (Array.isArray(d.features)) count = d.features.length
    else if (Array.isArray(d.coordinates)) count = d.coordinates.length
    totalFeatures += count
    if (t === 'point' || t === 'marker' || t === 'circleMarker' || t === 'circle') {
      pointLayers += 1
      pointFeatures += count
    } else if (t === 'line' || t === 'polyline') {
      lineLayers += 1
      lineFeatures += count
    } else if (t === 'polygon' || t === 'area') {
      polygonLayers += 1
      polygonFeatures += count
    }
  })
  const c = panel.map.getCenter()
  const b = panel.map.getBounds()
  const themeCfg = (window as any).CONFIG?.mapThemes?.[mapStore.currentTheme]
  const meta = mapStore.metadata || {}
  window.dispatchEvent(new CustomEvent('map-stats-data', {
    detail: {
      totalLayers: mapStore.sortedLayers.length,
      totalFeatures,
      pointLayers,
      lineLayers,
      polygonLayers,
      pointFeatures,
      lineFeatures,
      polygonFeatures,
      center: `${c.lat.toFixed(4)}, ${c.lng.toFixed(4)}`,
      zoom: panel.map.getZoom().toFixed(2),
      bounds: `${b.getSouthWest().lat.toFixed(2)},${b.getSouthWest().lng.toFixed(2)} ~ ${b.getNorthEast().lat.toFixed(2)},${b.getNorthEast().lng.toFixed(2)}`,
      baseMap: themeCfg?.name || '高德地图',
      dataSource: meta['数据来源'] || meta['资料来源'] || 'OSM / 本地数据',
      createTime: meta['出版日期'] || meta['制图时间'] || meta['资料截止'] || '',
    },
  }))
}

/** 标注模式：点击地图添加自定义标注（调用后端持久化） */
async function handleMarkerClick(e: any) {
  if (!panel?.map || !mapStore.currentMapId) return
  const { lat, lng } = e.latlng
  const name = await showInputDialog({ title: '标注名称', defaultValue: '自定义标注' })
  if (!name || !name.trim()) return
  try {
    await api.addMarker(mapStore.currentMapId, { name: name.trim(), lat, lng })
    const resp = await api.getMap(mapStore.currentMapId)
    const data = resp.data || resp
    mapStore.setMapData(data)
    renderMapData(data)
    ;(window as any).Utils?.showToast?.(`已添加标注: ${name}`, 'success')
    appStore.markerMode = false
  } catch (err: any) {
    ;(window as any).Utils?.showToast?.(`添加标注失败: ${err.message}`, 'error')
  }
}

/** 经纬网开关（图例/比例尺之外的整饰要素） */
let graticuleInited = false
function syncGraticule() {
  if (!panel?.map) return
  const p = panel as any
  if (appStore.showGraticule) {
    if (!graticuleInited) {
      p.initGraticule?.()
      graticuleInited = true
    }
    if (p.graticuleGroup && !panel.map.hasLayer(p.graticuleGroup)) {
      p.graticuleGroup.addTo(panel.map)
      p.graticuleLabelGroup?.addTo(panel.map)
      p._updateGraticule?.()
    }
  } else {
    if (p.graticuleGroup && panel.map.hasLayer(p.graticuleGroup)) {
      panel.map.removeLayer(p.graticuleGroup)
      panel.map.removeLayer(p.graticuleLabelGroup)
    }
  }
}

/** 更新底部比例尺（按当前缩放与纬度估算地面距离） */
function updateScaleBar() {
  if (!panel?.map) return
  const map = panel.map
  const size = map.getSize()
  const y = size.y / 2
  const mPerPx = size.x > 0
    ? map.distance(map.containerPointToLatLng([0, y]), map.containerPointToLatLng([size.x, y])) / size.x
    : 0
  if (!mPerPx) return
  const barW = 120
  const groundM = mPerPx * barW
  let val = groundM >= 1000 ? groundM / 1000 : groundM
  const unit = groundM >= 1000 ? 'km' : 'm'
  if (val <= 0) val = 1
  const mag = Math.pow(10, Math.floor(Math.log10(val)))
  let nice = mag
  for (const n of [1, 2, 5, 10]) {
    if (val <= n * mag) {
      nice = n * mag
      break
    }
  }
  scaleLabel.value = `${nice} ${unit}`
}

/** 向 MapTopBar 同步数字比例尺（1:denominator），denominator = 50000000 / 2^zoom */
function dispatchScaleUpdate() {
  if (!panel?.map) return
  const zoom = panel.map.getZoom()
  const denominator = Math.round(50000000 / Math.pow(2, zoom))
  mapEl.value?.dispatchEvent(
    new CustomEvent('map-scale-update', { detail: { denominator } }),
  )
}

/** 按数字比例尺分母设置缩放级别 */
function setScaleByDenominator(denominator: number) {
  if (!panel?.map) return
  const zoom = Math.log2(50000000 / denominator)
  panel.map.setZoom(zoom)
}

/** 确保经典 MapPanel 的编辑引擎已初始化（headless 模式下按需懒初始化，避免 DOM 耦合） */
function ensureEditReady(): boolean {
  if (!panel?.map) return false
  const p = panel as any
  if (!p.currentMapId) {
    console.warn('[LegacyMapPanel] 请先生成地图再编辑')
    return false
  }
  if (!p.editMode) {
    p.editMode = true
    p._editDirty = {}
    p._undoStack = {}
    p._redoStack = {}
    p._currentEdit = null
    p._tempEditLayer = null
    p._lastSnapTime = {}
  }
  ensureLeafletEditable()
  try { p._initEditable?.() } catch (e) { console.warn('[LegacyMapPanel] 初始化编辑失败', e) }
  try { p._attachAllEditMetadata?.() } catch (e) { console.warn('[LegacyMapPanel] 挂载编辑元数据失败', e) }
  return true
}

/**
 * 确保全局 L 上已挂载 Leaflet.Editable。
 * 根因：index.html 中 leaflet-editable.js 在 CDN 的 leaflet.js 就绪前执行，
 * 导致 factory(window.L) 时 L 尚不存在，Editable 未挂上；这里同步补挂。
 */
function ensureLeafletEditable() {
  const L = (window as any).L
  if (!L) return
  if (L.Editable) return
  try {
    const xhr = new XMLHttpRequest()
    xhr.open('GET', '/legacy/leaflet-editable.js', false)
    xhr.send()
    if (xhr.status === 200) {
      // 重新执行 UMD 工厂，将 Editable 挂到当前 window.L
      ;(0, eval)(xhr.responseText)
    }
  } catch (e) {
    console.warn('[LegacyMapPanel] 补挂 leaflet-editable 失败', e)
  }
}

// ===== 测量工具 =====
function startMeasure(mode: 'distance' | 'area') {
  if (!panel?.map) return
  clearMeasure()
  measureMode.value = mode
  measurePoints.value = []
  measureResult.value = mode === 'distance' ? '点击地图添加测量点，双击结束' : '点击地图添加顶点，双击结束'
  measureLayer = (window as any).L.polyline([], { color: '#f59e0b', weight: 3, dashArray: '6,4' }).addTo(panel.map)
  const onMove = (e: any) => {
    if (measurePoints.value.length > 0) {
      const pts = [...measurePoints.value, [e.latlng.lat, e.latlng.lng]]
      measureLayer.setLatLngs(pts)
    }
  }
  panel.map.on('mousemove', onMove)
  ;(measureLayer as any).__onMove = onMove
}

function clearMeasure() {
  if (measureLayer && panel?.map) {
    const onMove = (measureLayer as any).__onMove
    if (onMove) panel.map.off('mousemove', onMove)
    panel.map.removeLayer(measureLayer)
    measureLayer = null
  }
  measureMode.value = null
  measurePoints.value = []
  measureResult.value = ''
}

/** 在主地图上渲染路径规划结果 */
function showRoute(route: any) {
  const L = (window as any).L
  if (!panel?.map || !L || !route?.coordinates?.length) return
  clearRouteLayer()
  routeLayerGroup = L.layerGroup()
  const coords = route.coordinates.map((c: any) => [c[0], c[1]])
  L.polyline(coords, { color: '#2563eb', weight: 5, opacity: 0.85 }).addTo(routeLayerGroup)
  if (coords.length > 0) {
    L.circleMarker(coords[0], {
      radius: 7, color: '#16a34a', fillColor: '#16a34a', fillOpacity: 1, weight: 2,
    }).addTo(routeLayerGroup).bindPopup('起点')
    L.circleMarker(coords[coords.length - 1], {
      radius: 7, color: '#dc2626', fillColor: '#dc2626', fillOpacity: 1, weight: 2,
    }).addTo(routeLayerGroup).bindPopup('终点')
  }
  routeLayerGroup.addTo(panel.map)
  panel.map.fitBounds(L.latLngBounds(coords), { padding: [60, 60] })
}

function clearRouteLayer() {
  if (routeLayerGroup && panel?.map) {
    panel.map.removeLayer(routeLayerGroup)
    routeLayerGroup = null
  }
}

function updateMeasureResult() {
  if (!panel?.map || measurePoints.value.length < 2) return
  if (measureMode.value === 'distance') {
    let total = 0
    for (let i = 1; i < measurePoints.value.length; i++) {
      total += panel.map.distance(measurePoints.value[i - 1], measurePoints.value[i])
    }
    measureResult.value = `距离：${total < 1000 ? total.toFixed(1) + ' m' : (total / 1000).toFixed(2) + ' km'}`
  } else if (measureMode.value === 'area' && measurePoints.value.length >= 3) {
    const area = panel.map.distance
      ? calcArea(measurePoints.value)
      : 0
    measureResult.value = `面积：${area < 1000000 ? area.toFixed(0) + ' m²' : (area / 1000000).toFixed(2) + ' km²'}`
  }
}

function calcArea(points: [number, number][]): number {
  let area = 0
  const R = 6378137
  for (let i = 0; i < points.length; i++) {
    const p1 = points[i]
    const p2 = points[(i + 1) % points.length]
    area += (p2[1] - p1[1]) * (R * Math.PI / 180) * (R * Math.cos(p1[0] * Math.PI / 180) * Math.PI / 180)
  }
  return Math.abs(area / 2)
}

function handleMapClickForMeasure(e: any) {
  if (!measureMode.value) return
  const { lat, lng } = e.latlng
  measurePoints.value = [...measurePoints.value, [lat, lng] as [number, number]]
  if (measureLayer) measureLayer.setLatLngs(measurePoints.value)
  updateMeasureResult()
}

function handleMapDblClickForMeasure() {
  if (measureMode.value && measurePoints.value.length >= 2) {
    updateMeasureResult()
    clearMeasure()
    if (panel?.map) panel.map.off('click', handleMapClickForMeasure)
  }
}

// ===== 事件处理 =====
function handleMapEvent(e: Event) {
  if (!panel?.map) return
  const detail = (e as CustomEvent).detail
  const type = e.type

  switch (type) {
    case 'map-zoom-in': panel.map.zoomIn(); break
    case 'map-zoom-out': panel.map.zoomOut(); break
    case 'map-zoom-full':
    case 'map-reset-view': {
      const c = mapStore.currentMapData?.center
      panel.map.setView(c && c.length >= 2 ? [c[0], c[1]] : (window as any).CONFIG.defaultMapCenter, mapStore.currentMapData?.zoom || (window as any).CONFIG.defaultZoom)
      break
    }
    case 'map-set-theme': {
      const theme = detail?.theme
      if (theme) {
        panel.setTheme(theme)
        mapStore.setTheme(theme)
      }
      break
    }
    case 'map-set-scale': {
      const denom = Number(detail?.denominator)
      if (denom >= 1000) setScaleByDenominator(denom)
      break
    }
    case 'map-scale-request': {
      dispatchScaleUpdate()
      break
    }
    case 'map-set-projection': {
      const projection = detail?.projection
      if (projection) {
        ;(window as any).Utils?.showToast?.(
          `投影已切换：${projection}（Web 墨卡托渲染保持不变）`,
          'info',
        )
      }
      break
    }
    case 'map-reset-north': {
      if (panel?.map) panel.map.setView(panel.map.getCenter(), panel.map.getZoom())
      break
    }
    case 'map-undo': {
      if (!ensureEditReady()) break
      try { panel.undoEdit?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-redo': {
      if (!ensureEditReady()) break
      try { panel.redoEdit?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-locate': {
      const p = detail
      if (p && p.lat !== undefined && p.lng !== undefined) {
        panel.map.setView([p.lat, p.lng], Math.max(panel.map.getZoom(), 13))
      }
      break
    }
    case 'map-refresh-layers': {
      rebuildFromStore()
      break
    }
    case 'map-apply-data': {
      const data = detail?.data
      if (data) renderMapData(data)
      break
    }
    case 'map-zoom-to-layer': {
      if (detail?.layerId) zoomToLayer(detail.layerId)
      break
    }
    case 'map-clear-layers': {
      clearPanelLayers()
      mapStore.clearAllLayers()
      break
    }
    case 'map-get-stats': emitStats(); break
    case 'map-apply-task-params': {
      const theme = BASEMAP_TO_THEME[detail?.baseMap]
      if (theme) {
        panel.setTheme(theme)
        mapStore.setTheme(theme)
      }
      // 应用图层整体透明度
      if (detail?.opacityValue !== undefined && detail.opacityValue !== null) {
        const op = Math.max(0, Math.min(1, Number(detail.opacityValue) / 100))
        Object.keys(mapStore.layerGroups).forEach((layerId) => {
          mapStore.updateLayerStyle(layerId, { opacity: op })
        })
      }
      break
    }
    case 'map-set-tool': {
      const tool = detail?.tool
      if (!panel?.map) break
      const container = panel.map.getContainer()
      if (tool === 'zoom-box') {
        try { panel.map.boxZoom?.enable() } catch (e) { /* ignore */ }
        container.style.cursor = 'crosshair'
      } else if (tool === 'select') {
        try { panel.map.boxZoom?.disable() } catch (e) { /* ignore */ }
        if (ensureEditReady()) {
          ;(panel as any).editMode = true
          try { (panel as any)._attachAllEditMetadata?.() } catch (e) { /* ignore */ }
        }
        container.style.cursor = 'pointer'
      } else {
        try { panel.map.boxZoom?.disable() } catch (e) { /* ignore */ }
        container.style.cursor = ''
      }
      break
    }
    case 'map-measure-start': {
      startMeasure(detail?.mode || 'distance')
      panel.map.on('click', handleMapClickForMeasure)
      panel.map.on('dblclick', handleMapDblClickForMeasure)
      break
    }
    case 'map-export-image': {
      panel.exportMap?.('png')
      break
    }
    case 'map-show-route': {
      showRoute(detail?.route)
      break
    }
    case 'map-clear-route': {
      clearRouteLayer()
      break
    }
    // ===== 编辑事件：转发到经典 MapPanel 的编辑方法（map-edit.js） =====
    case 'map-edit-draw': {
      if (!ensureEditReady()) break
      try {
        const tool = detail?.tool || detail
        if (tool && panel.startDraw) panel.startDraw(tool)
      } catch (err) { console.warn('[LegacyMapPanel] 开始绘制失败:', err) }
      break
    }
    case 'map-edit-finish-draw': {
      // 编程方式提交当前绘制（等效双击结束）：leaflet-editable 提供 commitDrawing
      try {
        const tools = (panel as any)?.map?.editTools
        if (tools && typeof tools.drawing === 'function' && tools.drawing() && typeof tools.commitDrawing === 'function') {
          tools.commitDrawing()
        }
      } catch (err) { console.warn('[LegacyMapPanel] 结束绘制失败:', err) }
      break
    }
    case 'map-edit-cancel-draw': {
      if (panel?.map) panel.map.fire('editable:drawing:end')
      break
    }
    case 'map-edit-delete': {
      if (!ensureEditReady()) break
      try { panel.deleteSelectedFeature?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-undo': {
      if (!ensureEditReady()) break
      try { panel.undoEdit?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-redo': {
      if (!ensureEditReady()) break
      try { panel.redoEdit?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-copy': {
      if (!ensureEditReady()) break
      try { panel.copySelectedFeature?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-simplify': {
      if (!ensureEditReady()) break
      try { panel.simplifySelectedFeature?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-save': {
      if (!ensureEditReady()) break
      try { panel.saveEdits?.() } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-coord': {
      if (!ensureEditReady()) break
      const p = panel as any
      const lat = detail?.lat
      const lng = detail?.lng
      if (lat == null || lng == null) break
      const candidate = Object.entries(p.layerGroups || {}).find(([, item]: any) => {
        const t = item?.data?.type
        return t === 'circleMarker' || t === 'marker' || t === 'point'
      })
      if (!candidate) { console.warn('[LegacyMapPanel] 没有点状图层可添加'); break }
      const [layerId, item]: any = candidate
      try {
        p._pushUndoSnapshot?.(layerId)
        if (!Array.isArray(item.data.coordinates)) item.data.coordinates = []
        item.data.coordinates.push([lat, lng])
        if (!Array.isArray(item.data.properties)) item.data.properties = []
        item.data.properties.push({ name: '坐标标注' })
        p._markDirty?.(layerId)
        p.rerenderLayer?.(layerId)
      } catch (err) { console.warn('[LegacyMapPanel] 按坐标添加点失败', err) }
      break
    }
    case 'map-edit-attr': {
      if (!ensureEditReady()) break
      try { (panel as any)._updateSelectedAttr?.({ name: detail?.name }) } catch (err) { console.warn(err) }
      break
    }
    case 'map-edit-exit': {
      const p = panel as any
      try { p._clearEditSelection?.() } catch (e) { /* ignore */ }
      p.editMode = false
      p._editDirty = {}
      break
    }
    case 'map-edit-clear-selection': {
      try { (panel as any)._clearEditSelection?.() } catch (e) { /* ignore */ }
      break
    }
    case 'map-feature-select': {
      if (detail?.layerId) {
        appStore.setSelectedLayer(detail.layerId)
      }
      break
    }
    // ===== 高级几何编辑（粘贴/平滑/全选/旋转/缩放/镜像/偏移/合并节点/分割/合并） =====
    case 'map-edit-paste': {
      if (!ensureEditReady()) break
      try { (panel as any).pasteSelectedFeature?.() } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-smooth': {
      if (!ensureEditReady()) break
      try { (panel as any).smoothSelectedFeature?.() } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-select-all': {
      if (!ensureEditReady()) break
      try { (panel as any)._selectAllFeatures?.() } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-rotate': {
      if (!ensureEditReady()) break
      try { (panel as any).rotateSelected?.(Number(detail?.angle) || 0) } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-scale': {
      if (!ensureEditReady()) break
      try { (panel as any).scaleSelected?.(Number(detail?.factor) || 1) } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-mirror': {
      if (!ensureEditReady()) break
      const axis = detail?.axis
      if (axis === 'horizontal' || axis === 'vertical') {
        try { (panel as any).mirrorSelected?.(axis) } catch (e) { console.warn(e) }
      }
      break
    }
    case 'map-edit-offset': {
      if (!ensureEditReady()) break
      try { (panel as any).offsetSelected?.(Number(detail?.distance) || 0) } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-merge-vertex': {
      if (!ensureEditReady()) break
      try { (panel as any).mergeVerticesSelected?.() } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-split': {
      if (!ensureEditReady()) break
      try { (panel as any).splitSelectedFeature?.() } catch (e) { console.warn(e) }
      break
    }
    case 'map-edit-merge': {
      if (!ensureEditReady()) break
      try { (panel as any).mergeSelectedFeatures?.() } catch (e) { console.warn(e) }
      break
    }
    // ===== 分析 / 视图历史 =====
    case 'map-density': {
      generateDensityLayer()
      break
    }
    case 'map-view-prev': {
      prevView()
      break
    }
    case 'map-view-next': {
      nextView()
      break
    }
  }
}

/** 创建经典 JS MapPanel 实例，仅初始化做图渲染所需状态（headless 模式） */
function setupPanel() {
  const w = window as any
  const MP = w.MapPanel
  const L = w.L
  const CONFIG = w.CONFIG
  if (!MP || !L || !CONFIG) {
    console.error('[LegacyMapPanel] 经典 JS 做图模块未加载', { MP: !!MP, L: !!L, CONFIG: !!CONFIG })
    return
  }

  panel = new MP(null) as MapPanelInstance
  // headless 模式：跳过经典前端的图层面板/图例/状态栏等 UI 更新（这些由 Vue 接管）
  panel._headless = true

  // 创建 Leaflet 地图实例（Canvas 渲染 + 0.05 级缩放，禁用默认缩放控件）
  panel.map = L.map(mapEl.value, {
    center: CONFIG.defaultMapCenter,
    zoom: CONFIG.defaultZoom,
    zoomControl: false,
    zoomSnap: 0.05,
    preferCanvas: true,
    attributionControl: true,
  })

  // 初始化做图渲染所需的核心状态（等价于 MapPanel 构造器的字段初始化）
  panel.mapCrsKey = 'WebMercator'
  panel.currentTheme = 'plain'
  panel.currentMapType = null
  panel.currentMapId = null
  panel.currentMapData = null
  panel.tileLayer = null
  panel.layerGroups = {}
  panel._layerOrder = []
  panel._lockedGroups = {}
  panel._labelPlaced = []
  panel._labelNames = new Set()
  panel._poiMarkers = []
  panel.layerControl = null

  // 缩放结束重新应用载负量 LOD（等价于经典前端 initGraticule 中的 zoomend -> refreshLabels）
  panel.map.on('zoomend', () => panel?.refreshLabels())
  // 比例尺随缩放/平移更新
  panel.map.on('zoomend moveend', updateScaleBar)
  updateScaleBar()
  // 底部状态栏：缩放级别 + 数字比例尺同步
  panel.map.on('zoomend moveend', () => {
    statusZoom.value = panel!.map.getZoom().toFixed(2)
    dispatchScaleUpdate()
  })
  // 底部状态栏：鼠标坐标实时显示
  panel.map.on('mousemove', (e: any) => {
    if (!e?.latlng) return
    statusLat.value = e.latlng.lat.toFixed(4) + '°'
    statusLng.value = e.latlng.lng.toFixed(4) + '°'
  })
  // 记录视图历史（上一视图/下一视图）
  panel.map.on('moveend', () => recordView())

  // 注册地图事件监听（主视图工具栏/图层面板/浮动面板通过 #map-container 派发）
  const eventNames = [
    'map-zoom-in', 'map-zoom-out', 'map-zoom-full', 'map-reset-view',
    'map-set-theme', 'map-set-scale', 'map-scale-request', 'map-set-projection',
    'map-reset-north', 'map-undo', 'map-redo',
    'map-locate', 'map-refresh-layers', 'map-apply-data',
    'map-zoom-to-layer', 'map-clear-layers', 'map-get-stats',
    'map-apply-task-params', 'map-measure-start', 'map-export-image',
    'map-set-tool', 'map-show-route', 'map-clear-route',
    'map-feature-select',
    'map-edit-draw', 'map-edit-finish-draw', 'map-edit-cancel-draw',
    'map-edit-delete', 'map-edit-undo', 'map-edit-redo', 'map-edit-copy',
    'map-edit-paste', 'map-edit-smooth', 'map-edit-select-all',
    'map-edit-simplify', 'map-edit-save', 'map-edit-coord', 'map-edit-attr',
    'map-edit-exit', 'map-edit-clear-selection',
    'map-edit-rotate', 'map-edit-scale', 'map-edit-mirror', 'map-edit-offset',
    'map-edit-merge-vertex', 'map-edit-split', 'map-edit-merge',
    'map-density', 'map-view-prev', 'map-view-next',
  ]
  eventNames.forEach((name) => mapEl.value?.addEventListener(name, handleMapEvent))

  // 暴露实例到 window，便于浏览器调试/验证
  ;(window as any).__mapPanel = panel
}

onMounted(async () => {
  setupPanel()
  // 等待 Vue 首轮布局完成再渲染，确保地图容器尺寸正确
  await nextTick()
  if (panel?.map) {
    statusZoom.value = panel.map.getZoom().toFixed(2)
    dispatchScaleUpdate()
  }
  if (mapStore.currentMapData) {
    renderMapData(mapStore.currentMapData)
  }
})

// 地图数据变化（智能体生成新地图 / 切换会话）时重新渲染
watch(
  () => mapStore.currentMapData,
  (data) => {
    if (data) renderMapData(data)
  },
)

// 编辑模式开关：进入/退出经典 MapPanel 编辑会话（编辑界面与主界面共用）
watch(
  () => appStore.showEditPanel,
  (show) => {
    if (show) {
      ensureEditReady()
    } else {
      const p = panel as any
      if (p?.editMode) {
        try { p._clearEditSelection?.() } catch (e) { /* ignore */ }
        p.editMode = false
        p._editDirty = {}
      }
    }
  },
)

// 面板显隐导致地图容器尺寸变化，延迟重算尺寸（等布局稳定）
watch(
  [() => appStore.showChatPanel, () => appStore.showLayerPanel],
  () => setTimeout(() => panel?.map?.invalidateSize(), 300),
)

// 标注模式：启用/停用地图点击监听
watch(
  () => appStore.markerMode,
  (on) => {
    if (!panel?.map) return
    if (on) {
      panel.map.on('click', handleMarkerClick)
      panel.map.getContainer().style.cursor = 'copy'
    } else {
      panel.map.off('click', handleMarkerClick)
      panel.map.getContainer().style.cursor = ''
    }
  }
)

// 经纬网显隐
watch(
  () => appStore.showGraticule,
  () => syncGraticule()
)

// 载负量等级（计划 3.3）：写入全局 LOD 系数并重渲染
watch(
  () => appStore.loadLevel,
  (level) => {
    ;(window as any).CARTO_LOAD_MODE = level
    if (panel?.map) rebuildFromStore()
  }
)

// 图层样式/显隐/排序/增删变化时，防抖重渲染（使图层面板/样式面板/分析结果即时生效）
let layerSyncTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => mapStore.sortedLayers.map((l) => ({ id: l.id, order: l.order, visible: l.visible, style: l.data.style, name: l.data.name })),
  () => {
    if (!panel?.map) return
    if (layerSyncTimer) clearTimeout(layerSyncTimer)
    layerSyncTimer = setTimeout(() => rebuildFromStore(), 120)
  },
  { deep: true },
)

onBeforeUnmount(() => {
  clearMeasure()
  panel?.map?.remove()
  panel = null
})
</script>

<style scoped>
.legacy-map-panel {
  width: 100%;
  height: 100%;
  position: relative;
}
.legacy-map-container {
  width: 100%;
  height: 100%;
}

/* ===== 底部状态栏 ===== */
.map-status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  z-index: 850;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 20px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.map-status-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.map-status-item i {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.status-quality {
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.status-quality.ok {
  background: #dcfce7;
  color: #16a34a;
}

.status-quality.warn {
  background: #fef3c7;
  color: #d97706;
}

.status-edit {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  background: #f3f4f6;
  color: var(--color-text-secondary);
}

.status-edit.editing {
  background: #dbeafe;
  color: #2563eb;
}

.measure-tooltip {
  position: absolute;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: white;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  font-size: 13px;
  color: #374151;
  font-weight: 500;
  pointer-events: none;
}

.measure-tooltip i {
  color: var(--color-primary, #a78bfa);
}

/* ===== 标准制图整饰（图名/指北针/比例尺/审图落款） ===== */
.map-decoration-title {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 780;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #1f2937;
  font-family: 'SimHei', 'Microsoft YaHei', sans-serif;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.85);
  pointer-events: none;
  white-space: nowrap;
}

.map-decoration-north {
  position: absolute;
  top: 10px;
  right: 14px;
  z-index: 780;
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #dc2626;
  font-weight: 700;
  pointer-events: none;
}

.north-arrow {
  font-size: 20px;
  line-height: 1;
}

.north-text {
  font-size: 11px;
}

.map-decoration-scale {
  position: absolute;
  bottom: 34px;
  left: 14px;
  z-index: 780;
  background: rgba(255, 255, 255, 0.85);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  pointer-events: none;
}

.scale-bar {
  display: flex;
  width: 120px;
  height: 6px;
  border: 1px solid #333;
  background: #fff;
}

.scale-seg {
  flex: 1;
}

.scale-seg.dark {
  background: #333;
}

.scale-label {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #333;
  margin-top: 2px;
}

.map-decoration-attribution {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 780;
  font-size: 10px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.75);
  padding: 2px 8px;
  border-radius: 3px;
  pointer-events: none;
  white-space: nowrap;
}

/* 主界面带顶栏/底栏时，制图整饰整体下移/上移，避免被遮挡 */
.legacy-map-panel.with-chrome .map-decoration-title {
  top: 52px;
}

.legacy-map-panel.with-chrome .map-decoration-north {
  top: 52px;
}

.legacy-map-panel.with-chrome .map-decoration-scale {
  bottom: 44px;
}

.legacy-map-panel.with-chrome .map-decoration-attribution {
  bottom: 40px;
}

/* Leaflet 版权控件上移，避免被底部状态栏遮挡 */
.legacy-map-panel.with-chrome :deep(.leaflet-bottom.leaflet-right) {
  bottom: 34px;
}
</style>
