<template>
  <div class="trace-panel">
    <div class="trace-header">
      <span class="trace-title"><i class="fa-solid fa-diagram-project"></i> 智能制图过程</span>
      <button class="trace-close" title="关闭" @click="appStore.closeTracePanel()">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <div class="trace-body">
      <!-- 输入需求 -->
      <section v-if="prompt" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-comment-dots"></i> 用户需求</div>
        <div class="trace-prompt">{{ prompt }}</div>
      </section>

      <!-- 执行步骤时间线 -->
      <section v-if="traceSteps.length" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-list-check"></i> 执行步骤</div>
        <div class="trace-steps">
          <div
            v-for="(step, i) in traceSteps"
            :key="i"
            class="trace-step"
            :class="`step-${step.status || 'pending'}`"
          >
            <span class="step-badge">{{ i + 1 }}</span>
            <div class="step-content">
              <span class="step-name">{{ step.name }}</span>
              <span v-if="step.thinking" class="step-thinking">{{ step.thinking }}</span>
              <span v-if="step.result" class="step-result">{{ formatResult(step.result) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 六维任务书 -->
      <section v-if="taskBook" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-list"></i> 六维任务书</div>
        <table class="trace-table">
          <thead>
            <tr><th>维度</th><th>取值</th><th>置信度</th><th>推断</th></tr>
          </thead>
          <tbody>
            <tr v-for="[key, dim] in taskDims" :key="key">
              <td>{{ DIM_LABELS[key] || key }}</td>
              <td>{{ dim.value || '—' }}</td>
              <td>
                <span class="conf-chip" :class="confClass(dim.confidence)">
                  {{ dim.confidence ? (dim.confidence * 100).toFixed(0) + '%' : '—' }}
                </span>
              </td>
              <td>{{ dim.inferred ? '推断' : '明确' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="taskBook.reasoning_summary" class="trace-note">
          <i class="fa-solid fa-circle-info"></i> {{ taskBook.reasoning_summary }}
        </div>
      </section>

      <!-- 知识引用 -->
      <section v-if="knowledgeRefs.length" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-book-open"></i> 知识引用</div>
        <div v-for="(ref, i) in knowledgeRefs" :key="i" class="trace-kv">
          <span class="kv-key">{{ ref.ref }}</span>
          <span class="kv-value">{{ ref.source }} · {{ ref.confidence }}</span>
        </div>
      </section>

      <!-- 规划 -->
      <section v-if="plan" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-map"></i> 制图规划</div>
        <div class="trace-plan-grid">
          <div v-if="plan.map_spec" class="trace-card">
            <div class="card-title">地图规格</div>
            <div class="trace-kv" v-for="(v, k) in plan.map_spec" :key="k">
              <span class="kv-key">{{ PLAN_LABELS[k] || k }}</span><span class="kv-value">{{ v }}</span>
            </div>
          </div>
          <div v-if="plan.projection_plan" class="trace-card">
            <div class="card-title">投影</div>
            <div class="trace-kv"><span class="kv-key">投影</span><span class="kv-value">{{ plan.projection_plan.display_name }}</span></div>
            <div class="trace-kv"><span class="kv-key">CRS</span><span class="kv-value">{{ plan.projection_plan.crs }}</span></div>
          </div>
          <div v-if="plan.generalization_plan" class="trace-card">
            <div class="card-title">制图综合</div>
            <div class="trace-kv"><span class="kv-key">载负量</span><span class="kv-value">{{ plan.generalization_plan.load_level }} ×{{ plan.generalization_plan.load_factor }}</span></div>
            <div class="trace-kv"><span class="kv-key">LOD</span><span class="kv-value">{{ (plan.generalization_plan.lod_bands || []).length }} 档比例尺</span></div>
          </div>
          <div v-if="plan.symbol_plan" class="trace-card">
            <div class="card-title">符号方案</div>
            <div class="trace-note">{{ plan.symbol_plan.note || '—' }}</div>
          </div>
          <div v-if="plan.layout_plan" class="trace-card">
            <div class="card-title">版式</div>
            <div class="trace-kv"><span class="kv-key">幅面</span><span class="kv-value">{{ plan.layout_plan.page }}</span></div>
            <div class="trace-kv"><span class="kv-key">整饰</span><span class="kv-value">{{ (plan.layout_plan.decoration || []).join('、') }}</span></div>
          </div>
          <div v-if="plan.validation_plan" class="trace-card">
            <div class="card-title">验证计划</div>
            <div class="trace-note">{{ ((plan.validation_plan.layers as any[]) || []).map((l: any) => l.layer).join(' → ') }}</div>
          </div>
          <div v-if="plan.export_plan" class="trace-card">
            <div class="card-title">导出</div>
            <div class="trace-kv"><span class="kv-key">格式</span><span class="kv-value">{{ (plan.export_plan.formats || []).join(' / ') }}</span></div>
          </div>
        </div>
      </section>

      <!-- 工具 -->
      <section v-if="tools.length" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-wrench"></i> 工具链（{{ tools.length }}）</div>
        <div class="trace-tools">
          <span v-for="(t, i) in tools" :key="i" class="trace-tool" :title="toolTitle(t)">
            <i class="fa-solid" :class="toolIcon(t.category)"></i>
            {{ t.name }}
          </span>
        </div>
      </section>

      <!-- 模型 -->
      <section v-if="model" class="trace-section">
        <div class="trace-section-title"><i class="fa-solid fa-microchip"></i> 模型</div>
        <div class="trace-kv">
          <span class="kv-key">Provider</span>
          <span class="kv-value">{{ model.provider }} / {{ model.model }}</span>
        </div>
      </section>

      <div v-if="empty" class="trace-empty">
        <i class="fa-solid fa-inbox"></i>
        <span>暂无制图过程记录</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/appStore'

const appStore = useAppStore()

const DIM_LABELS: Record<string, string> = {
  theme: '主题',
  region: '区域',
  temporal: '时间',
  cartographic_method: '制图方法',
  audience: '受众',
  symbol_expression: '符号表达',
}

const PLAN_LABELS: Record<string, string> = {
  map_type: '类型',
  region: '区域',
  audience: '受众',
  scale_level: '尺度',
  page_size: '幅面',
}

const data = computed(() => appStore.traceData || {})
const provenance = computed(() => data.value.provenance || {})
const prompt = computed(() => provenance.value.input_prompt || data.value.prompt || '')
const taskBook = computed(() => provenance.value.task || null)
const taskDims = computed(() => {
  const t = taskBook.value
  if (!t) return []
  return (Object.entries(t) as [string, any][]).filter(
    ([k]) => k !== 'clarification_required' && k !== 'reasoning_summary',
  )
})
const knowledgeRefs = computed(() => provenance.value.knowledge_refs || [])
const plan = computed(() => provenance.value.plan || null)
const tools = computed(() => provenance.value.tools || [])
const model = computed(() => provenance.value.model || null)
const traceSteps = computed(() => data.value.steps || [])
const empty = computed(() => !prompt.value && !taskBook.value && traceSteps.value.length === 0)

function confClass(conf: number | undefined): string {
  if (!conf) return ''
  if (conf >= 0.8) return 'high'
  if (conf >= 0.5) return 'mid'
  return 'low'
}

function toolIcon(category: string): string {
  const icons: Record<string, string> = {
    data: 'fa-database',
    rendering: 'fa-pen-ruler',
    analysis: 'fa-chart-line',
    export: 'fa-file-export',
    processing: 'fa-sliders',
  }
  return icons[category] || 'fa-wrench'
}

function toolTitle(t: any): string {
  const parts = []
  if (t.preconditions?.length) parts.push('前置: ' + t.preconditions.join(', '))
  if (t.postconditions?.length) parts.push('后置: ' + t.postconditions.join(', '))
  return parts.join('；') || t.name
}

function formatResult(result: any): string {
  if (result == null) return ''
  if (typeof result === 'string') return result.slice(0, 80)
  try {
    return JSON.stringify(result).slice(0, 120)
  } catch {
    return String(result).slice(0, 120)
  }
}
</script>

<style scoped>
.trace-panel {
  position: absolute;
  top: 48px;
  right: 12px;
  bottom: 40px;
  width: 420px;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  z-index: 1200;
  overflow: hidden;
  animation: traceIn 0.25s ease-out;
}

@keyframes traceIn {
  from { transform: translateX(30px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 100%);
}

.trace-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text);
}

.trace-title i {
  color: var(--color-primary);
  margin-right: 6px;
}

.trace-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-secondary);
}

.trace-close:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.trace-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trace-section {
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  padding: 10px 12px;
  background: var(--color-surface);
}

.trace-section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary-dark);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.trace-prompt {
  font-size: 13px;
  color: var(--color-text);
  background: var(--color-primary-50);
  border-radius: 8px;
  padding: 8px 10px;
  line-height: 1.5;
}

