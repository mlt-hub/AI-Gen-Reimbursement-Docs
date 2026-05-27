<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 日志级别过滤 -->
    <div class="flex items-center justify-between gap-3 border-b border-[var(--color-console-line)] bg-[var(--color-console)] px-5 py-2">
      <span class="text-xs font-semibold text-slate-400">运行日志</span>
      <div class="flex items-center gap-2">
      <span class="text-xs text-slate-500">显示级别</span>
      <select v-model="filterLevel" @change="saveLevel"
        class="rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-200 focus:border-[var(--color-focus)] focus:outline-none">
        <option v-for="lv in levels" :key="lv" :value="lv">{{ lv }}</option>
      </select>
      </div>
    </div>
    <!-- 日志列表 -->
    <div ref="logEl" class="flex-1 overflow-y-auto bg-[var(--color-console)] p-5 font-mono text-sm leading-6">
      <div v-if="logStore.entries.length === 0" class="flex h-full items-center justify-center text-sm text-slate-500">
        等待任务启动，实时日志将在此处显示
      </div>
      <template v-for="(entry, i) in filteredEntries" :key="i">
        <div v-if="entry.level === 'DONE'"
          class="my-2 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-center font-semibold text-emerald-300">
          {{ entry.msg }}
        </div>
        <div v-else class="flex gap-3 py-0.5" :class="{ 'mt-3': entry.isStep }">
          <span class="w-20 shrink-0 text-slate-500">{{ entry.time }}</span>
          <span :class="['shrink-0 w-14 font-semibold', levelColor(entry.level)]">{{ entry.level }}</span>
          <span :class="['break-all whitespace-pre-wrap text-slate-300', { 'font-semibold text-amber-300': entry.isStep }]">{{ entry.msg }}</span>
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
