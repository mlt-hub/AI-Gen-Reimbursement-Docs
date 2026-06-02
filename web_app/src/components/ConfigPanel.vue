<template>
  <div class="flex w-full max-w-full min-w-0 flex-col gap-5">
    <div v-if="config.backendStatus === 'offline'" class="min-w-0 max-w-full break-words rounded-lg border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-sm text-[var(--color-warning)]">
      <div class="font-semibold">后端服务未连接</div>
      <p class="mt-1 leading-5">当前只能查看界面。启动后端服务后可运行生成任务。</p>
    </div>

    <!-- 操作模式选择 -->
    <div>
      <label class="field-label">操作模式</label>
      <select v-model="config.pipelineMode"
        class="field-control"
        :disabled="config.backendStatus === 'offline' && modesOffline">
        <option v-for="(info, value) in modes" :key="value" :value="value">{{ info.label }}</option>
      </select>
      <p class="mt-2 text-xs leading-5 text-[var(--color-ink-soft)]">{{ modes[config.pipelineMode]?.desc }}</p>
    </div>

    <FileInput />

    <router-link
      to="/preview/fpa"
      class="group rounded-lg border border-[var(--color-accent)] bg-[var(--color-accent-soft)] px-3 py-3 transition-colors hover:bg-[var(--color-surface-raised)]"
    >
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="text-sm font-semibold text-[var(--color-accent-strong)]">预览 FPA 功能点</div>
          <p class="mt-1 text-xs leading-5 text-[var(--color-ink-muted)]">按当前输入和 FPA 方案先生成可审阅的功能点估算。</p>
        </div>
        <span class="shrink-0 text-lg font-semibold text-[var(--color-accent-strong)] transition-transform group-hover:translate-x-0.5">→</span>
      </div>
    </router-link>

    <div class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3">
      <AdvancedOptions />
      <TemplateUpload />
      <TemplateDownload />
    </div>

    <button @click="$emit('start')"
      :disabled="!config.isValid || session.isRunning || config.backendStatus === 'offline'"
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
import { useConfigStore } from '@/stores/config.ts'
import { useSessionStore } from '@/stores/session.ts'
import FileInput from './FileInput.vue'
import AdvancedOptions from './AdvancedOptions.vue'
import TemplateUpload from './TemplateUpload.vue'
import TemplateDownload from './TemplateDownload.vue'
import { apiFetch } from '@/lib/api.ts'

import { ref, onMounted } from 'vue'

defineEmits<{ start: [] }>()

const config = useConfigStore()
const session = useSessionStore()

const fallbackModes: Record<string, { label: string; desc: string }> = {
  'from-excel-gen-all': { label: '全套报账文档', desc: '生成完整报账文档。' },
  'from-excel-gen-basedata': { label: '基础数据', desc: '仅生成基础数据文件。' },
  'from-excel-gen-fpa': { label: 'FPA 工作量评估', desc: '仅生成 FPA 工作量评估。' },
  'from-excel-gen-spec': { label: '项目需求说明书', desc: '仅生成项目需求说明书。' },
  'from-excel-gen-cosmic': { label: 'COSMIC 估算', desc: '仅生成 COSMIC 相关文档。' },
  'from-excel-gen-list': { label: '项目需求清单', desc: '仅生成项目需求清单。' },
}

const modes = ref<Record<string, { label: string; desc: string }>>(fallbackModes)
const modesOffline = ref(false)

onMounted(async () => {
  try {
    modes.value = await apiFetch<Record<string, { label: string; desc: string }>>('/api/modes')
    modesOffline.value = false
  } catch {
    modes.value = fallbackModes
    modesOffline.value = true
  }
})

const statusText = computed(() => {
  const map = { idle: '就绪', running: '运行中...', done: '完成', error: '出错', cancelled: '已停止' }
  return map[session.runState]
})

const statusClass = computed(() => {
  const map = {
    idle: 'text-[var(--color-ink-soft)]',
    running: 'text-[var(--color-accent-strong)]',
    done: 'text-[var(--color-success)]',
    error: 'text-[var(--color-danger)]',
    cancelled: 'text-[var(--color-warning)]',
  }
  return map[session.runState]
})
</script>
