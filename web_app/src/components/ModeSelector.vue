<template>
  <div>
    <label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">使用方式</label>
    <div class="flex bg-gray-100 rounded-lg p-1">
      <button v-for="m in modes" :key="m.key"
        @click="config.workMode = m.key"
        :class="['flex-1 py-2 text-sm rounded-md font-medium transition-all',
          config.workMode === m.key ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">
        {{ m.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useConfigStore } from '@/stores/config'

const config = useConfigStore()
const modes = [
  { key: 'local', label: '本机' },
  { key: 'remote', label: '远程' },
] as const
</script>
