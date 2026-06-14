import { ref, nextTick } from 'vue'
import { defineStore } from 'pinia'
import { useSessionStore } from './session.ts'
import type { DoneFile, FpaConfirmationQuestion } from './session.ts'
import { useStepsStore } from './steps.ts'
import type { PipelineEvent } from './steps.ts'
import { useToastStore } from './toast.ts'

export interface LogEntry {
  level: string
  msg: string
  time: string
  isStep?: boolean
}

export interface RawLogEvent {
  type?: string
  level?: string
  msg?: string
  message?: string
  time?: string
  step?: string
  field?: string
  default?: number
  cfp_default?: number
  fpa_default?: number
  confirmation_mode?: string
  module?: Record<string, unknown>
  payload?: Record<string, unknown>
  key?: string
  files?: DoneFile[]
  confirmation_questions?: FpaConfirmationQuestion[]
}

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])
  const eventSource = ref<EventSource | null>(null)
  const logPanelEl = ref<HTMLElement | null>(null)
  const activeSessionId = ref<string | null>(null)
  let _wasConnected = false

  function append(entry: LogEntry) {
    // 以"第N"开头的日志行为步骤行
    entry.isStep = /^第\d/.test(entry.msg)
    entries.value.push(entry)
    nextTick(() => {
      if (logPanelEl.value) {
        logPanelEl.value.scrollTop = logPanelEl.value.scrollHeight
      }
    })
  }

  function clear() {
    entries.value = []
  }

  function formatEvent(event: RawLogEvent): LogEntry {
    const type = String(event.type || '')
    if (type === 'done') return { level: 'DONE', msg: '── 任务完成 ──', time: event.time || '' }
    if (type === 'cancelled') return { level: 'WARNING', msg: '── 任务已被用户停止 ──', time: event.time || '' }
    if (type === 'error') return { level: 'ERROR', msg: `── 任务失败: ${event.msg || '未知错误'} ──`, time: event.time || '' }
    if (type === 'prompt') return { level: 'INFO', msg: `等待输入：${event.msg || ''}`, time: event.time || '' }
    if (type === 'prompt_list') return { level: 'INFO', msg: '等待确认送审工作量和送审功能点', time: event.time || '' }
    if (type === 'fpa_confirmation_required') return { level: 'INFO', msg: '等待确认 FPA 计量口径', time: event.time || '' }
    if (type.startsWith('step') || ['activity', 'artifact', 'input_required'].includes(type)) {
      return { level: 'INFO', msg: `${event.step || '阶段'}：${event.message || type}`, time: event.time || '' }
    }
    return {
      level: event.level || 'INFO',
      msg: event.msg || event.message || '',
      time: event.time || '',
    }
  }

  function replaceFromEvents(events: RawLogEvent[]) {
    entries.value = events.map(formatEvent).map((entry) => ({
      ...entry,
      isStep: /^第\d/.test(entry.msg),
    }))
    nextTick(() => {
      if (logPanelEl.value) {
        logPanelEl.value.scrollTop = logPanelEl.value.scrollHeight
      }
    })
  }

  function connect(sessionId?: string) {
    const session = useSessionStore()
    const targetSessionId = sessionId || session.sessionId
    if (!targetSessionId) return
    close()
    _wasConnected = false
    activeSessionId.value = targetSessionId
    const es = new EventSource('/api/log-stream?session=' + targetSessionId)
    es.onmessage = (e) => {
      try {
        if (activeSessionId.value !== targetSessionId || session.sessionId !== targetSessionId) return
        if (!_wasConnected) {
          _wasConnected = true
        }
        const data = JSON.parse(e.data) as RawLogEvent
        switch (data.type) {
          case 'done':
            close()
            append({ level: 'DONE', msg: '── 任务完成 ──', time: '' })
            session.finish(data.files || [])
            useStepsStore().finishAll()
            return
          case 'error':
            close()
            append({ level: 'ERROR', msg: `── 任务失败: ${data.msg || '未知错误'} ──`, time: '' })
            session.setError()
            useStepsStore().failActive(data.msg || '任务失败')
            return
          case 'cancelled':
            close()
            append({ level: 'WARNING', msg: '── 任务已被用户停止 ──', time: '' })
            session.setCancelled()
            useStepsStore().cancelActive('任务已被用户停止')
            return
          case 'prompt':
            append({ level: 'INFO', msg: `⏸ ${data.msg || '等待用户输入...'}`, time: data.time || '' })
            session.showInputPrompt({
              sessionId: targetSessionId,
              field: data.field || '',
              default: data.default || 0,
              msg: data.msg || '',
            })
            return
          case 'prompt_list':
            append({ level: 'INFO', msg: '⏸ 等待确认送审工作量和送审功能点...', time: data.time || '' })
            session.showListPrompt({
              sessionId: targetSessionId,
              cfpDefault: data.cfp_default || 0,
              fpaDefault: data.fpa_default || 0,
            })
            return
          case 'fpa_confirmation_required':
            append({ level: 'INFO', msg: '⏸ 等待确认 FPA 计量口径...', time: data.time || '' })
            session.showFpaConfirmationPrompt({
              sessionId: targetSessionId,
              confirmationMode: data.confirmation_mode || 'auto',
              module: data.module || {},
              questions: data.confirmation_questions || [],
            })
            return
          case 'step':
            useStepsStore().handlePipelineEvent(data as PipelineEvent)
            return
          case 'step_started':
          case 'activity':
          case 'artifact':
          case 'input_required':
          case 'step_done':
          case 'step_failed':
          case 'step_cancelled':
            useStepsStore().handlePipelineEvent(data as PipelineEvent)
            return
          case 'log':
            append({ level: data.level || 'INFO', msg: data.msg || '', time: data.time || '' })
            return
          default:
            append({ level: data.level || 'INFO', msg: data.msg || '', time: data.time || '' })
        }
      } catch {
        /* heartbeat */
      }
    }
    es.onerror = () => {
      if (_wasConnected) {
        append({ level: 'ERROR', msg: '── 与服务端断开连接 ──', time: '' })
        const toast = useToastStore()
        toast.show('error', '服务已断开，请刷新页面重连', 10000)
        _wasConnected = false
      }
    }
    es.onopen = () => {
      if (_wasConnected) {
        // EventSource 重连成功
        _wasConnected = false  // reset to trigger re-detect
      }
    }
    eventSource.value = es
  }

  function close() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    activeSessionId.value = null
    _wasConnected = false
  }

  return { entries, logPanelEl, append, clear, connect, close, replaceFromEvents, activeSessionId }
})
