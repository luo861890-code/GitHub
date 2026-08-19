<template>
  <main class="map-panel">
    <!-- 顶部地图信息条：名称/主题/比例尺/经纬网 -->
    <MapTopBar />

    <!-- 地图容器 -->
    <div id="map-container" ref="mapContainerRef"></div>

    <!-- 自然语言修改输入框 -->
    <div class="map-modify-wrapper">
      <input
        v-model="modifyInput"
        type="text"
        class="map-modify-input"
        placeholder="自然语言修改地图，如'把道路改成红色'..."
        @keydown.enter="handleModify"
      />
      <button class="map-modify-btn" @click="handleModify" title="执行修改">
        <i class="fa-solid fa-wand-magic-sparkles"></i>
      </button>
    </div>

    <!-- 图例按钮 -->
    <button
      v-if="legendData || mapStore.sortedLayers.length > 0"
      class="map-legend-btn"
      :class="{ active: appStore.showLegendPanel }"
      title="显示完整图例"
      @click="appStore.toggleLegendPanel()"
    >
      <i class="fa-solid fa-book-open"></i>
      <span>图例</span>
    </button>

    <!-- 完整图例面板 -->
    <MapLegendPanel v-if="appStore.showLegendPanel" :legend-data="legendData" />

    <!-- 行政区划迷你图例 -->
    <MiniLegend v-if="mapStore.mapType === 'administrative'" />

    <!-- 任务参数面板 -->
    <ParamsPanel v-if="appStore.showParamsPanel" />

    <!-- 空间分析面板 -->
    <AnalysisPanel v-if="appStore.showAnalysisPanel" />

    <!-- 编辑模式面板 -->
    <MapEditPanel v-if="appStore.showEditPanel" />

    <!-- 路径规划面板 -->
    <div v-if="appStore.showRoutePanel" class="map-route-panel">
      <div class="route-panel-header">
        <span><i class="fa-solid fa-route"></i> 路径规划</span>
        <button class="route-panel-close" @click="appStore.toggleRoutePanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="route-panel-body">
        <div class="route-field">
          <label>出行方式</label>
          <div class="route-profile-group">
            <button :class="{ active: routeProfile === 'driving' }" @click="routeProfile = 'driving'"><i class="fa-solid fa-car"></i> 驾车</button>
            <button :class="{ active: routeProfile === 'walking' }" @click="routeProfile = 'walking'"><i class="fa-solid fa-person-walking"></i> 步行</button>
            <button :class="{ active: routeProfile === 'cycling' }" @click="routeProfile = 'cycling'"><i class="fa-solid fa-bicycle"></i> 骑行</button>
          </div>
        </div>
        <div class="route-field">
          <label>
            <i class="fa-solid fa-circle-dot route-start-icon"></i> 起点
            <span class="route-hint">（在地图上点击设置）</span>
          </label>
          <div class="route-coord-input">
            <input id="route-start-lat" v-model="routeStartLat" type="number" placeholder="纬度" step="0.0001" class="route-input" @focus="enterRoutePick('start')" />
            <input id="route-start-lng" v-model="routeStartLng" type="number" placeholder="经度" step="0.0001" class="route-input" @focus="enterRoutePick('start')" />
          </div>
        </div>
        <div class="route-field">
          <label>
            <i class="fa-solid fa-location-dot route-end-icon"></i> 终点
            <span class="route-hint">（在地图上点击设置）</span>
          </label>
          <div class="route-coord-input">
            <input id="route-end-lat" v-model="routeEndLat" type="number" placeholder="纬度" step="0.0001" class="route-input" @focus="enterRoutePick('end')" />
            <input id="route-end-lng" v-model="routeEndLng" type="number" placeholder="经度" step="0.0001" class="route-input" @focus="enterRoutePick('end')" />
          </div>
        </div>
        <button class="route-plan-btn" @click="handlePlanRoute">
          <i class="fa-solid fa-route"></i> 开始规划
        </button>
        <div v-if="mapStore.routeData" class="route-result">
          <div class="route-result-stats">
            <div class="route-stat">
              <span class="route-stat-label">距离</span>
              <span class="route-stat-value">{{ (mapStore.routeData.distance / 1000).toFixed(2) }} km</span>
            </div>
            <div class="route-stat">
              <span class="route-stat-label">预计时间</span>
              <span class="route-stat-value">{{ Math.round(mapStore.routeData.duration / 60) }} 分钟</span>
            </div>
          </div>
          <div class="route-steps">
            <div v-for="(step, idx) in mapStore.routeData.steps" :key="idx" class="route-step">
              <span class="route-step-num">{{ idx + 1 }}</span>
              <span class="route-step-text">{{ step.instruction }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 测量工具提示 -->
    <div v-if="measureMode" class="measure-tooltip">
      <i class="fa-solid fa-ruler"></i>
      <span>{{ measureResult }}</span>
    </div>

    <!-- 底部状态栏 -->
    <div class="map-status-bar">
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
        <span class="status-quality" :class="qualityClass" :title="qualityTitle">
          {{ qualityText }}
        </span>
      </div>
      <div class="map-status-item">
        <span class="status-edit" :class="{ editing: editStore.active }">
          {{ editStore.active ? '编辑中' : '未编辑' }}
        </span>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
/**
 * 地图渲染与编辑组件（编辑界面专用）。
 *
 * 职责边界：
 *  - 主界面（App 的 main 视图）的「做图渲染」已由 LegacyMapPanel.vue 接管
 *    （复用经典 JS MapPanel 做图模块，保证与 8080/app 行政区划图效果一致）；
 *  - 本组件保留给 QgisEditor 编辑界面使用，额外承载 QGIS 式几何编辑
 *    （Leaflet editable）、自然语言修改、图层样式编辑等交互能力。
 */
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import importL from 'leaflet'
import 'leaflet/dist/leaflet.css'
// 运行时统一使用全局 window.L（与 LegacyMapPanel / 经典 MapPanel 共享同一 Leaflet 实例，
// 确保 leaflet-editable 等全局插件可用）；importL 仅用于 TS 类型推导。
const L = ((window as any).L as typeof importL) || importL
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { useEditStore } from '@/stores/editStore'
import api from '@/services/api'
import { CONFIG } from '@/config'
import MapTopBar from './MapTopBar.vue'
import MapLegendPanel from './MapLegendPanel.vue'
import MiniLegend from './MiniLegend.vue'
import MapEditPanel from './MapEditPanel.vue'
import ParamsPanel from './ParamsPanel.vue'
import AnalysisPanel from './AnalysisPanel.vue'
import type { MapData, MapLayer, LegendData } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()
const editStore = useEditStore()

const mapContainerRef = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let currentBaseLayer: L.TileLayer | null = null
const layerMap = new Map<string, L.Layer>()
// 图层数据索引（用于 LOD 显隐控制与取景）
const layerDataById = new Map<string, MapLayer>()

// 状态
const currentTheme = ref('amap_normal')
const modifyInput = ref('')
const legendData = ref<LegendData | null>(null)
const statusLat = ref('30.5928°')
const statusLng = ref('114.3055°')
const statusZoom = ref('12')

// 路径规划
const routeProfile = ref('driving')
const routeStartLat = ref('')
const routeStartLng = ref('')
const routeEndLat = ref('')
const routeEndLng = ref('')
const routePickMode = ref<'start' | 'end' | null>(null)

// 测量工具
const measureMode = ref<'distance' | 'area' | 'angle' | null>(null)
const measurePoints = ref<[number, number][]>([])
const measureResult = ref('')
let measureLayer: L.LayerGroup | null = null

// 编辑模式
let vertexMarkers: L.Marker[] = []

const layerEntries = computed(() => {
  return Object.entries(mapStore.layerGroups)
})

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
  if (!q) return '数据质量检测（点击查看异常）'
  const items = q.items || []
  const failed = items.filter((i: any) => !i.passed)
  return failed.map((i: any) => i.check + (i.message ? ': ' + i.message : '')).join('\n') || '全部通过'
})

