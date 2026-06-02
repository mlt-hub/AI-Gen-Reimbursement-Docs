<template>
  <section class="min-h-0 flex-1 overflow-y-auto bg-[var(--color-page)] p-4 sm:p-5">
    <div class="mb-3 flex items-center justify-between gap-3">
      <div>
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">生成过程</p>
        <h3 class="mt-1 text-base font-bold text-[var(--color-ink)]">阶段进展与产物</h3>
      </div>
      <span class="text-xs text-[var(--color-ink-soft)]">按实际动作更新，不展示估算百分比</span>
    </div>
    <div class="grid gap-3 xl:grid-cols-2">
      <article
        v-for="step in stepsStore.steps"
        :key="step.key"
        class="rounded-lg border bg-[var(--color-surface)] p-4"
        :class="cardClass(step.status)"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <h4 class="text-sm font-bold text-[var(--color-ink)]">{{ step.label }}</h4>
            <p class="mt-1 text-xs text-[var(--color-ink-muted)]">
              {{ step.current_action || '等待前序阶段完成' }}
            </p>
          </div>
          <span class="shrink-0 rounded-md px-2 py-1 text-xs font-semibold" :class="badgeClass(step.status)">
            {{ statusLabel(step.status) }}
          </span>
        </div>
        <p v-if="step.error" class="mt-3 rounded-md bg-[var(--color-danger-soft)] px-3 py-2 text-xs text-[var(--color-danger)]">
          {{ step.error }}
        </p>
        <div v-if="step.artifacts.length" class="mt-3 border-t border-[var(--color-rule)] pt-3">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">阶段产物</p>
          <div v-for="artifact in step.artifacts" :key="artifact.path || artifact.name" class="mt-2 flex items-center justify-between gap-3 text-xs">
            <span class="min-w-0 truncate text-[var(--color-ink-muted)]">{{ artifact.name || artifact.label }}</span>
            <span v-if="artifact.is_temp" class="shrink-0 rounded bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[var(--color-ink-soft)]">中间文件</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useStepsStore } from '@/stores/steps.ts'
import type { StepStatus } from '@/stores/steps.ts'

const stepsStore = useStepsStore()

function statusLabel(status: StepStatus) {
  return {
    pending: '等待中',
    running: '运行中',
    done: '已完成',
    failed: '失败',
    waiting_input: '等待确认',
  }[status]
}

function cardClass(status: StepStatus) {
  return status === 'failed'
    ? 'border-[var(--color-danger)]'
    : status === 'running' || status === 'waiting_input'
      ? 'border-[var(--color-accent)]'
      : 'border-[var(--color-rule)]'
}

function badgeClass(status: StepStatus) {
  return {
    pending: 'bg-[var(--color-surface-muted)] text-[var(--color-ink-soft)]',
    running: 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]',
    done: 'bg-[var(--color-success-soft)] text-[var(--color-success)]',
    failed: 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]',
    waiting_input: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  }[status]
}
</script>
