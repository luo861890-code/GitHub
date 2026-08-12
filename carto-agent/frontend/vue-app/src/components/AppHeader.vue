<template>
  <header class="app-header">
    <div class="header-left">
      <div class="header-logo">
        <i class="fa-solid fa-map-location-dot"></i>
      </div>
      <span class="header-title">地图制图智能体</span>
      <span class="header-subtitle">CartoAgent</span>
    </div>

    <div class="header-center">
      <div class="llm-status">
        <span
          class="status-dot"
          :class="{
            loading: appStore.providerStatus === 'connecting',
            online: appStore.providerStatus === 'online',
            offline: appStore.providerStatus === 'offline',
          }"
        ></span>
        <span class="status-text">
          {{ statusText }}
        </span>
      </div>
    </div>

    <div class="header-right">
      <button class="header-icon-btn" title="新会话" @click="handleNewSession">
        <i class="fa-solid fa-plus"></i>
      </button>
      <button class="header-icon-btn" title="历史记录" @click="appStore.toggleSessionDrawer()">
        <i class="fa-solid fa-clock-rotate-left"></i>
      </button>
      <button class="header-icon-btn" title="设置" @click="appStore.toggleSettings()">
        <i class="fa-solid fa-gear"></i>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'

const appStore = useAppStore()
const chatStore = useChatStore()

const statusText = computed(() => {
  const displayNames: Record<string, string> = {
    deepseek: 'DeepSeek',
    qwen: '通义千问',
    openai: 'OpenAI',
    zhipu: '智谱GLM',
    ollama: 'Ollama',
  }
  if (appStore.providerStatus === 'connecting') return '连接中...'
  if (appStore.providerStatus === 'offline') return '离线'
  const name = displayNames[appStore.currentProvider] || appStore.currentProvider
  let text = name
  if (appStore.currentModel) text += ` / ${appStore.currentModel}`
  return text
})

async function handleNewSession() {
  await chatStore.createNewSession()
}
</script>

<style scoped>
.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%);
  color: #fff;
  position: relative;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  backdrop-filter: blur(4px);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.header-subtitle {
  font-size: 11px;
  opacity: 0.7;
  font-weight: 400;
  letter-spacing: 1px;
  padding: 2px 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}

.header-center {
  display: flex;
  align-items: center;
}

.llm-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 20px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}
.status-dot.loading {
  background: #fbbf24;
  animation: pulse 1.5s infinite;
}
.status-dot.online {
  background: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}
.status-dot.offline {
  background: #ef4444;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.status-text {
  font-size: 12px;
  opacity: 0.9;
}

.header-right {
  display: flex;
  gap: 4px;
}

.header-icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}
.header-icon-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: translateY(-1px);
}
</style>