// ========== 初始化地图 ==========
onMounted(() => {
  if (!mapContainerRef.value) return

  const [lat, lng] = CONFIG.defaultMapCenter

  // 初始化Leaflet地图
  map = L.map(mapContainerRef.value, {
    center: [lat, lng],
    zoom: CONFIG.defaultZoom,
    zoomControl: false,
    attributionControl: false,
  })

  // 添加缩放控件
  L.control.zoom({ position: 'topright' }).addTo(map)

  // 添加比例尺控件
  L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map)

  // 设置初始底图（制图底图，无瓦片，和carto-agent-1一致）
  setTheme('plain')

  // 监听地图移动
  map.on('move', updateStatusBar)
  map.on('moveend', () => {
    updateScaleDisplay()
    recordView()
  })
  map.on('zoomend', () => {
    updateScaleDisplay()
    applyLod()
  })
  map.on('click', handleMapClick)
  map.on('dblclick', handleMapDblClick)

  // 如果已经有地图数据，直接渲染
  if (mapStore.currentMapData) {
    renderMap(mapStore.currentMapData)
  }
  // 记录初始视图（供上一视图/下一视图）
  setTimeout(() => recordView(), 150)

  // ===== 自定义事件监听 =====
  const el = mapContainerRef.value
  const listeners: Array<[string, EventListener]> = [
    ['map-reset-view', () => { map?.setView([lat, lng], CONFIG.defaultZoom) }],
    ['map-clear-layers', () => { mapStore.clearAllLayers(); mapStore.clearRoute() }],
    ['map-zoom-in', () => { map?.zoomIn() }],
    ['map-zoom-out', () => { map?.zoomOut() }],
    ['map-zoom-full', () => { map?.setView([lat, lng], CONFIG.defaultZoom) }],
    ['map-export-image', handleExportImage],
    ['map-refresh-layers', () => { refreshLayersFromStore() }],
    ['map-zoom-to-layer', handleZoomToLayer],
    ['map-locate', (e) => {
      const p = (e as CustomEvent).detail
      if (p && map) {
        map.setView([p.lat, p.lng], Math.max(map.getZoom(), 13))
      }
    }],
    ['map-set-theme', (e) => { const theme = (e as CustomEvent).detail?.theme; if (theme) setTheme(theme) }],
    ['map-set-scale', (e) => { const denom = (e as CustomEvent).detail?.denominator; if (denom) zoomForScale(denom) }],
    ['map-scale-request', () => { updateScaleDisplay() }],
    ['map-apply-data', (e) => {
      const data = (e as CustomEvent).detail?.data
      if (data) {
        renderMap(data)
      }
    }],
    ['map-undo', () => { undoEdit() }],
    ['map-redo', () => { redoEdit() }],
    ['map-reset-north', () => { map?.setView(map.getCenter(), map.getZoom()) }],
    ['map-get-stats', () => {
      // 发送地图统计数据
      const stats = {
        layerCount: mapStore.sortedLayers.length,
        featureCount: 0,
        center: map?.getCenter(),
        zoom: map?.getZoom(),
      }
      window.dispatchEvent(new CustomEvent('map-stats-data', { detail: stats }))
    }],
    ['map-apply-task-params', (e) => {
      const params = (e as CustomEvent).detail || {}
      const themeMap: Record<string, string> = {
        '高德地图': 'amap_normal',
        '高德卫星': 'amap_satellite',
        '天地图矢量': 'tianditu_vec',
        '天地图影像': 'tianditu_img',
        'OSM标准': 'standard',
        'OSM暗色': 'dark',
        '纯色底图': 'plain',
      }
      const theme = themeMap[params.baseMap]
      if (theme) setTheme(theme)
      if (params.opacityValue !== undefined && params.opacityValue !== null) {
        const op = Math.max(0, Math.min(1, Number(params.opacityValue) / 100))
        mapStore.sortedLayers.forEach((l) => mapStore.updateLayerStyle(l.id, { opacity: op }))
      }
    }],
    ['map-set-projection', (e) => {
      const projection = (e as CustomEvent).detail?.projection
      if (projection) {
        ;(window as any).Utils?.showToast?.(`投影已切换：${projection}（渲染仍为 Web墨卡托）`, 'info')
      }
    }],
    // 测量工具
    ['map-measure-start', (e) => {
      const mode = (e as CustomEvent).detail?.mode
      if (mode === 'distance' || mode === 'area' || mode === 'angle') startMeasure(mode)
    }],
    ['map-measure-clear', clearMeasure],
    // 视图历史
    ['map-view-prev', prevView],
    ['map-view-next', nextView],
    // 编辑工具（QGIS/ArcGIS 式矢量编辑）
    ['map-edit-draw', (e) => { const t = (e as CustomEvent).detail?.tool; if (t) startDraw(t) }],
    ['map-edit-delete', deleteSelectedFeature],
    ['map-edit-undo', undoEdit],
    ['map-edit-redo', redoEdit],
    ['map-edit-copy', copySelectedFeature],
    ['map-edit-paste', pasteSelectedFeature],
    ['map-edit-simplify', simplifySelectedFeature],
    ['map-edit-smooth', smoothSelectedFeature],
    ['map-edit-save', saveEdits],
    ['map-edit-coord', (e) => { const d = (e as CustomEvent).detail; if (d?.lat != null && d?.lng != null) addPointByCoord(d.lat, d.lng) }],
    ['map-edit-attr', (e) => { const d = (e as CustomEvent).detail; if (d?.name != null && currentEdit) { const p = getSelectedProps(); if (p) { p.name = d.name; markDirty(currentEdit.layerId) } } }],
    ['map-edit-exit', exitEditMode],
    ['map-edit-clear-selection', clearSelection],
    ['map-edit-select-all', selectAllFeatures],
    ['map-edit-finish-draw', () => {
      // 编程方式提交当前绘制（等效双击结束）：leaflet-editable 提供 commitDrawing
      try {
        const tools = (map as any)?.editTools
        if (tools && typeof tools.drawing === 'function' && tools.drawing() && typeof tools.commitDrawing === 'function') {
          tools.commitDrawing()
        }
      } catch (e) { console.warn('[MapCanvas] 结束绘制失败', e) }
    }],
    ['map-edit-cancel-draw', () => { if (map) map.fire('editable:drawing:end') }],
    ['map-set-tool', (e) => {
      const tool = (e as CustomEvent).detail?.tool
      if (!map) return
      const container = map.getContainer()
      if (tool === 'zoom-box') {
        try { (map as any).boxZoom?.enable() } catch (err) { /* ignore */ }
        container.style.cursor = 'crosshair'
      } else if (tool === 'select') {
        try { (map as any).boxZoom?.disable() } catch (err) { /* ignore */ }
        enterEditMode()
        container.style.cursor = 'pointer'
      } else {
        try { (map as any).boxZoom?.disable() } catch (err) { /* ignore */ }
        container.style.cursor = ''
      }
    }],
    // 几何变换
    ['map-edit-rotate', (e) => rotateSelected(Number((e as CustomEvent).detail?.angle) || 0)],
    ['map-edit-scale', (e) => scaleSelected(Number((e as CustomEvent).detail?.factor) || 1)],
    ['map-edit-mirror', (e) => { const axis = (e as CustomEvent).detail?.axis; if (axis === 'horizontal' || axis === 'vertical') mirrorSelected(axis) }],
    ['map-edit-offset', (e) => offsetSelected(Number((e as CustomEvent).detail?.distance) || 0)],
    ['map-edit-merge-vertex', mergeVerticesSelected],
    ['map-edit-split', splitSelectedFeature],
    ['map-edit-merge', mergeSelectedFeatures],
    ['map-density', generateDensityLayer],
    // 清空地图（新对话时）
    ['map-clear-all', () => {
      if (!map) return
      layerMap.forEach((l) => map?.removeLayer(l))
      layerMap.clear()
      layerDataById.clear()
      if (measureLayer) { map.removeLayer(measureLayer); measureLayer = null }
      measureMode.value = null
      measurePoints.value = []
      measureResult.value = ''
      clearSelection()
      if (editing) exitEditMode()
    }],
  ]
  listeners.forEach(([name, fn]) => el.addEventListener(name, fn))

  // 面板切换时 resize
  watch(
    () => appStore.showChatPanel,
    () => setTimeout(() => map?.invalidateSize(), 300)
  )
  watch(
    () => appStore.showLayerPanel,
    () => setTimeout(() => map?.invalidateSize(), 300)
  )

  // 底图主题变化
  watch(
    () => mapStore.currentTheme,
    (theme) => {
      if (theme && theme !== currentTheme.value) setTheme(theme)
    }
  )

  // 地图数据变化
  watch(
    () => mapStore.currentMapData,
    (data) => {
      if (data && map) renderMap(data)
    }
  )

  // 图层变化实时刷新
  watch(
    () => mapStore.sortedLayers,
    () => {
      if (map) refreshLayersFromStore()
    },
    { deep: true }
  )

  // 编辑模式开关
  watch(
    () => appStore.showEditPanel,
    (show) => {
      if (show) enterEditMode()
      else exitEditMode()
    }
  )

  // 键盘快捷键：Ctrl+Z / Ctrl+Y
  const handleKeydown = (e: KeyboardEvent) => {
    if (!editStore.active) return
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault()
      undoEdit()
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
      e.preventDefault()
      redoEdit()
    }
  }
  document.addEventListener('keydown', handleKeydown)

  const handleEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && measureMode.value) {
      clearMeasure()
    }
  }
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  map?.remove()
  map = null
  clearVertexMarkers()
})

// ========== 底图主题 ==========
function setTheme(themeName: string) {
  const themeConfig = CONFIG.mapThemes[themeName]
  if (!themeConfig || !map) return

  // 移除当前底图
  if (currentBaseLayer) {
    map.removeLayer(currentBaseLayer)
    currentBaseLayer = null
  }

  // 添加新底图（如果有url的话）
  if (themeConfig.url && themeConfig.url.trim() !== '') {
    let tileUrl = themeConfig.url
    let subdomains: string | string[] | undefined

    if (themeConfig.subdomains && themeConfig.subdomains.length > 0) {
      subdomains = themeConfig.subdomains.split('')
    }

    currentBaseLayer = L.tileLayer(tileUrl, {
      maxZoom: themeConfig.maxZoom,
      attribution: themeConfig.attribution,
      subdomains: subdomains,
      crossOrigin: true,
    }).addTo(map)
  }

  currentTheme.value = themeName
  
  // 同步更新store中的底图名称
  if (mapStore.currentTheme !== themeName) {
    mapStore.setTheme(themeName)
  }
}

// ========== 状态栏更新 ==========
function updateStatusBar() {
  if (!map) return
  const center = map.getCenter()
  statusLat.value = center.lat.toFixed(4) + '°'
  statusLng.value = center.lng.toFixed(4) + '°'
  statusZoom.value = map.getZoom().toString()
}

function updateScaleDisplay() {
  // 发送比例尺更新事件
  if (map) {
    const zoom = map.getZoom()
    window.dispatchEvent(new CustomEvent('map-scale-update', { detail: { zoom } }))
  }
}

function zoomForScale(denominator: number) {
  // 简单的比例尺转缩放级别
  if (!map) return
  const zoom = Math.log2(50000000 / denominator)
  map.setZoom(zoom)
}

// ========== 地图点击 ==========
function handleMapClick(e: L.LeafletMouseEvent) {
  const { lat, lng } = e.latlng

  // 路径规划选点
  if (routePickMode.value) {
    if (routePickMode.value === 'start') {
      routeStartLat.value = lat.toFixed(4)
      routeStartLng.value = lng.toFixed(4)
    } else {
      routeEndLat.value = lat.toFixed(4)
      routeEndLng.value = lng.toFixed(4)
    }
    routePickMode.value = null
    return
  }

  // 标注模式：点击后吸附到最近的要素（50像素范围内）
  if (appStore.markerMode) {
    const snapped = snapToNearestFeature(lat, lng, 50)
    const target = snapped || [lat, lng]
    addAnnotationMarker(target[0], target[1], snapped ? snapped.name : null)
    appStore.toggleMarkerMode()
    return
  }

  // 测量模式
  if (measureMode.value) {
    measurePoints.value.push([lat, lng])
    drawMeasureOverlay()
    updateMeasureResult()
    return
  }

  // 编辑模式
  if (editStore.active) {
    // 编辑模式点击处理
    return
  }
}

function handleMapDblClick(e: L.LeafletMouseEvent) {
  // 测量模式双击结束
  if (measureMode.value && measurePoints.value.length > 1) {
    updateMeasureResult()
  }
}

// ========== 路径规划 ==========
function enterRoutePick(mode: 'start' | 'end') {
  routePickMode.value = mode
}

async function handlePlanRoute() {
  if (!routeStartLat.value || !routeStartLng.value || !routeEndLat.value || !routeEndLng.value) {
    alert('请先设置起点和终点')
    return
  }

  try {
    const res = await api.planRoute(mapStore.currentMapData?.map_id ?? '', {
      start: [parseFloat(routeStartLng.value), parseFloat(routeStartLat.value)],
      end: [parseFloat(routeEndLng.value), parseFloat(routeEndLat.value)],
      profile: routeProfile.value,
    })
    if (res.success && res.data) {
      mapStore.setRouteData(res.data)
    }
  } catch (e) {
    console.error('路径规划失败', e)
  }
}

// ========== 测量工具 ==========
function startMeasure(mode: 'distance' | 'area' | 'angle') {
  measureMode.value = mode
  measurePoints.value = []
  if (measureLayer) { map?.removeLayer(measureLayer); measureLayer = null }
  measureLayer = L.layerGroup().addTo(map!)
  const hint = mode === 'distance' ? '点击地图添加测量点，双击结束'
    : mode === 'area' ? '点击地图添加顶点，双击结束'
    : '依次点击 3 个点测量夹角'
  measureResult.value = hint
  setMapCursor('crosshair')
  editStore.setStatus(`测量${mode === 'distance' ? '距离' : mode === 'area' ? '面积' : '角度'}：${hint}`)
}

function clearMeasure() {
  measureMode.value = null
  measurePoints.value = []
  measureResult.value = ''
  if (measureLayer) { map?.removeLayer(measureLayer); measureLayer = null }
  setMapCursor('')
  editStore.setStatus('')
}

