<template>
  <div class="analysis-panel">
    <div class="analysis-header">
      <span><i class="fa-solid fa-chart-line"></i> 空间分析</span>
      <button class="analysis-close" title="关闭" @click="appStore.toggleAnalysisPanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <div class="analysis-tabs">
      <button
        class="analysis-tab"
        :class="{ active: mode === 'buffer' }"
        @click="setMode('buffer')"
      >缓冲区</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'overlay' }"
        @click="setMode('overlay')"
      >叠加分析</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'clip' }"
        @click="setMode('clip')"
      >裁剪</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'intersect' }"
        @click="setMode('intersect')"
      >相交</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'union' }"
        @click="setMode('union')"
      >并集</button>
      <button
        class="analysis-tab"
        :class="{ active: mode === 'nearest' }"
        @click="setMode('nearest')"
      >最近邻</button>
    </div>

    <div class="analysis-body">
      <div class="analysis-field">
        <label>源图层</label>
        <select v-model="sourceId" class="analysis-select">
          <option v-for="l in mapStore.sortedLayers" :key="l.id" :value="l.id">
            {{ l.data.name }}（{{ typeLabel(l.data.type) }}）
          </option>
        </select>
      </div>

      <div v-if="mode !== 'buffer'" class="analysis-field">
        <label>目标图层</label>
        <select v-model="targetId" class="analysis-select">
          <option v-for="l in mapStore.sortedLayers" :key="l.id" :value="l.id">
            {{ l.data.name }}（{{ typeLabel(l.data.type) }}）
          </option>
        </select>
      </div>

      <div v-if="mode === 'buffer'" class="analysis-field">
        <label>缓冲距离（km）</label>
        <input v-model.number="bufferKm" type="number" min="0.1" step="0.1" class="analysis-input" />
      </div>

      <button class="analysis-run-btn" :disabled="running" @click="run">
        <div v-if="running" class="analysis-spinner"></div>
        <i v-else class="fa-solid fa-play"></i>
        开始分析
      </button>

      <div v-if="message" class="analysis-message">{{ message }}</div>

      <div v-if="summary.length > 0" class="analysis-summary">
        <div class="analysis-summary-title">结果</div>
        <div v-for="(line, i) in summary" :key="i" class="analysis-summary-line">{{ line }}</div>
        <div v-if="resultLayerId" class="analysis-zoom" @click="zoomToResult">
          <i class="fa-solid fa-magnifying-glass-plus"></i> 缩放至结果图层
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import {
  intersectPointPolygon,
  nearestPairs,
  bufferPoint,
  bufferPolygon,
  extractLayerGeometries,
  clipPolylineToRing,
  intersectRings,
} from '@/utils/analysis'
import api from '@/services/api'
import type { MapLayer, MapFeature } from '@/types'
import type { LatLng } from '@/utils/analysis'

const appStore = useAppStore()
const mapStore = useMapStore()

const mode = ref<'buffer' | 'overlay' | 'clip' | 'intersect' | 'union' | 'nearest'>('buffer')
const sourceId = ref('')
const targetId = ref('')
const bufferKm = ref(1)
const running = ref(false)
const message = ref('')
const summary = ref<string[]>([])
const resultLayerId = ref('')

const sourceLayer = computed(() =>
  sourceId.value ? mapStore.layerGroups[sourceId.value]?.data : null
)
const targetLayer = computed(() =>
  targetId.value ? mapStore.layerGroups[targetId.value]?.data : null
)

function setMode(m: 'buffer' | 'overlay' | 'clip' | 'intersect' | 'union' | 'nearest') {
  mode.value = m
  message.value = ''
  summary.value = []
  resultLayerId.value = ''
}

function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    polyline: '线',
    line: '线',
    polygon: '面',
    area: '面',
    circleMarker: '点',
    marker: '点',
    point: '点',
    textLabel: '标注',
    label: '标注',
    heatmap: '热力',
  }
  return labels[type] || type
}

