/**
 * 全局应用状态管理 (Pinia)
 * 管理面板显示/隐藏、设置面板、当前LLM提供者/模型等全局状态
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '@/services/api'

export const useAppStore = defineStore('app', () => {
  /** 图层面板是否显示（左侧） */
  const showLayerPanel = ref(true)

  /** AI聊天面板是否显示（右侧） */
  const showChatPanel = ref(true)

  /** 知识图谱面板是否显示 */
  const showKGPanel = ref(false)

  /** 样式编辑面板是否显示 */
  const showStylePanel = ref(false)

  /** 空间分析面板是否显示 */
  const showAnalysisPanel = ref(false)

  const analysisMode = ref<'buffer' | 'overlay' | 'nearest' | 'clip' | 'intersect' | 'union' | null>(null)

  /** 设置面板是否显示 */
  const showSettings = ref(false)

  /** 会话抽屉是否显示 */
  const showSessionDrawer = ref(false)

  /** 路径规划面板是否显示 */
  const showRoutePanel = ref(false)

  const showParamsPanel = ref(false)

  const showMetadataModal = ref(false)

  const showImportModal = ref(false)

  /** 智能制图过程 Trace 面板（研究基线版 §33：Agent 可解释性） */
  const showTracePanel = ref(false)
  const traceData = ref<Record<string, any> | null>(null)

  /** 地图质量验收报告面板（1000 分制） */
  const showQaPanel = ref(false)
  const qaReport = ref<Record<string, any> | null>(null)

  const showEditPanel = ref(false)

  const editDrawTool = ref<'point' | 'line' | 'polygon' | null>(null)

  const showLegendPanel = ref(false)

  const showGraticule = ref(false)

  const markerMode = ref(false)

  /** 载负量等级（简洁/标准/详细，计划 3.3） */
  const loadLevel = ref<'lite' | 'standard' | 'detail'>('standard')

  /** 当前选中的图层ID */
  const selectedLayerId = ref<string | null>(null)

  /** 当前视图模式: 'main' | 'editor' */
  const currentView = ref<'main' | 'editor'>('main')

  /** 属性表面板是否显示 */
  const showAttributeTable = ref(false)

  /** 当前属性表的图层ID */
  const attributeTableLayerId = ref<string | null>(null)

  /** 地图标题（图名） */
  const mapTitle = ref('未命名地图')

  /** 布局导出面板是否显示 */
  const showLayoutExport = ref(false)

  /** 当前工程文件路径 */
  const currentProjectPath = ref<string | null>(null)

  /** 工程是否有未保存修改 */
  const projectDirty = ref(false)

  /** LLM提供者状态 */
  const providerStatus = ref<{
    current_provider?: string
    current_model?: string
    providers?: Array<{ id: string; name: string; models: string[]; configured?: boolean }>
  }>({})

  /** 当前LLM提供者 */
  const currentProvider = ref('deepseek')

  /** 当前LLM模型 */
  const currentModel = ref('deepseek-chat')

  // ========== Actions ==========

  /** 切换图层面板 */
  function toggleLayerPanel() {
    showLayerPanel.value = !showLayerPanel.value
  }

  /** 切换聊天面板 */
  function toggleChatPanel() {
    showChatPanel.value = !showChatPanel.value
    // 互斥：如果聊天面板打开，关闭知识图谱面板
    if (showChatPanel.value) {
      showKGPanel.value = false
    }
  }

  /** 切换知识图谱面板 */
  function toggleKGPanel() {
    showKGPanel.value = !showKGPanel.value
    // 互斥：如果知识图谱面板打开，关闭聊天面板
    if (showKGPanel.value) {
      showChatPanel.value = false
    }
  }

  /** 切换样式面板 */
  function toggleStylePanel() {
    showStylePanel.value = !showStylePanel.value
  }

  /** 切换空间分析面板 */
  function toggleAnalysisPanel() {
    showAnalysisPanel.value = !showAnalysisPanel.value
  }

  function setAnalysisMode(mode: 'buffer' | 'overlay' | 'nearest' | 'clip' | 'intersect' | 'union' | null) {
    analysisMode.value = mode
    if (mode) showAnalysisPanel.value = true
  }

  /** 设置当前选中图层 */
  function setSelectedLayer(layerId: string | null) {
    selectedLayerId.value = layerId
  }

  /** 打开/关闭设置面板 */
  function toggleSettings() {
    showSettings.value = !showSettings.value
  }

  /** 打开/关闭会话抽屉 */
  function toggleSessionDrawer() {
    showSessionDrawer.value = !showSessionDrawer.value
  }

  /** 切换路径规划面板 */
  function toggleRoutePanel() {
    showRoutePanel.value = !showRoutePanel.value
  }

  function toggleParamsPanel() {
    showParamsPanel.value = !showParamsPanel.value
  }

  function toggleMetadataModal() {
    showMetadataModal.value = !showMetadataModal.value
  }

  function toggleImportModal() {
    showImportModal.value = !showImportModal.value
  }

  /** 打开制图过程 Trace 面板 */
  function openTracePanel(data: Record<string, any>) {
    traceData.value = data
    showTracePanel.value = true
  }

  /** 关闭制图过程 Trace 面板 */
  function closeTracePanel() {
    showTracePanel.value = false
    traceData.value = null
  }

  /** 打开质量验收报告面板 */
  function openQaPanel(report: Record<string, any>) {
    qaReport.value = report
    showQaPanel.value = true
  }

  /** 关闭质量验收报告面板 */
  function closeQaPanel() {
    showQaPanel.value = false
    qaReport.value = null
  }

  function toggleEditPanel() {
    showEditPanel.value = !showEditPanel.value
    if (!showEditPanel.value) {
      editDrawTool.value = null
    }
  }

  function setEditDrawTool(tool: 'point' | 'line' | 'polygon' | null) {
    editDrawTool.value = tool
  }

  function toggleLegendPanel() {
    showLegendPanel.value = !showLegendPanel.value
  }

  function toggleGraticule() {
    showGraticule.value = !showGraticule.value
  }

  function toggleMarkerMode() {
    markerMode.value = !markerMode.value
  }

  function setLoadLevel(level: 'lite' | 'standard' | 'detail') {
    loadLevel.value = level
  }

  /** 切换到主界面 */
  function switchToMainView() {
    currentView.value = 'main'
  }

  /** 切换到编辑界面 */
  function switchToEditorView() {
    currentView.value = 'editor'
  }

  /** 切换视图 */
  function toggleView() {
    currentView.value = currentView.value === 'main' ? 'editor' : 'main'
  }

  /** 打开属性表 */
  function openAttributeTable(layerId: string) {
    attributeTableLayerId.value = layerId
    showAttributeTable.value = true
  }

  /** 关闭属性表 */
  function closeAttributeTable() {
    showAttributeTable.value = false
    attributeTableLayerId.value = null
  }

  /** 切换属性表 */
  function toggleAttributeTable() {
    showAttributeTable.value = !showAttributeTable.value
  }

  /** 设置地图标题 */
  function setMapTitle(title: string) {
    mapTitle.value = title
    projectDirty.value = true
  }

  /** 切换布局导出面板 */
  function toggleLayoutExport() {
    showLayoutExport.value = !showLayoutExport.value
  }

  /** 标记工程为已修改 */
  function markProjectDirty() {
    projectDirty.value = true
  }

  /** 清除工程修改标记 */
  function clearProjectDirty() {
    projectDirty.value = false
  }

  /** 保存工程到本地文件（.carto JSON格式，类似QGIS .qgz） */
  function saveProject(mapStore: any) {
    const project = {
      version: '1.0',
      type: 'carto-project',
      title: mapTitle.value,
      savedAt: new Date().toISOString(),
      mapData: mapStore.currentMapData,
      layerGroups: mapStore.layerGroups,
      layerOrder: mapStore.sortedLayers.map((l: any) => l.id),
      viewState: mapStore.currentMapData ? {
        center: mapStore.currentMapData.center,
        zoom: mapStore.currentMapData.zoom,
        theme: mapStore.currentMapData.theme,
      } : null,
      uiState: {
        selectedLayerId: selectedLayerId.value,
        loadLevel: loadLevel.value,
      },
    }
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (mapTitle.value || '未命名地图') + '.carto'
    a.click()
    URL.revokeObjectURL(url)
    projectDirty.value = false
    currentProjectPath.value = a.download
  }

  /** 从本地文件加载工程 */
  function loadProject(file: File, mapStore: any): Promise<boolean> {
    return new Promise((resolve) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const project = JSON.parse(e.target?.result as string)
          if (project.type !== 'carto-project') {
            alert('无效的工程文件格式')
            resolve(false)
            return
          }
          mapTitle.value = project.title || '未命名地图'
          if (project.mapData) {
            mapStore.setMapData(project.mapData)
          }
          if (project.layerGroups) {
            Object.assign(mapStore.layerGroups, project.layerGroups)
          }
          currentProjectPath.value = file.name
          projectDirty.value = false
          resolve(true)
        } catch (err) {
          alert('工程文件解析失败: ' + (err as Error).message)
          resolve(false)
        }
      }
      reader.onerror = () => {
        alert('文件读取失败')
        resolve(false)
      }
      reader.readAsText(file)
    })
  }

  /** 加载LLM状态（兼容旧接口） */
  async function loadLLMStatus(apiService: any) {
    try {
      const result = await apiService.getProviders()
      const data = result.data || result
      if (data) {
        providerStatus.value = data
        if (data.current) {
          currentProvider.value = data.current
        }
        if (data.current_model) {
          currentModel.value = data.current_model
        }
        // 如果没有current，尝试从providers中找active的
        if (!currentProvider.value && data.providers) {
          const active = data.providers.find((p: any) => p.active)
          if (active) {
            currentProvider.value = active.id
            currentModel.value = active.model || active.models?.[0] || ''
          }
        }
      }
    } catch (error) {
      console.error('加载LLM状态失败:', error)
      // 加载失败时，使用默认值，确保显示正常
      if (!currentProvider.value) {
        currentProvider.value = 'deepseek'
        currentModel.value = 'deepseek-chat'
      }
    }
    
    // 最终兜底：如果还是没有，设置默认值
    if (!currentProvider.value) {
      currentProvider.value = 'deepseek'
      currentModel.value = 'deepseek-chat'
    }
  }

  /** 加载当前提供者/模型 */
  async function loadProviders() {
    try {
      const result = await api.getProviders()
      const data = result.data || result
      const providers = data.providers || data.available || []
      if (Array.isArray(providers) && providers.length > 0) {
        const active = providers.find((p: any) => p.active)
        if (active) {
          currentProvider.value = active.id || active.name || ''
          currentModel.value = active.current_model || active.model || active.models?.[0] || ''
        }
      }
    } catch (error) {
      console.error('加载提供者信息失败:', error)
    }
  }

  /** 切换提供者 */
  async function switchProvider(provider: string, model: string) {
    try {
      await api.switchProvider(provider, model)
      currentProvider.value = provider
      currentModel.value = model
    } catch (error) {
      console.error('切换提供者失败:', error)
    }
  }

  return {
    // State
    showLayerPanel,
    showChatPanel,
    showKGPanel,
    showStylePanel,
    showAnalysisPanel,
    analysisMode,
    showSettings,
    showSessionDrawer,
    showRoutePanel,
    showParamsPanel,
    showMetadataModal,
    showImportModal,
    showTracePanel,
    traceData,
    showQaPanel,
    qaReport,
    showEditPanel,
    editDrawTool,
    showLegendPanel,
    showGraticule,
    markerMode,
    loadLevel,
    selectedLayerId,
    currentProvider,
    currentModel,
    providerStatus,
    currentView,
    showAttributeTable,
    attributeTableLayerId,
    mapTitle,
    showLayoutExport,
    currentProjectPath,
    projectDirty,
    // Actions
    toggleLayerPanel,
    toggleChatPanel,
    toggleKGPanel,
    toggleStylePanel,
    toggleAnalysisPanel,
    setAnalysisMode,
    toggleSettings,
    toggleSessionDrawer,
    toggleRoutePanel,
    toggleParamsPanel,
    toggleMetadataModal,
    toggleImportModal,
    openTracePanel,
    closeTracePanel,
    openQaPanel,
    closeQaPanel,
    toggleEditPanel,
    setEditDrawTool,
    toggleLegendPanel,
    toggleGraticule,
    toggleMarkerMode,
    setLoadLevel,
    setSelectedLayer,
    switchToMainView,
    switchToEditorView,
    toggleView,
    openAttributeTable,
    closeAttributeTable,
    toggleAttributeTable,
    setMapTitle,
    toggleLayoutExport,
    markProjectDirty,
    clearProjectDirty,
    saveProject,
    loadProject,
    loadLLMStatus,
    loadProviders,
    switchProvider,
  }
})