/** 在地图上绘制测量临时图形（点标记+连线+面） */
function drawMeasureOverlay() {
  if (!measureLayer || !map) return
  measureLayer.clearLayers()
  const pts = measurePoints.value
  if (pts.length === 0) return
  // 绘制点标记
  pts.forEach((p, i) => {
    L.circleMarker(p, {
      radius: 5, color: '#7c3aed', fillColor: '#fff', fillOpacity: 1, weight: 2,
    }).addTo(measureLayer!)
    L.marker(p, {
      icon: L.divIcon({
        className: 'measure-num',
        html: `<div style="background:#7c3aed;color:#fff;border-radius:50%;width:18px;height:18px;line-height:18px;text-align:center;font-size:11px;font-weight:bold;">${i + 1}</div>`,
        iconSize: [18, 18], iconAnchor: [9, 9],
      }),
      interactive: false,
    }).addTo(measureLayer!)
  })
  // 绘制连线
  if (pts.length >= 2) {
    if (measureMode.value === 'area') {
      L.polygon(pts, { color: '#7c3aed', weight: 2, fillColor: '#7c3aed', fillOpacity: 0.15, dashArray: '5,5' }).addTo(measureLayer!)
    } else {
      L.polyline(pts, { color: '#7c3aed', weight: 3, dashArray: '5,5' }).addTo(measureLayer!)
    }
  }
}

function bearing(a: [number, number], b: [number, number]): number {
  const φ1 = (a[0] * Math.PI) / 180
  const φ2 = (b[0] * Math.PI) / 180
  const Δλ = ((b[1] - a[1]) * Math.PI) / 180
  const y = Math.sin(Δλ) * Math.cos(φ2)
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ)
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
}

function calcAngle(a: [number, number], b: [number, number], c: [number, number]): number {
  const br1 = bearing(b, a)
  const br2 = bearing(b, c)
  let ang = Math.abs(br1 - br2)
  if (ang > 180) ang = 360 - ang
  return ang
}

function updateMeasureResult() {
  if (measureMode.value === 'angle') {
    if (measurePoints.value.length === 3) {
      const [a, b, c] = measurePoints.value
      const ang = calcAngle(a, b, c)
      measureResult.value = `角度：${ang.toFixed(1)}°`
      editStore.setStatus(`测量角度：${ang.toFixed(1)}°`)
      setTimeout(() => clearMeasure(), 2000)
    } else {
      measureResult.value = `已选 ${measurePoints.value.length}/3 个点`
    }
    return
  }

  if (measurePoints.value.length < 2) {
    measureResult.value = measureMode.value === 'distance' ? '点击继续添加点' : '点击继续添加顶点'
    return
  }

  if (measureMode.value === 'distance') {
    let total = 0
    for (let i = 1; i < measurePoints.value.length; i++) {
      const p1 = measurePoints.value[i - 1]
      const p2 = measurePoints.value[i]
      total += map?.distance(p1, p2) || 0
    }
    measureResult.value = `距离：${total < 1000 ? total.toFixed(1) + ' m' : (total / 1000).toFixed(2) + ' km'}`
  } else if (measureMode.value === 'area') {
    // 简单的面积计算（球面多边形）
    const area = calculatePolygonArea(measurePoints.value)
    measureResult.value = `面积：${area < 1000000 ? area.toFixed(0) + ' m²' : (area / 1000000).toFixed(2) + ' km²'}`
  }
}

function calculatePolygonArea(points: [number, number][]): number {
  if (points.length < 3) return 0
  // 简化的平面面积计算（仅用于显示）
  let area = 0
  const R = 6378137
  for (let i = 0; i < points.length; i++) {
    const p1 = points[i]
    const p2 = points[(i + 1) % points.length]
    area += (p2[1] - p1[1]) * (R * Math.PI / 180) * (R * Math.cos(p1[0] * Math.PI / 180) * Math.PI / 180)
  }
  return Math.abs(area / 2)
}

function setMapCursor(cursor: string) {
  if (mapContainerRef.value) {
    mapContainerRef.value.style.cursor = cursor
  }
}

// ========== 标注吸附 ==========
/** 在指定像素范围内查找最近的矢量要素，返回其坐标和名称 */
function snapToNearestFeature(lat: number, lng: number, pixelTolerance: number): { lat: number; lng: number; name: string } | null {
  if (!map) return null
  const clickPoint = map.latLngToContainerPoint([lat, lng])
  let best: { lat: number; lng: number; name: string; dist: number } | null = null

  layerMap.forEach((leafletLayer, layerId) => {
    const data = layerDataById.get(layerId)
    if (!data || data.visible === false) return
    const t = data.type || ''
    if (!['polyline', 'line', 'polygon', 'area', 'circleMarker', 'marker', 'point'].includes(t)) return
    const children: any[] = []
    if (typeof (leafletLayer as any).eachLayer === 'function') {
      ;(leafletLayer as any).eachLayer((l: any) => children.push(l))
    } else if ((leafletLayer as any)._layers) {
      Object.values((leafletLayer as any)._layers).forEach((l: any) => children.push(l))
    } else {
      children.push(leafletLayer)
    }
    children.forEach((child, idx) => {
      let center: L.LatLng | null = null
      try {
        if (child.getLatLng) center = child.getLatLng()
        else if (child.getBounds) {
          const b = child.getBounds()
          center = b.getCenter()
        }
      } catch (e) { return }
      if (!center) return
      const pt = map!.latLngToContainerPoint(center)
      const dist = Math.hypot(pt.x - clickPoint.x, pt.y - clickPoint.y)
      if (dist <= pixelTolerance && (!best || dist < best.dist)) {
        const props = (Array.isArray(data.properties) && data.properties[idx]) ||
          (Array.isArray(data.features) && data.features[idx]?.properties) || {}
        best = { lat: center.lat, lng: center.lng, name: props.name || props.NAME || data.name || '', dist }
      }
    })
  })
  return best ? { lat: best.lat, lng: best.lng, name: best.name } : null
}

/** 在地图上添加一个文字标注标记 */
function addAnnotationMarker(lat: number, lng: number, name?: string | null) {
  if (!map) return
  const text = name || '标注'
  const marker = L.marker([lat, lng], {
    icon: L.divIcon({
      className: 'annotation-marker',
      html: `<div style="background:#fff;border:2px solid #7c3aed;border-radius:4px;padding:2px 8px;font-size:12px;color:#1f2937;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.2);">${text}</div>`,
      iconSize: null,
      iconAnchor: [0, 0],
    }),
    draggable: true,
  }).addTo(map)
  marker.bindTooltip('拖动可移动，双击删除', { permanent: false })
  marker.on('dblclick', () => { map?.removeLayer(marker) })
}

// ========== 视图历史（上一视图 / 下一视图） ==========
const viewHistory: { center: [number, number]; zoom: number }[] = []
let viewHistoryIndex = -1
let viewHistoryLock = false

function recordView() {
  if (!map || viewHistoryLock) return
  const c = map.getCenter()
  const v = { center: [c.lat, c.lng] as [number, number], zoom: map.getZoom() }
  const last = viewHistory[viewHistoryIndex]
  if (last && last.center[0] === v.center[0] && last.center[1] === v.center[1] && last.zoom === v.zoom) return
  viewHistory.splice(viewHistoryIndex + 1)
  viewHistory.push(v)
  viewHistoryIndex = viewHistory.length - 1
  if (viewHistory.length > 50) { viewHistory.shift(); viewHistoryIndex-- }
}

function prevView() {
  if (!map || viewHistoryIndex <= 0) { editStore.setStatus('没有上一视图'); return }
  viewHistoryIndex--
  const v = viewHistory[viewHistoryIndex]
  viewHistoryLock = true
  map.setView(v.center, v.zoom)
  setTimeout(() => { viewHistoryLock = false }, 300)
}

function nextView() {
  if (!map || viewHistoryIndex >= viewHistory.length - 1) { editStore.setStatus('没有下一视图'); return }
  viewHistoryIndex++
  const v = viewHistory[viewHistoryIndex]
  viewHistoryLock = true
  map.setView(v.center, v.zoom)
  setTimeout(() => { viewHistoryLock = false }, 300)
}

// ========== 图层管理 ==========
function refreshLayersFromStore() {
  if (!map) return

  // 移除所有图层
  layerMap.forEach((layer, id) => {
    map?.removeLayer(layer)
  })
  layerMap.clear()

  // 添加新图层
  mapStore.sortedLayers.forEach((item) => {
    if (item.visible && item.data) {
      addLayer(item.data)
    }
  })

  updateStatusBar()
}

function addLayer(layer: MapLayer) {
  if (!map) return
  layerDataById.set(layer.id, layer)

  try {
    const style = layer.style || {}
    const type = (layer.type || '').toLowerCase()
    
    // 线图层
    if (type === 'polyline' || type === 'line' || type === 'linestring' || 
        type === '线' || type === '线状' || type === '道路' || type === '河流' || type === '边界') {
      addPolylineLayer(layer, style)
      return
    }
    
    // 面图层
    if (type === 'polygon' || type === 'area' || type === 'polygon' || 
        type === '面' || type === '面状' || type === '水体' || type === '湖泊' || type === '建筑') {
      addPolygonLayer(layer, style)
      return
    }
    
    // 点图层
    if (type === 'circlemarker' || type === 'point' || type === 'marker' || type === 'point' || 
        type === '点' || type === '点状' || type === '地标' || type === 'poi') {
      addPointLayer(layer, style)
      return
    }
    
    // 文字标注图层
    if (type === 'textlabel' || type === 'label' || type === 'text' || 
        type === '标注' || type === '注记' || type === '文字' || type === '名称') {
      addTextLabelLayer(layer, style)
      return
    }
    
    // 热力图图层
    if (type === 'heatmap' || type === 'heat' || type === '热力图') {
      addHeatmapLayer(layer, style)
      return
    }

    // 栅格/影像图层（imageOverlay）
    if (type === 'imageoverlay' || type === 'raster' || type === 'image' || type === '栅格' || type === '影像') {
      addImageOverlayLayer(layer, style)
      return
    }
    
    // 尝试用GeoJSON方式渲染
    if (layer.data) {
      addGeoJsonLayer(layer, style)
      return
    }
    
    // 如果有coordinates，尝试根据坐标格式判断
    if (layer.coordinates) {
      const coords = layer.coordinates
      if (Array.isArray(coords) && coords.length > 0) {
        const first = coords[0]
        if (Array.isArray(first)) {
          // 二维数组，可能是线或面
          if (first.length >= 4) {
            // 可能是面（闭合的）
            addPolygonLayer(layer, style)
          } else {
            // 可能是线
            addPolylineLayer(layer, style)
          }
        } else if (typeof first === 'number') {
          // 扁平数组，可能是点或线
          if (coords.length === 2) {
            // 单个点
            addPointLayer(layer, style)
          } else {
            // 多个点，可能是线
            addPolylineLayer(layer, style)
          }
        }
      }
    }
  } catch (e) {
    console.error('添加图层失败', layer.id, layer.name, layer.type, e)
  }
}

// 坐标标准化：智能体生成的是 [lat, lng] 格式，Leaflet 也用 [lat, lng] 格式
// 主要处理扁平数组转二维数组的情况
function normalizeCoords(coordinates: any): [number, number][] | null {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return null
  
  const first = coordinates[0]
  if (first == null) return null
  
  // 扁平数组：[lat1, lng1, lat2, lng2, ...]
  if (typeof first === 'number') {
    if (coordinates.length >= 2 && typeof coordinates[1] === 'number' && !Array.isArray(coordinates[1])) {
      const result: [number, number][] = []
      for (let i = 0; i < coordinates.length; i += 2) {
        if (i + 1 < coordinates.length) {
          // 智能体生成的是 [lat, lng] 格式，Leaflet 也用 [lat, lng]，直接用
          result.push([coordinates[i], coordinates[i + 1]])
        }
      }
      return result.length > 0 ? result : null
    }
    // 单个点
    if (coordinates.length >= 2) {
      return [[coordinates[0], coordinates[1]]]
    }
    return null
  }
  
  // 二维数组：[[lat, lng], [lat, lng], ...]
  if (Array.isArray(first) && first.length >= 2) {
    return coordinates.map((c: number[]) => [c[0], c[1]] as [number, number])
  }
  
  return null
}