/** 将分析结果坐标集合拆分为 features 型要素，保证多要素结果在地图上正确渲染 */
function toResultFeatures(type: string, coordinates: any): MapFeature[] {
  const t = (type || '').toLowerCase()
  if (['polygon', 'area'].includes(t)) {
    return (Array.isArray(coordinates) ? coordinates : []).map((ring: any) => ({
      type: 'polygon',
      coordinates: ring,
      properties: {},
    }))
  }
  if (['polyline', 'line', 'linestring'].includes(t)) {
    return (Array.isArray(coordinates) ? coordinates : []).map((line: any) => ({
      type: 'polyline',
      coordinates: line,
      properties: {},
    }))
  }
  return (Array.isArray(coordinates) ? coordinates : []).map((p: any) => ({
    type: 'point',
    coordinates: p,
    properties: {},
  }))
}

async function addResultLayer(name: string, type: string, coordinates: any, style: Record<string, any>): Promise<string> {
  const id = 'analysis_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7)
  const layer: MapLayer = {
    id,
    type: type as any,
    name,
    features: toResultFeatures(type, coordinates),
    coordinates,
    style,
    group: '分析结果',
  }
  const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l) => l.order))
  mapStore.layerGroups[id] = { visible: true, data: layer, order: maxOrder + 1 }
  // 有地图时持久化到后端（刷新后仍保留）
  if (mapStore.currentMapId) {
    try {
      const resp = await api.addLayer(mapStore.currentMapId, {
        layer_type: type,
        name,
        coordinates,
        properties: (layer.features || []).map((f) => f.properties || {}),
        style,
        group: '分析结果',
      })
      const data = resp.data || resp
      const serverLayer = (data.layers || [])[(data.layers || []).length - 1]
      if (serverLayer && serverLayer.id) {
        mapStore.setMapData(data)
        const el = document.getElementById('map-container')
        el?.dispatchEvent(new CustomEvent('map-apply-data', { detail: { data } }))
        return serverLayer.id
      }
    } catch (e) {
      console.warn('分析结果持久化失败，仅保留本地图层:', e)
    }
  }
  return id
}

function run() {
  message.value = ''
  summary.value = []
  resultLayerId.value = ''
  if (!sourceLayer.value) {
    message.value = '请选择源图层'
    return
  }
  running.value = true
  setTimeout(async () => {
    try {
      if (mode.value === 'buffer') {
        await runBuffer()
      } else if (mode.value === 'overlay') {
        await runOverlay()
      } else if (mode.value === 'clip') {
        await runClip()
      } else if (mode.value === 'intersect') {
        await runIntersect()
      } else if (mode.value === 'union') {
        await runUnion()
      } else {
        await runNearest()
      }
    } catch (e: any) {
      message.value = '分析失败: ' + e.message
    } finally {
      running.value = false
    }
  }, 30)
}

async function runBuffer() {
  const layer = sourceLayer.value!
  const geo = extractLayerGeometries(layer)
  const km = bufferKm.value || 1
  const rings: LatLng[][] = []
  geo.rings.forEach((ring) => { if (ring.length >= 3) rings.push(bufferPolygon(ring, km)) })
  geo.points.forEach((p) => rings.push(bufferPoint(p, km)))
  if (rings.length === 0) {
    message.value = '源图层没有可缓冲的几何（点或面）'
    return
  }
  const id = await addResultLayer(`缓冲区（${km}km）`, 'polygon', rings, {
    color: '#7c3aed',
    fillColor: '#a78bfa',
    fillOpacity: 0.35,
    weight: 1.5,
  })
  resultLayerId.value = id
  summary.value = [
    `生成 ${rings.length} 个缓冲面`,
    `缓冲距离 ${km} km`,
    '结果已加入“分析结果”图层组',
  ]
}

async function runOverlay() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标图层'
    return
  }
  const t = targetLayer.value
  const rings = extractLayerGeometries(t).rings
  if (rings.length === 0) {
    message.value = '目标图层没有面状几何，叠加分析需要目标为面图层'
    return
  }
  const pts = extractLayerGeometries(layer).points
  if (pts.length === 0) {
    message.value = '源图层没有点状几何，暂支持“点 ∩ 面”叠加'
    return
  }
  const kept = intersectPointPolygon(pts, rings)
  if (kept.length === 0) {
    message.value = '没有点落在目标面内'
    return
  }
  const id = await addResultLayer(`叠加结果（${layer.name} ∩ ${t.name}）`, 'circleMarker', kept, {
    color: '#ef4444',
    radius: 7,
    fillOpacity: 0.9,
    weight: 2,
  })
  resultLayerId.value = id
  summary.value = [
    `源点 ${pts.length} 个`,
    `保留 ${kept.length} 个（落在目标面内）`,
    '结果已加入“分析结果”图层组',
  ]
}

