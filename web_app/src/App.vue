<template>
  <div class="flex flex-col h-screen">
    <header class="bg-gray-50 border-b border-gray-100 px-6 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <h1 class="text-lg font-semibold text-gray-800">AI 生成项目报账文档</h1>
        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{{ modeLabel }}</span>
        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">v{{ version }}</span>
      </div>
      <nav class="flex items-center gap-4 text-sm">
        <router-link to="/" class="text-gray-500 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">生成</router-link>
        <router-link to="/config" class="text-gray-500 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">配置</router-link>
        <router-link to="/prompt-debug" class="text-gray-500 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">提示词调试</router-link>
      </nav>
    </header>
    <main class="flex-1 min-h-0">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useConfigStore } from '@/stores/config'

const config = useConfigStore()
const version = ref('-')

const modeLabel = computed(() => config.workMode === 'local' ? '本机模式' : '远程服务模式')

onMounted(async () => {
  try {
    const [verResp, modeResp, localResp] = await Promise.all([
      fetch('/api/version'),
      fetch('/api/default-work-mode'),
      fetch('/api/is-local')
    ])
    const verData = await verResp.json()
    version.value = verData.version
    const modeData = await modeResp.json()
    if (modeData.work_mode === 'local' || modeData.work_mode === 'remote') {
      config.workMode = modeData.work_mode
    } else {
      const localData = await localResp.json()
      config.workMode = localData.local ? 'local' : 'remote'
    }
  } catch {
    version.value = '-'
  }
})
</script>
