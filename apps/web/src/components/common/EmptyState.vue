<script setup lang="ts">
/** 空状态占位 */

import { ElButton, ElEmpty } from 'element-plus'

withDefaults(
  defineProps<{
    description?: string
    /** 操作按钮文案, 为空则不渲染按钮 */
    actionText?: string
    imageSize?: number
  }>(),
  { description: '暂无数据', actionText: '', imageSize: 96 },
)

const emit = defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="empty-state">
    <ElEmpty :description="description" :image-size="imageSize">
      <ElButton v-if="actionText" type="primary" @click="emit('action')">
        {{ actionText }}
      </ElButton>
    </ElEmpty>
    <p v-if="$slots.hint" class="empty-state__hint">
      <slot name="hint" />
    </p>
  </div>
</template>

<style scoped lang="scss">
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 0;

  &__hint {
    margin-top: 8px;
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}
</style>
