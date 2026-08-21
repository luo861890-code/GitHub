<template>
  <div class="async-load-error">
    <i class="fa-solid fa-triangle-exclamation"></i>
    <span>模块加载失败，请刷新页面重试</span>
  </div>
</template>

<style scoped>
.async-load-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--color-error);
  font-size: 13px;
  background: #fef2f2;
  border-radius: 8px;
}
</style>
