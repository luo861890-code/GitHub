<template>
  <div class="app-root">
    <AppHeader />
    <div class="app-body">
      <ChatPanel v-show="appStore.showChatPanel" />
      <MapCanvas />
      <KGPanel v-show="appStore.showKGPanel" />
      <Toolbar />
    </div>
    <SettingsModal v-if="appStore.showSettings" />
    <SessionDrawer v-if="appStore.showSessionDrawer" />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import KGPanel from '@/components/KGPanel.vue'
import Toolbar from '@/components/Toolbar.vue'
import SettingsModal from '@/components/SettingsModal.vue'
import SessionDrawer from '@/components/SessionDrawer.vue'
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'
import { api } from '@/services/api'

const appStore = useAppStore()
const chatStore = useChatStore()

onMounted(async () => {
  await appStore.loadLLMStatus(api)
  await chatStore.loadSessions()
})
</script>

<style>
:root {
  --header-height: 56px;
  --chat-width: 380px;
  --toolbar-width: 56px;
  --color-primary: #7c3aed;
  --color-primary-dark: #6d28d9;
  --color-primary-light: #a78bfa;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-border: #e2e8f0;
  --color-text: #1e293b;
  --color-text-secondary: #64748b;
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  overflow: hidden;
}

.app-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-body {
  display: flex;
  flex-direction: row;
  height: calc(100vh - var(--header-height));
  position: relative;
  overflow: hidden;
}
</style>
