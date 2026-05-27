<template>
  <div class="flex flex-col gap-5">
    <!-- 操作模式选择 -->
    <div>
      <label class="field-label">操作模式</label>
      <select v-model="config.pipelineMode"
        class="field-control">
        <option v-for="(info, value) in modes" :key="value" :value="value">{{ info.label }}</option>
      </select>
      <p class="mt-2 text-xs leading-5 text-[var(--color-ink-soft)]">{{ modes[config.pipelineMode]?.desc }}</p>
    </div>

    <FileInput />

    <div class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3">
      <AdvancedOptions />
      <TemplateUpload />
      <TemplateDownload />
    </div>

    <button @click="$emit('start')"
      :disabled="!config.isValid || session.isRunning"
      class="btn-primary w-full text-base">
      开始生成
    </button>

    <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2 text-sm">
      <div class="flex items-center justify-between gap-3">
        <span class="text-[var(--color-ink-muted)]">任务状态</span>
        <span :class="['font-semibold', statusClass]">{{ statusText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useSessionStore } from '@/stores/session'
import FileInput from './FileInput.vue'
import AdvancedOptions from './AdvancedOptions.vue'
import TemplateUpload from './TemplateUpload.vue'
import TemplateDownload from './TemplateDownload.vue'

import { ref, onMounted } from 'vue'

defineEmits<{ start: [] }>()

const config = useConfigStore()
const session = useSessionStore()

const modes = ref<Record<string, { label: string; desc: string }>>({})

onMounted(async () => {
  try {
    const resp = await fetch('/api/modes')
    modes.value = await resp.json()
  } catch {
    modes.value = {}
  }
})

const statusText = computed(() => {
  const map = { idle: '就绪', running: '运行中...', done: '完成', error: '出错' }
  return map[session.runState]
})

const statusClass = computed(() => {
  const map = {
    idle: 'text-[var(--color-ink-soft)]',
    running: 'text-[var(--color-accent-strong)]',
    done: 'text-[var(--color-success)]',
    error: 'text-[var(--color-danger)]',
  }
  return map[session.runState]
})
</script>
