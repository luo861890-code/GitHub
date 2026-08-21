/**
 * 全局输入对话框（替代浏览器原生 prompt，避免 Electron 环境下 prompt() 不可用）。
 *
 * 用法：
 *   const value = await showInputDialog({ title: '旋转角度', defaultValue: '45' })
 *   // value 为用户输入字符串；点取消时为 null
 */
import { reactive } from 'vue'

export interface InputDialogOptions {
  /** 对话框标题（原 prompt 的提示文本） */
  title: string
  /** 可选：输入框上方说明文字 */
  label?: string
  /** 可选：默认值 */
  defaultValue?: string
  /** 可选：占位符 */
  placeholder?: string
}

interface DialogState {
  visible: boolean
  title: string
  label: string
  defaultValue: string
  placeholder: string
  resolve: ((value: string | null) => void) | null
}

const state = reactive<DialogState>({
  visible: false,
  title: '',
  label: '',
  defaultValue: '',
  placeholder: '',
  resolve: null,
})

/** 弹出输入对话框，返回 Promise<string | null>（取消为 null） */
export function showInputDialog(options: InputDialogOptions): Promise<string | null> {
  return new Promise((resolve) => {
    state.title = options.title
    state.label = options.label || ''
    state.defaultValue = options.defaultValue || ''
    state.placeholder = options.placeholder || ''
    state.resolve = resolve
    state.visible = true
  })
}

/** 提交输入（内部由 PromptDialog 组件调用） */
export function resolveInputDialog(value: string) {
  state.visible = false
  const resolve = state.resolve
  state.resolve = null
  resolve?.(value)
}

/** 取消输入（内部由 PromptDialog 组件调用） */
export function cancelInputDialog() {
  state.visible = false
  const resolve = state.resolve
  state.resolve = null
  resolve?.(null)
}

/** 获取对话框状态（供 PromptDialog 组件读取） */
export function useInputDialogState() {
  return state
}
