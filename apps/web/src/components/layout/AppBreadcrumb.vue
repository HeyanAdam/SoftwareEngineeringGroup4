<script setup lang="ts">
/** 面包屑: 根据当前路由的 matched 链生成 */

import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElBreadcrumb, ElBreadcrumbItem } from 'element-plus'

const route = useRoute()

interface Crumb {
  title: string
  path: string
}

const crumbs = computed<Crumb[]>(() => {
  const list: Crumb[] = []
  for (const record of route.matched) {
    const title = record.meta?.title
    if (!title) continue
    if (record.path === '/' || record.path.includes(':')) continue
    list.push({ title, path: record.path })
  }
  // 最后一级不可点击
  return list
})
</script>

<template>
  <ElBreadcrumb class="app-breadcrumb" separator="/">
    <ElBreadcrumbItem :to="{ path: '/dashboard' }">首页</ElBreadcrumbItem>
    <ElBreadcrumbItem
      v-for="(crumb, index) in crumbs"
      :key="crumb.path"
      :to="index === crumbs.length - 1 ? undefined : { path: crumb.path }"
    >
      {{ crumb.title }}
    </ElBreadcrumbItem>
  </ElBreadcrumb>
</template>

<style scoped lang="scss">
.app-breadcrumb {
  font-size: 13px;
}
</style>
