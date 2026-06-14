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
  let entryKeys = new Set<string>()

  function entrySignature(entry: LogEntry) {
    return [entry.level, entry.time, entry.msg].join('\u001f')
  }

  function rawEventSignature(event: RawLogEvent, entry: LogEntry) {
    const payload = event.payload || {}
    const module = event.module || {}
    return JSON.stringify([
      event.type || '',
      event.time || entry.time || '',
      event.level || entry.level || '',
      event.msg || '',
      event.message || entry.msg || '',
      event.step || '',
      event.field || '',
      event.default ?? '',
      event.cfp_default ?? '',
      event.fpa_default ?? '',
      event.confirmation_mode || '',
      String(payload.label || ''),
      String(payload.path || ''),
      String(payload.name || ''),
      String(payload.toc_status || ''),
      String(payload.toc_note || ''),
      String(module.index || ''),
      String(module.l3 || ''),
    ])
  }

  function pushEntry(entry: LogEntry, key: string = entrySignature(entry)) {
    if (entryKeys.has(key)) return
    entry.isStep = /^第\d/.test(entry.msg)
    entryKeys.add(key)
    entries.value.push(entry)
    nextTick(() => {
      if (logPanelEl.value) {
        logPanelEl.value.scrollTop = logPanelEl.value.scrollHeight
      }
    })
  }

  function append(entry: LogEntry) {
    // 以"第N"开头的日志行为步骤行
    pushEntry(entry)
  }

  function clear() {
    entries.value = []
    entryKeys = new Set()
  }

  function formatEvent(event: RawLogEvent): LogEntry {
    const type = String(event.type || '')
    if (type === 'done') return { level: 'DONE', msg: '── 任务完成 ──', time: event.time || '' }
    if (type === 'cancelled') return { level: 'WARNING', msg: '── 任务已被用户停止 ──', time: event.time || '' }
    if (type === 'error') return { level: 'ERROR', msg: `── 任务失败: ${event.msg || '未知错误'} ──`, time: event.time || '' }
    if (type === 'prompt') return { level: 'INFO', msg: `⏸ ${event.msg || '等待用户输入...'}`, time: event.time || '' }
    if (type === 'prompt_list') return { level: 'INFO', msg: '⏸ 等待确认送审工作量和送审功能点...', time: event.time || '' }
    if (type === 'fpa_confirmation_required') return { level: 'INFO', msg: '⏸ 等待确认 FPA 计量口径...', time: event.time || '' }
    if (type === 'step_failed') return { level: 'ERROR', msg: `${event.step || '阶段'}：${event.message || type}`, time: event.time || '' }
    if (type === 'step_cancelled') return { level: 'WARNING', msg: `${event.step || '阶段'}：${event.message || type}`, time: event.time || '' }
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
    entries.value = []
    entryKeys = new Set()
    for (const event of events) {
      const entry = formatEvent(event)
      pushEntry(entry, rawEventSignature(event, entry))
    }
    nextTick(() => {
      if (logPanelEl.value) {
        logPanelEl.value.scrollTop = logPanelEl.value.scrollHeight
      }
    })
  }

  function mergeFromEvents(events: RawLogEvent[]) {
    for (const event of events) {
      const entry = formatEvent(event)
      pushEntry(entry, rawEventSignature(event, entry))
    }
  }

  function appendFromEvent(event: RawLogEvent) {
    const entry = formatEvent(event)
    pushEntry(entry, rawEventSignature(event, entry))
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
            appendFromEvent(data)
            session.finish(data.files || [])
            useStepsStore().finishAll()
            return
          case 'error':
            close()
            appendFromEvent(data)
            session.setError()
            useStepsStore().failActive(data.msg || '任务失败')
            return
          case 'cancelled':
            close()
            appendFromEvent(data)
            session.setCancelled()
            useStepsStore().cancelActive('任务已被用户停止')
            return
          case 'prompt':
            appendFromEvent(data)
            session.showInputPrompt({
              sessionId: targetSessionId,
              field: data.field || '',
              default: data.default || 0,
              msg: data.msg || '',
            })
            return
          case 'prompt_list':
            appendFromEvent(data)
            session.showListPrompt({
              sessionId: targetSessionId,
              cfpDefault: data.cfp_default || 0,
              fpaDefault: data.fpa_default || 0,
            })
            return
          case 'fpa_confirmation_required':
            appendFromEvent(data)
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
            appendFromEvent(data)
            return
          case 'log':
            appendFromEvent(data)
            return
          default:
            appendFromEvent(data)
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

  return { entries, logPanelEl, append, clear, connect, close, replaceFromEvents, mergeFromEvents, activeSessionId }
})
