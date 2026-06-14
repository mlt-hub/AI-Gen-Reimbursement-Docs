<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 日志级别过滤 -->
    <div
      :class="[
        'flex items-center justify-between gap-3 border-b px-5 py-2',
        hasEntries
          ? 'border-[var(--color-console-line)] bg-[var(--color-console)]'
          : 'border-[var(--color-rule)] bg-[var(--color-surface-raised)]',
      ]"
    >
      <span :class="['text-xs font-semibold', hasEntries ? 'text-slate-400' : 'text-[var(--color-ink-muted)]']">运行日志</span>
      <div class="flex items-center gap-2">
        <span :class="['text-xs', hasEntries ? 'text-slate-500' : 'text-[var(--color-ink-soft)]']">显示级别</span>
        <select v-model="filterLevel" @change="saveLevel"
          :class="[
            'rounded-md border px-2 py-1 text-xs focus:border-[var(--color-focus)] focus:outline-none',
            hasEntries
              ? 'border-slate-600 bg-slate-800 text-slate-200'
              : 'border-[var(--color-rule-strong)] bg-[var(--color-surface)] text-[var(--color-ink-muted)]',
          ]">
          <option v-for="lv in levels" :key="lv" :value="lv">{{ lv }}</option>
        </select>
        <span class="text-xs text-[var(--color-ink-soft)]">
          {{ filterLevel === 'DEBUG' ? '显示全部日志' : 'DEBUG 已隐藏' }}
        </span>
      </div>
    </div>
    <!-- 日志列表 -->
    <div
      ref="logEl"
      :class="[
        'flex-1 overflow-y-auto p-5 text-sm leading-6',
        hasEntries ? 'bg-[var(--color-console)] font-mono' : 'bg-[var(--color-surface-raised)]',
      ]"
    >
      <div v-if="!hasEntries" class="flex h-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-8 text-center text-sm text-[var(--color-ink-muted)]">
        <p class="font-semibold text-[var(--color-ink)]">等待任务启动</p>
        <p class="max-w-md leading-5">实时日志会在生成任务开始后显示。当前可以先填写主操作区参数并启动生成。</p>
        <p v-if="config.backendStatus === 'offline'" class="text-xs text-[var(--color-warning)]">未检测到后端服务，启动后端后才可运行生成任务。</p>
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
import { useLogStore } from '@/stores/log.ts'
import { useToastStore } from '@/stores/toast.ts'
import { useConfigStore } from '@/stores/config.ts'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface LogLevelResponse {
  level?: string
}

const logStore = useLogStore()
const toast = useToastStore()
const config = useConfigStore()
const logEl = ref<HTMLElement | null>(null)
const filterLevel = ref('INFO')
const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']

const levelOrder: Record<string, number> = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3, DONE: -1 }
const hasEntries = computed(() => logStore.entries.length > 0)

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
    const data = await apiFetch<LogLevelResponse>('/api/log-level')
    if (data.level && levels.includes(data.level)) filterLevel.value = data.level
  } catch {}
})

async function saveLevel() {
  try {
    await apiFetch('/api/log-level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: filterLevel.value }),
    })
  } catch (e) {
    toast.show('error', normalizeApiError(e))
  }
}

function levelColor(level: string) {
  const map: Record<string, string> = {
    INFO: 'text-blue-400',
    DEBUG: 'text-slate-400',
    WARNING: 'text-yellow-400',
    ERROR: 'text-red-400',
    DONE: 'text-green-400',
  }
  return map[level] || 'text-slate-300'
}
</script>
