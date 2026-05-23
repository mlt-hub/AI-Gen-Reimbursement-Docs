<template>
  <div v-if="stepsStore.steps.length" class="flex items-center gap-1 px-2 py-3">
    <template v-for="(step, i) in stepsStore.steps" :key="step.key">
      <div class="flex items-center gap-1.5" :class="i > 0 ? 'ml-1' : ''">
        <span v-if="step.state === 'done'" class="w-5 h-5 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold">✓</span>
        <span v-else-if="step.state === 'active'" class="w-5 h-5 rounded-full bg-primary-500 text-white flex items-center justify-center text-xs font-bold animate-pulse">{{ i }}</span>
        <span v-else class="w-5 h-5 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center text-xs">{{ i }}</span>
        <span :class="['text-xs whitespace-nowrap', step.state === 'active' ? 'text-primary-600 font-medium' : step.state === 'done' ? 'text-green-600' : 'text-gray-400']">
          {{ step.label }}
        </span>
      </div>
      <span v-if="i < stepsStore.steps.length - 1" class="w-4 h-px bg-gray-200 mx-0.5 shrink-0" :class="step.state === 'done' ? 'bg-green-300' : ''" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useStepsStore } from '@/stores/steps'
const stepsStore = useStepsStore()
</script>
