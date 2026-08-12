<template>
  <aside class="toolbar">
    <button class="toolbar-btn" :class="{ active: appStore.showChatPanel }" title="切换聊天面板" @click="appStore.toggleChatPanel()">
      <i class="fa-solid fa-comments"></i>
    </button>
    <button class="toolbar-btn" :class="{ active: appStore.showKGPanel }" title="知识图谱" @click="appStore.toggleKGPanel()">
      <i class="fa-solid fa-diagram-project"></i>
    </button>
    <div class="toolbar-divider"></div>
    <button class="toolbar-btn" :class="{ active: appStore.showRoutePanel }" title="路径规划" @click="appStore.toggleRoutePanel()">
      <i class="fa-solid fa-route"></i>
    </button>
    <button class="toolbar-btn" :class="{ active: appStore.showLayerPanel }" title="图层管理" @click="appStore.toggleLayerPanel()">
      <i class="fa-solid fa-layer-group"></i>
    </button>
    <button class="toolbar-btn" title="切换底图主题" @click="handleCycleTheme">
      <i class="fa-solid fa-palette"></i>
    </button>
    <button class="toolbar-btn" title="导出地图" @click="handleExport">
      <i class="fa-solid fa-download"></i>
    </button>
    <div class="toolbar-divider"></div>
    <button class="toolbar-btn" title="回到中心" @click="handleResetView">
      <i class="fa-solid fa-location-crosshairs"></i>
    </button>
    <button class="toolbar-btn" title="清除地图" @click="handleClearMap">
      <i class="fa-solid fa-trash-can"></i>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { CONFIG } from '@/config'

const appStore = useAppStore()
const mapStore = useMapStore()

function handleCycleTheme() {
  const themes = Object.keys(CONFIG.mapThemes)
  const currentIndex = themes.indexOf(mapStore.currentTheme)
  const nextIndex = (currentIndex + 1) % themes.length
  mapStore.setTheme(themes[nextIndex])
}

function handleExport() {
  if (!mapStore.currentMapId) {
    alert('请先生成地图')
    return
  }
  // 弹出导出选择
  const format = prompt('选择导出格式: geojson / png / svg', 'geojson')
  if (format) {
    // 导出逻辑由 MapCanvas 处理
  }
}

function handleResetView() {
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-reset-view'))
  }
}

function handleClearMap() {
  mapStore.clearAllLayers()
  const mapEl = document.getElementById('map-container')
  if (mapEl) {
    mapEl.dispatchEvent(new CustomEvent('map-clear-layers'))
  }
}
</script>

<style scoped>
.toolbar {
  width: var(--toolbar-width);
  min-width: var(--toolbar-width);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
  gap: 4px;
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  position: relative;
  z-index: 10;
}

.toolbar-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
  position: relative;
}
.toolbar-btn:hover {
  background: var(--color-bg);
  color: var(--color-primary);
  transform: translateX(-1px);
}
.toolbar-btn.active {
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-primary);
}
.toolbar-btn.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background: var(--color-primary);
  border-radius: 0 3px 3px 0;
}

/* tooltip */
.toolbar-btn::after {
  content: attr(title);
  position: absolute;
  right: 48px;
  background: var(--color-text);
  color: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  z-index: 20;
}
.toolbar-btn:hover::after {
  opacity: 1;
}

.toolbar-divider {
  width: 24px;
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}
</style>
