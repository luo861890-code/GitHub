<template>
  <!-- 面板显隐由 App.vue 的 v-if="appStore.showAttributeTable" 控制挂载，组件内不再判断 visible（Boolean prop 未传时 Vue 默认 false，会导致永不渲染） -->
  <div class="attribute-table-panel">
    <!-- 头部 -->
    <div class="table-header">
      <div class="header-title">
        <i class="fa-solid fa-table"></i>
        <span>属性表 - {{ layerName }}</span>
        <span class="feature-count">{{ featureCount }} 个要素</span>
      </div>
      <div class="header-actions">
        <button class="icon-btn" title="导出CSV" @click="exportCSV">
          <i class="fa-solid fa-file-csv"></i>
        </button>
        <button class="icon-btn" title="关闭" @click="close">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="table-toolbar">
      <div class="search-box">
        <i class="fa-solid fa-magnifying-glass search-icon"></i>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索属性..."
        />
      </div>
      <div class="toolbar-right">
        <button class="tool-btn" title="添加字段" @click="addField">
          <i class="fa-solid fa-plus"></i>
        </button>
        <button class="tool-btn" title="删除字段" @click="deleteField">
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="tool-btn" title="字段计算器" @click="fieldCalculator">
          <i class="fa-solid fa-calculator"></i>
        </button>
      </div>
    </div>

    <!-- 表格内容 -->
    <div class="table-container" ref="tableContainerRef">
      <table class="data-table">
        <thead>
          <tr>
            <th class="row-header">#</th>
            <th
              v-for="field in fields"
              :key="field"
              class="field-header"
              @click="sortByField(field)"
            >
              <span>{{ field }}</span>
              <i
                v-if="sortField === field"
                class="fa-solid sort-icon"
                :class="sortAsc ? 'fa-sort-up' : 'fa-sort-down'"
              ></i>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in filteredRows"
            :key="idx"
            class="data-row"
            :class="{ selected: selectedRows.includes(idx) }"
            @click="selectRow(idx, $event)"
          >
            <td class="row-header">{{ idx + 1 }}</td>
            <td v-for="field in fields" :key="field" class="data-cell">
              {{ formatValue(row[field]) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="filteredRows.length === 0" class="empty-state">
        <i class="fa-solid fa-inbox"></i>
        <span>暂无数据</span>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="table-footer">
      <div class="footer-left">
        <span>选中 {{ selectedRows.length }} 行</span>
      </div>
      <div class="footer-right">
        <button class="page-btn" :disabled="currentPage <= 1" @click="prevPage">
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="page-btn" :disabled="currentPage >= totalPages" @click="nextPage">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'
import { showInputDialog } from '@/utils/dialog'

const appStore = useAppStore()
const mapStore = useMapStore()

const props = defineProps<{ visible?: boolean }>()
const emit = defineEmits<{ (e: 'row-select', idx: number): void }>()

// 当前图层数据
const currentLayer = computed(() => {
  if (!appStore.attributeTableLayerId) return null
  return mapStore.layerGroups[appStore.attributeTableLayerId] || null
})

const layerName = computed(() => currentLayer.value?.data.name || '未知图层')

// 统一提取图层属性行：支持 features 型（每个 feature.properties）与
// coordinates+properties 型（两个数组按索引对应）两种图层结构
const layerProps = computed(() => {
  const data = currentLayer.value?.data
  if (!data) return []
  if (data.features && data.features.length) {
    return data.features.map((f: any) => f.properties || {})
  }
  if (data.properties && data.properties.length) {
    const props = data.properties as any[]
    // 与几何一一对应：属性行数不超过几何要素数（防止清理孤儿属性多显示）
    const n = Array.isArray(data.coordinates) ? data.coordinates.length : null
    if (n != null && props.length > n) return props.slice(0, n)
    return props
  }
  return []
})

// 从图层属性行中提取字段和行数据
const fields = computed(() => {
  const props = layerProps.value
  if (!props.length) return []
  const first = props[0]
  if (first && typeof first === 'object') {
    return Object.keys(first)
  }
  return []
})

const rows = computed(() => layerProps.value)

const featureCount = computed(() => rows.value.length)

function close() {
  appStore.closeAttributeTable()
}

const searchQuery = ref('')
const sortField = ref<string | null>(null)
const sortAsc = ref(true)
const selectedRows = ref<number[]>([])
const currentPage = ref(1)
const pageSize = 50
const tableContainerRef = ref<HTMLDivElement | null>(null)

const filteredRows = computed(() => {
  let result = [...rows.value]

  // 搜索过滤
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(query)
      )
    )
  }

  // 排序
  if (sortField.value) {
    const field = sortField.value
    result.sort((a, b) => {
      const valA = a[field]
      const valB = b[field]
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc.value ? valA - valB : valB - valA
      }
      const strA = String(valA || '')
      const strB = String(valB || '')
      return sortAsc.value ? strA.localeCompare(strB) : strB.localeCompare(strA)
    })
  }

  return result
})

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(filteredRows.value.length / pageSize))
})

