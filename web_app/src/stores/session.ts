import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type RunState = 'idle' | 'running' | 'done' | 'error'

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const runState = ref<RunState>('idle')
  const outputDir = ref<string>('')

  const isRunning = computed(() => runState.value === 'running')
  const isDone = computed(() => runState.value === 'done')

  function start(sid: string, out: string) {
    sessionId.value = sid
    outputDir.value = out
    runState.value = 'running'
  }

  function finish() {
    runState.value = 'done'
  }

  function setError() {
    runState.value = 'error'
  }

  function reset() {
    sessionId.value = null
    outputDir.value = ''
    runState.value = 'idle'
  }

  return { sessionId, runState, outputDir, isRunning, isDone, start, finish, setError, reset }
})