// ========== features 型图层支持（carto-agent-1 同款：区县政区/专题面等以 features 存储） ==========
function validLatLng(c: any): c is [number, number] {
  return (
    Array.isArray(c) &&
    c.length >= 2 &&
    typeof c[0] === 'number' &&
    typeof c[1] === 'number' &&
    isFinite(c[0]) &&
    isFinite(c[1]) &&
    c[0] >= -90 &&
    c[0] <= 90 &&
    c[1] >= -180 &&
    c[1] <= 180
  )
}

/** 过滤出有效的 [lat, lng] 坐标对 */
function filterValidCoords(coords: any): [number, number][] {
  if (!Array.isArray(coords)) return []
  return coords.filter((c: any) => validLatLng(c)) as [number, number][]
}

/** 将 feature 的 coordinates 转换为 Leaflet 多边形环数组（支持多环/带洞面） */
function polygonRingsFromFeature(coords: any): [number, number][][] {
  if (!Array.isArray(coords) || coords.length === 0) return []
  // 单个环：[[lat,lng], [lat,lng], ...]
  if (validLatLng(coords[0])) {
    const ring = filterValidCoords(coords)
    return ring.length >= 3 ? [ring] : []
  }
  // 多环：[[[lat,lng],...], [[lat,lng],...], ...]
  return coords
    .map((ring: any) => filterValidCoords(ring))
    .filter((ring: [number, number][]) => ring.length >= 3)
}

// 线图层
function addPolylineLayer(layer: MapLayer, style: any) {
  // features 型线图层（专题地图）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      const coords = filterValidCoords(
        Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates],
      )
      if (coords.length < 2) return
      L.polyline(coords, {
        color: featStyle.color || style.color || '#3388ff',
        weight: featStyle.weight || style.weight || 3,
        opacity: featStyle.opacity !== undefined ? featStyle.opacity : (style.opacity !== undefined ? style.opacity : 1),
        dashArray: featStyle.dashArray || style.dashArray || undefined,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const line = L.polyline(coords, {
    color: style.color || '#3388ff',
    weight: style.weight || 3,
    opacity: style.opacity !== undefined ? style.opacity : 1,
    dashArray: style.dashArray || undefined,
  }).addTo(map!)
  
  layerMap.set(layer.id, line)
}

// 面图层
function addPolygonLayer(layer: MapLayer, style: any) {
  // features 型面图层（行政区划图：区县政区等 24 个面；carto-agent-1 同款渲染）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    const isAdmin = mapStore.mapType === 'administrative'
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      const rings = polygonRingsFromFeature(feat.coordinates)
      if (rings.length === 0) return

      let fColor = featStyle.color || style.color || '#3388ff'
      let fFill = featStyle.fillColor || featStyle.color || style.fillColor || style.color || '#3388ff'
      let fWeight = featStyle.weight || style.weight || 1
      let fOpac = featStyle.opacity !== undefined ? featStyle.opacity : (style.opacity !== undefined ? style.opacity : 0.5)
      let fFillOpac = featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : (style.fillOpacity !== undefined ? style.fillOpacity : 0.4)

      // 行政区划图：保留各要素自己的填充色（WUHAN_DISTRICT_FILLS四色普染），仅降低透明度露出底图
      if (isAdmin) {
        fFillOpac = featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.45
        fWeight = featStyle.weight !== undefined ? featStyle.weight : 1.2
        // 若要素未指定填充色，才使用默认浅灰
        if (!featStyle.fillColor && !style.fillColor) fFill = '#f0f4f8'
      }

      const poly = L.polygon(rings, {
        color: fColor,
        fillColor: fFill,
        weight: fWeight,
        opacity: fOpac,
        fillOpacity: fFillOpac,
      })

      // 悬停交互：边界红色加粗高亮、区块微泛白（carto-agent-1 同款）
      if (isAdmin) {
        poly.on('mouseover', function (this: L.Polygon) {
          this.setStyle({ weight: 3, color: '#FF0000', fillOpacity: 0.12 })
          this.bringToFront()
        })
        poly.on('mouseout', function (this: L.Polygon) {
          this.setStyle({ weight: fWeight, color: fColor, fillOpacity: fFillOpac })
        })
      }
      group.addLayer(poly)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const polygon = L.polygon(coords, {
    color: style.borderColor || style.color || '#3388ff',
    fillColor: style.fillColor || style.color || '#3388ff',
    weight: style.weight || 2,
    opacity: style.opacity !== undefined ? style.opacity : 1,
    fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
  }).addTo(map!)
  
  layerMap.set(layer.id, polygon)
}

// 点图层
function addPointLayer(layer: MapLayer, style: any) {
  // features 型点图层（专题地图点/圆点）
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates) return
      const featStyle = feat.style || style
      if (!validLatLng(feat.coordinates)) return
      const coord = [feat.coordinates[0], feat.coordinates[1]] as [number, number]
      L.circleMarker(coord, {
        radius: featStyle.radius || style.radius || 6,
        color: featStyle.color || style.color || '#3388ff',
        fillColor: featStyle.fillColor || featStyle.color || style.fillColor || style.color || '#3388ff',
        fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : (style.fillOpacity !== undefined ? style.fillOpacity : 0.7),
        weight: featStyle.weight || style.weight || 2,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  // 多个点
  if (coords.length > 1) {
    const layerGroup = L.layerGroup()
    coords.forEach((coord) => {
      const marker = L.circleMarker(coord, {
        radius: style.radius || 4,
        fillColor: style.color || '#f59e0b',
        color: style.borderColor || '#fff',
        weight: style.weight || 2,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
      })
      layerGroup.addLayer(marker)
    })
    layerGroup.addTo(map!)
    layerMap.set(layer.id, layerGroup)
  } else {
    // 单个点
    const marker = L.circleMarker(coords[0], {
      radius: style.radius || 4,
      fillColor: style.color || '#f59e0b',
      color: style.borderColor || '#fff',
      weight: style.weight || 2,
      opacity: style.opacity !== undefined ? style.opacity : 1,
      fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
    }).addTo(map!)
    layerMap.set(layer.id, marker)
  }
}

// 文字标注图层
function addTextLabelLayer(layer: MapLayer, style: any) {
  // features 型注记图层
  if (layer.features && Array.isArray(layer.features) && layer.features.length > 0) {
    const group = L.layerGroup()
    layer.features.forEach((feat: any) => {
      if (!feat || !feat.coordinates || !validLatLng(feat.coordinates)) return
      const featStyle = feat.style || style
      const text = feat.properties?.name || feat.name || ''
      if (!text) return
      const coord = [feat.coordinates[0], feat.coordinates[1]] as [number, number]
      L.marker(coord, {
        icon: L.divIcon({
          className: 'text-label-icon',
          html: `<div style="
            color: ${featStyle.color || style.color || '#1a1a1a'};
            font-size: ${featStyle.fontSize || style.fontSize || 13}px;
            font-weight: ${featStyle.fontWeight || style.fontWeight || 'normal'};
            text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff;
            white-space: nowrap;
            text-align: center;
          ">${text}</div>`,
          iconSize: [100, 20],
          iconAnchor: [50, 10],
        }),
        interactive: false,
      }).addTo(group)
    })
    group.addTo(map!)
    layerMap.set(layer.id, group)
    return
  }

  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const layerGroup = L.layerGroup()
  
  coords.forEach((coord, idx) => {
    const text = layer.properties?.[idx]?.name || layer.name || ''
    if (!text) return
    
    const marker = L.marker(coord, {
      icon: L.divIcon({
        className: 'text-label-icon',
        html: `<div style="
          color: ${style.color || '#1a1a1a'};
          font-size: ${style.fontSize || 13}px;
          font-weight: ${style.fontWeight || 'normal'};
          text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff;
          white-space: nowrap;
          text-align: center;
        ">${text}</div>`,
        iconSize: [100, 20],
        iconAnchor: [50, 10],
      }),
      interactive: false,
    })
    layerGroup.addLayer(marker)
  })
  
  layerGroup.addTo(map!)
  layerMap.set(layer.id, layerGroup)
}

// 热力图图层（简化版，用circleMarker模拟）
function addHeatmapLayer(layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return
  
  const layerGroup = L.layerGroup()
  
  coords.forEach((coord) => {
    const marker = L.circleMarker(coord, {
      radius: style.radius || 25,
      fillColor: '#ff6b6b',
      color: 'transparent',
      weight: 0,
      fillOpacity: 0.15,
    })
    layerGroup.addLayer(marker)
  })
  
  layerGroup.addTo(map!)
  layerMap.set(layer.id, layerGroup)
}

// 栅格影像图层（imageOverlay）- 支持DEM/影像/栅格数据导入
function addImageOverlayLayer(layer: MapLayer, style: any) {
  if (!map || !(layer as any).imageUrl) return
  const bounds = map.getBounds()
  const overlay = L.imageOverlay((layer as any).imageUrl, bounds, {
    opacity: style.opacity !== undefined ? style.opacity : 0.7,
    interactive: false,
  }).addTo(map)
  layerMap.set(layer.id, overlay)
}

// GeoJSON图层
function addGeoJsonLayer(layer: MapLayer, style: any) {
  const geoJsonLayer = L.geoJSON(layer.data as any, {
    style: (feature) => {
      return {
        color: style.borderColor || style.color || '#3388ff',
        fillColor: style.fillColor || style.color || '#3388ff',
        weight: style.weight || 2,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
      }
    },
    pointToLayer: (feature, latlng) => {
      return L.circleMarker(latlng, {
        radius: style.radius || 4,
        fillColor: style.color || '#3388ff',
        color: style.borderColor || style.color || '#3388ff',
        weight: style.weight || 1,
        opacity: style.opacity !== undefined ? style.opacity : 1,
        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.8,
      })
    },
  }).addTo(map!)
  
  layerMap.set(layer.id, geoJsonLayer)
}

function getLayerStyle(layer: MapLayer, feature: any): L.PathOptions {
  return {
    color: layer.style?.borderColor || layer.style?.color || '#3388ff',
    fillColor: layer.style?.color || '#3388ff',
    weight: layer.style?.weight || 2,
    opacity: layer.style?.opacity || 1,
    fillOpacity: layer.style?.fillOpacity || 0.3,
  }
}

function handleZoomToLayer(e: Event) {
  const layerId = (e as CustomEvent).detail?.layerId
  if (!layerId || !map) return

  const layer = layerMap.get(layerId)
  if (layer) {
    const bounds = (layer as any).getBounds?.()
    if (bounds) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }
}

// ========== 渲染地图数据 ==========
function renderMap(mapData: MapData) {
  if (!map || !mapData) return

  // 设置中心和缩放
  if (mapData.center && mapData.center.length >= 2) {
    map.setView([mapData.center[0], mapData.center[1]], mapData.zoom || CONFIG.defaultZoom)
  }

  // 设置底图：行政区划图与 carto-agent-1 一致，强制制图底图（无瓦片）
  if (mapData.map_type === 'administrative') {
    setTheme('plain')
  } else if (mapData.theme && mapData.theme !== currentTheme.value) {
    setTheme(mapData.theme)
  }

  // 直接从mapData渲染图层
  if (mapData.layers && mapData.layers.length > 0) {
    // 先清除现有图层
    layerMap.forEach((layer, id) => {
      map?.removeLayer(layer)
    })
    layerMap.clear()

    // 按图层顺序排序（面在下，线在中，点和文字在上）
    const sortedLayers = [...mapData.layers].sort((a, b) => layerZ(a) - layerZ(b))
    
    // 添加新图层
    sortedLayers.forEach((layer) => {
      addLayer(layer)
    })
    // LOD 载负量控制（与 carto-agent-1 map-lod.js 一致）
    applyLod()
  }

  updateStatusBar()

  // 自动取景：行政区划图按"武汉全域+周边地市"取景（maxZoom 10.5，与 carto-agent-1 一致）
  if (mapData.map_type === 'administrative') {
    fitAdminBounds(mapData)
  } else if (mapData.layers && mapData.layers.length > 0) {
    const layers = mapData.layers
    setTimeout(() => fitToLayers(layers), 100)
  }
}

// ========== LOD 载负量控制（移植自 carto-agent-1 frontend/src/js/map-lod.js） ==========
const ROAD_LEVEL: Record<string, number> = {
  motorway: 0, motorway_link: 1,
  trunk: 1, trunk_link: 2,
  primary: 2, primary_link: 3,
  secondary: 3, secondary_link: 4,
  tertiary: 4, tertiary_link: 5,
  residential: 5, living_street: 5, service: 5, unclassified: 5, other: 5,
}

function roadLevel(layer: MapLayer): number {
  const nm = layer.name || ''
  // 优先使用后端标注的道路等级（metadata.raw_class）
  const raw = (layer.metadata as any)?.raw_class
  if (raw && ROAD_LEVEL[raw] !== undefined) return ROAD_LEVEL[raw]
  if (nm.indexOf('道路-') === 0) {
    const l = nm.replace('道路-', '').split('_')[0]
    if (ROAD_LEVEL[l] !== undefined) return ROAD_LEVEL[l]
    // 中文道路名映射
    if (/高速公路|高速互通/.test(nm)) return 0
    if (/城市干线主干道|主干道连接|主干道衔接/.test(nm)) return 1
    if (/城市主干道/.test(nm)) return 2
    if (/城市次干道|次干道连接/.test(nm)) return 3
    if (/三级道路/.test(nm)) return 4
    return 5
  }
  if (/高速公路/.test(nm)) return 0
  if (/国道|主干道/.test(nm)) return 1
  if (/省道|主要道路/.test(nm)) return 2
  if (/次干道/.test(nm)) return 3
  if (/三级道路/.test(nm)) return 4
  return 5
}

/** 按比例尺分级显隐（五档：概览/市域/城区/街区/详图），与 carto-agent-1 map-lod.js 完全一致 */
function lodVisible(layer: MapLayer, zoom: number): boolean {
  const _z = zoom
  const _nm = layer.name || ''
  const t = layer.type || ''
  // ---- 道路分级 ----
  if ((t === 'polyline' || t === 'line') &&
      (_nm.indexOf('道路-') === 0 || /高速|国道|主干道|省道|次干道|支路|社区道路|服务道路|其他道路|三级道路/.test(_nm))) {
    const level = roadLevel(layer)
    let maxShow = 5
    if (_z < 9) maxShow = 0
    else if (_z < 11) maxShow = 1
    else if (_z < 13) maxShow = 3
    else if (_z < 15) maxShow = 4
    return level <= maxShow
  }
  // ---- 水系 ----
  if (t === 'polyline' || t === 'line') {
    if (_nm === '河流中心线（主要）') return _z >= 9
    if (_nm === '河流中心线（支流）') return _z >= 12
    if (_nm === '等高线（计曲线）') return _z >= 9
    if (_nm === '等高线（首曲线）') return _z >= 11
    if (_nm === '支流溪流' || /河源细流/.test(_nm)) return _z >= 13
    if (_nm === '主要河流') return _z >= 11
    return true
  }
  // ---- 面要素 ----
  if (t === 'polygon' || t === 'area') {
    if (_nm === '河流水面') return _z >= 11
    if (_nm === '集中居民地（大型）') return _z >= 11
    if (_nm === '集中居民地（中型）') return _z >= 13
    if (_nm === '集中居民地（小型）') return _z >= 15
    if (_nm === '湖泊（概览级）' || _nm === '湖泊点符号（概览）') return _z >= 6 && _z < 9
    if (_nm === '湖泊（市域级）') return _z >= 9 && _z < 11
    if (_nm === '湖泊（城区级）') return _z >= 11 && _z < 13
    if (_nm === '湖泊（详图级）') return _z >= 13
    if (/住宅|公寓|宿舍|商业|零售|酒店|工业|公共|政府|学校|大学|医院|宗教|文化|体育|停车|车库|仓储|交通枢纽|农业|温室/.test(_nm)) return _z >= 13
    if (/绿地|公园|森林|草地|草甸|用地/.test(_nm)) return _z >= 11
    return true
  }
  // ---- 注记 ----
  if (t === 'textLabel' || t === 'label') {
    if (_nm === '水系注记') return _z >= 12
    if (_nm === '区县名称标注') return _z >= 9
    if (_nm === '地标名称' || _nm === '重点地标') return _z >= 11
    return true
  }
  // ---- POI/符号 ----
  if (t === 'circleMarker' || t === 'point' || t === 'marker') {
    if (_nm === '湖泊点符号（概览）') return _z >= 6 && _z < 9
    if (_nm === '市级行政中心' || _nm === '区县行政中心' || _nm === '乡镇居民点') return _z >= 8
    if (_nm === '重点地标') return _z >= 11
    return _z >= 12
  }
  return true
}

/** 缩放变化时按 LOD 规则显隐图层 */
function applyLod() {
  if (!map) return
  const zoom = map.getZoom()
  layerMap.forEach((layer, id) => {
    const data = layerDataById.get(id)
    if (!data) return
    const visible = data.visible !== false && lodVisible(data, zoom)
    const onMap = map!.hasLayer(layer)
    if (visible && !onMap) layer.addTo(map!)
    if (!visible && onMap) map!.removeLayer(layer)
  })
}

/** 行政区划图取景：武汉全域 + 周边相邻地市（与 carto-agent-1 规范九-5 一致） */
function fitAdminBounds(mapData: MapData) {
  if (!map) return
  const bounds = L.latLngBounds([])
  const collect = (c: any) => {
    if (!Array.isArray(c)) return
    if (c.length >= 2 && typeof c[0] === 'number' && !isNaN(c[0]) && !isNaN(c[1])) {
      bounds.extend([c[0], c[1]])
    } else {
      c.forEach(collect)
    }
  }
  ;(mapData.layers || []).forEach((ld) => {
    const t = ld.type || ''
    if (['polygon', 'polyline', 'circleMarker', 'textLabel', 'line'].includes(t)) {
      if (ld.coordinates) collect(ld.coordinates)
      if (ld.features && Array.isArray(ld.features)) {
        ld.features.forEach((f: any) => { if (f.coordinates) collect(f.coordinates) })
      }
    }
  })
  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [12, 12], maxZoom: 10.5 })
  }
}

