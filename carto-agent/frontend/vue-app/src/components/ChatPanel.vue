<template>
  <aside class="chat-panel">
    <!-- 快捷指令区 -->
    <div class="quick-commands" :class="{ collapsed: quickCommandsCollapsed }">
      <div class="quick-commands-header" @click="quickCommandsCollapsed = !quickCommandsCollapsed">
        <span><i class="fa-solid fa-bolt"></i> 快捷指令</span>
        <i class="fa-solid" :class="quickCommandsCollapsed ? 'fa-chevron-down' : 'fa-chevron-up'"></i>
      </div>
      <div v-if="!quickCommandsCollapsed" class="quick-commands-list">
        <button
          v-for="cmd in quickCommands"
          :key="cmd.label"
          class="quick-command-btn"
          @click="handleQuickCommand(cmd)"
        >
          <i class="fa-solid" :class="cmd.icon"></i>
          <span>{{ cmd.label }}</span>
        </button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div ref="messageListRef" class="chat-messages">
      <div v-if="chatStore.messages.length === 0" class="chat-welcome">
        <div class="chat-welcome-icon">
          <i class="fa-solid fa-map-location-dot"></i>
        </div>
        <h2 class="chat-welcome-title">欢迎使用地图制图智能体</h2>
        <p class="chat-welcome-hint">描述你想要的地图效果，我来帮你生成</p>
      </div>

      <div
        v-for="(msg, idx) in chatStore.messages"
        :key="idx"
        class="message"
        :class="`message-${msg.role}`"
      >
        <div class="message-avatar">
          <i class="fa-solid" :class="msg.role === 'user' ? 'fa-user' : 'fa-robot'"></i>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <span class="message-role">{{ msg.role === 'user' ? '我' : '智能体' }}</span>
            <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
          </div>

          <!-- 思考面板 -->
          <div v-if="msg.thinking" class="thinking-panel" :class="{ expanded: expandedThinking[idx] }">
            <div class="thinking-header" @click="toggleThinking(idx)">
              <i class="fa-solid fa-brain"></i>
              <span>思考过程</span>
              <i class="fa-solid thinking-arrow" :class="expandedThinking[idx] ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
            </div>
            <div v-if="expandedThinking[idx]" class="thinking-body">{{ msg.thinking }}</div>
          </div>

          <!-- 步骤面板 -->
          <div v-if="msg.steps && msg.steps.length" class="steps-panel">
            <div
              v-for="(step, si) in msg.steps"
              :key="si"
              class="step-item"
              :class="`step-${step.status || 'pending'}`"
            >
              <i class="fa-solid" :class="stepIcons[step.status] || 'fa-clock'"></i>
              <div class="step-info">
                <span class="step-name">{{ step.name || step.step_id }}</span>
                <span class="step-desc">{{ step.description || '' }}</span>
              </div>
            </div>
          </div>

          <!-- 文本内容（Markdown渲染） -->
          <div class="message-text" v-html="renderMarkdown(msg.content)"></div>

          <!-- 地图链接 -->
          <div
            v-if="msg.map_data"
            class="message-map-link"
            @click="handleMapClick(msg.map_data!)"
          >
            <i class="fa-solid fa-map"></i>
            <span>查看地图: {{ msg.map_data.name || '地图' }}</span>
            <i class="fa-solid fa-arrow-right"></i>
          </div>

          <!-- 知识来源卡片 -->
          <div
            v-if="msg.knowledge_sources && (msg.knowledge_sources.rag?.length || msg.knowledge_sources.graphrag?.entities?.length)"
            class="knowledge-sources-card"
          >
            <div class="ks-header"><i class="fa-solid fa-book-open"></i> <span>知识来源</span></div>
            <div v-if="msg.knowledge_sources.rag?.length" class="ks-section">
              <div class="ks-section-title">RAG检索</div>
              <div v-for="(item, ri) in msg.knowledge_sources.rag" :key="ri" class="ks-item ks-rag">
                <span class="ks-badge">RAG</span>
                <span class="ks-title">{{ item.title }}</span>
                <span v-if="item.score" class="ks-score">{{ (item.score * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div v-if="msg.knowledge_sources.graphrag?.entities?.length" class="ks-section">
              <div class="ks-section-title">GraphRAG实体</div>
              <span v-for="(e, ei) in msg.knowledge_sources.graphrag.entities" :key="ei" class="ks-tag ks-graphrag">{{ e }}</span>
            </div>
          </div>

          <!-- 模型信息 -->
          <div v-if="msg.provider" class="message-footer">
            <span class="message-model">
              <i class="fa-solid fa-microchip"></i>
              {{ msg.provider }}{{ msg.model ? ' / ' + msg.model : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 流式打字指示器 -->
      <div v-if="chatStore.isStreaming" class="message message-assistant">
        <div class="message-avatar">
          <i class="fa-solid fa-robot"></i>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <span class="message-role">智能体</span>
          </div>
          <div class="streaming-content">
            <div v-if="chatStore.streamingThinking" class="thinking-panel expanded">
              <div class="thinking-header">
                <i class="fa-solid fa-brain"></i>
                <span>思考过程</span>
              </div>
              <div class="thinking-body">{{ chatStore.streamingThinking }}</div>
            </div>
            <div v-if="chatStore.streamingContent" class="message-text" v-html="renderMarkdown(chatStore.streamingContent) + '<span class=&quot;streaming-cursor&quot;></span>'"></div>
            <div v-if="!chatStore.streamingContent && !chatStore.streamingThinking" class="typing-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="chat-input-area">
      <div class="chat-input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="描述你想要的地图效果，我来帮你生成"
          rows="1"
          :maxlength="maxMsgLen"
          @keydown="handleKeydown"
          @input="autoResize"
        ></textarea>
        <button
          class="chat-send-btn"
          :disabled="chatStore.isSending"
          @click="sendMessage"
          title="发送 (Enter)"
        >
          <div v-if="chatStore.isSending" class="btn-spinner"></div>
          <i v-else class="fa-solid fa-paper-plane"></i>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted, reactive } from 'vue'
import { useMapStore } from '@/stores/mapStore'
import { useChatStore } from '@/stores/chatStore'
import { CONFIG } from '@/config'
import type { MapData } from '@/types'

const chatStore = useChatStore()
const mapStore = useMapStore()

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const messageListRef = ref<HTMLDivElement | null>(null)
const quickCommandsCollapsed = ref(false)
const maxMsgLen = CONFIG.maxMessageLength
const expandedThinking = reactive<Record<number, boolean>>({})

const quickCommands = CONFIG.quickCommands

const stepIcons: Record<string, string> = {
  pending: 'fa-clock',
  running: 'fa-spinner fa-spin',
  success: 'fa-circle-check',
  failed: 'fa-circle-xmark',
}

function toggleThinking(idx: number) {
  expandedThinking[idx] = !expandedThinking[idx]
}

function formatTime(timestamp: number): string {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function escapeHtml(text: string): string {
  if (text === null || text === undefined) return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = escapeHtml(text)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`(.+?)`/g, '<code>$1</code>')
  html = html.replace(/```([\s\S]+?)```/g, '<pre><code>$1</code></pre>')
  html = html.replace(/\n/g, '<br>')
  return html
}

function autoResize() {
  const textarea = inputRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || chatStore.isSending) return
  if (text.length > maxMsgLen) return

  inputText.value = ''
  autoResize()
  await chatStore.sendMessage(text)
  scrollToBottom()
}

function handleQuickCommand(cmd: { message: string }) {
  inputText.value = cmd.message
  autoResize()
  sendMessage()
}

function handleMapClick(mapData: MapData) {
  mapStore.setMapData(mapData)
}

function scrollToBottom() {
  nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

watch(() => chatStore.streamingContent.value, () => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-panel {
  width: var(--chat-width);
  min-width: var(--chat-width);
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  position: relative;
  z-index: 10;
}

/* 快捷指令 */
.quick-commands {
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #7c3aed08 0%, #6d28d908 100%);
}
.quick-commands-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
}
.quick-commands-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 10px;
}
.quick-command-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  background: rgba(124, 58, 237, 0.06);
  border: 1px solid rgba(124, 58, 237, 0.15);
  border-radius: 16px;
  font-size: 12px;
  color: var(--color-primary);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.quick-command-btn:hover {
  background: rgba(124, 58, 237, 0.12);
  border-color: var(--color-primary-light);
}

/* 消息列表 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-welcome {
  text-align: center;
  padding: 40px 20px;
}
.chat-welcome-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7c3aed, #a78bfa);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 28px;
}
.chat-welcome-title {
  font-size: 18px;
  color: var(--color-text);
  margin-bottom: 8px;
}
.chat-welcome-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* 消息气泡 */
.message {
  display: flex;
  gap: 10px;
  max-width: 100%;
}
.message-user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.message-assistant .message-avatar {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #4f46e5;
}
.message-user .message-avatar {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.message-body {
  max-width: calc(100% - 42px);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-user .message-body {
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.message-role {
  font-weight: 600;
}

.message-text {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.message-assistant .message-text {
  background: #f1f5f9;
  color: var(--color-text);
  border-top-left-radius: 2px;
}
.message-user .message-text {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-top-right-radius: 2px;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  margin: 4px 0;
}

/* 思考面板 */
.thinking-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: #f8fafc;
  user-select: none;
}
.thinking-body {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  background: #fafafa;
  max-height: 200px;
  overflow-y: auto;
}

/* 步骤面板 */
.steps-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: #f8fafc;
  border-left: 3px solid var(--color-border);
}
.step-success {
  border-left-color: var(--color-success);
}
.step-running {
  border-left-color: var(--color-warning);
}
.step-failed {
  border-left-color: var(--color-error);
}
.step-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.step-name {
  font-weight: 600;
  color: var(--color-text);
}
.step-desc {
  color: var(--color-text-secondary);
  font-size: 11px;
}

/* 地图链接 */
.message-map-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: #2563eb;
  cursor: pointer;
  transition: all 0.2s;
}
.message-map-link:hover {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
}

/* 知识来源卡片 */
.knowledge-sources-card {
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: 12px;
}
.ks-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}
.ks-section {
  margin-top: 6px;
}
.ks-section-title {
  color: var(--color-text-secondary);
  font-size: 11px;
  margin-bottom: 4px;
}
.ks-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
}
.ks-badge {
  background: #dbeafe;
  color: #2563eb;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.ks-title {
  color: var(--color-text);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ks-score {
  color: var(--color-text-secondary);
  font-size: 11px;
}
.ks-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 10px;
  font-size: 11px;
  margin: 2px 4px 2px 0;
}

/* 模型信息 */
.message-footer {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.message-model {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: #f1f5f9;
  border-radius: var(--radius-md);
  border-top-left-radius: 2px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary-light);
  animation: bounce 1.4s infinite ease-in-out both;
}
.dot:nth-child(1) {
  animation-delay: -0.32s;
}
.dot:nth-child(2) {
  animation-delay: -0.16s;
}
@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
  }
  40% {
    transform: scale(1);
  }
}

/* 流式光标 */
:deep(.streaming-cursor) {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s infinite;
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

/* 输入区 */
.chat-input-area {
  padding: 10px 12px;
  border-top: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
}
.chat-input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  transition: border-color 0.2s;
}
.chat-input-wrapper:focus-within {
  border-color: var(--color-primary-light);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}
.chat-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  max-height: 120px;
  font-family: inherit;
  color: var(--color-text);
}
.chat-input::placeholder {
  color: var(--color-text-secondary);
}
.chat-send-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
}
.chat-send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
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
</style>
