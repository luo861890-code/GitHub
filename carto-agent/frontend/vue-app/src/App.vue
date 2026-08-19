<template>
  <div class="app-root">
    <!-- 主界面 -->
    <template v-if="appStore.currentView === 'main'">
      <AppHeader />
      <div class="app-body">
        <Toolbar class="left-toolbar" v-show="appStore.showLayerPanel" />
        <LayerPanel v-show="appStore.showLayerPanel" />
        <div class="map-area">
          <LegacyMapPanel />
          <MapLegendPanel v-if="appStore.showLegendPanel" :legend-data="mapStore.currentMapData?.legend || null" />
          <MiniLegend v-if="mapStore.mapType === 'administrative'" />
          <ParamsPanel v-if="appStore.showParamsPanel" />
          <RoutePanel v-if="appStore.showRoutePanel" />
          <AnalysisPanel v-if="appStore.showAnalysisPanel" />
          <MapEditPanel v-if="appStore.showEditPanel" />
        </div>
        <ChatPanel v-show="appStore.showChatPanel" />
        <KGPanel v-show="appStore.showKGPanel" />
      </div>

    </template>

    <!-- QGIS编辑界面 -->
    <template v-else>
      <QgisEditor />
    </template>

    <!-- 全局悬浮面板/弹窗（主界面与编辑界面共用） -->
    <StylePanel />
    <SettingsModal v-if="appStore.showSettings" />
    <SessionDrawer v-if="appStore.showSessionDrawer" />
    <AttributeTable v-if="appStore.showAttributeTable" />
    <MetadataModal v-if="appStore.showMetadataModal" />
    <ImportModal v-if="appStore.showImportModal" />

    <!-- 全局输入对话框（替代原生 prompt） -->
    <PromptDialog />
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, onMounted } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import LayerPanel from '@/components/LayerPanel.vue'
import LegacyMapPanel from '@/components/LegacyMapPanel.vue'
import Toolbar from '@/components/Toolbar.vue'
import PromptDialog from '@/components/PromptDialog.vue'
import AsyncLoadError from '@/components/AsyncLoadError.vue'

// 非首屏/重组件按需拆包，减小初始加载体积
function lazyLoad(loader: () => Promise<any>) {
  return defineAsyncComponent({
    loader,
    errorComponent: AsyncLoadError,
    timeout: 10000,
  })
}
const KGPanel = lazyLoad(() => import('@/components/KGPanel.vue'))
const StylePanel = lazyLoad(() => import('@/components/StylePanel.vue'))
const SettingsModal = lazyLoad(() => import('@/components/SettingsModal.vue'))
const SessionDrawer = lazyLoad(() => import('@/components/SessionDrawer.vue'))
const QgisEditor = lazyLoad(() => import('@/components/QgisEditor.vue'))
const AttributeTable = lazyLoad(() => import('@/components/AttributeTable.vue'))
const MetadataModal = lazyLoad(() => import('@/components/MetadataModal.vue'))
const ImportModal = lazyLoad(() => import('@/components/ImportModal.vue'))
const MapLegendPanel = lazyLoad(() => import('@/components/MapLegendPanel.vue'))
const MiniLegend = lazyLoad(() => import('@/components/MiniLegend.vue'))
const ParamsPanel = lazyLoad(() => import('@/components/ParamsPanel.vue'))
const AnalysisPanel = lazyLoad(() => import('@/components/AnalysisPanel.vue'))
const MapEditPanel = lazyLoad(() => import('@/components/MapEditPanel.vue'))
const RoutePanel = lazyLoad(() => import('@/components/RoutePanel.vue'))
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'

const appStore = useAppStore()
const chatStore = useChatStore()
const mapStore = useMapStore()

onMounted(async () => {
  await appStore.loadLLMStatus(api)
  await chatStore.loadSessions()
})
</script>

<style>
:root {
  --header-height: 56px;
  --chat-width: 360px;
  --layer-panel-width: 280px;
  --toolbar-width: 50px;
  /* 紫罗兰淡紫色调 - 整体偏浅色，透明度合理下调 */
  --color-primary: #a78bfa;
  --color-primary-dark: #8b5cf6;
  --color-primary-light: #c4b5fd;
  --color-primary-50: #f5f3ff;
  --color-primary-100: #ede9fe;
  --color-primary-200: #ddd6fe;
  --color-primary-300: #c4b5fd;
  --color-accent: #8b5cf6;
  --color-accent-light: #a78bfa;
  --color-bg: #fafafa;
  --color-bg-gradient: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 30%, #fdf4ff 70%, #fff7ed 100%);
  --color-surface: #ffffff;
  --color-surface-hover: #fafafa;
  --color-border: #e5e7eb;
  --color-border-light: #f3f4f6;
  --color-text: #1f2937;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #9ca3af;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --shadow-sm: 0 1px 3px rgba(139, 92, 246, 0.12);
  --shadow-md: 0 4px 12px -2px rgba(139, 92, 246, 0.15);
  --shadow-lg: 0 10px 30px -5px rgba(139, 92, 246, 0.18);
  --shadow-glow: 0 0 20px rgba(139, 92, 246, 0.18);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--color-bg-gradient);
  color: var(--color-text);
  overflow: hidden;
}

.app-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-gradient);
  position: relative;
}

.app-body {
  display: flex;
  flex-direction: row;
  height: calc(100vh - var(--header-height));
  position: relative;
  overflow: hidden;
}

.left-toolbar {
  width: 50px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.map-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}
</style>
