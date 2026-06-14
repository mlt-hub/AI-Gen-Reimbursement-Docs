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
        v-for="step in displaySteps"
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
        <div v-if="templatePreflightPayloads(step).length" class="mt-3 border-t border-[var(--color-rule)] pt-3">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">输出模板</p>
          <div
            v-for="template in templatePreflightTemplates(step)"
            :key="template.kind + template.template_id"
            class="mt-2 grid gap-1 text-xs text-[var(--color-ink-muted)] sm:grid-cols-[5rem_1fr]"
          >
            <span class="font-semibold text-[var(--color-ink)]">{{ templateKindLabel(template.kind) }}</span>
            <span class="min-w-0">
              {{ templateSourceLabel(template) }}
              <template v-if="template.kind === 'spec' && template.capabilities">
                · {{ specAnchorModeLabel(template.capabilities) }}
                · 模块表 {{ specModuleColumnCount(template.capabilities) }} 列
                <template v-if="specSupportsSampleTable(template.capabilities)"> · 样例表</template>
              </template>
            </span>
          </div>
        </div>
        <div v-if="intermediateArtifacts(step).length" class="mt-3 border-t border-[var(--color-rule)] pt-3">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">中间文件</p>
          <div v-for="artifact in intermediateArtifacts(step)" :key="artifact.path || artifact.name" class="mt-2 flex items-center justify-between gap-3 text-xs">
            <span class="min-w-0">
              <span class="block truncate text-[var(--color-ink-muted)]" :title="artifact.path || artifact.name || artifact.label">
                {{ artifact.name || artifact.label }}
              </span>
              <span v-if="artifact.toc_note" class="mt-0.5 block text-[var(--color-ink-soft)]">{{ artifact.toc_note }}</span>
            </span>
            <span class="flex shrink-0 items-center gap-2">
              <span class="rounded bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[var(--color-ink-soft)]">
                中间文件
              </span>
              <button
                v-if="canUseArtifactAction"
                class="btn-secondary min-h-0 shrink-0 px-2 py-1 text-xs"
                @click="useArtifactAction"
              >
                {{ artifactActionLabel }}
              </button>
              <span v-else class="rounded bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[var(--color-ink-soft)]">完成后可操作</span>
            </span>
          </div>
        </div>
        <div v-if="deliveryArtifacts(step).length" class="mt-3 border-t border-[var(--color-rule)] pt-3">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">阶段产物</p>
          <div v-for="artifact in deliveryArtifacts(step)" :key="artifact.path || artifact.name" class="mt-2 flex items-center justify-between gap-3 text-xs">
            <span class="min-w-0">
              <span class="block truncate text-[var(--color-ink-muted)]" :title="artifact.path || artifact.name || artifact.label">
                {{ artifact.name || artifact.label }}
              </span>
              <span v-if="artifact.toc_note" class="mt-0.5 block text-[var(--color-ink-soft)]">{{ artifact.toc_note }}</span>
            </span>
            <span class="flex shrink-0 items-center gap-2">
              <span class="rounded bg-[var(--color-success-soft)] px-1.5 py-0.5 text-[var(--color-success)]">
                交付物
              </span>
              <button
                v-if="canUseArtifactAction"
                class="btn-secondary min-h-0 shrink-0 px-2 py-1 text-xs"
                @click="useArtifactAction"
              >
                {{ artifactActionLabel }}
              </button>
              <span v-else class="rounded bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[var(--color-ink-soft)]">完成后可操作</span>
            </span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStepsStore } from '@/stores/steps.ts'
import type { StepProgress, StepStatus } from '@/stores/steps.ts'
import { useSessionStore } from '@/stores/session.ts'
import { useConfigStore } from '@/stores/config.ts'
import { useToastStore } from '@/stores/toast.ts'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

const props = defineProps<{
  steps?: StepProgress[]
  sessionId?: string
  mode?: 'local' | 'remote'
  isDone?: boolean
}>()

const stepsStore = useStepsStore()
const session = useSessionStore()
const config = useConfigStore()
const toast = useToastStore()
const displaySteps = computed(() => props.steps || stepsStore.steps)
const effectiveSessionId = computed(() => props.sessionId || session.sessionId || '')
const effectiveMode = computed(() => props.mode || config.workMode)
const effectiveIsDone = computed(() => props.isDone ?? session.isDone)

const canUseArtifactAction = computed(() => {
  if (!effectiveSessionId.value) return false
  if (effectiveMode.value === 'local') return true
  return effectiveIsDone.value
})
const artifactActionLabel = computed(() => (
  effectiveMode.value === 'local' ? '打开目录' : '下载 ZIP'
))

interface TemplatePreflightItem {
  kind: string
  template_id?: string
  manifest_path?: string
  source?: string
  capabilities?: Record<string, unknown>
}

interface TemplatePreflightPayload {
  summary_type?: string
  templates?: TemplatePreflightItem[]
}

function statusLabel(status: StepStatus) {
  return {
    pending: '等待中',
    running: '运行中',
    done: '已完成',
    failed: '失败',
    waiting_input: '等待确认',
    cancelled: '已停止',
  }[status]
}

function cardClass(status: StepStatus) {
  return status === 'failed'
    ? 'border-[var(--color-danger)]'
    : status === 'cancelled'
      ? 'border-[var(--color-warning)]'
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
    cancelled: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  }[status]
}

function templatePreflightPayloads(step: StepProgress): TemplatePreflightPayload[] {
  return (step.activity_payloads || [])
    .filter((payload) => payload && payload.summary_type === 'template_preflight') as TemplatePreflightPayload[]
}

function templatePreflightTemplates(step: StepProgress): TemplatePreflightItem[] {
  return templatePreflightPayloads(step).flatMap((payload) => payload.templates || [])
}

function intermediateArtifacts(step: StepProgress) {
  return (step.artifacts || []).filter((artifact) => artifact.is_temp)
}

function deliveryArtifacts(step: StepProgress) {
  return (step.artifacts || []).filter((artifact) => !artifact.is_temp)
}

function templateKindLabel(kind: string) {
  return {
    fpa: 'FPA',
    cosmic: 'COSMIC',
    list: '需求清单',
    spec: '需求说明书',
  }[kind] || kind
}

function templateSourceLabel(template: TemplatePreflightItem) {
  if (template.source === 'manifest') return `manifest：${template.template_id || template.manifest_path || '已加载'}`
  return `默认契约：${template.template_id || '已加载'}`
}

function specAnchorModeLabel(capabilities: Record<string, unknown>) {
  return {
    split: '拆分锚点',
    full: '完整章节锚点',
    legacy_full: '历史完整锚点',
    optional: '可选锚点',
  }[String(capabilities.anchor_mode || '')] || '锚点已配置'
}

function specModuleColumnCount(capabilities: Record<string, unknown>) {
  const moduleTable = capabilities.module_table as Record<string, unknown> | undefined
  return Number(moduleTable?.column_count || 0)
}

function specSupportsSampleTable(capabilities: Record<string, unknown>) {
  const moduleTable = capabilities.module_table as Record<string, unknown> | undefined
  return Boolean(moduleTable?.supports_sample_table)
}

function useArtifactAction() {
  if (!effectiveSessionId.value) return
  if (effectiveMode.value === 'local') {
    apiFetch('/api/open-folder?session=' + effectiveSessionId.value).catch((e) => {
      toast.show('error', normalizeApiError(e))
    })
    return
  }
  if (!effectiveIsDone.value) return
  const a = document.createElement('a')
  a.href = '/api/download/' + effectiveSessionId.value
  a.click()
}
</script>
