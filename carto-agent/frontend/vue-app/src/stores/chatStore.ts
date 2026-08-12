/**
 * 聊天状态管理 (Pinia)
 * 管理会话列表、当前会话、消息列表、流式聊天状态
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Session, ChatMessage, MapData, AgentStep } from '@/types'
import * as api from '@/services/api'

export const useChatStore = defineStore('chat', () => {
  /** 会话列表 */
  const sessions = ref<Session[]>([])

  /** 当前会话ID */
  const currentSessionId = ref<string | null>(null)

  /** 当前会话的消息列表 */
  const messages = ref<ChatMessage[]>([])

  /** 是否正在发送消息 */
  const isSending = ref(false)

  /** 流式输出缓冲区（主文本） */
  const streamingText = ref('')

  /** 流式输出缓冲区（思考过程） */
  const streamingThinking = ref('')

  /** 流式返回的地图数据 */
  const streamingMap = ref<MapData | null>(null)

  /** 流式返回的执行步骤 */
  const streamingSteps = ref<AgentStep[]>([])

  /** 流式消息的模型/提供者信息 */
  const streamingInfo = ref<{ provider: string; model: string } | null>(null)

  // ========== Getters ==========

  /** 当前会话对象 */
  const currentSession = computed<Session | undefined>(() =>
    sessions.value.find((s) => s.session_id === currentSessionId.value),
  )

  // ========== Actions ==========

  /** 加载会话列表 */
  async function loadSessions() {
    try {
      sessions.value = await api.listSessions()
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }

  /** 创建新会话，返回会话ID */
  async function createSession(title?: string): Promise<string> {
    const session = await api.createSession(title || '新会话')
    sessions.value.unshift(session)
    currentSessionId.value = session.session_id
    messages.value = []
    return session.session_id
  }

  /** 切换到指定会话 */
  async function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
    messages.value = []
    try {
      const msgs = await api.getMessages(sessionId)
      messages.value = msgs
    } catch (error) {
      console.error('加载会话消息失败:', error)
    }
  }

  /** 添加消息到当前会话 */
  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 清空流式状态 */
  function clearStreamingState() {
    streamingText.value = ''
    streamingThinking.value = ''
    streamingMap.value = null
    streamingSteps.value = []
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

    // 添加用户消息到列表
    const userMsg: ChatMessage = {
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
        onSteps: (steps: AgentStep[]) => {
          streamingSteps.value = steps
        },
        onDone: (info: { provider: string; model: string }) => {
          streamingInfo.value = info
          // 流式完成后构造 assistant 消息并加入列表
          if (streamingText.value) {
            const assistantMsg: ChatMessage = {
              id: `assistant-${Date.now()}`,
              session_id: sessionId,
              role: 'assistant',
              content: streamingText.value,
              thinking: streamingThinking.value || undefined,
              map_data: streamingMap.value,
              steps: streamingSteps.value,
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
      })
    } catch (error) {
      console.error('发送消息失败:', error)
      // 添加错误消息
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        session_id: sessionId,
        role: 'assistant',
        content: `抱歉，请求失败: ${error instanceof Error ? error.message : '未知错误'}`,
        created_at: new Date().toISOString(),
      }
      messages.value.push(errorMsg)
    } finally {
      isSending.value = false
    }
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
    streamingInfo,
    // Getters
    currentSession,
    // Actions
    loadSessions,
    createSession,
    switchSession,
    addMessage,
    clearStreamingState,
    sendMessage,
    deleteCurrentSession,
  }
})
