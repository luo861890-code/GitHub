<template>
  <div class="eval-panel">
    <div class="eval-header">
      <span><i class="fa-solid fa-chart-column"></i> 实证驱动评估</span>
      <div class="eval-header-actions">
        <button class="eval-refresh" title="刷新" @click="load()">
          <i class="fa-solid fa-rotate"></i>
        </button>
        <button class="eval-close" title="关闭" @click="appStore.toggleEvalPanel()">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <div class="eval-body">
      <div v-if="loading" class="eval-empty">正在加载评估数据…</div>
      <div v-else-if="!stats || !stats.total_tasks" class="eval-empty">
        <i class="fa-solid fa-chart-simple"></i>
        <p>暂无任务评估记录</p>
        <p class="eval-empty-sub">在右侧对话框向智能体发送制图/修改指令后，这里会自动记录任务完成率、端到端延迟与规范性评分。</p>
      </div>
      <template v-else>
        <!-- 规范性 5 分制 -->
        <div class="eval-card eval-norm">
          <div class="eval-card-title">
            <i class="fa-solid fa-shield-halved"></i> 地图规范性 <span class="eval-sub">（5 分制 · QA 1000 分制映射）</span>
          </div>
          <div v-if="stats.normativity" class="eval-norm-row">
            <div class="eval-norm-score">
              <span class="eval-big">{{ stats.normativity.score_5 }}</span><span class="eval-small">/ 5</span>
            </div>
            <div class="eval-norm-meta">
              <div class="eval-tag" :class="'eval-grade-' + (stats.normativity.grade || '').toLowerCase()">
                等级 {{ stats.normativity.grade }} · {{ stats.normativity.score_1000 }}/1000
              </div>
              <div class="eval-norm-map">{{ stats.normativity.map_name || '未命名地图' }}</div>
            </div>
          </div>
          <div v-else class="eval-empty-sub">暂无规范性评分（需先生成地图）</div>
        </div>

        <!-- 完成率与延迟 -->
        <div class="eval-grid">
          <div class="eval-card">
            <div class="eval-card-title"><i class="fa-solid fa-bullseye"></i> 任务完成率</div>
            <div class="eval-kpi">
              <span class="eval-big">{{ (stats.task_success_rate != null ? (stats.task_success_rate * 100).toFixed(0) : '—') + '%' }}</span>
            </div>
            <div class="eval-meta">任务类 {{ stats.task_success_rate != null ? (stats.task_success_rate * 100).toFixed(0) : '—' }}% · 全部 {{ (stats.success_rate * 100).toFixed(0) }}%（{{ stats.success_rate != null ? '' : '' }}{{ stats.task_tasks }} 任务 / {{ stats.total_tasks }} 条）</div>
          </div>
          <div class="eval-card">
            <div class="eval-card-title"><i class="fa-solid fa-stopwatch"></i> 端到端延迟</div>
            <div class="eval-kpi"><span class="eval-big">{{ formatMs(stats.avg_latency_ms) }}</span></div>
            <div class="eval-meta">平均 · 最大 {{ formatMs(stats.max_latency_ms) }} · 中位 {{ formatMs(stats.median_latency_ms) }}</div>
          </div>
        </div>

        <!-- 三场景分组 -->
        <div class="eval-card">
          <div class="eval-card-title"><i class="fa-solid fa-layer-group"></i> 场景分组（基础 / 核心 / 压力）</div>
          <div v-if="sceneList.length" class="eval-scene">
            <div v-for="s in sceneList" :key="s.scene" class="eval-scene-row">
              <span class="eval-scene-name">{{ s.scene }}</span>
              <div class="eval-scene-bar">
                <div class="eval-scene-fill" :style="{ width: (s.success_rate != null ? s.success_rate * 100 : 0) + '%' }"></div>
              </div>
              <span class="eval-scene-meta">{{ s.success }}/{{ s.total }} · {{ formatMs(s.avg_latency_ms) }}</span>
            </div>
          </div>
          <div v-else class="eval-empty-sub">暂无场景数据</div>
        </div>

        <!-- 近 10 条趋势 -->
        <div class="eval-card">
          <div class="eval-card-title"><i class="fa-solid fa-list"></i> 近 {{ stats.recent_trend.length }} 条任务</div>
          <div class="eval-trend">
            <div v-for="(r, i) in stats.recent_trend" :key="i" class="eval-trend-row">
              <i class="fa-solid" :class="r.success ? 'fa-circle-check eval-ok' : 'fa-circle-xmark eval-fail'"></i>
              <span class="eval-trend-msg">{{ r.message }}</span>
              <span class="eval-trend-lat">{{ formatMs(r.latency_ms) }}</span>
              <span class="eval-trend-scene">{{ r.scene }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import api from '@/services/api'

const appStore = useAppStore()
const loading = ref(false)
const stats = ref<Record<string, any> | null>(null)

const sceneList = computed(() => {
  const by = stats.value?.by_scene || {}
  return Object.keys(by).map((scene) => ({ scene, ...by[scene] }))
})

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return ms.toFixed(0) + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}

