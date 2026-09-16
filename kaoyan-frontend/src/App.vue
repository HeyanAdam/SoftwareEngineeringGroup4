<template>
  <!-- 应用外壳：所有页面（含登录页与带布局的业务页）都通过路由渲染 -->
  <router-view />
</template>

<script setup lang="ts">
// App.vue 只作为路由出口，具体布局见 src/layouts/DefaultLayout.vue
</script>

<style>
/* 全局基础样式 */
* {
  box-sizing: border-box;
}

html,
body,
#app {
  height: 100%;
  margin: 0;
  padding: 0;
}

body {
  font-family:
    'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial,
    sans-serif;
  color: #303133;
  background-color: #f5f7fa;
}
</style>
