<template>
  <div class="flex flex-col gap-5">
    <!-- 操作模式选择 -->
    <div>
      <label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">操作模式</label>
      <select v-model="config.pipelineMode"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white">
        <option v-for="(info, value) in modes" :key="value" :value="value">{{ info.label }}</option>
      </select>
      <p class="text-xs text-gray-400 mt-1">{{ modes[config.pipelineMode]?.desc }}</p>
    </div>

    <FileInput />

    <div class="space-y-3">
      <AdvancedOptions />
      <TemplateUpload />
    </div>

    <button @click="$emit('start')"
      :disabled="!config.isValid || session.isRunning"
      class="w-full py-3 bg-primary-500 text-white font-semibold rounded-lg hover:bg-primary-600 disabled:bg-primary-300 disabled:cursor-not-allowed transition-colors text-base">
      开始生成
    </button>

    <p :class="['text-center text-sm font-medium',
      session.runState === 'idle' ? 'text-gray-400' :
      session.runState === 'running' ? 'text-primary-500' :
      session.runState === 'done' ? 'text-green-500' : 'text-red-500']">
      {{ statusText }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useSessionStore } from '@/stores/session'
import FileInput from './FileInput.vue'
import AdvancedOptions from './AdvancedOptions.vue'
import TemplateUpload from './TemplateUpload.vue'

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
</script>
