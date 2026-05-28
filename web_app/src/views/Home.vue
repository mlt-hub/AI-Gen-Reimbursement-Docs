<template>
  <div class="flex h-full flex-col gap-4 overflow-hidden p-4 lg:flex-row lg:p-5">
    <!-- 左侧配置面板 -->
    <aside class="surface min-h-0 shrink-0 overflow-y-auto rounded-xl p-4 lg:w-[390px]">
      <div class="mb-5 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold uppercase text-[var(--color-ink-soft)]">Run setup</p>
        <h2 class="mt-1 text-xl font-bold text-[var(--color-ink)]">生成任务</h2>
        <p class="mt-1 text-sm text-[var(--color-ink-muted)]">选择输入、模式和模板后启动文档生成。</p>
      </div>
      <ConfigPanel @start="startTask" />
    </aside>

    <!-- 右侧日志区 -->
    <div class="surface flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl">
      <div class="border-b border-[var(--color-rule)] px-5 py-4">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="min-w-0">
            <p class="text-xs font-semibold uppercase text-[var(--color-ink-soft)]">Execution monitor</p>
            <h2 class="mt-1 truncate text-lg font-bold text-[var(--color-ink)]">{{ runTitle }}</h2>
          </div>
          <div :class="['inline-flex w-fit items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold', runStateClass]">
            <span class="h-2 w-2 rounded-full" :class="runDotClass" />
            {{ runStateText }}
          </div>
        </div>
      </div>
      <StepsBar v-if="session.isRunning || session.isDone" />
      <LogViewer />
      <ActionBar @ai="openAIModal" @reset="resetTask" />
    </div>

    <!-- FPA核减后的工作量输入弹窗 -->
    <Teleport to="body">
      <div v-if="session.inputPrompt" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="surface w-full max-w-[420px] rounded-xl p-6">
          <h3 class="text-lg font-semibold mb-2">FPA核减后的工作量确认</h3>
          <p class="text-sm text-gray-500 mb-4">请输入FPA核减后的工作量（人/天），或直接确认使用默认值。</p>
          <div class="mb-4">
            <label class="field-label">FPA核减后的工作量（人/天）</label>
            <input
              v-model="fpaInputValue"
              type="number"
              step="0.1"
              min="0"
              class="field-control"
              @keyup.enter="submitFpaInput"
            />
          </div>
          <div class="flex justify-end gap-3">
            <button @click="cancelTask" class="btn-quiet">取消任务</button>
            <button @click="submitFpaInput" class="btn-primary">确认继续</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 送审工作量和功能点确认弹窗 -->
    <Teleport to="body">
      <div v-if="session.listPrompt" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="surface w-full max-w-[420px] rounded-xl p-6">
          <h3 class="text-lg font-semibold mb-2">送审确认</h3>
          <p class="text-sm text-gray-500 mb-4">请确认送审工作量和送审功能点，或直接使用默认值。</p>
          <div class="mb-3">
            <label class="field-label">送审工作量（人/天）</label>
            <input
              v-model.number="listFpaValue"
              type="number"
              step="0.1"
              min="0"
              class="field-control"
              @keyup.enter="submitListInput"
            />
          </div>
          <div class="mb-4">
            <label class="field-label">送审功能点（个）</label>
            <input
              v-model.number="listCfpValue"
              type="number"
              step="0.1"
              min="0"
              class="field-control"
              @keyup.enter="submitListInput"
            />
          </div>
          <div class="flex justify-end gap-3">
            <button @click="cancelTask" class="btn-quiet">取消任务</button>
            <button @click="submitListInput" class="btn-primary">确认继续</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- AI 交互弹窗 -->
    <Teleport to="body">
      <div v-if="aiModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeAIModal">
        <div class="surface flex h-[85vh] w-[92vw] max-w-5xl flex-col overflow-hidden rounded-xl">
          <div class="px-5 py-3 border-b border-[var(--color-rule)] flex items-center justify-between">
            <h3 class="text-lg font-semibold">AI 交互记录</h3>
            <button @click="closeAIModal" class="btn-quiet min-h-0 px-2 py-1 text-xl leading-none">&times;</button>
          </div>
          <div class="flex border-b border-[var(--color-rule)] px-5">
            <button v-for="tab in ['list', 'combined']" :key="tab"
              @click="aiTab = tab"
              :class="['py-2 px-4 text-sm border-b-2 transition-colors',
                aiTab === tab ? 'border-[var(--color-accent)] text-[var(--color-accent-strong)] font-medium' : 'border-transparent text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]']">
              {{ tab === 'list' ? '交互列表' : '合并日志' }}
            </button>
          </div>
          <div class="flex-1 overflow-y-auto bg-[var(--color-page)] p-5">
            <div v-if="aiLoading" class="flex h-full items-center justify-center text-[var(--color-ink-soft)]">加载中...</div>
            <div v-else-if="aiTab === 'list' && aiInteractions.length === 0" class="flex h-full items-center justify-center text-[var(--color-ink-soft)]">暂无 AI 交互记录</div>
            <template v-else-if="aiTab === 'list'">
              <div v-for="item in aiInteractions" :key="item.name"
                class="mb-3 overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)]">
                <div @click="item.expanded = !item.expanded"
                  class="flex cursor-pointer select-none items-center justify-between bg-[var(--color-surface)] px-4 py-2 hover:bg-[var(--color-surface-muted)]">
                  <span class="flex items-center gap-2 text-sm">
                    <span :class="['rounded px-1.5 py-0.5 text-xs font-bold', item.type === 'prompt' ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]' : 'bg-[var(--color-success-soft)] text-[var(--color-success)]']">
                      {{ item.type === 'prompt' ? 'P' : 'R' }}
                    </span>
                    {{ item.name }}
                  </span>
                  <span class="text-xs text-[var(--color-ink-soft)]">点击展开</span>
                </div>
                <pre v-show="item.expanded" class="m-0 max-h-96 overflow-y-auto overflow-x-auto bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300 whitespace-pre-wrap">{{ item.content }}</pre>
              </div>
            </template>
            <pre v-else class="overflow-x-auto rounded-lg bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300 whitespace-pre-wrap">{{ aiCombinedLog }}</pre>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { DoneFile, RunState } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useLogStore } from '@/stores/log'
