import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export type StepStatus = 'pending' | 'running' | 'done' | 'failed' | 'waiting_input' | 'cancelled'

export interface StepArtifact {
  label?: string
  name?: string
  path?: string
  is_temp?: boolean
}

export interface StepProgress {
  key: string
  label: string
  status: StepStatus
  current_action: string
  activity_payloads: Record<string, unknown>[]
  artifacts: StepArtifact[]
  started_at?: string | null
  finished_at?: string | null
  error?: string
}

export interface PipelineEvent {
  type: string
  step?: string
  key?: string
  message?: string
  payload?: Record<string, unknown>
}

const STEP_ORDER = ['basedata', 'fpa', 'spec', 'cosmic', 'list']
const STEP_LABELS: Record<string, string> = {
  basedata: '读取基础数据',
  fpa: '生成 FPA',
  spec: '生成需求说明书',
  cosmic: '生成 COSMIC',
  list: '生成需求清单',
}

function createStep(key: string): StepProgress {
  return {
    key,
    label: STEP_LABELS[key] || key,
    status: 'pending',
    current_action: '',
    activity_payloads: [],
    artifacts: [],
    started_at: null,
    finished_at: null,
    error: '',
  }
}

export const useStepsStore = defineStore('steps', () => {
  const byKey = ref<Record<string, StepProgress>>(
    Object.fromEntries(STEP_ORDER.map((key) => [key, createStep(key)])),
  )

  const steps = computed<StepProgress[]>(() => STEP_ORDER.map((key) => byKey.value[key] || createStep(key)))
  const hasProgress = computed(() => steps.value.some((step) => step.status !== 'pending' || step.artifacts.length > 0))

  function upsert(key: string): StepProgress {
    if (!byKey.value[key]) {
      byKey.value = { ...byKey.value, [key]: createStep(key) }
    }
    return byKey.value[key]
  }

  function setActive(key: string) {
    const step = upsert(key)
    if (step.status !== 'done') {
      step.status = 'running'
      step.started_at = step.started_at || new Date().toISOString()
    }
  }

  function handlePipelineEvent(event: PipelineEvent) {
    const key = event.step || event.key
    if (!key) return
    const step = upsert(key)
    switch (event.type) {
      case 'step':
        setActive(key)
        return
      case 'step_started':
        step.status = 'running'
        step.started_at = new Date().toISOString()
        step.finished_at = null
        step.error = ''
        if (event.message) step.current_action = event.message
        return
      case 'activity':
        step.current_action = event.message || step.current_action
        if (event.payload && !step.activity_payloads.includes(event.payload)) {
          step.activity_payloads.push(event.payload)
        }
        return
      case 'artifact':
        if (event.payload) {
          const artifact = event.payload as StepArtifact
          if (!step.artifacts.some((item) => item.path === artifact.path && item.label === artifact.label)) {
            step.artifacts.push(artifact)
          }
        }
        return
      case 'input_required':
        step.status = 'waiting_input'
        step.current_action = event.message || '等待用户确认'
        return
      case 'step_done':
        step.status = 'done'
        step.current_action = event.message || step.current_action
        step.finished_at = new Date().toISOString()
        return
      case 'step_failed':
        step.status = 'failed'
        step.error = event.message || '阶段失败'
        step.finished_at = new Date().toISOString()
        return
      case 'step_cancelled':
        step.status = 'cancelled'
        step.current_action = event.message || '任务已被用户停止'
        step.finished_at = new Date().toISOString()
        return
    }
  }

  function applySnapshot(progressSteps: Record<string, Partial<StepProgress>> | StepProgress[] | undefined) {
    reset()
    const items = Array.isArray(progressSteps)
      ? progressSteps
      : Object.values(progressSteps || {})
    for (const item of items) {
      if (!item.key) continue
      byKey.value[item.key] = {
        ...createStep(item.key),
        ...item,
        label: STEP_LABELS[item.key] || item.label || item.key,
        activity_payloads: item.activity_payloads || [],
        artifacts: item.artifacts || [],
      }
    }
  }

  function finishAll() {
    const now = new Date().toISOString()
    for (const step of steps.value) {
      if (step.status === 'running' || step.status === 'waiting_input') {
        step.status = 'done'
        step.finished_at = now
      }
    }
  }

  function failActive(message: string) {
    const active = steps.value.find((step) => step.status === 'running' || step.status === 'waiting_input')
    if (!active) return
    active.status = 'failed'
    active.error = message
    active.finished_at = new Date().toISOString()
  }

  function cancelActive(message: string) {
    const active = steps.value.find((step) => step.status === 'running' || step.status === 'waiting_input')
    if (!active) return
    active.status = 'cancelled'
    active.current_action = message
    active.finished_at = new Date().toISOString()
  }

  function reset() {
    byKey.value = Object.fromEntries(STEP_ORDER.map((key) => [key, createStep(key)]))
  }

  return { steps, hasProgress, setActive, handlePipelineEvent, applySnapshot, finishAll, failActive, cancelActive, reset }
})
