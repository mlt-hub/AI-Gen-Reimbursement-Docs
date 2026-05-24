<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 日志级别过滤 -->
    <div class="flex items-center gap-2 px-4 py-1.5 bg-gray-800 border-b border-gray-700">
      <span class="text-xs text-gray-500">显示级别</span>
      <select v-model="filterLevel" @change="saveLevel"
        class="bg-gray-700 border border-gray-600 rounded text-xs text-gray-300 px-2 py-0.5 focus:outline-none focus:border-primary-500">
        <option v-for="lv in levels" :key="lv" :value="lv">{{ lv }}</option>
      </select>
    </div>
    <!-- 日志列表 -->
    <div ref="logEl" class="flex-1 overflow-y-auto bg-gray-900 p-5 font-mono text-sm leading-6">
      <div v-if="logStore.entries.length === 0" class="flex items-center justify-center h-full text-gray-500 text-sm">
        选择操作模式并开始生成，实时日志将显示在此处
      </div>
      <template v-for="(entry, i) in filteredEntries" :key="i">
        <div v-if="entry.level === 'DONE'"
          class="text-center py-2 px-4 text-green-400 font-semibold border-t border-b border-green-400/30 my-1">
          {{ entry.msg }}
        </div>
        <div v-else class="flex gap-3 py-0.5">
          <span class="text-gray-500 shrink-0 w-20">{{ entry.time }}</span>
          <span :class="['shrink-0 w-14 font-semibold', levelColor(entry.level)]">{{ entry.level }}</span>
          <span class="text-gray-300 break-all">{{ entry.msg }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watchEffect, onMounted } from 'vue'
import { useLogStore } from '@/stores/log'

const logStore = useLogStore()
const logEl = ref<HTMLElement | null>(null)
const filterLevel = ref('INFO')
const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']

const levelOrder: Record<string, number> = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3, DONE: -1 }

const filteredEntries = computed(() => {
  const min = levelOrder[filterLevel.value] ?? 1
  return logStore.entries.filter(e => {
    const lv = levelOrder[e.level]
    return lv === undefined || lv < 0 || lv >= min
  })
})

watchEffect(() => {
  logStore.logPanelEl = logEl.value
})

onMounted(async () => {
  try {
    const resp = await fetch('/api/log-level')
    const data = await resp.json()
    if (levels.includes(data.level)) filterLevel.value = data.level
  } catch {}
})

async function saveLevel() {
  await fetch('/api/log-level', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level: filterLevel.value }),
  }).catch(() => {})
}

function levelColor(level: string) {
  const map: Record<string, string> = {
    INFO: 'text-blue-400',
    DEBUG: 'text-gray-400',
    WARNING: 'text-yellow-400',
    ERROR: 'text-red-400',
    DONE: 'text-green-400',
  }
  return map[level] || 'text-gray-300'
}
</script>
