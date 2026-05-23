<template>
  <div ref="logEl" class="flex-1 overflow-y-auto bg-gray-900 p-5 font-mono text-sm leading-6">
    <div v-if="logStore.entries.length === 0" class="flex items-center justify-center h-full text-gray-500 text-sm">
      选择操作模式并开始生成，实时日志将显示在此处
    </div>
    <div v-for="(entry, i) in logStore.entries" :key="i"
      :class="entry.level === 'DONE'
        ? 'text-center py-2 px-4 text-green-400 font-semibold border-t border-b border-green-400/30 my-1'
        : 'flex gap-3 py-0.5'">
      <template v-if="entry.level !== 'DONE'">
        <span class="text-gray-500 shrink-0 w-20">{{ entry.time }}</span>
        <span :class="['shrink-0 w-14 font-semibold', levelColor(entry.level)]">{{ entry.level }}</span>
        <span class="text-gray-300 break-all">{{ entry.msg }}</span>
      </template>
      <template v-else>
        {{ entry.msg }}
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import { useLogStore } from '@/stores/log'

const logStore = useLogStore()
const logEl = ref<HTMLElement | null>(null)

watchEffect(() => {
  logStore.logPanelEl = logEl.value
})

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
