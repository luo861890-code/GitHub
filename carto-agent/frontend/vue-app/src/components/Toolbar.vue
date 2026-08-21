<template>
  <div class="map-toolbar">
    <!-- 导航工具 -->
    <div class="toolbar-group">
      <button
        class="tool-btn"
        :class="{ active: currentTool === 'pan' }"
        title="平移地图"
        @click="setTool('pan')"
      >
        <i class="fa-solid fa-hand"></i>
        <span>平移</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: currentTool === 'zoom-box' }"
        title="框选缩放"
        @click="setTool('zoom-box')"
      >
        <i class="fa-solid fa-vector-square"></i>
        <span>框选</span>
      </button>
      <button class="tool-btn" title="放大" @click="zoomIn">
        <i class="fa-solid fa-magnifying-glass-plus"></i>
        <span>放大</span>
      </button>
      <button class="tool-btn" title="缩小" @click="zoomOut">
        <i class="fa-solid fa-magnifying-glass-minus"></i>
        <span>缩小</span>
      </button>
      <button class="tool-btn" title="回到初始视图" @click="resetView">
        <i class="fa-solid fa-house"></i>
        <span>复位</span>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 测量工具 -->
    <div class="toolbar-group">
      <button
        class="tool-btn"
        :class="{ active: currentTool === 'measure-distance' }"
        title="测量距离"
        @click="startMeasure('distance')"
      >
        <i class="fa-solid fa-ruler"></i>
        <span>测距</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: currentTool === 'measure-area' }"
        title="测量面积"
        @click="startMeasure('area')"
      >
        <i class="fa-solid fa-shapes"></i>
        <span>测面</span>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 选择工具 -->
    <div class="toolbar-group">
      <button
        class="tool-btn"
        :class="{ active: currentTool === 'select' }"
        title="选择要素"
        @click="setTool('select')"
      >
        <i class="fa-solid fa-pointer"></i>
        <span>选择</span>
      </button>
      <button class="tool-btn" title="清除选择" @click="clearSelection">
        <i class="fa-solid fa-eraser"></i>
        <span>清除</span>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 地图工具（分析与绘制入口统一收敛到浮动面板，避免重复） -->
    <div class="toolbar-group">
      <button
        class="tool-btn"
        :class="{ active: appStore.showAnalysisPanel }"
        title="空间分析（缓冲区/叠加/最近邻等）"
        @click="appStore.toggleAnalysisPanel()"
      >
        <i class="fa-solid fa-chart-line"></i>
        <span>分析</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.showRoutePanel }"
        title="路径规划"
        @click="appStore.toggleRoutePanel()"
      >
        <i class="fa-solid fa-route"></i>
        <span>路径</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.markerMode }"
        title="在地图上添加标注"
        @click="appStore.toggleMarkerMode()"
      >
        <i class="fa-solid fa-location-dot"></i>
        <span>标注</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.showLegendPanel }"
        title="地图图例"
        @click="appStore.toggleLegendPanel()"
      >
        <i class="fa-solid fa-book-open"></i>
        <span>图例</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.showParamsPanel }"
        title="任务参数（微调智能体规划参数）"
        @click="appStore.toggleParamsPanel()"
      >
        <i class="fa-solid fa-sliders"></i>
        <span>参数</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.showMetadataModal }"
        title="编制说明"
        @click="appStore.toggleMetadataModal()"
      >
        <i class="fa-solid fa-circle-info"></i>
        <span>编制</span>
      </button>
      <button
        class="tool-btn"
        :class="{ active: appStore.showEditPanel }"
        title="编辑工具（绘制点/线/面、几何编辑）"
        @click="appStore.toggleEditPanel()"
      >
        <i class="fa-solid fa-pen-to-square"></i>
        <span>编辑</span>
      </button>
    </div>

    <div class="toolbar-divider"></div>

    <!-- 导出 -->
    <div class="toolbar-group">
      <div class="tool-dropdown" @click="toggleExportMenu">
        <button class="tool-btn" title="导出地图">
          <i class="fa-solid fa-download"></i>
          <span>导出</span>
          <i class="fa-solid fa-caret-down dropdown-arrow"></i>
        </button>
        <div v-if="showExportMenu" class="dropdown-menu dropdown-right">
          <div class="dropdown-item" @click="exportImage('png')">
            <i class="fa-solid fa-image"></i>
            <span>导出为 PNG</span>
          </div>
          <div class="dropdown-item" @click="exportImage('svg')">
            <i class="fa-solid fa-file-vector"></i>
            <span>导出为 SVG</span>
          </div>
          <div class="dropdown-item" @click="exportGeoJSON">
            <i class="fa-solid fa-file-code"></i>
            <span>导出 GeoJSON</span>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-item" @click="exportLayout">
            <i class="fa-solid fa-file-export"></i>
            <span>布局导出...</span>
          </div>
        </div>
      </div>
    </div>

    <LayoutExport
      :visible="showLayoutExport"
      :map-title="mapStore.mapName"
      :layout-data="mapStore.layout"
      @close="showLayoutExport = false"
      @export="handleLayoutExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'
