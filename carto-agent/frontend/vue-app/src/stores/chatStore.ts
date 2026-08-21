/**
 * 聊天状态管理 (Pinia)
 * 管理会话列表、当前会话、消息列表、流式聊天状态
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Session, Message, MapData, Step, GeoTokenInfo, RagSource, KnowledgeSources } from '@/types'
import type { GraphragChainHop } from '@/types'
import api from '@/services/api'
import { useMapStore } from './mapStore'
import { useAppStore } from './appStore'

export const useChatStore = defineStore('chat', () => {
  /** 会话列表 */
  const sessions = ref<Session[]>([])

  /** 当前会话ID */
  const currentSessionId = ref<string | null>(null)

  /** 当前会话的消息列表 */
  const messages = ref<Message[]>([])

  /** 是否正在发送消息 */
  const isSending = ref(false)

  /** 流式输出缓冲区（主文本） */
  const streamingText = ref('')

  /** 流式输出缓冲区（思考过程） */
  const streamingThinking = ref('')

  /** 流式返回的地图数据 */
  const streamingMap = ref<MapData | null>(null)

  /** 流式返回的执行步骤 */
  const streamingSteps = ref<Step[]>([])

  const streamingGeotoken = ref<GeoTokenInfo | null>(null)

  const streamingKnowledgeSources = ref<KnowledgeSources | null>(null)

  const streamingRag = ref<RagSource[]>([])

  const streamingGraphrag = ref<{ entities?: string[] } | null>(null)
  const streamingGraphragChain = ref<GraphragChainHop[]>([])

  /** 流式消息的模型/提供者信息 */
  const streamingInfo = ref<{ provider?: string; model?: string } | null>(null)

  /** 当前流式请求的取消控制器 */
  const streamAbort = ref<AbortController | null>(null)

  // ========== Getters ==========

  /** 当前会话对象 */
  const currentSession = computed<Session | undefined>(() =>
    sessions.value.find((s) => s.session_id === currentSessionId.value),
  )

  // ========== Actions ==========

  /** 加载会话列表 */
  async function loadSessions() {
    try {
      const result = await api.listSessions()
      sessions.value = result.data || result
      // 自动恢复最近会话（当前未选择任何会话时），回溯消息与地图状态
      if (!currentSessionId.value && sessions.value.length > 0) {
        await switchSession(sessions.value[0].session_id)
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }

  /** 创建新会话，返回会话ID（同时清空地图区域） */
  async function createSession(title?: string): Promise<string> {
    const result = await api.createSession(title || '新会话')
    const session = result.data || result
    sessions.value.unshift(session)
    currentSessionId.value = session.session_id
    messages.value = []
    // 新对话：清空地图区域
    clearMapState()
    return session.session_id
  }

  /** 清空地图状态（新对话时调用） */
  function clearMapState() {
    const mapStore = useMapStore()
    const appStore = useAppStore()
    mapStore.setMapData(null as any)
    mapStore.layerGroups = {}
    appStore.setSelectedLayer(null)
    appStore.setMapTitle('未命名地图')
    // 派发事件通知MapCanvas清空
    const el = document.getElementById('map-container')
    if (el) el.dispatchEvent(new CustomEvent('map-clear-all'))
  }

  /** 从消息列表中恢复地图状态（切换历史对话时调用） */
  function restoreMapFromMessages(msgs: Message[]) {
    const mapStore = useMapStore()
    const appStore = useAppStore()
    // 找到最后一条包含地图的消息（优先内嵌 map_data，其次 map_id 引用）
    for (let i = msgs.length - 1; i >= 0; i--) {
      const msg = msgs[i]
      if (msg.map_data) {
        mapStore.setMapData(msg.map_data)
        if (msg.map_data.name) appStore.setMapTitle(msg.map_data.name)
        return
      }
      if (msg.map_id) {
        // 历史消息仅存轻量 map_id 引用（session 持久化不内嵌完整地图）：
        // 异步拉取完整地图数据恢复，避免刷新后出现“未加载地图”
        api
          .getMap(msg.map_id)
          .then((res: any) => {
            const data = res?.data || res
            if (data && data.map_id) {
              mapStore.setMapData(data)
              if (data.name) appStore.setMapTitle(data.name)
            }
          })
          .catch((err: any) => console.error('恢复地图失败:', err))
        return
      }
    }
    // 没有地图数据，清空
    clearMapState()
  }

  /** 切换到指定会话（同时回溯地图状态） */
  async function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
    messages.value = []
    try {
      const result = await api.getMessages(sessionId)
      const list = result.data || result
      const arr = Array.isArray(list) ? list : (list?.messages || list?.items || [])
      messages.value = arr
      // 回溯地图状态到该对话最后一次生成的地图
      restoreMapFromMessages(arr)
    } catch (error) {
      console.error('加载会话消息失败:', error)
    }
  }

  /** 添加消息到当前会话 */
  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  /** 清空流式状态 */
  function clearStreamingState() {
    streamingText.value = ''
    streamingThinking.value = ''
    streamingMap.value = null
    streamingSteps.value = []
    streamingGeotoken.value = null
    streamingKnowledgeSources.value = null
    streamingRag.value = []
    streamingGraphrag.value = null
    streamingGraphragChain.value = []
    streamingInfo.value = null
  }

  /** 发送消息（流式） */
  async function sendMessage(text: string) {
    if (!currentSessionId.value) {
      await createSession()
    }

    const sessionId = currentSessionId.value!
    isSending.value = true
    clearStreamingState()
    const controller = new AbortController()
    streamAbort.value = controller

    // 添加用户消息到列表
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    try {
      await api.streamMessage(sessionId, text, {
        onThinking: (content: string) => {
          streamingThinking.value += content
        },
        onChunk: (content: string) => {
          streamingText.value += content
        },
        onMap: (data: MapData) => {
          streamingMap.value = data
        },
        onSteps: (steps: Step[]) => {
          streamingSteps.value = steps
        },
        onRag: (sources: RagSource[]) => {
          streamingRag.value = sources
        },
        onGraphrag: (data: { entities?: string[] }) => {
          streamingGraphrag.value = data
        },
        onGraphragChain: (chain: GraphragChainHop[]) => {
          streamingGraphragChain.value = chain
        },
        onGeotoken: (info: GeoTokenInfo) => {
          streamingGeotoken.value = info
        },
        onKnowledgeSources: (sources: KnowledgeSources) => {
          streamingKnowledgeSources.value = sources
        },
        onDone: (info: { provider?: string; model?: string }) => {
          streamingInfo.value = info
          // 流式完成后构造 assistant 消息并加入列表
          if (streamingText.value) {
            const assistantMsg: Message = {
              id: `assistant-${Date.now()}`,
              session_id: sessionId,
              role: 'assistant',
              content: streamingText.value,
              thinking: streamingThinking.value || undefined,
              map_data: streamingMap.value,
              steps: streamingSteps.value,
              geotoken_info: streamingGeotoken.value,
              knowledge_sources: streamingKnowledgeSources.value || undefined,
              rag_sources: streamingRag.value,
              graphrag_entities: streamingGraphrag.value?.entities,
              graphrag_chain: streamingGraphragChain.value,
              provider: info.provider,
              model: info.model,
              created_at: new Date().toISOString(),
            }
            messages.value.push(assistantMsg)
          }
        },
        onError: (error: string) => {
          console.error('流式消息错误:', error)
        },
      }, controller.signal)
    } catch (error) {
      console.error('发送消息失败:', error)
      const aborted = (error as any)?.name === 'AbortError'
      const partial = streamingText.value
      // 添加错误/中断消息（保留已生成的部分内容）
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        session_id: sessionId,
        role: 'assistant',
        content: partial
          ? `${partial}\n\n[${aborted ? '已停止生成' : '输出中断：连接异常'}]`
          : `抱歉，请求失败: ${error instanceof Error ? error.message : '未知错误'}`,
        created_at: new Date().toISOString(),
      }
      messages.value.push(errorMsg)
    } finally {
      streamAbort.value = null
      isSending.value = false
    }
  }

  /** 取消当前流式生成 */
  function cancelStream() {
    streamAbort.value?.abort()
  }

  /** 删除会话 */
  async function deleteCurrentSession(sessionId: string) {
    try {
      await api.deleteSession(sessionId)
      sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = sessions.value[0]?.session_id || null
        messages.value = []
        if (currentSessionId.value) {
          await switchSession(currentSessionId.value)
        }
      }
    } catch (error) {
      console.error('删除会话失败:', error)
    }
  }

  /** 重命名会话 */
  async function renameSession(sessionId: string, title: string) {
    try {
      const result = await api.renameSession(sessionId, title)
      const data = result.data || result
      if (data && data.title) {
        const target = sessions.value.find((s) => s.session_id === sessionId)
        if (target) target.title = data.title
      }
    } catch (error) {
      console.error('重命名会话失败:', error)
    }
  }

  return {
    // State
    sessions,
    currentSessionId,
    messages,
    isSending,
    streamingText,
    streamingThinking,
    streamingMap,
    streamingSteps,
    streamingGeotoken,
    streamingKnowledgeSources,
    streamingRag,
    streamingGraphrag,
    streamingGraphragChain,
    streamingInfo,
    streamAbort,
    // Getters
    currentSession,
    // Actions
    loadSessions,
    createSession,
    switchSession,
    addMessage,
    clearStreamingState,
    sendMessage,
    cancelStream,
    renameSession,
    deleteCurrentSession,
    clearMapState,
    restoreMapFromMessages,
  }
})
