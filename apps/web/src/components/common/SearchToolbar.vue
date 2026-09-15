<script setup lang="ts">
/** 列表页搜索工具栏: 左内联表单 + 右侧按钮组 */

withDefaults(
  defineProps<{
    /** 表单宽度 (每项) */
    itemWidth?: string
  }>(),
  { itemWidth: '200px' },
)
</script>

<template>
  <div class="search-toolbar">
    <div class="search-toolbar__form" :style="{ '--item-width': itemWidth }">
      <slot />
    </div>
    <div v-if="$slots.actions" class="search-toolbar__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.search-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--app-border-color-light);

  &__form {
    display: flex;
    flex: 1;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;

    :deep(.el-input),
    :deep(.el-select) {
      width: var(--item-width);
    }
  }

  &__actions {
    display: flex;
    flex-shrink: 0;
    gap: 8px;
    align-items: center;
  }
}
</style>
