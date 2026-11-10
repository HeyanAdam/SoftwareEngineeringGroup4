<template>
  <div class="chat-page">
    <el-card shadow="never">
      <el-empty description="AI 问答由业务模块（ai_chat）提供，接入后即可在此对话" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
// 占位页：业务模块代码不在本鉴权交付包内，这里只保证路由可进入、可构建。
</script>

<style scoped lang="scss">
.chat-page {
  padding: 4px;
}
</style>
