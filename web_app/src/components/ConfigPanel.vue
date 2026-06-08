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

    <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-stretch">
      <button @click="$emit('start')"
        :disabled="!config.isValid || session.isRunning || config.backendStatus === 'offline'"
        class="btn-primary w-full text-base">
        <PlayIcon class="h-4 w-4" />
        开始生成
      </button>

      <router-link
        to="/preview/fpa"
        class="btn-secondary w-full text-sm sm:w-auto"
      >
        <EyeIcon class="h-4 w-4" />
        预览 FPA 功能点
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useConfigStore } from '@/stores/config.ts'
import { useSessionStore } from '@/stores/session.ts'
import FileInput from './FileInput.vue'
import { apiFetch } from '@/lib/api.ts'
import { EyeIcon, PlayIcon } from '@heroicons/vue/24/outline'

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
</script>
