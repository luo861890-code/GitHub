<template>
  <main class="map-panel">
    <!-- 地图容器 -->
    <div id="map-container" ref="mapContainerRef"></div>

    <!-- 浮动：底图主题选择器 -->
    <div class="map-toolbar-floating">
      <select v-model="currentTheme" class="map-theme-select" title="切换底图" @change="setTheme(currentTheme)">
        <option v-for="(theme, key) in CONFIG.mapThemes" :key="key" :value="key">{{ theme.name }}</option>
      </select>
    </div>

    <!-- 浮动：自然语言修改输入框 -->
    <div class="map-modify-wrapper">
      <input
        v-model="modifyInput"
        type="text"
        class="map-modify-input"
        placeholder="自然语言修改地图，如"把道路改成红色"..."
        @keydown.enter="handleModify"
      />
      <button class="map-modify-btn" @click="handleModify" title="执行修改">
        <i class="fa-solid fa-wand-magic-sparkles"></i>
      </button>
    </div>

    <!-- 浮动：图层管理面板 -->
    <div v-if="appStore.showLayerPanel" class="map-layer-panel">
      <div class="layer-panel-header">
        <span><i class="fa-solid fa-layer-group"></i> 图层管理</span>
        <button class="layer-panel-close" @click="appStore.toggleLayerPanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="layer-panel-body">
        <div v-if="layerEntries.length === 0" class="empty-hint">暂无图层</div>
        <div v-for="[id, item] in layerEntries" :key="id" class="layer-item">
          <div class="layer-item-header">
            <label class="layer-toggle">
              <input type="checkbox" :checked="item.visible" @change="mapStore.toggleLayer(id, ($event.target as HTMLInputElement).checked)" />
              <span class="layer-color-dot" :style="{ background: item.data.style?.color || '#3388ff' }"></span>
              <span class="layer-name">{{ item.data.name || '未命名图层' }}</span>
            </label>
          </div>
          <div class="layer-item-type">{{ item.data.type }}</div>
        </div>
      </div>
    </div>

    <!-- 浮动：路径规划面板 -->
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
          <label>起点</label>
          <div class="route-coord-input">
            <input v-model="routeStartLat" type="number" placeholder="纬度" step="0.0001" class="route-input" />
            <input v-model="routeStartLng" type="number" placeholder="经度" step="0.0001" class="route-input" />
          </div>
        </div>
        <div class="route-field">
          <label>终点</label>
          <div class="route-coord-input">
            <input v-model="routeEndLat" type="number" placeholder="纬度" step="0.0001" class="route-input" />
            <input v-model="routeEndLng" type="number" placeholder="经度" step="0.0001" class="route-input" />
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
        </div>
      </div>
    </div>

    <!-- 图例面板 -->
    <div v-if="showLegend && legendData" class="map-legend-panel">
      <div class="legend-panel-header">
        <span><i class="fa-solid fa-book-open"></i> 图例</span>
        <button @click="showLegend = false"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="legend-panel-body">
        <div v-for="item in legendData.items" :key="item.label" class="legend-item">
          <span class="legend-symbol" :style="{ background: item.color || '#999', borderColor: item.fillColor || item.color || '#999' }" :class="{ 'legend-line': item.type === 'line', 'legend-polygon': item.type === 'polygon' }"></span>
          <span class="legend-label">{{ item.label }}</span>
        </div>
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="map-status-bar">
      <div class="map-status-item">
        <i class="fa-solid fa-location-crosshairs"></i>
        <span>{{ statusLat }}</span>
        <span class="status-sep">&#8226;</span>
        <span>{{ statusLng }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-magnifying-glass-plus"></i>
        <span>缩放 {{ statusZoom }}</span>
      </div>
      <div class="map-status-item">
        <i class="fa-solid fa-layer-group"></i>
        <span>{{ layerEntries.length }} 图层</span>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { api } from '@/services/api'
import { CONFIG } from '@/config'
import type { MapData, MapLayer, LegendData } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()

const mapContainerRef = ref<HTMLDivElement | null>(null)
let map: maplibregl.Map | null = null
let currentRasterSource = ''

// 状态
const currentTheme = ref('plain')
const modifyInput = ref('')
const showLegend = ref(false)
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

const layerEntries = computed(() => {
  return Object.entries(mapStore.layerGroups)
})

// ========== 初始化地图 ==========
onMounted(() => {
  if (!mapContainerRef.value) return

  const [lat, lng] = CONFIG.defaultMapCenter

  map = new maplibregl.Map({
    container: mapContainerRef.value,
    style: {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'bg',
          type: 'background',
          paint: { 'background-color': '#FAF8F3' },
        },
      ],
    },
    center: [lng, lat], // MapLibre uses [lng, lat]
    zoom: CONFIG.defaultZoom,
  })

  map.addControl(new maplibregl.NavigationControl({ position: 'bottom-right' }))
  map.addControl(new maplibregl.ScaleControl({ position: 'bottom-left' }))

  map.on('move', updateStatusBar)
  map.on('click', (e) => {
    statusLat.value = e.lngLat.lat.toFixed(4) + '°'
    statusLng.value = e.lngLat.lng.toFixed(4) + '°'
  })

  // 设置初始底图
  setTheme('plain')

  // 监听自定义事件
  const handleReset = () => {
    map?.flyTo({ center: [lng, lat], zoom: CONFIG.defaultZoom })
  }
  const handleClear = () => {
    clearAllMapLayers()
  }
  mapContainerRef.value.addEventListener('map-reset-view', handleReset)
  mapContainerRef.value.addEventListener('map-clear-layers', handleClear)

  // 监听面板切换
  watch(
    () => appStore.showChatPanel,
    () => {
      setTimeout(() => map?.resize(), 300)
    }
  )
})

