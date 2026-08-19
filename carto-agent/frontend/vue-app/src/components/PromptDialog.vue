<template>
  <div v-if="state.visible" class="prompt-dialog-overlay" @click.self="cancel">
    <div class="prompt-dialog" role="dialog" aria-modal="true">
      <div class="prompt-dialog-title">{{ state.title }}</div>
      <div v-if="state.label" class="prompt-dialog-label">{{ state.label }}</div>
      <input
        ref="inputRef"
        v-model="inputValue"
        class="prompt-dialog-input"
        :placeholder="state.placeholder"
        @keydown.enter="submit"
        @keydown.esc="cancel"
      />
      <div class="prompt-dialog-actions">
        <button class="prompt-btn prompt-btn-cancel" @click="cancel">取消</button>
        <button class="prompt-btn prompt-btn-ok" @click="submit">确定</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useInputDialogState, resolveInputDialog, cancelInputDialog } from '@/utils/dialog'

const state = useInputDialogState()
const inputValue = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => state.visible,
  (visible) => {
    if (visible) {
      inputValue.value = state.defaultValue
      nextTick(() => inputRef.value?.focus())
    }
  }
)

function submit() {
  resolveInputDialog(inputValue.value)
}

function cancel() {
  cancelInputDialog()
}
</script>

<style scoped>
.prompt-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
}

.prompt-dialog {
  width: 360px;
  max-width: calc(100vw - 40px);
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
  padding: 18px 20px;
  animation: prompt-pop 0.15s ease;
}

@keyframes prompt-pop {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.prompt-dialog-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.prompt-dialog-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}

.prompt-dialog-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.prompt-dialog-input:focus {
  border-color: #8b5cf6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
}

.prompt-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.prompt-btn {
  padding: 7px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s;
}

.prompt-btn-cancel {
  background: #f3f4f6;
  color: #4b5563;
}

.prompt-btn-cancel:hover {
  background: #e5e7eb;
}

.prompt-btn-ok {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  color: #fff;
}

.prompt-btn-ok:hover {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
}
</style>