// 过滤/排序后每行对应的【原始数据索引】（用于属性表选中 ↔ 地图要素联动）
const filteredOrigIdx = computed(() => {
  let result = rows.value.map((row, i) => ({ row, i }))
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((o) =>
      Object.values(o.row).some((val) =>
        String(val).toLowerCase().includes(query)
      )
    )
  }
  if (sortField.value) {
    const field = sortField.value
    result.sort((a, b) => {
      const valA = a.row[field]
      const valB = b.row[field]
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc.value ? valA - valB : valB - valA
      }
      const strA = String(valA || '')
      const strB = String(valB || '')
      return sortAsc.value ? strA.localeCompare(strB) : strB.localeCompare(strA)
    })
  }
  return result.map((o) => o.i)
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredRows.value.slice(start, start + pageSize)
})

function sortByField(field: string) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value
  } else {
    sortField.value = field
    sortAsc.value = true
  }
}

function selectRow(idx: number, event: MouseEvent) {
  if (event.ctrlKey || event.metaKey) {
    const index = selectedRows.value.indexOf(idx)
    if (index > -1) {
      selectedRows.value.splice(index, 1)
    } else {
      selectedRows.value.push(idx)
    }
  } else if (event.shiftKey) {
    // Shift多选
    if (selectedRows.value.length > 0) {
      const last = selectedRows.value[selectedRows.value.length - 1]
      const start = Math.min(last, idx)
      const end = Math.max(last, idx)
      selectedRows.value = Array.from({ length: end - start + 1 }, (_, i) => start + i)
    } else {
      selectedRows.value = [idx]
    }
  } else {
    selectedRows.value = [idx]
  }
  emit('row-select', idx)
  // 属性表选中 → 地图联动：派发到地图容器（MapCanvas 监听 #map-container），window 兜底
  const origIdx = filteredOrigIdx.value[idx] ?? idx
  try {
    const detail = { layerId: appStore.attributeTableLayerId, idx: origIdx }
    const el = document.getElementById('map-container')
    if (el) el.dispatchEvent(new CustomEvent('map-attr-select', { detail }))
    else window.dispatchEvent(new CustomEvent('map-attr-select', { detail }))
  } catch (e) { /* ignore */ }
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(4)
  }
  return String(value)
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

function exportCSV() {
  if (!fields.value.length || !rows.value.length) return

  const header = fields.value.join(',')
  const csvRows = rows.value.map((row) =>
    fields.value
      .map((field) => {
        const val = row[field]
        if (typeof val === 'string' && val.includes(',')) {
          return `"${val}"`
        }
        return val ?? ''
      })
      .join(',')
  )
  const csv = [header, ...csvRows].join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${layerName.value || 'attributes'}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

/** 将属性表编辑（增删字段/字段计算）持久化回后端 */
let attrSaveTimer: ReturnType<typeof setTimeout> | null = null
function persistLayerData() {
  const layer = currentLayer.value?.data
  if (!layer || !mapStore.currentMapId) return
  if (attrSaveTimer) clearTimeout(attrSaveTimer)
  attrSaveTimer = setTimeout(async () => {
    try {
      await api.updateLayerGeometry(
        mapStore.currentMapId!,
        layer.id,
        { features: layer.features }
      )
    } catch (e) {
      console.warn('属性表保存失败:', e)
    }
  }, 400)
}

async function addField() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) {
    alert('当前图层没有要素数据')
    return
  }
  const name = await showInputDialog({ title: '请输入新字段名（英文/数字，如 area_km2）' })
  if (!name || !name.trim()) return
  const field = name.trim()
  layer.features.forEach((f: any) => {
    if (!f.properties) f.properties = {}
    f.properties[field] = null
  })
  persistLayerData()
  searchQuery.value = ''
}

async function deleteField() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) return
  const field = await showInputDialog({ title: '请输入要删除的字段名' })
  if (!field || !field.trim()) return
  layer.features.forEach((f: any) => {
    if (f.properties) delete f.properties[field.trim()]
  })
  persistLayerData()
}