import { useStepsStore } from '@/stores/steps'
import { useToastStore } from '@/stores/toast'
import { apiFetch, normalizeApiError } from '@/lib/api'
import ConfigPanel from '@/components/ConfigPanel.vue'
import StepsBar from '@/components/StepsBar.vue'
import LogViewer from '@/components/LogViewer.vue'
import ActionBar from '@/components/ActionBar.vue'

interface RunTaskResponse {
  session_id: string
  output_dir?: string
}

interface SessionStatusResponse {
  session_id: string
  mode: 'local' | 'remote'
  run_state: RunState
  output_dir?: string
  done_files?: DoneFile[]
}

interface AiInteraction {
  name: string
  type: 'prompt' | 'response'
  content: string
  expanded?: boolean
}

interface AiInteractionsResponse {
  interactions?: Omit<AiInteraction, 'expanded'>[]
}

interface AiLogResponse {
  content?: string
}

const session = useSessionStore()
const config = useConfigStore()
const log = useLogStore()
const toast = useToastStore()
const LAST_SESSION_KEY = 'ard:lastSessionId'

const runStateLabels = { idle: '就绪', running: '运行中', done: '已完成', error: '出错' }
const runTitle = computed(() => {
  if (session.outputDir) return session.outputDir
  if (!session.sessionId) return '等待任务启动'
  const taskLabel = config.workMode === 'local' ? '本机任务' : '远程任务'
  return `${taskLabel} ${session.sessionId}`
})
const runStateText = computed(() => {
  return runStateLabels[session.runState]
})
const runStateClass = computed(() => {
  const map = {
    idle: 'border-[var(--color-rule)] bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]',
    running: 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]',
    done: 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]',
    error: 'border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]',
  }
  return map[session.runState]
})
const runDotClass = computed(() => {
  const map = {
    idle: 'bg-[var(--color-ink-soft)]',
    running: 'bg-[var(--color-accent)]',
    done: 'bg-[var(--color-success)]',
    error: 'bg-[var(--color-danger)]',
  }
  return map[session.runState]
})

// ── 送审工作量输入 ──
const fpaInputValue = ref(0)
watch(() => session.inputPrompt, (p) => {
  if (p) {
    fpaInputValue.value = p.default
  }
})

// ── 送审确认（gen-list）──
const listFpaValue = ref(0)
const listCfpValue = ref(0)

watch(() => session.listPrompt, (p) => {
  if (p) {
    listFpaValue.value = p.fpaDefault
    listCfpValue.value = p.cfpDefault
  }
})

async function submitFpaInput() {
  if (!session.sessionId) return
  const val = parseFloat(String(fpaInputValue.value)) || 0
  try {
    await apiFetch('/api/continue/' + session.sessionId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field: 'fpa_reduced', fpa_reduced: val }),
    })
  } catch (e) {
    toast.show('error', normalizeApiError(e))
    return
  }
  session.inputPrompt = null
}

