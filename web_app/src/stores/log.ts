import { ref, nextTick } from 'vue'
import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useStepsStore } from './steps'

const STEP_MARKER = '>>>STEP:'

export interface LogEntry {
  level: string
  msg: string
  time: string
}

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])
  const eventSource = ref<EventSource | null>(null)
  const logPanelEl = ref<HTMLElement | null>(null)

  function append(entry: LogEntry) {
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
        if (data.level === 'DONE') {
          append({ level: 'DONE', msg: '── 任务完成 ──', time: '' })
          session.finish()
          useStepsStore().finishAll()
          return
        }
        if (data.level === 'CANCELLED') {
          append({ level: 'WARNING', msg: '── 任务已被用户中断 ──', time: '' })
          session.setError()
          return
        }
        // 检测步骤事件
        const msg = data.msg || ''
        if (typeof msg === 'string' && msg.startsWith(STEP_MARKER)) {
          const stepKey = msg.slice(STEP_MARKER.length)
          useStepsStore().setActive(stepKey)
          // 不追加到日志面板（纯控制事件）
          return
        }
        append({ level: data.level, msg, time: data.time || '' })
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