// 图层Z轴顺序（和carto-agent-1保持一致）
function layerZ(layer: MapLayer): number {
  const t = layer.type || ''
  const n = layer.name || ''
  if (t === 'polygon' || t === 'area') {
    if (/水体|湖泊|水库/.test(n)) return 150
    if (/建筑|住宅|商业/.test(n)) return 200
    return 100
  }
  if (t === 'polyline' || t === 'line') {
    if (/水系|河流/.test(n)) return 330
    if (/边界|市域|省界|县界/.test(n)) return 460
    if (/铁路|地铁|轻轨|高铁/.test(n)) return 500
    return 400
  }
  if (t === 'textLabel' || t === 'label') return 650
  return 600
}

function fitToLayers(layers: MapLayer[]) {
  if (!map || layers.length === 0) return

  let bounds: L.LatLngBounds | null = null

  layers.forEach((layer) => {
    const layerObj = layerMap.get(layer.id)
    if (layerObj) {
      const layerBounds = (layerObj as any).getBounds?.()
      if (layerBounds) {
        if (bounds) {
          bounds.extend(layerBounds)
        } else {
          bounds = layerBounds
        }
      }
    }
  })

  if (bounds) {
    map.fitBounds(bounds, { padding: [50, 50] })
  }
}

// ========== 编辑模式 ==========
// 编辑引擎状态（与经典 map-edit.js 同构，适配 Vue/Leaflet 架构）
let editing = false
let editDirty: Record<string, boolean> = {}
let currentEdit: { layerId: string; idx: number; layer: any } | null = null
let tempEditLayer: any = null
let editClipboard: { layerId: string; feature: any } | null = null
let bulkSelected: any[] = []

function getLayerData(layerId: string): MapLayer | null {
  return mapStore.layerGroups[layerId]?.data || null
}

function markDirty(layerId: string) {
  if (!layerId) return
  editDirty[layerId] = true
  editStore.markDirty(layerId)
}

function pushUndo(layerId: string) {
  const data = getLayerData(layerId)
  if (data) editStore.pushUndo(layerId, data)
}

/** 确保全局 L 已挂载 Leaflet.Editable（CDN leaflet 慢时 Editable 可能在 L 就绪前执行） */
function ensureLeafletEditable() {
  const gL = (window as any).L
  if (!gL) return
  if (gL.Editable) return
  try {
    const xhr = new XMLHttpRequest()
    xhr.open('GET', '/legacy/leaflet-editable.js', false)
    xhr.send()
    if (xhr.status === 200) (0, eval)(xhr.responseText)
  } catch (e) { console.warn('[MapCanvas] 补挂 leaflet-editable 失败', e) }
}

/** 初始化 leaflet-editable（几何编辑能力） */
function initEditable() {
  if (!map) return
  ensureLeafletEditable()
  const Editable = (L as any).Editable
  if (!Editable) return
  if (!(map as any).editTools) {
    ;(map as any).editTools = new Editable(map)
    map.on('editable:vertex:dragend editable:vertex:deleted editable:vertex:new', (e: any) => {
      // 拖拽/增删节点后，把 Leaflet 图层当前几何回写到数据源，保证主界面与编辑界面一致
      syncFeatureGeom(e?.layer)
    })
    map.on('editable:editing:start editable:vertex:dragstart', (e: any) => {
      const lid = e?.layer?._cartoLayerId
      if (lid) pushUndo(lid)
    })
  }
}

