import type { RunState } from '@/stores/session.ts'
import type { StepProgress } from '@/stores/steps.ts'

export type TaskRunState = RunState | 'closed' | string
export type TaskStatusTone = 'idle' | 'queued' | 'running' | 'done' | 'error' | 'cancelled' | 'warning'

export interface TaskStatusDisplay {
  label: string
  detail: string
  tone: TaskStatusTone
}

const RUN_STATE_LABELS: Record<string, string> = {
  idle: '就绪',
  queued: '排队中',
  running: '运行中',
  done: '已完成',
  error: '出错',
  cancelled: '已停止',
  closed: '已关闭',
}

export const TASK_STATUS_BADGE_CLASSES: Record<TaskStatusTone, string> = {
  idle: 'border-[var(--color-rule)] bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]',
  queued: 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  running: 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]',
  done: 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]',
  error: 'border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]',
  cancelled: 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  warning: 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
}

export const TASK_STATUS_DOT_CLASSES: Record<TaskStatusTone, string> = {
  idle: 'bg-[var(--color-ink-soft)]',
  queued: 'bg-[var(--color-warning)]',
  running: 'bg-[var(--color-accent)]',
  done: 'bg-[var(--color-success)]',
  error: 'bg-[var(--color-danger)]',
  cancelled: 'bg-[var(--color-warning)]',
  warning: 'bg-[var(--color-warning)]',
}

export function selectTaskStatusStep(steps: StepProgress[]): StepProgress | null {
  const active = steps.find(step => step.status === 'running' || step.status === 'waiting_input')
  if (active) return active
  return [...steps]
    .reverse()
    .find(step => step.status !== 'pending' || step.artifacts.length > 0 || Boolean(step.current_action)) || null
}

export function getTaskStatusDisplay(runState: TaskRunState, steps: StepProgress[] = []): TaskStatusDisplay {
  const step = selectTaskStatusStep(steps)
  const state = String(runState || 'idle')
  const isWaitingInput = step?.status === 'waiting_input'
  const stateLabel = isWaitingInput ? '等待确认' : (RUN_STATE_LABELS[state] || state)
  const tone = isWaitingInput ? 'warning' : toneForRunState(state)
  return {
    label: step ? `${stateLabel} · ${step.label}` : stateLabel,
    detail: step?.current_action || '',
    tone,
  }
}

function toneForRunState(state: string): TaskStatusTone {
  if (state === 'queued') return 'queued'
  if (state === 'running') return 'running'
  if (state === 'done') return 'done'
  if (state === 'error') return 'error'
  if (state === 'cancelled') return 'cancelled'
  return 'idle'
}
