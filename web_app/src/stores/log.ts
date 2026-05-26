import { ref, nextTick } from 'vue'
import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useStepsStore } from './steps'

export interface LogEntry {
  level: string
  msg: string
  time: string
  isStep?: boolean
}

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])
  const eventSource = ref<EventSource | null>(null)
  const logPanelEl = ref<HTMLElement | null>(null)

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

  function connect() {
    const session = useSessionStore()
    if (!session.sessionId) return
    close()
    const es = new EventSource('/api/log-stream?session=' + session.sessionId)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        switch (data.type) {
          case 'done':
            append({ level: 'DONE', msg: '── 任务完成 ──', time: '' })
            session.finish(data.files || [])
            useStepsStore().finishAll()
            return
          case 'error':
            append({ level: 'ERROR', msg: `── 任务失败: ${data.msg || '未知错误'} ──`, time: '' })
            session.setError()
            return
          case 'cancelled':
            append({ level: 'WARNING', msg: '── 任务已被用户停止 ──', time: '' })
            session.setError()
            return
          case 'prompt':
            append({ level: 'INFO', msg: `⏸ ${data.msg || '等待用户输入...'}`, time: data.time || '' })
            session.showInputPrompt({
              field: data.field || '',
              default: data.default || 0,
              msg: data.msg || '',
            })
            return
          case 'step':
            useStepsStore().setActive(data.key)
            return
          case 'log':
            append({ level: data.level, msg: data.msg, time: data.time || '' })
            return
          default:
            append({ level: data.level || 'INFO', msg: data.msg || '', time: data.time || '' })
        }
      } catch {
        /* heartbeat */
      }
    }
    es.onerror = () => {}
    eventSource.value = es
  }

  function close() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  return { entries, logPanelEl, append, clear, connect, close }
})
