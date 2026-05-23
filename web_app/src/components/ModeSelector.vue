<template>
  <div>
    <label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">使用方式</label>
    <div class="flex bg-gray-100 rounded-lg p-1">
      <button v-if="isLocal" @click="config.workMode = 'local'"
        :class="['flex-1 py-2 text-sm rounded-md font-medium transition-all',
          config.workMode === 'local' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">
        本机
      </button>
      <button @click="config.workMode = 'remote'"
        :class="['flex-1 py-2 text-sm rounded-md font-medium transition-all',
          config.workMode === 'remote' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">
        远程
      </button>
    </div>
    <p v-if="!isLocal" class="text-xs text-gray-400 mt-1">非本机访问，仅支持远程上传模式</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/config'

const config = useConfigStore()
const isLocal = ref(true)

onMounted(async () => {
  try {
    const resp = await fetch('/api/is-local')
    const data = await resp.json()
    isLocal.value = data.local
    if (!data.local) {
      config.workMode = 'remote'
    }
  } catch {
    isLocal.value = true
  }
})
</script>
