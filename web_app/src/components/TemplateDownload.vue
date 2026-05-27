<template>
  <details class="group" @toggle="onToggle">
    <summary class="text-sm text-primary-600 cursor-pointer select-none hover:text-primary-700 font-medium">下载模板</summary>
    <div class="flex flex-col gap-2 mt-3 pt-3 border-t border-gray-100">
      <p class="text-xs text-gray-400">录入模板</p>
      <a href="/api/templates/input"
        class="text-xs text-gray-500 hover:text-primary-600 flex items-center gap-1">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        功能清单-录入模板.xlsx
      </a>
      <p class="text-xs text-gray-400 mt-2">输出模板</p>
      <div v-if="loading" class="text-xs text-gray-400">加载中...</div>
      <template v-else>
        <a v-for="t in templates" :key="t" :href="'/api/templates/output/' + t"
          class="text-xs text-gray-500 hover:text-primary-600 flex items-center gap-1">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {{ t }}
        </a>
      </template>
    </div>
  </details>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const templates = ref<string[]>([])
const loading = ref(true)

async function load() {
  try {
    const resp = await fetch('/api/templates/output')
    if (resp.ok) {
      const data = await resp.json()
      templates.value = data.templates || []
    }
  } catch { /* 忽略 */ }
  loading.value = false
}

// details toggle 事件，打开时加载
function onToggle(e: Event) {
  const el = e.target as HTMLDetailsElement
  if (el.open) load()
}
</script>
