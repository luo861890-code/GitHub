/**
 * 全局应用状态管理 (Pinia)
 * 管理面板显示/隐藏、设置面板、当前LLM提供者/模型等全局状态
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/services/api'

export const useAppStore = defineStore('app', () => {
  /** 聊天面板是否显示 */
  const showChatPanel = ref(true)

  /** 知识图谱面板是否显示 */
  const showKGPanel = ref(false)

  /** 设置面板是否显示 */
  const showSettings = ref(false)

  /** 会话抽屉是否显示 */
  const showSessionDrawer = ref(false)

  /** 当前LLM提供者 */
  const currentProvider = ref('')

  /** 当前LLM模型 */
  const currentModel = ref('')

  // ========== Actions ==========

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

  /** 打开/关闭设置面板 */
  function toggleSettings() {
    showSettings.value = !showSettings.value
  }

  /** 打开/关闭会话抽屉 */
  function toggleSessionDrawer() {
    showSessionDrawer.value = !showSessionDrawer.value
  }

  /** 加载当前提供者/模型 */
  async function loadProviders() {
    try {
      const providers = await api.getProviders()
      if (providers && providers.length > 0) {
        const active = providers.find((p: any) => p.active)
        if (active) {
          currentProvider.value = active.name || ''
          currentModel.value = active.current_model || active.models?.[0]?.name || ''
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
    showChatPanel,
    showKGPanel,
    showSettings,
    showSessionDrawer,
    currentProvider,
    currentModel,
    // Actions
    toggleChatPanel,
    toggleKGPanel,
    toggleSettings,
    toggleSessionDrawer,
    loadProviders,
    switchProvider,
  }
})