async function fieldCalculator() {
  const layer = currentLayer.value?.data
  if (!layer || !layer.features || layer.features.length === 0) {
    alert('当前图层没有要素数据')
    return
  }
  const fieldList = fields.value
  const expr = await showInputDialog({
    title: '输入计算表达式（支持字段名和 + - * / % 括号，如 pop / area）',
    label: '可用字段: ' + fieldList.join(', '),
  })
  if (!expr) return
  const calculator = buildCalculator(expr, fieldList)
  if (!calculator) {
    alert('表达式无效，请检查语法和字段名')
    return
  }
  const target = await showInputDialog({ title: '结果写入字段名（可新建）' })
  if (!target || !target.trim()) return
  const field = target.trim()
  layer.features.forEach((f: any) => {
    if (!f.properties) f.properties = {}
    try {
      f.properties[field] = calculator(f.properties)
    } catch {
      f.properties[field] = null
    }
  })
  persistLayerData()
}

/**
 * 安全字段计算器（替代 new Function，杜绝任意代码执行）。
 * 仅支持：数字、字段名、四则运算 + - * / %、一元 - 与 !、括号，
 * 以及白名单函数 min/max/abs/round/floor/ceil/sqrt/pow。
 */
const SAFE_FUNCS: Record<string, (a: number[]) => number> = {
  min: (a) => Math.min(...a),
  max: (a) => Math.max(...a),
  abs: (a) => Math.abs(a[0] ?? 0),
  round: (a) => Math.round(a[0] ?? 0),
  floor: (a) => Math.floor(a[0] ?? 0),
  ceil: (a) => Math.ceil(a[0] ?? 0),
  sqrt: (a) => Math.sqrt(a[0] ?? 0),
  pow: (a) => Math.pow(a[0] ?? 0, a[1] ?? 0),
}

type ASTNode =
  | { t: 'num'; v: number }
  | { t: 'field'; name: string }
  | { t: 'binop'; op: string; l: ASTNode; r: ASTNode }
  | { t: 'neg'; c: ASTNode }
  | { t: 'not'; c: ASTNode }
  | { t: 'call'; name: string; args: ASTNode[] }

function buildCalculator(
  expr: string,
  fields: string[]
): ((props: Record<string, any>) => number) | null {
  const tokens = tokenizeCalculator(expr, fields)
  if (!tokens) return null
  let pos = 0
  const peek = () => tokens[pos]
  const next = () => tokens[pos++]

  function parseExpr(): ASTNode {
    let n = parseTerm()
    while (peek() && peek().t === 'op' && (peek().v === '+' || peek().v === '-')) {
      const op = next().v as string
      n = { t: 'binop', op, l: n, r: parseTerm() }
    }
    return n
  }
  function parseTerm(): ASTNode {
    let n = parseFactor()
    while (peek() && peek().t === 'op' && (peek().v === '*' || peek().v === '/' || peek().v === '%')) {
      const op = next().v as string
      n = { t: 'binop', op, l: n, r: parseFactor() }
    }
    return n
  }
  function parseFactor(): ASTNode {
    const tk = peek()
    if (!tk) throw new Error('表达式不完整')
    if (tk.t === 'num') { next(); return { t: 'num', v: tk.v as number } }
    if (tk.t === 'field') { next(); return { t: 'field', name: tk.v as string } }
    if (tk.t === 'op' && tk.v === '-') { next(); return { t: 'neg', c: parseFactor() } }
    if (tk.t === 'op' && tk.v === '!') { next(); return { t: 'not', c: parseFactor() } }
    if (tk.t === 'lp') {
      next(); const inner = parseExpr()
      if (!peek() || peek().t !== 'rp') throw new Error('缺少右括号')
      next(); return inner
    }
    if (tk.t === 'func') {
      const name = next().v as string
      if (!peek() || peek().t !== 'lp') throw new Error('缺少 (')
      next()
      const args: ASTNode[] = []
      if (peek() && peek().t !== 'rp') {
        args.push(parseExpr())
        while (peek() && peek().t === 'comma') { next(); args.push(parseExpr()) }
      }
      if (!peek() || peek().t !== 'rp') throw new Error('缺少右括号')
      next()
      return { t: 'call', name, args }
    }
    throw new Error('包含非法符号: ' + tk.v)
  }

  function evalNode(n: ASTNode, props: Record<string, any>): number {
    switch (n.t) {
      case 'num': return n.v
      case 'field': return Number(props[n.name] ?? 0) || 0
      case 'neg': return -evalNode(n.c, props)
      case 'not': return evalNode(n.c, props) === 0 ? 1 : 0
      case 'binop': {
        const l = evalNode(n.l, props)
        const r = evalNode(n.r, props)
        switch (n.op) {
          case '+': return l + r
          case '-': return l - r
          case '*': return l * r
          case '/': return r === 0 ? 0 : l / r
          case '%': return r === 0 ? 0 : l % r
          default: return 0
        }
      }
      case 'call': {
        const fn = SAFE_FUNCS[n.name]
        if (!fn) throw new Error('不支持的函数: ' + n.name)
        return fn(n.args.map((a) => evalNode(a, props)))
      }
      default: return 0
    }
  }

  try {
    const root = parseExpr()
    if (pos !== tokens.length) throw new Error('包含多余符号')
    return (props: Record<string, any>) => evalNode(root, props)
  } catch {
    return null
  }
}