onUnmounted(() => {
  map?.remove()
  map = null
})

// ========== 底图主题 ==========
function setTheme(themeName: string) {
  const themeConfig = CONFIG.mapThemes[themeName]
  if (!themeConfig || !map) return

  // 移除旧的raster source
  if (currentRasterSource) {
    try {
      if (map.getLayer(currentRasterSource + '-layer')) {
        map.removeLayer(currentRasterSource + '-layer')
      }
      if (map.getSource(currentRasterSource)) {
        map.removeSource(currentRasterSource)
      }
    } catch {}
  }

  if (themeConfig.url) {
    const sourceId = 'raster-' + themeName
    map.addSource(sourceId, {
      type: 'raster',
      tiles: [themeConfig.url],
      tileSize: 256,
      maxzoom: themeConfig.maxZoom,
      attribution: themeConfig.attribution,
    })
    map.addLayer({
      id: sourceId + '-layer',
      type: 'raster',
      source: sourceId,
      paint: {},
    })
    currentRasterSource = sourceId
  } else {
    currentRasterSource = ''
  }
  currentTheme.value = themeName
  mapStore.setTheme(themeName)
}

// ========== 渲染地图数据 ==========
watch(
  () => mapStore.currentMapData,
  (data) => {
    if (data && map) {
      renderMap(data)
    }
  }
)

function renderMap(mapData: MapData) {
  if (!map || !mapData) return

  clearAllMapLayers()

  const center = mapData.center
  if (center && center.length === 2 && center[0] != null && center[1] != null) {
    map.setCenter([center[1], center[0]])
    map.setZoom(mapData.zoom || CONFIG.defaultZoom)
  }

  if (mapData.theme && mapData.theme !== currentTheme.value) {
    setTheme(mapData.theme)
  }

  if (mapData.layers) {
    const sorted = [...mapData.layers].sort((a, b) => layerZ(a) - layerZ(b))
    sorted.forEach((layer) => addLayer(layer))
  }

  if (mapData.legend) {
    legendData.value = mapData.legend
    showLegend.value = true
  }

  updateStatusBar()
}

function clearAllMapLayers() {
  if (!map) return
  const style = map.getStyle()
  if (!style) return
  const layers = style.layers?.filter((l) => l.id !== 'bg' && !l.id.startsWith('raster-'))
  layers?.forEach((l) => {
    try {
      map!.removeLayer(l.id)
    } catch {}
  })
}

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

// ========== 图层添加方法 ==========
function addLayer(layer: MapLayer) {
  if (!map) return
  const style = layer.style || {}
  const layerId = layer.id
  const sourceId = 'src-' + layerId

  try {
    switch (layer.type) {
      case 'polyline':
      case 'line':
        addPolyline(sourceId, layerId, layer, style)
        break
      case 'polygon':
      case 'area':
        addPolygon(sourceId, layerId, layer, style)
        break
      case 'circleMarker':
      case 'point':
      case 'marker':
        addCircleMarker(sourceId, layerId, layer, style)
        break
      case 'heatmap':
        addHeatmap(sourceId, layerId, layer, style)
        break
      case 'textLabel':
      case 'label':
        addTextLabel(sourceId, layerId, layer, style)
        break
    }
  } catch (e) {
    console.warn('添加图层失败:', layer.name, e)
  }
}

function addPolyline(sourceId: string, layerId: string, layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return

  map!.addSource(sourceId, {
    type: 'geojson',
    data: {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: {},
    },
  })
  map!.addLayer({
    id: layerId,
    type: 'line',
    source: sourceId,
    paint: {
      'line-color': style.color || '#3388ff',
      'line-width': style.weight || 3,
      'line-opacity': style.opacity !== undefined ? style.opacity : 1,
      'line-dasharray': parseDashArray(style.dashArray),
    },
  })
}