.trace-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.trace-step {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.step-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.trace-step.step-success .step-badge {
  background: #dcfce7;
  color: #16a34a;
}

.trace-step.step-failed .step-badge {
  background: #fee2e2;
  color: #dc2626;
}

.trace-step.step-running .step-badge {
  background: #dbeafe;
  color: #2563eb;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.step-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
}

.step-thinking,
.step-result {
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  word-break: break-all;
}

.trace-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.trace-table th {
  text-align: left;
  color: var(--color-text-tertiary);
  font-weight: 500;
  padding: 4px 6px;
  border-bottom: 1px solid var(--color-border-light);
}

.trace-table td {
  padding: 5px 6px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text);
}

.conf-chip {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 9px;
  font-size: 11px;
}

.conf-chip.high { background: #dcfce7; color: #16a34a; }
.conf-chip.mid { background: #fef3c7; color: #d97706; }
.conf-chip.low { background: #fee2e2; color: #dc2626; }

.trace-note {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 6px;
  line-height: 1.5;
}

.trace-kv {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  padding: 3px 0;
}

.kv-key {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

.kv-value {
  color: var(--color-text);
  text-align: right;
  word-break: break-all;
}

.trace-plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.trace-card {
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--color-bg);
}

.card-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary-dark);
  margin-bottom: 4px;
}

.trace-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.trace-tool {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 3px 8px;
  background: var(--color-primary-50);
  color: var(--color-primary-dark);
  border: 1px solid var(--color-primary-200);
  border-radius: 12px;
  cursor: default;
}

.trace-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--color-text-tertiary);
  font-size: 13px;
}
</style>