async function load() {
  loading.value = true
  try {
    const result = await api.getEvaluation()
    stats.value = result?.data || result || null
  } catch (e) {
    console.error('加载评估数据失败:', e)
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.eval-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 340px;
  max-height: calc(100% - 24px);
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--shadow-lg, 0 10px 30px -5px rgba(139, 92, 246, 0.18));
  display: flex;
  flex-direction: column;
  z-index: 60;
  overflow: hidden;
}
.eval-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border-light, #f3f4f6);
  font-weight: 600;
  color: var(--color-text, #1f2937);
  background: var(--color-primary-50, #f5f3ff);
}
.eval-header-actions { display: flex; gap: 6px; }
.eval-refresh, .eval-close {
  border: none; background: transparent; cursor: pointer;
  color: var(--color-text-secondary, #6b7280); font-size: 14px;
  padding: 4px 6px; border-radius: 6px;
}
.eval-refresh:hover, .eval-close:hover { background: var(--color-primary-100, #ede9fe); color: var(--color-primary-dark, #8b5cf6); }
.eval-body { padding: 12px 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.eval-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 30px 12px; color: var(--color-text-secondary, #6b7280);
  font-size: 13px; text-align: center;
}
.eval-empty i { font-size: 26px; color: var(--color-primary-light, #c4b5fd); }
.eval-empty-sub { font-size: 12px; color: var(--color-text-tertiary, #9ca3af); }
.eval-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border-light, #f3f4f6);
  border-radius: var(--radius-md, 12px);
  padding: 10px 12px;
}
.eval-card-title { font-size: 12px; font-weight: 600; color: var(--color-text-secondary, #6b7280); margin-bottom: 8px; }
.eval-sub { font-weight: 400; color: var(--color-text-tertiary, #9ca3af); }
.eval-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.eval-norm-row { display: flex; align-items: center; gap: 14px; }
.eval-norm-score { display: flex; align-items: baseline; }
.eval-big { font-size: 26px; font-weight: 700; color: var(--color-primary-dark, #8b5cf6); }
.eval-small { font-size: 13px; color: var(--color-text-tertiary, #9ca3af); }
.eval-kpi .eval-big { font-size: 24px; }
.eval-norm-meta { display: flex; flex-direction: column; gap: 4px; }
.eval-tag {
  display: inline-block; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px;
}
.eval-grade-a { background: #ecfdf5; color: #059669; }
.eval-grade-b { background: #eff6ff; color: #2563eb; }
.eval-grade-c { background: #fffbeb; color: #d97706; }
.eval-grade-d { background: #fef2f2; color: #dc2626; }
.eval-norm-map { font-size: 12px; color: var(--color-text-secondary, #6b7280); }
.eval-meta { font-size: 11px; color: var(--color-text-tertiary, #9ca3af); margin-top: 4px; }
.eval-scene { display: flex; flex-direction: column; gap: 8px; }
.eval-scene-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.eval-scene-name { width: 110px; flex-shrink: 0; color: var(--color-text, #1f2937); }
.eval-scene-bar { flex: 1; height: 8px; background: var(--color-primary-50, #f5f3ff); border-radius: 4px; overflow: hidden; }
.eval-scene-fill { height: 100%; background: linear-gradient(90deg, var(--color-primary-light, #c4b5fd), var(--color-primary, #a78bfa)); border-radius: 4px; }
.eval-scene-meta { width: 90px; text-align: right; color: var(--color-text-tertiary, #9ca3af); }
.eval-trend { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.eval-trend-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.eval-ok { color: var(--color-success, #10b981); }
.eval-fail { color: var(--color-error, #ef4444); }
.eval-trend-msg { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text, #1f2937); }
.eval-trend-lat { color: var(--color-primary-dark, #8b5cf6); font-variant-numeric: tabular-nums; }
.eval-trend-scene { color: var(--color-text-tertiary, #9ca3af); font-size: 11px; }
</style>