function addPolygon(sourceId: string, layerId: string, layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords || coords.length === 0) return

  map!.addSource(sourceId, {
    type: 'geojson',
    data: {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [coords] },
      properties: {},
    },
  })
  map!.addLayer({
    id: layerId,
    type: 'fill',
    source: sourceId,
    paint: {
      'fill-color': style.fillColor || style.color || '#3388ff',
      'fill-opacity': style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
      'fill-outline-color': style.color || '#3388ff',
    },
  })
}

function addCircleMarker(sourceId: string, layerId: string, layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords) return

  const features = coords.map((c: number[]) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: c },
    properties: {},
  }))

  map!.addSource(sourceId, {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features,
    },
  })
  map!.addLayer({
    id: layerId,
    type: 'circle',
    source: sourceId,
    paint: {
      'circle-color': style.color || '#f59e0b',
      'circle-radius': style.radius || 6,
      'circle-opacity': style.fillOpacity !== undefined ? style.fillOpacity : 0.7,
      'circle-stroke-width': style.weight || 2,
      'circle-stroke-color': '#fff',
    },
  })
}

function addHeatmap(sourceId: string, layerId: string, layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords) return

  const features = coords.map((c: number[]) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: c },
    properties: {},
  }))

  map!.addSource(sourceId, {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features,
    },
  })
  map!.addLayer({
    id: layerId,
    type: 'heatmap',
    source: sourceId,
    paint: {
      'heatmap-radius': style.radius || 35,
      'heatmap-opacity': style.minOpacity || 0.6,
      'heatmap-intensity': 1,
      'heatmap-color': [
        'interpolate', ['linear'], ['heatmap-density'],
        0, 'rgba(0,0,4,0)',
        0.2, 'rgb(50,10,94)',
        0.4, 'rgb(120,28,109)',
        0.6, 'rgb(187,55,84)',
        0.8, 'rgb(237,105,37)',
        1, 'rgb(252,191,73)',
      ],
    },
  })
}

function addTextLabel(sourceId: string, layerId: string, layer: MapLayer, style: any) {
  const coords = normalizeCoords(layer.coordinates)
  if (!coords) return

  const features = coords.map((c: number[], idx: number) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: c },
    properties: {
      name: layer.properties?.[idx]?.name || layer.name || '',
    },
  }))

  map!.addSource(sourceId, {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features,
    },
  })
  map!.addLayer({
    id: layerId,
    type: 'symbol',
    source: sourceId,
    layout: {
      'text-field': ['get', 'name'],
      'text-size': style.fontSize || 13,
      'text-offset': [0, 1.2],
      'text-anchor': 'top',
    },
    paint: {
      'text-color': style.color || '#1a1a1a',
      'text-halo-color': '#fff',
      'text-halo-width': 2,
    },
  })
}

// ========== 坐标标准化 ==========
function normalizeCoords(coordinates: any): number[][] | null {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return null
  // 已经是 [lng, lat] 格式
  const first = coordinates[0]
  if (first == null || isNaN(first)) return null
  if (typeof first === 'number') {
    // [lat, lng] 格式，需要反转
    if (coordinates.length >= 2 && typeof coordinates[1] === 'number' && !Array.isArray(coordinates[1])) {
      // 每个坐标对是 [lat, lng]
      const result: number[][] = []
      for (let i = 0; i < coordinates.length; i += 2) {
        if (i + 1 < coordinates.length) {
          result.push([coordinates[i + 1], coordinates[i]])
        }
      }
      return result.length > 0 ? result : null
    }
    return [coordinates as number[]] // 单个点
  }
  if (Array.isArray(first)) {
    // 已经是 [lat, lng] 数组
    return coordinates.map((c: number[]) => [c[1], c[0]])
  }
  return null
}

function parseDashArray(dash: string | null | undefined): number[] {
  if (!dash) return [1]
  return dash.split(',').map(Number)
}

// ========== 自然语言修改 ==========
async function handleModify() {
  const instruction = modifyInput.value.trim()
  if (!instruction || !mapStore.currentMapId) return
  try {
    const result = await api.modifyMap(mapStore.currentMapId, instruction)
    if (result.map_data) {
      renderMap(result.map_data)
    }
    modifyInput.value = ''
  } catch (e: any) {
    alert('修改失败: ' + e.message)
  }
}