/** 给已渲染要素挂载编辑元数据与点击选中事件（幂等） */
function attachEditMetadata(layerId: string, leafletLayer: any) {
  if (!leafletLayer) return
  const setType = (l: any) => {
    if (l instanceof (L as any).Polygon) l._cartoGeomType = 'polygon'
    else if (l instanceof (L as any).Polyline) l._cartoGeomType = 'polyline'
    else l._cartoGeomType = 'point'
  }
  const attach = (l: any, idx: number) => {
    if (!l || typeof l.on !== 'function' || l._cartoLayerId) return
    l._cartoLayerId = layerId
    l._cartoFeatureIdx = idx
    setType(l)
    l.on('click', (e: any) => {
      if (editing) {
        L.DomEvent.stopPropagation(e)
        selectFeature(layerId, idx, l)
      }
    })
  }
  const children: any[] = []
  if (typeof leafletLayer.eachLayer === 'function') leafletLayer.eachLayer((l: any) => children.push(l))
  else if (leafletLayer._layers) Object.values(leafletLayer._layers).forEach((l: any) => children.push(l))
  else children.push(leafletLayer)
  children.forEach((l, idx) => attach(l, idx))
}

function attachAllEditMetadata() {
  layerMap.forEach((layer, id) => attachEditMetadata(id, layer))
}

function enterEditMode() {
  editing = true
  editDirty = {}
  editStore.setActive(true)
  initEditable()
  attachAllEditMetadata()
  editStore.setStatus('编辑模式已开启，点击要素进入编辑')
}

function exitEditMode() {
  clearSelection()
  editing = false
  editDirty = {}
  editStore.setActive(false)
  editStore.setStatus('未选择要素')
}

function clearVertexMarkers() {
  vertexMarkers.forEach((m) => m.remove())
  vertexMarkers = []
}

function selectFeature(layerId: string, idx: number, leafletLayer: any) {
  clearSelection()
  currentEdit = { layerId, idx, layer: leafletLayer }
  editStore.setSelected(layerId, idx)
  const data = getLayerData(layerId)
  const props = (Array.isArray(data?.properties) && data!.properties[idx]) || (Array.isArray(data?.features) && data!.features[idx]?.properties) || {}
  editStore.setSelectedFeatureInfo({ layerName: data?.name || '未知图层', properties: props, index: idx })
  pushUndo(layerId)
  if (leafletLayer.setStyle) {
    try { leafletLayer.setStyle({ color: '#ca8a04', weight: 4, opacity: 1, fillColor: '#fef08a', fillOpacity: 0.5 }) } catch (e) { /* ignore */ }
  }
  try {
    if (leafletLayer instanceof (L as any).Polyline || leafletLayer instanceof (L as any).Polygon) {
      if (leafletLayer.editEnabled && !leafletLayer.editEnabled()) leafletLayer.enableEdit()
    } else if (leafletLayer instanceof (L as any).Marker) {
      leafletLayer.dragging?.enable()
    } else if (leafletLayer instanceof (L as any).CircleMarker) {
      const latlng = leafletLayer.getLatLng()
      if (tempEditLayer) map!.removeLayer(tempEditLayer)
      tempEditLayer = (L as any).marker(latlng, { draggable: true }).addTo(map!)
      tempEditLayer.on('dragend', () => {
        const ll = tempEditLayer.getLatLng()
        leafletLayer.setLatLng(ll)
        // 回写数据源，保证主界面与编辑界面一致（不再整体重渲染，避免点被旧坐标“弹回”）
        syncFeatureGeom(leafletLayer)
        markDirty(layerId)
      })
    }
  } catch (e) { console.warn('[MapCanvas] 启用编辑失败', e) }
}

function clearSelection() {
  if (currentEdit) {
    const l: any = currentEdit.layer
    const st = getLayerData(currentEdit.layerId)?.style || {}
    if (l?.setStyle) {
      try { l.setStyle({ color: st.color || '#3388ff', weight: st.weight || 3, opacity: st.opacity !== undefined ? st.opacity : 1 }) } catch (e) { /* ignore */ }
    }
    if (l?.editEnabled?.() && l?.disableEdit) { try { l.disableEdit() } catch (e) { /* ignore */ } }
  }
  if (tempEditLayer) { map?.removeLayer(tempEditLayer); tempEditLayer = null }
  resetBulkHighlight()
  currentEdit = null
  editStore.setSelected(null, null)
}

/** 复位全选产生的高亮样式 */
function resetBulkHighlight() {
  bulkSelected.forEach((l) => {
    if (!l?.setStyle) return
    const st = getLayerData(l._cartoLayerId)?.style || {}
    try {
      l.setStyle({ color: st.color || '#3388ff', weight: st.weight || 3, opacity: st.opacity !== undefined ? st.opacity : 1 })
    } catch (e) { /* ignore */ }
  })
  bulkSelected = []
}

/** 收集图层内的全部子要素（兼容 layerGroup 与单要素） */
function collectLayerChildren(layer: any): any[] {
  const children: any[] = []
  if (!layer) return children
  if (typeof layer.eachLayer === 'function') layer.eachLayer((l: any) => children.push(l))
  else if (layer._layers) Object.values(layer._layers).forEach((l: any) => children.push(l))
  else children.push(layer)
  return children
}

/** 全选当前（或首个）矢量图层的全部要素 */
function selectAllFeatures() {
  let targetId: string | null = null
  for (const [id, item] of Object.entries(mapStore.layerGroups)) {
    const t = item.data?.type
    if (['polyline', 'line', 'polygon', 'area', 'circleMarker', 'marker', 'point'].includes(t)) {
      targetId = id
      break
    }
  }
  if (!targetId) { editStore.setStatus('没有可选择的矢量图层'); return }
  const children = collectLayerChildren(layerMap.get(targetId))
  if (children.length === 0) { editStore.setStatus('图层无要素'); return }

  // 清除旧选择（含旧批量高亮）
  clearSelection()

  // 高亮全部要素
  children.forEach((l) => {
    if (l?.setStyle) {
      try { l.setStyle({ color: '#ca8a04', weight: 4, opacity: 1, fillColor: '#fef08a', fillOpacity: 0.5 }) } catch (e) { /* ignore */ }
    }
  })
  bulkSelected = children

  // 将首个要素设为当前选中（供删除/复制/属性查看等单要素操作使用）
  currentEdit = { layerId: targetId, idx: 0, layer: children[0] }
  editStore.setSelected(targetId, 0)
  const data = getLayerData(targetId)
  const props = (Array.isArray(data?.properties) && data!.properties[0]) || (Array.isArray(data?.features) && data!.features[0]?.properties) || {}
  editStore.setSelectedFeatureInfo({ layerName: data?.name || '未知图层', properties: props, index: 0 })
  pushUndo(targetId)
  editStore.setStatus(`已全选 ${children.length} 个要素`)
}

function leafletGeomToData(type: string, layer: any): any {
  try {
    if (type === 'point') { const ll = layer.getLatLng(); return ll ? [ll.lat, ll.lng] : null }
    if (type === 'line') {
      const ls = layer.getLatLngs()
      const arr = Array.isArray(ls) && Array.isArray(ls[0]) ? ls[0] : ls
      return (arr || []).map((p: any) => [p.lat, p.lng])
    }
    if (type === 'polygon') {
      const rings = layer.getLatLngs()
      const ring = Array.isArray(rings) && Array.isArray(rings[0]) ? rings[0] : rings
      return (ring || []).map((p: any) => [p.lat, p.lng])
    }
  } catch (e) { console.warn('[MapCanvas] 几何解析失败', e) }
  return null
}

/** 将 Leaflet 图层的当前几何坐标回写到数据源（mapStore），实现主界面与编辑界面实时同步 */
function syncFeatureGeom(leafletLayer: any) {
  if (!leafletLayer) return
  const lid = leafletLayer._cartoLayerId
  const idx = leafletLayer._cartoFeatureIdx
  if (lid == null || idx == null) return
  const data = getLayerData(lid)
  if (!data) return
  const geomType = leafletLayer._cartoGeomType === 'polygon'
    ? 'polygon'
    : leafletLayer._cartoGeomType === 'polyline'
      ? 'line'
      : 'point'
  const geom = leafletGeomToData(geomType, leafletLayer)
  if (!geom) return
  if (Array.isArray(data.coordinates)) {
    data.coordinates[idx] = geom
  } else if (Array.isArray(data.features) && data.features[idx]) {
    data.features[idx].coordinates = geom
  }
  markDirty(lid)
}

function startDraw(type: 'point' | 'line' | 'polygon') {
  if (!map) return
  if (!mapStore.currentMapId) { editStore.setStatus('请先生成地图'); return }
  enterEditMode()
  initEditable()
  const editTools = (map as any).editTools
  if (!editTools) { editStore.setStatus('绘图组件未加载'); return }
  let handler: any = null
  try {
    if (type === 'point') handler = editTools.startMarker()
    else if (type === 'line') handler = editTools.startPolyline()
    else if (type === 'polygon') handler = editTools.startPolygon()
  } catch (e) { editStore.setStatus('开始绘制失败'); return }
  editStore.setStatus(type === 'point' ? '点击地图放置点' : '在地图上绘制，双击结束')
  if (handler) handler.on('editable:created', (e: any) => onDrawn(type, e.layer))
}