async function runClip() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择裁剪面图层'
    return
  }
  const t = targetLayer.value
  const clipRings = extractLayerGeometries(t).rings
  if (clipRings.length === 0) {
    message.value = '裁剪图层没有面状几何'
    return
  }
  const src = extractLayerGeometries(layer)
  const srcType = (layer.type || '').toLowerCase()
  const isArea = ['polygon', 'area'].includes(srcType)
  const isLine = ['polyline', 'line', 'linestring'].includes(srcType)

  if (isArea) {
    // 面裁剪：源面 ∩ 裁剪面
    const outRings: LatLng[][] = []
    src.rings.forEach((r) => {
      clipRings.forEach((cr) => {
        const inter = intersectRings(r, cr)
        if (inter.length >= 3) outRings.push(inter)
      })
    })
    if (outRings.length === 0) { message.value = '裁剪后没有交集面'; return }
    const id = await addResultLayer(`裁剪结果（${layer.name}）`, 'polygon', outRings, {
      color: '#f59e0b',
      fillColor: '#fbbf24',
      fillOpacity: 0.4,
      weight: 1.5,
    })
    resultLayerId.value = id
    summary.value = [`生成 ${outRings.length} 个裁剪面`, '结果已加入“分析结果”图层组']
  } else if (isLine) {
    // 线裁剪：保留面内线段
    const outLines: LatLng[][] = []
    src.lines.forEach((line) => {
      clipRings.forEach((cr) => {
        clipPolylineToRing(line, cr).forEach((seg) => { if (seg.length >= 2) outLines.push(seg) })
      })
    })
    if (outLines.length === 0) { message.value = '裁剪后没有落在面内的线段'; return }
    const id = await addResultLayer(`裁剪结果（${layer.name}）`, 'polyline', outLines, {
      color: '#f59e0b',
      weight: 2.5,
      opacity: 1,
    })
    resultLayerId.value = id
    summary.value = [`保留 ${outLines.length} 条线段`, '结果已加入“分析结果”图层组']
  } else {
    // 点裁剪：保留面内点
    const kept = intersectPointPolygon(src.points, clipRings)
    if (kept.length === 0) { message.value = '没有点落在裁剪面内'; return }
    const id = await addResultLayer(`裁剪结果（${layer.name}）`, 'circleMarker', kept, {
      color: '#f59e0b',
      radius: 6,
      fillOpacity: 0.9,
      weight: 2,
    })
    resultLayerId.value = id
    summary.value = [`源点 ${src.points.length} 个`, `保留 ${kept.length} 个`, '结果已加入“分析结果”图层组']
  }
}

async function runIntersect() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标面图层'
    return
  }
  const t = targetLayer.value
  const aRings = extractLayerGeometries(layer).rings
  const bRings = extractLayerGeometries(t).rings
  if (aRings.length === 0 || bRings.length === 0) {
    message.value = '相交分析需要源与目标均为面图层'
    return
  }
  const outRings: LatLng[][] = []
  aRings.forEach((ra) => {
    bRings.forEach((rb) => {
      const inter = intersectRings(ra, rb)
      if (inter.length >= 3) outRings.push(inter)
    })
  })
  if (outRings.length === 0) { message.value = '两个面图层没有交集'; return }
  const id = await addResultLayer(`相交结果（${layer.name} ∩ ${t.name}）`, 'polygon', outRings, {
    color: '#0ea5e9',
    fillColor: '#38bdf8',
    fillOpacity: 0.4,
    weight: 1.5,
  })
  resultLayerId.value = id
  summary.value = [`生成 ${outRings.length} 个交集面`, '结果已加入“分析结果”图层组']
}

