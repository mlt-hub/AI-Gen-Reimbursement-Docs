<template>
  <details class="group" @toggle="onToggle">
    <summary class="subtle-link cursor-pointer select-none text-sm">下载模板</summary>
    <div class="mt-3 flex flex-col gap-2 border-t border-[var(--color-rule)] pt-3">
      <p class="text-xs font-semibold text-[var(--color-ink-soft)]">录入模板</p>
      <a href="/api/templates/input"
        class="flex items-center gap-1 text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-accent-strong)]">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        功能清单-录入模板.xlsx
      </a>
      <p class="mt-2 text-xs font-semibold text-[var(--color-ink-soft)]">输出模板</p>
      <div v-if="loading" class="text-xs text-[var(--color-ink-soft)]">加载中...</div>
      <template v-else>
        <a v-for="t in templates" :key="t" :href="'/api/templates/output/' + t"
          class="flex items-center gap-1 text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-accent-strong)]">
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