import LayoutExport from './LayoutExport.vue'

const appStore = useAppStore()
const mapStore = useMapStore()

const currentTool = ref('pan')
const showExportMenu = ref(false)
const showLayoutExport = ref(false)

window.addEventListener('map-open-export', () => {
  showExportMenu.value = true
})

/** 切换地图工具（平移/框选缩放/选择要素） */
function setTool(tool: string) {
  currentTool.value = tool
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-set-tool', { detail: { tool } }))
  showExportMenu.value = false
}

function zoomIn() {
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-zoom-in'))
}

function zoomOut() {
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-zoom-out'))
}

function resetView() {
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-reset-view'))
}

function clearSelection() {
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-edit-clear-selection'))
}

function startMeasure(mode: 'distance' | 'area') {
  currentTool.value = mode === 'distance' ? 'measure-distance' : 'measure-area'
  const mapEl = document.getElementById('map-container')
  mapEl?.dispatchEvent(new CustomEvent('map-measure-start', { detail: { mode } }))
}

function toggleExportMenu() {
  showExportMenu.value = !showExportMenu.value
}

function exportImage(format: string) {
  if (format === 'png') {
    const mapEl = document.getElementById('map-container')
    mapEl?.dispatchEvent(new CustomEvent('map-export-image'))
  } else {
    exportMapFile(format, format === 'svg' ? 'svg' : 'png', format === 'svg' ? 'image/svg+xml' : 'image/png')
  }
  showExportMenu.value = false
}

async function exportMapFile(format: string, ext: string, mime: string) {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  try {
    const resp = await api.exportMap(mapStore.currentMapId, format)
    const data = resp.data || resp
    const filename = `map-${Date.now()}.${ext}`
    if (format === 'png' && typeof data === 'string' && data.startsWith('data:')) {
      const link = document.createElement('a')
      link.href = data
      link.download = filename
      link.click()
      return
    }
    const blob = new Blob([String(data)], { type: mime })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert('导出失败: ' + e.message)
  }
}

async function exportGeoJSON() {
  await exportMapFile('geojson', 'geojson', 'application/geo+json')
  showExportMenu.value = false
}

function exportLayout() {
  showLayoutExport.value = true
  showExportMenu.value = false
}

async function handleLayoutExport(options: any) {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  showLayoutExport.value = false
  try {
    const resp = await api.exportMap(mapStore.currentMapId, 'png', options)
    const data = resp.data || resp
    const filename = `map-layout-${Date.now()}.png`
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
    alert('布局导出失败: ' + e.message)
  }
}
</script>

<style scoped>
.map-toolbar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 6px 2px;
  background: var(--color-surface);
  height: 100%;
  overflow-y: auto;
  user-select: none;
}

.toolbar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  width: 100%;
}

.toolbar-divider {
  width: 28px;
  height: 1px;
  background: var(--color-border);
  margin: 5px 0;
}

.tool-btn {
  width: 44px;
  height: 40px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  font-size: 13px;
  transition: all 0.15s;
  position: relative;
}

.tool-btn i {
  font-size: 13px;
  line-height: 1;
}

.tool-btn span {
  font-size: 9px;
  line-height: 1;
  white-space: nowrap;
  color: inherit;
}

.tool-btn:hover {
  background: var(--color-bg);
  color: var(--color-primary);
}

.tool-btn.active {
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-primary);
}

.dropdown-arrow {
  position: absolute;
  bottom: 3px;
  right: 6px;
  font-size: 8px;
  color: var(--color-text-secondary);
}

/* 下拉菜单 */
.tool-dropdown {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  min-width: 180px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
  z-index: 1200;
}

.dropdown-menu.dropdown-right {
  left: auto;
  right: 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--color-text);
  cursor: pointer;
  transition: background 0.1s;
}

.dropdown-item:hover {
  background: var(--color-bg);
}

.dropdown-item.active {
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.06);
}

.dropdown-item i {
  width: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.dropdown-item.active i {
  color: var(--color-primary);
}

.dropdown-item span {
  flex: 1;
}

.dropdown-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}
</style>
