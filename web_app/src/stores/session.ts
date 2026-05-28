import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type RunState = 'idle' | 'running' | 'done' | 'error'

export interface InputPrompt {
  field: string
  default: number
  msg: string
}

export interface ListPrompt {
  cfpDefault: number
  fpaDefault: number
}

export interface DoneFile {
  label: string
  path: string
  size_kb: number
  is_temp: boolean
}

export interface SessionSnapshot {
  session_id: string
  run_state: RunState
  output_dir?: string
  done_files?: DoneFile[]
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const runState = ref<RunState>('idle')
  const outputDir = ref<string>('')
  const inputPrompt = ref<InputPrompt | null>(null)
  const listPrompt = ref<ListPrompt | null>(null)
  const doneFiles = ref<DoneFile[]>([])

  const isRunning = computed(() => runState.value === 'running')
  const isDone = computed(() => runState.value === 'done')

  function start(sid: string, out: string) {
    sessionId.value = sid
    outputDir.value = out
    runState.value = 'running'
    inputPrompt.value = null
    listPrompt.value = null
    doneFiles.value = []
  }

  function restore(snapshot: SessionSnapshot) {
    sessionId.value = snapshot.session_id
    outputDir.value = snapshot.output_dir || ''
    runState.value = snapshot.run_state
    inputPrompt.value = null
    listPrompt.value = null
    doneFiles.value = snapshot.done_files || []
  }

  function finish(files?: DoneFile[]) {
    runState.value = 'done'
    inputPrompt.value = null
    listPrompt.value = null
    if (files) doneFiles.value = files
  }

  function setError() {
    runState.value = 'error'
    inputPrompt.value = null
    listPrompt.value = null
  }

  function reset() {
    sessionId.value = null
    outputDir.value = ''
    runState.value = 'idle'
    inputPrompt.value = null
    listPrompt.value = null
    doneFiles.value = []
  }

  function showInputPrompt(prompt: InputPrompt) {
    inputPrompt.value = prompt
  }

  function showListPrompt(prompt: ListPrompt) {
    listPrompt.value = prompt
  }

  return { sessionId, runState, outputDir, inputPrompt, listPrompt, doneFiles, isRunning, isDone, start, restore, finish, setError, reset, showInputPrompt, showListPrompt }
})