async function runUnion() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标面图层'
    return
  }
  const t = targetLayer.value
  const aRings = extractLayerGeometries(layer).rings
  const bRings = extractLayerGeometries(t).rings
  if (aRings.length === 0 || bRings.length === 0) {
    message.value = '并集分析需要源与目标均为面图层'
    return
  }
  const outRings: LatLng[][] = [...aRings, ...bRings]
  const id = await addResultLayer(`并集结果（${layer.name} ∪ ${t.name}）`, 'polygon', outRings, {
    color: '#10b981',
    fillColor: '#34d399',
    fillOpacity: 0.35,
    weight: 1.5,
  })
  resultLayerId.value = id
  summary.value = [
    `合并 ${outRings.length} 个面（源 ${aRings.length} + 目标 ${bRings.length}）`,
    '结果已加入“分析结果”图层组',
  ]
}

async function runNearest() {
  const layer = sourceLayer.value!
  if (!targetLayer.value) {
    message.value = '请选择目标图层'
    return
  }
  const t = targetLayer.value
  const sources = extractLayerGeometries(layer).points
  const targets = extractLayerGeometries(t).points
  if (sources.length === 0 || targets.length === 0) {
    message.value = '源/目标图层缺少点状几何'
    return
  }
  const pairs = nearestPairs(sources, targets)
  const segments = pairs.map((p) => p.segment)
  const id = await addResultLayer(`最近邻连线（${layer.name} → ${t.name}）`, 'polyline', segments, {
    color: '#0ea5e9',
    weight: 2,
    opacity: 0.85,
  })
  resultLayerId.value = id
  const avg = pairs.reduce((s, p) => s + p.distanceKm, 0) / pairs.length
  const max = Math.max(...pairs.map((p) => p.distanceKm))
  summary.value = [
    `源 ${sources.length} 个要素，目标 ${targets.length} 个要素`,
    `平均最近距离 ${avg.toFixed(2)} km`,
    `最大最近距离 ${max.toFixed(2)} km`,
    '结果已加入“分析结果”图层组',
  ]
}

function zoomToResult() {
  if (!resultLayerId.value) return
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent('map-zoom-to-layer', { detail: { layerId: resultLayerId.value } }))
  }
}

watch(
  () => appStore.showAnalysisPanel,
  (show) => {
    if (show && appStore.analysisMode) {
      mode.value = appStore.analysisMode
      appStore.setAnalysisMode(null)
    }
  },
  { immediate: true }
)

function ensureSelection() {
  const ids = mapStore.sortedLayers.map((l) => l.id)
  if (!ids.includes(sourceId.value)) sourceId.value = ids[0] || ''
  if (!ids.includes(targetId.value)) targetId.value = ids[1] || ids[0] || ''
}

watch(
  () => mapStore.currentMapId,
  ensureSelection,
  { immediate: true }
)

watch(
  () => mapStore.sortedLayers.map((l) => l.id).join(','),
  ensureSelection,
  { immediate: true }
)
</script>

<style scoped>
.analysis-panel {
  position: absolute;
  top: 48px;
  left: 12px;
  width: 300px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 850;
  overflow: hidden;
}

.analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
}

.analysis-close {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
}

.analysis-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

.analysis-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
}

.analysis-tab {
  flex: 1;
  padding: 6px 4px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}

.analysis-tab.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.analysis-body {
  padding: 12px 14px;
  font-size: 12px;
}

.analysis-field {
  margin-bottom: 10px;
}

.analysis-field label {
  display: block;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.analysis-select,
.analysis-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
}

.analysis-select:focus,
.analysis-input:focus {
  border-color: var(--color-primary-light);
}

.analysis-run-btn {
  width: 100%;
  padding: 9px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.analysis-run-btn:disabled {
  opacity: 0.6;
}

.analysis-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.analysis-message {
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  border-radius: 6px;
  font-size: 11px;
}

.analysis-summary {
  margin-top: 10px;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.analysis-summary-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 6px;
}

.analysis-summary-line {
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.analysis-zoom {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--color-border);
  font-size: 11px;
  color: var(--color-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
}
</style>