// ========== 路径规划 ==========
async function handlePlanRoute() {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  const slat = parseFloat(routeStartLat.value)
  const slng = parseFloat(routeStartLng.value)
  const elat = parseFloat(routeEndLat.value)
  const elng = parseFloat(routeEndLng.value)
  if (isNaN(slat) || isNaN(slng) || isNaN(elat) || isNaN(elng)) {
    alert('请设置起点和终点')
    return
  }
  try {
    const result = await api.planRoute(mapStore.currentMapId, {
      start: [slat, slng],
      end: [elat, elng],
      profile: routeProfile.value,
    })
    const routeData = result.data || result
    if (routeData) {
      mapStore.setRouteData(routeData)
      // 渲染路径线
      const sourceId = 'route-source'
      const layerId = 'route-layer'
      try {
        if (map!.getLayer(layerId)) map!.removeLayer(layerId)
        if (map!.getSource(sourceId)) map!.removeSource(sourceId)
      } catch {}
      map!.addSource(sourceId, {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: routeData.coordinates.map((c: number[]) => [c[1], c[0]]) },
          properties: {},
        },
      })
      map!.addLayer({
        id: layerId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': '#3b82f6',
          'line-width': 5,
          'line-opacity': 0.8,
        },
      })
    }
  } catch (e: any) {
    alert('路径规划失败: ' + e.message)
  }
}

// ========== 状态栏更新 ==========
function updateStatusBar() {
  if (!map) return
  const center = map.getCenter()
  statusLat.value = center.lat.toFixed(4) + '°'
  statusLng.value = center.lng.toFixed(4) + '°'
  statusZoom.value = map.getZoom().toFixed(2)
}
</script>

<style scoped>
.map-panel {
  flex: 1;
  position: relative;
  overflow: hidden;
}

#map-container {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
}

/* 底图选择器 */
.map-toolbar-floating {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
}
.map-theme-select {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  font-size: 12px;
  color: var(--color-text);
  cursor: pointer;
  outline: none;
}

/* 自然语言修改 */
.map-modify-wrapper {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  z-index: 10;
}
.map-modify-input {
  width: 360px;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  font-size: 13px;
  outline: none;
  box-shadow: var(--shadow-md);
}
.map-modify-input:focus {
  border-color: var(--color-primary-light);
}
.map-modify-btn {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  box-shadow: var(--shadow-md);
  transition: all 0.2s;
}
.map-modify-btn:hover {
  opacity: 0.9;
}

/* 图层面板 */
.map-layer-panel {
  position: absolute;
  top: 10px;
  right: calc(var(--toolbar-width) + 10px);
  width: 240px;
  max-height: 50vh;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 20;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.layer-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
}
.layer-panel-close {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.layer-panel-body {
  overflow-y: auto;
  padding: 8px;
}
.layer-item {
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}
.layer-item:hover {
  background: var(--color-bg);
}
.layer-item-header {
  display: flex;
  align-items: center;
}
.layer-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
}
.layer-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.layer-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.layer-item-type {
  font-size: 11px;
  color: var(--color-text-secondary);
  padding-left: 26px;
}
.empty-hint {
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: center;
  padding: 16px;
}

/* 路径规划面板 */
.map-route-panel {
  position: absolute;
  top: 10px;
  right: calc(var(--toolbar-width) + 10px);
  width: 300px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 20;
  overflow: hidden;
}
.route-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
}
.route-panel-close {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.route-panel-body {
  padding: 14px;
}
.route-field {
  margin-bottom: 12px;
}
.route-field label {
  font-size: 12px;
  color: var(--color-text-secondary);
  display: block;
  margin-bottom: 6px;
}
.route-profile-group {
  display: flex;
  gap: 6px;
}
.route-profile-group button {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.route-profile-group button.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.route-coord-input {
  display: flex;
  gap: 6px;
}
.route-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  outline: none;
}
.route-plan-btn {
  width: 100%;
  padding: 10px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
}
.route-result {
  margin-top: 10px;
  padding: 10px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
}
.route-result-stats {
  display: flex;
  gap: 20px;
}
.route-stat {
  display: flex;
  flex-direction: column;
}
.route-stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.route-stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
}

/* 图例面板 */
.map-legend-panel {
  position: absolute;
  bottom: 40px;
  right: calc(var(--toolbar-width) + 10px);
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 20;
  max-height: 300px;
  overflow-y: auto;
  min-width: 200px;
}
.legend-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
  font-weight: 600;
}
.legend-panel-body {
  padding: 8px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  font-size: 12px;
}
.legend-symbol {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid;
  flex-shrink: 0;
}
.legend-symbol.legend-line {
  height: 3px;
  border: none;
  border-radius: 2px;
}
.legend-symbol.legend-polygon {
  background: rgba(0, 0, 0, 0.1) !important;
}

/* 状态栏 */
.map-status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--color-border);
  font-size: 11px;
  color: var(--color-text-secondary);
  z-index: 5;
}
.map-status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.status-sep {
  margin: 0 2px;
}
</style>
