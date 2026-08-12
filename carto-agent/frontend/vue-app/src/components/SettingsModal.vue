<template>
  <Teleport to="body">
    <div class="modal-overlay" @click="handleClose"></div>
    <div class="modal-dialog">
      <div class="modal-header">
        <span class="modal-title">
          <i class="fa-solid fa-gear"></i> 系统设置
        </span>
        <button class="modal-close-btn" @click="handleClose">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="modal-body">
        <!-- LLM设置 -->
        <div class="settings-section">
          <div class="settings-section-title">大语言模型</div>
          <div class="settings-field">
            <label>LLM提供者</label>
            <select v-model="selectedProvider" class="settings-select" @change="onProviderChange">
              <option v-for="p in providersList" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="settings-field">
            <label>模型</label>
            <select v-model="selectedModel" class="settings-select">
              <option v-for="m in currentModels" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
        </div>

        <!-- API Key管理 -->
        <div class="settings-section">
          <div class="settings-section-title">
            <i class="fa-solid fa-key"></i> API 密钥管理
          </div>
          <div v-for="keyProvider in keyProviders" :key="keyProvider" class="settings-field">
            <label>
              {{ providerNames[keyProvider] }}
              <span class="api-key-status" :class="apiKeyStatus[keyProvider] ? 'configured' : 'not-configured'">
                <i :class="apiKeyStatus[keyProvider] ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'"></i>
                {{ apiKeyStatus[keyProvider] ? '已配置' : '未配置' }}
              </span>
            </label>
            <div class="api-key-input-wrapper">
              <input
                :ref="(el: any) => { apiKeyInputs[keyProvider] = el }"
                type="password"
                class="api-key-input"
                :placeholder="`输入 ${providerNames[keyProvider]} API Key...`"
              />
              <button class="api-key-save-btn" @click="saveApiKey(keyProvider)">
                <i class="fa-solid fa-floppy-disk"></i> 保存
              </button>
            </div>
          </div>
        </div>

        <!-- 底图主题 -->
        <div class="settings-section">
          <div class="settings-section-title">地图底图主题</div>
          <div class="settings-themes">
            <button
              v-for="(theme, key) in CONFIG.mapThemes"
              :key="key"
              class="theme-option-btn"
              :class="{ active: key === appStore.currentTheme || key === mapStore.currentTheme }"
              @click="handleThemeChange(key as string)"
            >{{ theme.name }}</button>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="handleClose">取消</button>
        <button class="btn btn-primary" @click="handleSave">
          <i class="fa-solid fa-check"></i> 保存
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { api } from '@/services/api'
import { CONFIG } from '@/config'
import type { LLMProvider } from '@/types'

const appStore = useAppStore()
const mapStore = useMapStore()

const selectedProvider = ref('')
const selectedModel = ref('')
const providersList = ref<LLMProvider[]>([])
const apiKeyStatus = ref<Record<string, boolean>>({})
const apiKeyInputs = ref<Record<string, HTMLInputElement | null>>({})

const keyProviders = ['deepseek', 'qwen', 'openai', 'zhipu']
const providerNames: Record<string, string> = {
  deepseek: 'DeepSeek',
  qwen: '通义千问',
  openai: 'OpenAI',
  zhipu: '智谱GLM',
}

const currentModels = computed(() => {
  const provider = providersList.value.find((p) => p.id === selectedProvider.value)
  return provider?.models || []
})

async function loadSettingsData() {
  try {
    const data = await api.getProviders()
    const providers = data.data || data
    const list = (providers.providers || providers.available || [
      { id: 'ollama', name: 'Ollama（本地）', models: ['qwen3:8b'] },
      { id: 'qwen', name: '通义千问', models: ['qwen-plus', 'qwen-turbo'] },
      { id: 'openai', name: 'OpenAI', models: ['gpt-4o-mini', 'gpt-4o'] },
      { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat'] },
      { id: 'zhipu', name: '智谱GLM', models: ['glm-4'] },
    ]) as LLMProvider[]
    providersList.value = list
    if (!selectedProvider.value && list.length > 0) {
      selectedProvider.value = list[0].id
    }
    // 更新API Key状态
    list.forEach((p) => {
      apiKeyStatus.value[p.id] = p.configured || false
    })
  } catch (e) {
    console.error('加载设置失败:', e)
  }
}

function onProviderChange() {
  const provider = providersList.value.find((p) => p.id === selectedProvider.value)
  if (provider?.models?.length) {
    selectedModel.value = provider.models[0]
  }
}

function handleThemeChange(key: string) {
  mapStore.setTheme(key)
}

async function saveApiKey(provider: string) {
  const input = apiKeyInputs.value[provider]
  if (!input || !input.value.trim()) {
    alert('请输入API Key')
    return
  }
  try {
    await api.updateApiKey(provider, input.value.trim())
    apiKeyStatus.value[provider] = true
    input.value = ''
    alert('API Key 已保存')
  } catch (e: any) {
    alert('保存失败: ' + e.message)
  }
}

async function handleSave() {
  try {
    await api.switchProvider(selectedProvider.value, selectedModel.value)
    appStore.currentProvider = selectedProvider.value
    appStore.currentModel = selectedModel.value
    appStore.showSettings = false
  } catch (e: any) {
    alert('保存设置失败: ' + e.message)
  }
}

function handleClose() {
  appStore.showSettings = false
}

onMounted(() => {
  selectedProvider.value = appStore.currentProvider
  selectedModel.value = appStore.currentModel
  loadSettingsData()
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.modal-dialog {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 520px;
  max-height: 85vh;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 1001;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-primary);
}
.modal-close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--color-text-secondary);
  transition: all 0.2s;
}
.modal-close-btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--color-border);
}

.settings-section {
  margin-bottom: 20px;
}
.settings-section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--color-text);
}
.settings-field {
  margin-bottom: 12px;
}
.settings-field label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.settings-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  outline: none;
}
.settings-select:focus {
  border-color: var(--color-primary-light);
}

.api-key-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}
.api-key-status.configured {
  background: #dcfce7;
  color: #15803d;
}
.api-key-status.not-configured {
  background: #fee2e2;
  color: #b91c1c;
}
.api-key-input-wrapper {
  display: flex;
  gap: 6px;
}
.api-key-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
}
.api-key-input:focus {
  border-color: var(--color-primary-light);
}
.api-key-save-btn {
  padding: 8px 14px;
  border: none;
  background: var(--color-primary);
  color: #fff;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.api-key-save-btn:hover {
  background: var(--color-primary-dark);
}

.settings-themes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.theme-option-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  color: var(--color-text);
  transition: all 0.2s;
}
.theme-option-btn:hover {
  border-color: var(--color-primary-light);
  background: rgba(124, 58, 237, 0.04);
}
.theme-option-btn.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.btn {
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.btn-secondary {
  background: var(--color-bg);
  color: var(--color-text);
}
.btn-secondary:hover {
  background: var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-primary:hover {
  opacity: 0.9;
}
</style>