function onDrawn(type: string, layer: any) {
  if (!map) return
  let targetId: string | null = currentEdit?.layerId || null
  if (!targetId) {
    for (const [id, item] of Object.entries(mapStore.layerGroups)) {
      const t = item.data?.type
      if (t === 'polyline' || t === 'line' || t === 'polygon' || t === 'area' || t === 'circleMarker' || t === 'marker' || t === 'point') {
        targetId = id
        break
      }
    }
  }
  if (!targetId) { map.removeLayer(layer); editStore.setStatus('没有可追加的图层'); return }
  const data = getLayerData(targetId)
  if (!data) { map.removeLayer(layer); return }
  const geom = leafletGeomToData(type, layer)
  if (!geom) { map.removeLayer(layer); editStore.setStatus('绘制数据解析失败'); return }
  pushUndo(targetId)
  if (!Array.isArray(data.coordinates)) data.coordinates = []
  if (!Array.isArray(data.properties)) data.properties = []
  data.coordinates.push(geom)
  data.properties.push({ name: type === 'point' ? '新建点要素' : type === 'line' ? '新建线要素' : '新建面要素' })
  markDirty(targetId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已添加要素（记得保存）')
}

function deleteSelectedFeature() {
  if (!currentEdit) { editStore.setStatus('请先点击选中要删除的要素'); return }
  const { layerId, idx } = currentEdit
  const data = getLayerData(layerId)
  if (!data) { clearSelection(); return }
  pushUndo(layerId)
  if (Array.isArray(data.coordinates)) data.coordinates.splice(idx, 1)
  if (Array.isArray(data.properties)) data.properties.splice(idx, 1)
  if (Array.isArray(data.features)) data.features.splice(idx, 1)
  markDirty(layerId)
  clearSelection()
  refreshLayersFromStore()
  editStore.setStatus('已删除要素（记得保存）')
}

function addPointByCoord(lat: number, lng: number) {
  let targetId: string | null = null
  for (const [id, item] of Object.entries(mapStore.layerGroups)) {
    const t = item.data?.type
    if (t === 'circleMarker' || t === 'marker' || t === 'point') { targetId = id; break }
  }
  if (!targetId) { editStore.setStatus('没有点状图层可添加'); return }
  const data = getLayerData(targetId)
  if (!data) return
  pushUndo(targetId)
  if (!Array.isArray(data.coordinates)) data.coordinates = []
  data.coordinates.push([lat, lng])
  if (!Array.isArray(data.properties)) data.properties = []
  data.properties.push({ name: '坐标标注' })
  markDirty(targetId)
  refreshLayersFromStore()
  editStore.setStatus('已按坐标添加点（记得保存）')
}

function getSelectedProps(): Record<string, any> | null {
  if (!currentEdit) return null
  const data = getLayerData(currentEdit.layerId)
  if (!data) return null
  const idx = currentEdit.idx
  if (Array.isArray(data.features) && data.features[idx]) {
    if (!data.features[idx].properties) data.features[idx].properties = {}
    return data.features[idx].properties
  }
  if (!Array.isArray(data.properties)) data.properties = []
  if (!data.properties[idx]) data.properties[idx] = {}
  return data.properties[idx]
}

function copySelectedFeature() {
  if (!currentEdit) { editStore.setStatus('请先点击选中要复制的要素'); return }
  const { layerId, idx } = currentEdit
  const data = getLayerData(layerId)
  if (!data) return
  pushUndo(layerId)
  const offset = (arr: any) => {
    if (Array.isArray(arr[0])) arr.forEach((p: any) => { p[0] += 0.002; p[1] += 0.002 })
    else { arr[0] += 0.002; arr[1] += 0.002 }
  }
  if (Array.isArray(data.coordinates) && data.coordinates[idx]) {
    const copy = JSON.parse(JSON.stringify(data.coordinates[idx]))
    offset(copy)
    data.coordinates.push(copy)
    if (Array.isArray(data.properties)) data.properties.push(JSON.parse(JSON.stringify(data.properties[idx] || {})))
    editClipboard = { layerId, feature: { coordinates: JSON.parse(JSON.stringify(copy)) } }
  } else if (Array.isArray(data.features) && data.features[idx]) {
    const copy = JSON.parse(JSON.stringify(data.features[idx]))
    if (copy.coordinates) offset(copy.coordinates)
    data.features.push(copy)
    editClipboard = { layerId, feature: JSON.parse(JSON.stringify(copy)) }
  } else { editStore.setStatus('该图层不支持复制'); return }
  markDirty(layerId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已复制要素（记得保存）')
}

function pasteSelectedFeature() {
  if (!editClipboard) { editStore.setStatus('剪贴板为空，请先复制要素'); return }
  const { layerId, feature } = editClipboard
  const data = getLayerData(layerId)
  if (!data) { editStore.setStatus('目标图层不存在'); return }
  pushUndo(layerId)
  if (feature.coordinates) {
    if (!Array.isArray(data.coordinates)) data.coordinates = []
    data.coordinates.push(JSON.parse(JSON.stringify(feature.coordinates)))
    if (!Array.isArray(data.properties)) data.properties = []
    data.properties.push({ name: '粘贴要素' })
  } else if (feature.type) {
    if (!Array.isArray(data.features)) data.features = []
    data.features.push(JSON.parse(JSON.stringify(feature)))
  } else {
    editStore.setStatus('剪贴板数据无效')
    return
  }
  markDirty(layerId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已粘贴要素（记得保存）')
}

function pointLineDist(p: number[], a: number[], b: number[]): number {
  const x = p[0], y = p[1], x1 = a[0], y1 = a[1], x2 = b[0], y2 = b[1]
  const dx = x2 - x1, dy = y2 - y1
  if (dx === 0 && dy === 0) return Math.hypot(x - x1, y - y1)
  return Math.abs(dy * x - dx * y + x2 * y1 - y2 * x1) / Math.hypot(dx, dy)
}

function douglasPeucker(points: number[][], eps: number): number[][] {
  if (points.length <= 2) return points.map((p) => p.slice())
  let maxD = 0
  let idx = 0
  const first = points[0]
  const last = points[points.length - 1]
  for (let i = 1; i < points.length - 1; i++) {
    const d = pointLineDist(points[i], first, last)
    if (d > maxD) { maxD = d; idx = i }
  }
  if (maxD > eps) {
    const left = douglasPeucker(points.slice(0, idx + 1), eps)
    const right = douglasPeucker(points.slice(idx), eps)
    return left.slice(0, -1).concat(right)
  }
  return [first.slice(), last.slice()]
}

function simplifySelectedFeature() {
  if (!currentEdit) { editStore.setStatus('请先点击选中要简化的要素'); return }
  const { layerId, idx } = currentEdit
  const data = getLayerData(layerId)
  if (!data) return
  let coords: any = null
  if (Array.isArray(data.coordinates) && data.coordinates[idx]) coords = data.coordinates[idx]
  else if (Array.isArray(data.features) && data.features[idx]) coords = data.features[idx].coordinates
  if (!Array.isArray(coords) || coords.length < 5) { editStore.setStatus('节点太少，无需简化'); return }
  pushUndo(layerId)
  const simp = douglasPeucker(coords, 0.0004)
  if (Array.isArray(data.coordinates)) data.coordinates[idx] = simp
  else if (Array.isArray(data.features)) data.features[idx].coordinates = simp
  markDirty(layerId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus(`已简化：${coords.length} → ${simp.length} 个节点`)
}

function chaikin(points: number[][], iterations = 2): number[][] {
  let pts = points
  const closed = pts.length > 0 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1]
  for (let it = 0; it < iterations; it++) {
    if (pts.length < 3) break
    const next: number[][] = []
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i]
      const p1 = pts[i + 1]
      next.push([0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]])
      next.push([0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]])
    }
    if (closed) next.push(next[0])
    pts = next
  }
  return pts
}

function smoothSelectedFeature() {
  if (!currentEdit) { editStore.setStatus('请先点击选中要平滑的要素'); return }
  const { layerId, idx } = currentEdit
  const data = getLayerData(layerId)
  if (!data) return
  let coords: any = null
  if (Array.isArray(data.coordinates) && data.coordinates[idx]) coords = data.coordinates[idx]
  else if (Array.isArray(data.features) && data.features[idx]) coords = data.features[idx].coordinates
  if (!Array.isArray(coords) || coords.length < 3) { editStore.setStatus('节点太少，无法平滑'); return }
  pushUndo(layerId)
  const smoothed = chaikin(coords, 2)
  if (Array.isArray(data.coordinates)) data.coordinates[idx] = smoothed
  else if (Array.isArray(data.features)) data.features[idx].coordinates = smoothed
  markDirty(layerId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已平滑要素（记得保存）')
}

// ========== 几何变换工具（旋转 / 缩放 / 镜像 / 偏移 / 合并节点 / 分割 / 合并） ==========
function getSelectedCoords(): number[][] | null {
  if (!currentEdit) return null
  const data = getLayerData(currentEdit.layerId)
  if (!data) return null
  const idx = currentEdit.idx
  if (Array.isArray(data.coordinates) && Array.isArray(data.coordinates[idx])) return data.coordinates[idx]
  if (Array.isArray(data.features) && data.features[idx] && Array.isArray(data.features[idx].coordinates)) return data.features[idx].coordinates
  return null
}

function setSelectedCoords(newCoords: number[][]) {
  if (!currentEdit) return
  const data = getLayerData(currentEdit.layerId)
  if (!data) return
  const idx = currentEdit.idx
  if (Array.isArray(data.coordinates) && data.coordinates[idx]) data.coordinates[idx] = newCoords
  else if (Array.isArray(data.features) && data.features[idx]) data.features[idx].coordinates = newCoords
}

function coordsCentroid(coords: number[][]): [number, number] {
  let lat = 0
  let lng = 0
  let n = 0
  coords.forEach((p) => {
    if (Array.isArray(p) && p.length >= 2 && isFinite(p[0]) && isFinite(p[1])) { lat += p[0]; lng += p[1]; n++ }
  })
  return n ? [lat / n, lng / n] : [0, 0]
}

function applySelectedTransform(fn: (coords: number[][]) => number[][], label: string) {
  const coords = getSelectedCoords()
  if (!coords || coords.length < 1) { editStore.setStatus('请先点击选中要素'); return }
  const layerId = currentEdit!.layerId
  pushUndo(layerId)
  const result = fn(coords)
  setSelectedCoords(result)
  markDirty(layerId)
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus(label)
}

function rotateSelected(angleDeg: number) {
  applySelectedTransform((coords) => {
    const c = coordsCentroid(coords)
    const rad = (angleDeg * Math.PI) / 180
    const cos = Math.cos(rad)
    const sin = Math.sin(rad)
    return coords.map((p) => {
      const dLat = p[0] - c[0]
      const dLng = p[1] - c[1]
      return [c[0] + dLat * cos - dLng * sin, c[1] + dLat * sin + dLng * cos]
    })
  }, `已旋转 ${angleDeg}°`)
}

function scaleSelected(factor: number) {
  applySelectedTransform((coords) => {
    const c = coordsCentroid(coords)
    return coords.map((p) => [c[0] + (p[0] - c[0]) * factor, c[1] + (p[1] - c[1]) * factor])
  }, `已缩放 ${factor}×`)
}

function mirrorSelected(axis: 'horizontal' | 'vertical') {
  applySelectedTransform((coords) => {
    const c = coordsCentroid(coords)
    return coords.map((p) => axis === 'horizontal'
      ? [c[0] + (p[0] - c[0]), c[1] - (p[1] - c[1])]
      : [c[0] - (p[0] - c[0]), c[1] + (p[1] - c[1])])
  }, axis === 'horizontal' ? '已水平镜像' : '已垂直镜像')
}

function offsetSelected(distanceMeters: number) {
  applySelectedTransform((coords) => {
    const result: number[][] = []
    for (let i = 0; i < coords.length; i++) {
      const prev = coords[Math.max(0, i - 1)]
      const next = coords[Math.min(coords.length - 1, i + 1)]
      const dx = next[0] - prev[0]
      const dy = next[1] - prev[1]
      const len = Math.hypot(dx, dy) || 1
      const nx = -dy / len
      const ny = dx / len
      const dLat = distanceMeters / 111320
      const dLng = distanceMeters / (111320 * Math.max(0.01, Math.cos((coords[i][0] * Math.PI) / 180)))
      result.push([coords[i][0] + nx * dLat, coords[i][1] + ny * dLng])
    }
    return result
  }, `已偏移 ${distanceMeters}m`)
}

function mergeVerticesSelected() {
  applySelectedTransform((coords) => {
    const result = [coords[0]]
    for (let i = 1; i < coords.length; i++) {
      const last = result[result.length - 1]
      if (Math.hypot(coords[i][0] - last[0], coords[i][1] - last[1]) > 0.0001) result.push(coords[i])
    }
    return result
  }, '已合并邻近节点')
}

function splitSelectedFeature() {
  if (!currentEdit) { editStore.setStatus('请先点击选中线要素'); return }
  const data = getLayerData(currentEdit.layerId)
  if (!data) return
  const idx = currentEdit.idx
  const coords = getSelectedCoords()
  if (!coords || coords.length < 4) { editStore.setStatus('线要素节点太少，无法分割'); return }
  const mid = Math.floor(coords.length / 2)
  const seg1 = coords.slice(0, mid + 1)
  const seg2 = coords.slice(mid)
  pushUndo(currentEdit.layerId)
  if (Array.isArray(data.coordinates)) {
    data.coordinates[idx] = seg1
    data.coordinates.splice(idx + 1, 0, seg2)
    if (Array.isArray(data.properties)) data.properties.splice(idx + 1, 0, { name: '分割要素 2' })
  } else if (Array.isArray(data.features)) {
    data.features[idx].coordinates = seg1
    const copy = JSON.parse(JSON.stringify(data.features[idx]))
    copy.coordinates = seg2
    copy.properties = { name: '分割要素 2' }
    data.features.splice(idx + 1, 0, copy)
  }
  markDirty(currentEdit.layerId)
  clearSelection()
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已分割要素')
}

function mergeSelectedFeatures() {
  if (!currentEdit) { editStore.setStatus('请先点击选中要合并的线要素'); return }
  const data = getLayerData(currentEdit.layerId)
  if (!data) return
  const coords = getSelectedCoords()
  if (!coords || coords.length < 2) { editStore.setStatus('请选择线要素进行合并'); return }
  const allCoords: number[][][] = Array.isArray(data.coordinates)
    ? data.coordinates
    : (Array.isArray(data.features) ? data.features.map((f: any) => f.coordinates) : [])
  let bestIdx = -1
  let bestDist = Infinity
  allCoords.forEach((c, i) => {
    if (i === currentEdit!.idx || !Array.isArray(c) || c.length < 2) return
    const d1 = Math.hypot(coords[coords.length - 1][0] - c[0][0], coords[coords.length - 1][1] - c[0][1])
    const d2 = Math.hypot(coords[coords.length - 1][0] - c[c.length - 1][0], coords[coords.length - 1][1] - c[c.length - 1][1])
    const d = Math.min(d1, d2)
    if (d < bestDist) { bestDist = d; bestIdx = i }
  })
  if (bestIdx < 0) { editStore.setStatus('没有可合并的相邻线要素'); return }
  pushUndo(currentEdit.layerId)
  const target = allCoords[bestIdx]
  const merged = [...coords, ...target]
  if (Array.isArray(data.coordinates)) {
    data.coordinates[currentEdit!.idx] = merged
    data.coordinates.splice(bestIdx, 1)
    if (Array.isArray(data.properties)) data.properties.splice(bestIdx, 1)
  } else if (Array.isArray(data.features)) {
    data.features[currentEdit!.idx].coordinates = merged
    data.features.splice(bestIdx, 1)
  }
  markDirty(currentEdit.layerId)
  clearSelection()
  refreshLayersFromStore()
  attachAllEditMetadata()
  editStore.setStatus('已合并要素')
}

// ========== 密度分析（点图层 → 热力密度图层） ==========
function generateDensityLayer() {
  let targetLayer: MapLayer | null = null
  for (const item of Object.values(mapStore.layerGroups)) {
    const t = item.data?.type
    if (t === 'circleMarker' || t === 'marker' || t === 'point') { targetLayer = item.data; break }
  }
  if (!targetLayer) { editStore.setStatus('没有点状图层，无法做密度分析'); return }
  const points = (targetLayer.coordinates || []).map((c: any) => {
    if (Array.isArray(c) && c.length >= 2 && isFinite(c[0]) && isFinite(c[1])) return [c[0], c[1], 1]
    return null
  }).filter(Boolean)
  if (points.length === 0) { editStore.setStatus('点图层无有效坐标'); return }
  const heatLayer: MapLayer = {
    id: 'density_' + Date.now(),
    type: 'heatmap',
    name: `密度分析（${targetLayer.name || '点图层'}）`,
    coordinates: points,
    style: { radius: 25, blur: 15 },
    group: '分析结果',
  }
  const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l) => l.order))
  mapStore.layerGroups[heatLayer.id] = { visible: true, data: heatLayer, order: maxOrder + 1 }
  refreshLayersFromStore()
  editStore.setStatus(`已生成密度热力图（${points.length} 个点）`)
}

