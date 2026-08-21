<template>
  <div class="qa-panel">
    <div class="qa-header">
      <span class="qa-title"><i class="fa-solid fa-shield-halved"></i> 地图质量验收报告（1000 分制）</span>
      <button class="qa-close" title="关闭" @click="appStore.closeQaPanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <div class="qa-body">
      <!-- 总分与等级 -->
      <div class="qa-score-row">
        <div class="qa-score-big">
          <span class="score-num">{{ report?.total_score ?? '—' }}</span>
          <span class="score-max">/ 1000</span>
        </div>
        <div class="qa-grade" :class="`grade-${(report?.grade || 'E').toLowerCase()}`">
          {{ report?.grade || '—' }}
        </div>
        <div class="qa-meta">
          <span>{{ report?.map_name || '未命名地图' }}</span>
          <span>{{ typeLabel(report?.map_type) }}</span>
          <span>C={{ report?.critical_count || 0 }} · M={{ report?.major_count || 0 }} · m={{ report?.minor_count || 0 }}</span>
        </div>
      </div>

      <!-- 六级得分 -->
      <section class="qa-section">
        <div class="qa-section-title"><i class="fa-solid fa-chart-simple"></i> 十项评分（A–J）</div>
        <div v-for="(dim, key) in (report?.dimensions || {})" :key="key" class="qa-dim">
          <div class="qa-dim-head">
            <span class="dim-name">{{ dim.name }}</span>
            <span class="dim-score">{{ dim.score }} / {{ dim.max }}</span>
          </div>
          <div class="qa-bar"><div class="qa-bar-fill" :style="{ width: pct(dim.score, dim.max) }"></div></div>
          <div v-if="dim.issues?.length" class="dim-issues">
            <div v-for="(i, idx) in dim.issues" :key="idx" class="dim-issue">{{ i }}</div>
          </div>
        </div>
      </section>

      <!-- 问题清单 -->
      <section v-if="hasIssues" class="qa-section">
        <div class="qa-section-title"><i class="fa-solid fa-triangle-exclamation"></i> 问题清单</div>
        <div v-if="report?.issues?.critical?.length" class="qa-issue-list critical">
          <div v-for="(i, idx) in report.issues.critical" :key="'c' + idx" class="qa-issue">CRITICAL · {{ i }}</div>
        </div>
        <div v-if="report?.issues?.major?.length" class="qa-issue-list major">
          <div v-for="(i, idx) in report.issues.major" :key="'m' + idx" class="qa-issue">MAJOR · {{ i }}</div>
        </div>
        <div v-if="report?.issues?.minor?.length" class="qa-issue-list minor">
          <div v-for="(i, idx) in report.issues.minor" :key="'n' + idx" class="qa-issue">MINOR · {{ i }}</div>
        </div>
      </section>

      <!-- 缺失要素 -->
      <section v-if="report?.missing_features?.length" class="qa-section">
        <div class="qa-section-title"><i class="fa-solid fa-list-check"></i> 缺失要素清单</div>
        <div v-for="(m, i) in report.missing_features" :key="i" class="qa-missing">{{ m }}</div>
      </section>

      <!-- 修改优先级 -->
      <section v-if="report?.priority?.length" class="qa-section">
        <div class="qa-section-title"><i class="fa-solid fa-arrow-trend-up"></i> 修改优先级</div>
        <ol class="qa-priority">
          <li v-for="(p, i) in report.priority" :key="i">{{ p }}</li>
        </ol>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/appStore'

const appStore = useAppStore()
const report = computed(() => appStore.qaReport)
const hasIssues = computed(() =>
  (report.value?.issues?.critical?.length || 0)
  + (report.value?.issues?.major?.length || 0)
  + (report.value?.issues?.minor?.length || 0) > 0,
)

const TYPE_NAMES: Record<string, string> = {
  administrative: '行政区划图', traffic: '交通图', tourism: '旅游图', terrain: '地势图',
  basic: '基础地图', campus: '校园图', food: '美食图',
}

function typeLabel(t?: string): string {
  return TYPE_NAMES[t || ''] || t || ''
}

function pct(score: number, max: number): string {
  if (!max) return '0%'
  return Math.max(0, Math.min(100, Math.round((score / max) * 100))) + '%'
}
</script>

<style scoped>
.qa-panel {
  position: absolute;
  top: 48px;
  right: 12px;
  bottom: 40px;
  width: 460px;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  z-index: 1210;
  overflow: hidden;
  animation: qaIn 0.25s ease-out;
}

@keyframes qaIn {
  from { transform: translateX(30px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.qa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 100%);
}

.qa-title { font-weight: 600; font-size: 14px; color: var(--color-text); }
.qa-title i { color: var(--color-primary); margin-right: 6px; }

.qa-close {
  width: 28px; height: 28px; border: none; background: transparent;
  border-radius: 6px; cursor: pointer; color: var(--color-text-secondary);
}
.qa-close:hover { background: var(--color-bg); color: var(--color-text); }

.qa-body { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; }

.qa-score-row {
  display: flex; align-items: center; gap: 12px;
  border: 1px solid var(--color-border-light); border-radius: 10px;
  padding: 12px; background: var(--color-surface);
}
.qa-score-big { display: flex; align-items: baseline; }
.score-num { font-size: 34px; font-weight: 700; color: var(--color-primary-dark); }
.score-max { font-size: 13px; color: var(--color-text-tertiary); margin-left: 3px; }
.qa-grade {
  width: 46px; height: 46px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.grade-a { background: #16a34a; }
.grade-b { background: #2563eb; }
.grade-c { background: #d97706; }
.grade-d { background: #dc2626; }
.grade-e { background: #7f1d1d; }
.qa-meta { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--color-text-secondary); }

.qa-section { border: 1px solid var(--color-border-light); border-radius: 10px; padding: 10px 12px; background: var(--color-surface); }
.qa-section-title { font-size: 12px; font-weight: 600; color: var(--color-primary-dark); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }

.qa-dim { margin-bottom: 8px; }
.qa-dim-head { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 3px; }
.dim-name { color: var(--color-text); }
.dim-score { color: var(--color-text-secondary); font-weight: 600; }
.qa-bar { height: 6px; background: var(--color-border-light); border-radius: 3px; overflow: hidden; }
.qa-bar-fill { height: 100%; background: linear-gradient(90deg, #a78bfa, #8b5cf6); border-radius: 3px; }
.dim-issues { margin-top: 4px; }
.dim-issue { font-size: 11px; color: var(--color-text-secondary); line-height: 1.5; }

.qa-issue-list { margin-bottom: 4px; }
.qa-issue {
  font-size: 11.5px; line-height: 1.5; padding: 4px 8px; border-radius: 6px; margin-bottom: 3px;
}
.qa-issue-list.critical .qa-issue { background: #fee2e2; color: #b91c1c; }
.qa-issue-list.major .qa-issue { background: #fef3c7; color: #b45309; }
.qa-issue-list.minor .qa-issue { background: #f3f4f6; color: #6b7280; }

.qa-missing { font-size: 12px; color: var(--color-text-secondary); padding: 3px 0; }
.qa-priority { margin: 0; padding-left: 18px; font-size: 12px; color: var(--color-text-secondary); }
.qa-priority li { margin-bottom: 3px; line-height: 1.5; }
</style>