async function submitListInput() {
  if (!session.sessionId) return
  try {
    await apiFetch('/api/continue/' + session.sessionId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fpa_reduced: parseFloat(String(listFpaValue.value)) || 0,
        cfp_total: parseFloat(String(listCfpValue.value)) || 0,
      }),
    })
  } catch (e) {
    toast.show('error', normalizeApiError(e))
    return
  }
  session.listPrompt = null
}

async function cancelTask() {
  if (!session.sessionId) return
  try {
    await apiFetch('/api/cancel/' + session.sessionId, { method: 'POST' })
  } catch { /* ignore */ }
}

// ── 任务启动 ──
async function startTask() {
  const mode = config.pipelineMode
  const body = new FormData()
  body.append('mode', mode)
  if (config.apiKey) body.append('api_key', config.apiKey)
  if (config.model) body.append('model', config.model)
  if (config.baseUrl) body.append('base_url', config.baseUrl)
  if (config.maxTokens) body.append('max_tokens', config.maxTokens)
  if (config.projectName) body.append('project_name', config.projectName)
  if (config.clean) body.append('clean', '1')

  let url: string
  if (config.workMode === 'local') {
    if (!config.xlsxPath.trim()) {
      toast.show('error', '请输入功能清单 .xlsx 路径')
      return
    }
    url = '/api/run-local'
    body.append('xlsx_path', config.xlsxPath)
    body.append('output_dir', config.outputDir)
  } else {
    if (!config.selectedFile) {
      toast.show('error', '请选择要上传的 .xlsx 文件')
      return
    }
    url = '/api/run-upload'
    body.append('file', config.selectedFile)
  }

  log.clear()
  session.reset()
  useStepsStore().reset()

  try {
    const data = await apiFetch<RunTaskResponse>(url, { method: 'POST', body })
    session.start(data.session_id, data.output_dir || '')
    localStorage.setItem(LAST_SESSION_KEY, data.session_id)
    log.connect()
  } catch (e) {
    const msg = normalizeApiError(e)
    log.append({ level: 'ERROR', msg: msg, time: '' })
    toast.show('error', msg)
    session.setError()
  }
}

async function restoreLastSession() {
  if (session.sessionId) return
  const sid = localStorage.getItem(LAST_SESSION_KEY)
  if (!sid) return

  try {
    const data = await apiFetch<SessionStatusResponse>('/api/sessions/' + sid)
    config.workMode = data.mode
    session.restore({
      session_id: data.session_id,
      run_state: data.run_state,
      output_dir: data.output_dir || '',
      done_files: data.done_files || [],
    })
    log.clear()
    if (data.run_state === 'running') {
      log.append({ level: 'INFO', msg: '已恢复正在运行的任务，继续接收后续日志', time: '' })
      log.connect()
    } else if (data.run_state === 'done') {
      log.append({ level: 'DONE', msg: '已恢复已完成的任务，可下载交付物', time: '' })
      useStepsStore().finishAll()
    } else {
      log.append({ level: 'ERROR', msg: '已恢复出错的任务', time: '' })
    }
  } catch {
    localStorage.removeItem(LAST_SESSION_KEY)
  }
}

// ── AI 交互弹窗 ──
const aiModalOpen = ref(false)
const aiTab = ref('list')
const aiLoading = ref(false)
const aiInteractions = ref<AiInteraction[]>([])
const aiCombinedLog = ref('')

async function openAIModal() {
  if (!session.sessionId) return
  aiModalOpen.value = true
  await loadAIList()
}

function closeAIModal() { aiModalOpen.value = false }

async function loadAIList() {
  if (!session.sessionId) return
  aiLoading.value = true
  try {
    const data = await apiFetch<AiInteractionsResponse>('/api/ai-interactions/' + session.sessionId)
    aiInteractions.value = (data.interactions || []).map((i) => ({ ...i, expanded: false }))
  } catch {
    aiInteractions.value = []
  } finally {
    aiLoading.value = false
  }
}

async function loadAICombined() {
  if (!session.sessionId) return
  aiLoading.value = true
  try {
    const data = await apiFetch<AiLogResponse>('/api/ai-log/' + session.sessionId)
    aiCombinedLog.value = data.content || ''
  } catch (e) {
    aiCombinedLog.value = '加载失败: ' + normalizeApiError(e)
  } finally {
    aiLoading.value = false
  }
}

// React to tab changes
watch(aiTab, (t) => {
  if (t === 'list') loadAIList()
  else loadAICombined()
})

function resetTask() {
  session.reset()
  log.clear()
  localStorage.removeItem(LAST_SESSION_KEY)
}

onMounted(() => {
  restoreLastSession()
})
</script>