function tokenizeCalculator(
  expr: string,
  fields: string[]
): Array<{ t: string; v: string | number }> | null {
  const out: Array<{ t: string; v: string | number }> = []
  const s = expr.replace(/\s+/g, '')
  if (!s) return null
  let i = 0
  while (i < s.length) {
    const ch = s[i]
    if ('+-*/%!(),'.includes(ch)) {
      const tokenType: Record<string, string> = {
        '+': 'op', '-': 'op', '*': 'op', '/': 'op', '%': 'op', '!': 'op',
        '(': 'lp', ')': 'rp', ',': 'comma',
      }
      out.push({ t: tokenType[ch], v: ch })
      i++
      continue
    }
    if (ch >= '0' && ch <= '9' || (ch === '.' && s[i + 1] >= '0' && s[i + 1] <= '9')) {
      let j = i
      while (j < s.length && /[0-9.]/.test(s[j])) j++
      const num = Number(s.slice(i, j))
      if (Number.isNaN(num)) return null
      out.push({ t: 'num', v: num })
      i = j
      continue
    }
    if (/[A-Za-z_]/.test(ch)) {
      let j = i
      while (j < s.length && /[A-Za-z0-9_.]/.test(s[j])) j++
      const ident = s.slice(i, j)
      // 函数：白名单函数名且后跟 (
      if (Object.prototype.hasOwnProperty.call(SAFE_FUNCS, ident) && s[j] === '(') {
        out.push({ t: 'func', v: ident })
      } else if (fields.includes(ident)) {
        out.push({ t: 'field', v: ident })
      } else {
        return null // 未知标识符（可能是注入企图），拒绝
      }
      i = j
      continue
    }
    return null // 非法字符
  }
  return out
}

watch(
  () => appStore.showAttributeTable,
  (val) => {
    if (val) {
      currentPage.value = 1
      selectedRows.value = []
      searchQuery.value = ''
    }
  }
)
</script>

<style scoped>
.attribute-table-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 300px;
  background: #fff;
  border-top: 1px solid var(--color-border);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
  z-index: 850;
  display: flex;
  flex-direction: column;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid var(--color-border);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.header-title i {
  color: var(--color-primary);
}

.feature-count {
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 10px;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  transition: all 0.15s;
}

.icon-btn:hover {
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-primary);
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border);
  background: #fafbfc;
}

.search-box {
  position: relative;
  flex: 1;
  max-width: 300px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.search-input {
  width: 100%;
  padding: 5px 10px 5px 28px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
  background: #fff;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--color-primary-light);
}

.toolbar-right {
  display: flex;
  gap: 4px;
}

.tool-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.15s;
}

.tool-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: rgba(124, 58, 237, 0.04);
}

.table-container {
  flex: 1;
  overflow: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.data-table thead {
  position: sticky;
  top: 0;
  z-index: 10;
}

.field-header {
  padding: 8px 10px;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  position: relative;
}

.field-header:hover {
  background: #f1f5f9;
}

.sort-icon {
  margin-left: 4px;
  font-size: 10px;
  color: var(--color-primary);
}

.row-header {
  padding: 6px 10px;
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
  width: 40px;
  position: sticky;
  left: 0;
  z-index: 5;
}

.data-row {
  transition: background 0.1s;
}

.data-row:hover {
  background: rgba(124, 58, 237, 0.04);
}

.data-row.selected {
  background: rgba(124, 58, 237, 0.12);
}

.data-row.selected .row-header {
  background: rgba(124, 58, 237, 0.12);
}

.data-cell {
  padding: 6px 10px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--color-text-secondary);
}

.empty-state i {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.3;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: all 0.15s;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-variant-numeric: tabular-nums;
}
</style>
