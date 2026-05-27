<template>
  <div v-if="stepsStore.steps.length" class="flex items-center gap-2 overflow-x-auto border-b border-[var(--color-rule)] bg-[var(--color-surface)] px-5 py-3">
    <template v-for="(step, i) in stepsStore.steps" :key="step.key">
      <div class="flex items-center gap-2" :class="i > 0 ? 'ml-1' : ''">
        <span v-if="step.state === 'done'" class="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-success)] text-xs font-bold text-white">✓</span>
        <span v-else-if="step.state === 'active'" class="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-accent)] text-xs font-bold text-white">{{ i + 1 }}</span>
        <span v-else class="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-surface-muted)] text-xs text-[var(--color-ink-soft)]">{{ i + 1 }}</span>
        <span :class="['whitespace-nowrap text-xs', step.state === 'active' ? 'font-semibold text-[var(--color-accent-strong)]' : step.state === 'done' ? 'text-[var(--color-success)]' : 'text-[var(--color-ink-soft)]']">
          {{ step.label }}
        </span>
      </div>
      <span v-if="i < stepsStore.steps.length - 1" class="mx-1 h-px w-6 shrink-0 bg-[var(--color-rule-strong)]" :class="step.state === 'done' ? 'bg-[var(--color-success)]' : ''" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useStepsStore } from '@/stores/steps'
const stepsStore = useStepsStore()
</script>
