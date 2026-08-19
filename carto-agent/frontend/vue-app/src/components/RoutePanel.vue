<template>
  <div class="route-panel">
    <div class="route-panel-header">
      <span><i class="fa-solid fa-route"></i> 路径规划</span>
      <button class="route-panel-close" title="关闭" @click="appStore.toggleRoutePanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="route-panel-body">
      <div class="route-field">
        <label>出行方式</label>
        <div class="route-profile-group">
          <button :class="{ active: routeProfile === 'driving' }" @click="routeProfile = 'driving'"><i class="fa-solid fa-car"></i> 驾车</button>
          <button :class="{ active: routeProfile === 'walking' }" @click="routeProfile = 'walking'"><i class="fa-solid fa-person-walking"></i> 步行</button>
          <button :class="{ active: routeProfile === 'cycling' }" @click="routeProfile = 'cycling'"><i class="fa-solid fa-bicycle"></i> 骑行</button>
        </div>
      </div>
      <div class="route-field">
        <label><i class="fa-solid fa-circle-dot route-start-icon"></i> 起点</label>
        <div class="route-coord-input">
          <input v-model="startLat" type="number" placeholder="纬度" step="0.0001" class="route-input" />
          <input v-model="startLng" type="number" placeholder="经度" step="0.0001" class="route-input" />
        </div>
      </div>
      <div class="route-field">
        <label><i class="fa-solid fa-location-dot route-end-icon"></i> 终点</label>
        <div class="route-coord-input">
          <input v-model="endLat" type="number" placeholder="纬度" step="0.0001" class="route-input" />
          <input v-model="endLng" type="number" placeholder="经度" step="0.0001" class="route-input" />
        </div>
      </div>
      <div class="route-hint">支持填写坐标或使用当前地图中心附近的经纬度</div>
      <button class="route-plan-btn" :disabled="running" @click="handlePlanRoute">
        <div v-if="running" class="route-spinner"></div>
        <i v-else class="fa-solid fa-route"></i>
        开始规划
      </button>

      <div v-if="message" class="route-message">{{ message }}</div>
      <div v-if="mapStore.routeData" class="route-result">
        <div class="route-result-stats">
          <div class="route-stat">
            <span class="route-stat-label">距离</span>
            <span class="route-stat-value">{{ (mapStore.routeData.distance / 1000).toFixed(2) }} km</span>
          </div>
          <div class="route-stat">
            <span class="route-stat-label">预计时间</span>
            <span class="route-stat-value">{{ Math.round(mapStore.routeData.duration / 60) }} 分钟</span>
          </div>
        </div>
        <div v-if="mapStore.routeData.steps?.length" class="route-steps">
          <div v-for="(step, idx) in mapStore.routeData.steps" :key="idx" class="route-step">
            <span class="route-step-num">{{ idx + 1 }}</span>
            <span class="route-step-text">{{ step.instruction }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'

const appStore = useAppStore()
const mapStore = useMapStore()

const routeProfile = ref<'driving' | 'walking' | 'cycling'>('driving')
const startLat = ref('')
const startLng = ref('')
const endLat = ref('')
const endLng = ref('')
const running = ref(false)
const message = ref('')

async function handlePlanRoute() {
  message.value = ''
  const mapId = mapStore.currentMapId
  if (!mapId) {
    message.value = '请先生成地图'
    return
  }
  const start = [parseFloat(startLat.value), parseFloat(startLng.value)]
  const end = [parseFloat(endLat.value), parseFloat(endLng.value)]
  if (start.some((v) => isNaN(v)) || end.some((v) => isNaN(v))) {
    message.value = '请填写有效的起终点坐标'
    return
  }
  running.value = true
  try {
    const resp = await api.planRoute(mapId, { start, end, profile: routeProfile.value })
    const data = resp.data || resp
    if (!data || !data.coordinates) {
      message.value = '路径规划失败'
      return
    }
    mapStore.setRouteData(data)
    const el = document.getElementById('map-container')
    el?.dispatchEvent(new CustomEvent('map-show-route', { detail: { route: data } }))
  } catch (e: any) {
    message.value = '路径规划失败: ' + e.message
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.route-panel {
  position: absolute;
  top: 48px;
  left: 12px;
  width: 300px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 855;
  overflow: hidden;
}
.route-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
}
.route-panel-close {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 5px;
  cursor: pointer;
}
.route-panel-body {
  padding: 12px 14px;
  font-size: 12px;
}
.route-field {
  margin-bottom: 10px;
}
.route-field label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 5px;
}
.route-start-icon { color: #22c55e; }
.route-end-icon { color: #ef4444; }
.route-profile-group {
  display: flex;
  gap: 6px;
}
.route-profile-group button {
  flex: 1;
  padding: 6px 4px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.route-profile-group button.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.route-coord-input {
  display: flex;
  gap: 6px;
}
.route-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
}
.route-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-bottom: 10px;
}
.route-plan-btn {
  width: 100%;
  padding: 9px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.route-plan-btn:disabled { opacity: 0.6; }
.route-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: route-spin 0.6s linear infinite;
}
@keyframes route-spin { to { transform: rotate(360deg); } }
.route-message {
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  border-radius: 6px;
  font-size: 11px;
}
.route-result {
  margin-top: 12px;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.route-result-stats {
  display: flex;
  gap: 20px;
}
.route-stat {
  display: flex;
  flex-direction: column;
}
.route-stat-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-primary);
}
.route-stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.route-steps {
  margin-top: 10px;
  border-top: 1px dashed var(--color-border);
  padding-top: 8px;
  max-height: 180px;
  overflow-y: auto;
}
.route-step {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 11px;
}
.route-step-num {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary-100);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}
</style>
