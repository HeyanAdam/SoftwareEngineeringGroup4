<script setup lang="ts">
/** 页面容器: 统一标题区 + 内容卡片间距 */

withDefaults(
  defineProps<{
    /** 页面标题 */
    title?: string
    /** 副标题 / 说明 */
    description?: string
    /** 内容是否包在卡片中 */
    card?: boolean
  }>(),
  { title: '', description: '', card: true },
)
</script>

<template>
  <section class="page-container">
    <header v-if="title || description || $slots.actions" class="page-container__header">
      <div class="page-container__titles">
        <h2 v-if="title" class="page-container__title">{{ title }}</h2>
        <p v-if="description" class="page-container__desc">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="page-container__actions">
        <slot name="actions" />
      </div>
    </header>

    <div :class="['page-container__body', { 'is-card': card }]">
      <slot />
    </div>
  </section>
</template>

<style scoped lang="scss">
.page-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100%;

  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
  }

  &__title {
    font-size: 18px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__desc {
    margin-top: 4px;
    font-size: 13px;
    color: var(--app-text-secondary);
  }

  &__actions {
    display: flex;
    flex-shrink: 0;
    gap: 8px;
    align-items: center;
  }

  &__body {
    flex: 1;
    min-height: 0;

    &.is-card {
      padding: 18px;
      background-color: var(--app-bg-container);
      border: 1px solid var(--app-border-color-light);
      border-radius: var(--app-radius-md);
      box-shadow: var(--app-shadow-sm);
    }
  }
}
</style>