function applySnapshot(layerId: string, snapshot: MapLayer) {
  const item = mapStore.layerGroups[layerId]
  if (!item) return
  item.data = JSON.parse(JSON.stringify(snapshot))
  currentEdit = null
  refreshLayersFromStore()
  attachAllEditMetadata()
}

function undoEdit() {
  const layerId = currentEdit?.layerId || Object.keys(editStore.undoStack)[0]
  if (!layerId) { editStore.setStatus('没有可撤销的操作'); return }
  const snap = editStore.popUndo(layerId)
  if (!snap) { editStore.setStatus('没有可撤销的操作'); return }
  const data = getLayerData(layerId)
  if (data) editStore.pushRedo(layerId, data)
  applySnapshot(layerId, snap)
  editStore.setStatus('已撤销')
}

function redoEdit() {
  const layerId = currentEdit?.layerId || Object.keys(editStore.redoStack)[0]
  if (!layerId) { editStore.setStatus('没有可重做的操作'); return }
  const snap = editStore.popRedo(layerId)
  if (!snap) { editStore.setStatus('没有可重做的操作'); return }
  const data = getLayerData(layerId)
  if (data) editStore.pushUndo(layerId, data)
  applySnapshot(layerId, snap)
  editStore.setStatus('已重做')
}

async function saveEdits() {
  const mapId = mapStore.currentMapId
  if (!mapId) { editStore.setStatus('没有可保存的地图'); return }
  const dirtyIds = Object.keys(editDirty)
  if (dirtyIds.length === 0) { editStore.setStatus('没有需要保存的修改'); return }
  let ok = 0
  for (const layerId of dirtyIds) {
    const data = getLayerData(layerId)
    if (!data || data.type === 'textLabel') continue
    const payload = { properties: data.properties, style: data.style, coordinates: data.coordinates, features: data.features }
    try {
      const resp: any = await api.updateLayerGeometry(mapId, layerId, payload)
      if (resp?.success) { ok += 1; delete editDirty[layerId] }
    } catch (e) { console.warn('[MapCanvas] 保存图层失败', layerId, e) }
  }
  if (ok > 0) {
    editStore.clearDirty()
    try {
      const resp: any = await api.getMap(mapId)
      const data = resp?.data || resp
      if (data) mapStore.setMapData(data)
    } catch (e) { /* ignore */ }
    editStore.setStatus(`已保存 ${ok} 个图层的修改`)
  } else {
    editStore.setStatus('保存失败')
  }
}

// ========== 导出图片 ==========
async function handleExportImage() {
  const mapId = mapStore.currentMapId
  if (!mapId) {
    alert('请先生成地图')
    return
  }
  try {
    const resp = await api.exportMap(mapId, 'png')
    const data = resp.data || resp
    const filename = `map-${Date.now()}.png`
    if (typeof data === 'string' && data.startsWith('data:image')) {
      const link = document.createElement('a')
      link.href = data
      link.download = filename
      link.click()
      return
    }
    const blob = new Blob([String(data)], { type: 'image/png' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert('导出图片失败: ' + e.message)
  }
}

// ========== 自然语言修改 ==========
async function handleModify() {
  if (!modifyInput.value.trim()) return

  try {
    const res = await api.modifyMap(
      mapStore.currentMapData?.map_id ?? '',
      modifyInput.value,
    )

    if (res.success && res.data) {
      if (res.data.mapData) {
        renderMap(res.data.mapData)
      }
    }
  } catch (e) {
    console.error('修改地图失败', e)
  }

  modifyInput.value = ''
}
</script>

<style scoped>
.map-panel {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

#map-container {
  width: 100%;
  height: calc(100% - 44px);
  position: absolute;
  top: 44px;
  left: 0;
  background: #FAF8F3;
  /* 内图廓框线（与 carto-agent-1 行政区划图一致：灰-白-灰三层描边） */
  box-shadow: inset 0 0 0 2px #6b7280, inset 0 0 0 5px #ffffff, inset 0 0 0 6px #9ca3af;
}

/* 自然语言修改输入框 */
.map-modify-wrapper {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1000;
  background: white;
  padding: 8px 12px;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.map-modify-input {
  width: 320px;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.map-modify-input:focus {
  border-color: var(--color-primary, #a78bfa);
}

.map-modify-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.map-modify-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(167, 139, 250, 0.4);
}

/* 图例按钮 */
.map-legend-btn {
  position: absolute;
  top: 60px;
  right: 12px;
  z-index: 850;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  z-index: 1000;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.map-legend-btn:hover {
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.map-legend-btn.active {
  background: var(--color-primary-50, #f5f3ff);
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.map-legend-btn i {
  font-size: 14px;
}

/* 路径规划面板 */
.map-route-panel {
  position: absolute;
  top: 60px;
  right: 12px;
  width: 280px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  overflow: hidden;
}

.route-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.route-panel-close {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 16px;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.route-panel-close:hover {
  opacity: 1;
}

.route-panel-body {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.route-field {
  margin-bottom: 14px;
}

.route-field label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
  font-weight: 500;
}

.route-hint {
  font-weight: 400;
  color: #9ca3af;
  font-size: 11px;
}

.route-profile-group {
  display: flex;
  gap: 6px;
}

.route-profile-group button {
  flex: 1;
  padding: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
  transition: all 0.2s;
}

.route-profile-group button:hover {
  border-color: var(--color-primary, #a78bfa);
}

.route-profile-group button.active {
  background: var(--color-primary-50, #f5f3ff);
  border-color: var(--color-primary, #a78bfa);
  color: var(--color-primary, #a78bfa);
}

.route-coord-input {
  display: flex;
  gap: 8px;
}

.route-input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.route-input:focus {
  border-color: var(--color-primary, #a78bfa);
}

.route-start-icon {
  color: #22c55e;
}

.route-end-icon {
  color: #ef4444;
}

.route-plan-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--color-primary, #a78bfa), var(--color-primary-dark, #8b5cf6));
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-top: 8px;
}

.route-plan-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(167, 139, 250, 0.4);
}

.route-result {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f3f4f6;
}

.route-result-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.route-stat {
  text-align: center;
}

.route-stat-label {
  display: block;
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 2px;
}

.route-stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.route-steps {
  max-height: 200px;
  overflow-y: auto;
}

.route-step {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  font-size: 12px;
  color: #4b5563;
  border-bottom: 1px solid #f9fafb;
}

.route-step:last-child {
  border-bottom: none;
}

.route-step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary-100, #ede9fe);
  color: var(--color-primary, #a78bfa);
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 测量工具提示 */
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
}

.measure-tooltip i {
  color: var(--color-primary, #a78bfa);
}

/* 底部状态栏 */
.map-status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  z-index: 850;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 20px;
  font-size: 11px;
  color: #6b7280;
  z-index: 1000;
}

.map-status-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.map-status-item i {
  font-size: 11px;
  color: #9ca3af;
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
  color: #6b7280;
}

.status-edit.editing {
  background: #dbeafe;
  color: #2563eb;
}

/* Leaflet控件样式覆盖 */
:deep(.leaflet-control-zoom) {
  border: 1px solid #e5e7eb !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
  overflow: hidden;
}

:deep(.leaflet-control-zoom a) {
  width: 30px !important;
  height: 30px !important;
  line-height: 30px !important;
  font-size: 16px !important;
  color: #6b7280 !important;
  background: white !important;
  border-bottom: 1px solid #f3f4f6 !important;
}

:deep(.leaflet-control-zoom a:hover) {
  background: var(--color-primary-50, #f5f3ff) !important;
  color: var(--color-primary, #a78bfa) !important;
}

:deep(.leaflet-control-zoom a:last-child) {
  border-bottom: none !important;
}

:deep(.leaflet-control-scale-line) {
  border: 1px solid #6b7280 !important;
  border-top: none !important;
  color: #6b7280 !important;
  font-size: 11px !important;
  padding: 2px 6px !important;
  background: rgba(255, 255, 255, 0.9) !important;
}
</style>
