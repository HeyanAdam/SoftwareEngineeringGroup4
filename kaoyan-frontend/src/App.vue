<template>
  <div style="padding: 40px; font-family: sans-serif;">
    <h1>考研AI导学平台</h1>
    <button @click="callBackend" style="padding: 10px 20px; font-size: 16px;">
      点我调用后端
    </button>
    <p v-if="result" style="margin-top: 20px; color: green; font-size: 18px;">
      后端返回：{{ result }}
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const result = ref('')

async function callBackend() {
  const res = await fetch('http://127.0.0.1:8001/api/hello')
  const data = await res.json()
  result.value = data.message
}
</script>