<template>
  <div class="mx-auto box-border w-full max-w-6xl space-y-4 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-4 border-b border-[var(--color-rule)] pb-4 lg:flex-row lg:items-start lg:justify-between">
        <div class="min-w-0">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">运行详情</p>
          <h2 class="mt-1 break-words text-xl font-bold text-[var(--color-ink)]">{{ title }}</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">Session {{ sessionId }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <RouterLink to="/tasks" class="btn-secondary">返回任务列表</RouterLink>
          <RouterLink
            :to="{ path: '/', query: { focus: 'input', fromSession: sessionId } }"
            class="btn-secondary"
          >
            返回生成设置
          </RouterLink>
          <button
            v-if="canCancel"
            class="btn-danger"
            :disabled="actionLoading || isStopping"
            @click="cancelTask"
          >
            {{ isStopping ? '停止中...' : '停止任务' }}
          </button>
          <button
            class="btn-secondary"
            :disabled="actionLoading || !canRerun"
            @click="rerun"
          >
            重新运行
          </button>
          <button
            v-if="canRestore"
            class="btn-secondary"
            :disabled="actionLoading"
            @click="restoreTask"
          >
            恢复任务
          </button>
        </div>
      </div>

      <div v-if="error" class="mt-4 rounded-lg border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
        {{ error }}
      </div>
      <div v-if="notice" class="mt-4 rounded-lg border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-sm text-[var(--color-success)]">
        {{ notice }}
      </div>
      <div v-if="stopNotice" class="mt-4 rounded-lg border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-[var(--color-warning)]">
        {{ stopNotice }}
      </div>

      <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-3">
          <div class="text-xs font-semibold text-[var(--color-ink-soft)]">状态</div>
          <div :class="['mt-2 inline-flex w-fit items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold', runStateClass]">
            <span class="h-2 w-2 rounded-full" :class="runDotClass" />
            {{ runStatusDisplay.label }}
          </div>
          <div v-if="runStatusDisplay.detail" class="mt-2 truncate text-xs text-[var(--color-ink-muted)]" :title="runStatusDisplay.detail">
            {{ runStatusDisplay.detail }}
          </div>
          <div v-if="effectiveRunState === 'queued'" class="mt-2 text-xs text-[var(--color-ink-muted)]">
            {{ queuePositionText }}
          </div>
        </div>
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-3">
          <div class="text-xs font-semibold text-[var(--color-ink-soft)]">来源</div>
          <div class="mt-2 text-sm font-semibold text-[var(--color-ink)]">{{ sourceLabel }}</div>
          <div class="mt-1 text-xs text-[var(--color-ink-muted)]">{{ historyItem?.owner_label || '本机用户' }}</div>
        </div>
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-3">
          <div class="text-xs font-semibold text-[var(--color-ink-soft)]">输入</div>
          <div class="mt-2 break-words text-sm text-[var(--color-ink)]">{{ historyItem?.input_name || '-' }}</div>
        </div>
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-3">
          <div class="text-xs font-semibold text-[var(--color-ink-soft)]">更新时间</div>
          <div class="mt-2 text-sm text-[var(--color-ink)]">{{ formatTime(sessionStatus?.updated_at || historyItem?.updated_at || historyItem?.created_at || '') }}</div>
        </div>
      </div>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">参数快照</p>
          <h3 class="mt-1 text-base font-bold text-[var(--color-ink)]">本次任务提交参数</h3>
        </div>
        <div class="flex flex-wrap gap-2">
          <RouterLink
            v-for="target in focusTargets"
            :key="target.value"
            :to="{ path: '/', query: { focus: target.value, fromSession: sessionId } }"
            class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
          >
            {{ target.label }}
          </RouterLink>
        </div>
      </div>
      <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="item in runConfigItems"
          :key="item.key"
          class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-3"
        >
          <div class="text-xs font-semibold text-[var(--color-ink-soft)]">{{ item.label }}</div>
          <div class="mt-2 break-words text-sm text-[var(--color-ink)]">{{ item.value || '-' }}</div>
        </div>
      </div>
    </section>

    <section class="surface overflow-hidden rounded-lg">
      <GenerationProgress
        v-if="hasProgress"
        :steps="progressSteps"
        :session-id="sessionId"
        :mode="effectiveMode"
        :is-done="effectiveRunState === 'done'"
      />
      <div v-else class="empty-state m-4">
        <div class="text-sm font-semibold text-[var(--color-ink)]">暂无生成过程</div>
        <p class="mt-1 text-xs">任务尚未写入阶段进展，或当前 session 已被清理。</p>
      </div>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">运行日志</p>
          <h3 class="mt-1 text-base font-bold text-[var(--color-ink)]">日志与错误详情</h3>
        </div>
        <button class="btn-secondary w-fit" :disabled="!logText" @click="copyLogs">复制日志</button>
      </div>
      <div v-if="logNotice" class="mt-4 rounded-lg border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-sm text-[var(--color-success)]">
        {{ logNotice }}
      </div>
      <div v-if="effectiveError" class="mt-4 rounded-lg border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
        <div class="font-semibold">错误详情</div>
        <p class="mt-1 whitespace-pre-wrap break-words">{{ effectiveError }}</p>
      </div>
      <div class="mt-4 h-96 overflow-y-auto rounded-lg bg-[var(--color-console)] p-4 font-mono text-xs leading-6 text-slate-300">
        <div v-if="logEntries.length === 0" class="flex h-full items-center justify-center text-center font-sans text-sm text-slate-400">
          {{ logEmptyText }}
        </div>
        <template v-else>
          <div v-for="(entry, index) in logEntries" :key="index" class="flex gap-3 py-0.5">
            <span class="w-20 shrink-0 text-slate-500">{{ entry.time }}</span>
            <span :class="['w-16 shrink-0 font-semibold', levelColor(entry.level)]">{{ entry.level }}</span>
            <span class="min-w-0 whitespace-pre-wrap break-words">{{ entry.msg }}</span>
          </div>
        </template>
      </div>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">交付物</p>
          <h3 class="mt-1 text-base font-bold text-[var(--color-ink)]">输出文件与操作</h3>
        </div>
        <div class="flex flex-wrap gap-2">
          <button v-if="canOpenFolder" class="btn-primary" @click="openFolder">打开目录</button>
          <button v-if="canDownload" class="btn-primary" @click="download">下载 .zip</button>
        </div>
      </div>
      <div v-if="doneFiles.length" class="mt-4 flex flex-wrap gap-2">
        <span
          v-for="file in doneFiles"
          :key="file.path || file.relative_path || file.name || file.label"
          :class="['inline-flex items-start gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold',
            file.is_temp ? 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]' : 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]']"
          :title="file.path || file.relative_path || file.name || ''"
        >
          <span>
            <span>{{ file.label || file.name || file.relative_path || file.path }}</span>
            <span v-if="file.size_kb" class="opacity-60"> {{ file.size_kb }} KB</span>
            <span v-if="file.toc_note" class="block font-normal opacity-80">{{ file.toc_note }}</span>
          </span>
        </span>
      </div>
      <div v-else class="empty-state mt-4">
        <div class="text-sm font-semibold text-[var(--color-ink)]">暂无交付物</div>
        <p class="mt-1 text-xs">任务完成后，这里会展示可下载或可打开的交付物。</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import GenerationProgress from '@/components/GenerationProgress.vue'
import { ApiError, apiFetch, normalizeApiError } from '@/lib/api.ts'
import type { StepProgress } from '@/stores/steps.ts'
import type { RunState } from '@/stores/session.ts'
import { getTaskStatusDisplay, TASK_STATUS_BADGE_CLASSES, TASK_STATUS_DOT_CLASSES } from '@/utils/taskStatusDisplay.ts'

interface DetailDoneFile {
  name?: string
  label?: string
  path?: string
  relative_path?: string
  size_kb?: number
  is_temp?: boolean
  toc_status?: string
  toc_note?: string
}

interface RunConfig {
  model?: string
  base_url?: string
  max_tokens?: string
  project_name?: string
  fpa_profile?: string
  fpa_strategy?: string
  fpa_rule_set?: string
  fpa_core_rules?: string
  fpa_system_prompt?: string
  fpa_user_prompt?: string
  fpa_base_profile?: string
  fpa_confirmation_mode?: string
  clean?: boolean
  custom_templates_dir?: string
}

interface HistoryItem {
  run_id: string
  session_id: string
  source: 'cli' | 'web'
  mode: 'local' | 'remote'
  owner_label: string
  task_mode: string
  run_state: RunState | 'closed'
  input_name: string
  output_dir?: string
  artifact_kind: 'local_dir' | 'remote_zip'
  download_available?: boolean
  open_folder_available?: boolean
  created_at: string
  started_at?: string
  updated_at?: string
  done_files?: DetailDoneFile[]
  run_config?: RunConfig
  error?: string
}

interface SessionStatusResponse {
  session_id: string
  mode: 'local' | 'remote'
  run_state: RunState
  output_dir?: string
  has_zip?: boolean
  done_files?: DetailDoneFile[]
  progress_steps?: Record<string, StepProgress>
  last_error?: string
  updated_at?: string
  queue_position?: number | null
}

interface RawLogEvent {
  type?: string
  level?: string
  msg?: string
  message?: string
  time?: string
  step?: string
  files?: DetailDoneFile[]
}

interface DisplayLogEntry {
  level: string
  msg: string
  time: string
}

const route = useRoute()
const router = useRouter()
const sessionId = computed(() => String(route.params.sessionId || ''))
const loading = ref(false)
const actionLoading = ref(false)
const isStopping = ref(false)
const error = ref('')
const notice = ref('')
const stopNotice = ref('')
const logNotice = ref('')
const historyItem = ref<HistoryItem | null>(null)
const sessionStatus = ref<SessionStatusResponse | null>(null)
const sessionAvailable = ref(false)
const logEntries = ref<DisplayLogEntry[]>([])
let eventSource: EventSource | null = null
let pollTimer: number | null = null

const focusTargets = [
  { value: 'mode', label: '操作模式' },
  { value: 'input', label: '输入路径' },
  { value: 'advanced', label: '高级参数' },
  { value: 'fpa-profile', label: 'FPA 方案' },
  { value: 'fpa-strategy', label: 'FPA 策略' },
  { value: 'fpa-rule-set', label: 'FPA 规则集' },
  { value: 'fpa-confirmation-mode', label: 'FPA 生成模式' },
]

const effectiveRunState = computed(() => sessionStatus.value?.run_state || historyItem.value?.run_state || 'running')
const effectiveMode = computed<'local' | 'remote'>(() => sessionStatus.value?.mode || historyItem.value?.mode || 'local')
const sourceLabel = computed(() => effectiveMode.value === 'remote' ? 'Web 远程' : 'Web 本机')
const title = computed(() => {
  const name = historyItem.value?.run_config?.project_name?.trim()
  if (name) return name
  return historyItem.value?.task_mode || `任务 ${sessionId.value}`
})
const effectiveError = computed(() => sessionStatus.value?.last_error || historyItem.value?.error || '')
const progressSteps = computed(() => normalizeSteps(sessionStatus.value?.progress_steps))
const hasProgress = computed(() => progressSteps.value.some(step => step.status !== 'pending' || step.artifacts.length > 0))
const runStatusDisplay = computed(() => getTaskStatusDisplay(effectiveRunState.value, progressSteps.value))
const doneFiles = computed(() => sessionStatus.value?.done_files?.length ? sessionStatus.value.done_files : (historyItem.value?.done_files || []))
const canRerun = computed(() => historyItem.value?.source === 'web' && ['done', 'error', 'cancelled'].includes(String(historyItem.value.run_state)))
const canCancel = computed(() => sessionAvailable.value && ['queued', 'running'].includes(String(effectiveRunState.value)))
const canRestore = computed(() => historyItem.value?.source === 'web' && historyItem.value.run_state === 'closed')
const canOpenFolder = computed(() => effectiveMode.value === 'local' && Boolean(historyItem.value?.open_folder_available || sessionStatus.value?.output_dir))
const canDownload = computed(() => effectiveMode.value === 'remote' && Boolean(historyItem.value?.download_available || sessionStatus.value?.has_zip))
const logText = computed(() => logEntries.value.map(entry => `[${entry.time || '--'}] ${entry.level} ${entry.msg}`).join('\n'))
const queuePositionText = computed(() => sessionStatus.value?.queue_position ? `队列位置 ${sessionStatus.value.queue_position}` : '已进入等待队列')
const logEmptyText = computed(() => {
  if (effectiveRunState.value === 'queued') return '任务正在排队，启动后会显示运行日志。'
  return sessionAvailable.value ? '暂无日志，运行中日志会在这里继续追加。' : '当前 session 不在内存中，无法读取实时日志快照。'
})

const runConfigItems = computed(() => {
  const cfg = historyItem.value?.run_config || {}
  return [
    { key: 'task_mode', label: '任务模式', value: historyItem.value?.task_mode || '' },
    { key: 'project_name', label: '项目名称', value: cfg.project_name || '' },
    { key: 'model', label: '模型', value: cfg.model || '' },
    { key: 'base_url', label: 'Base URL', value: cfg.base_url || '' },
    { key: 'max_tokens', label: '最大 Token', value: cfg.max_tokens || '' },
    { key: 'fpa_profile', label: 'FPA 方案', value: cfg.fpa_profile || '' },
    { key: 'fpa_strategy', label: 'FPA 执行策略', value: cfg.fpa_strategy || '' },
    { key: 'fpa_rule_set', label: 'FPA 规则集', value: cfg.fpa_rule_set || '' },
    { key: 'fpa_core_rules', label: 'FPA 核心口径', value: cfg.fpa_core_rules || '' },
    { key: 'fpa_system_prompt', label: 'FPA 系统提示词', value: cfg.fpa_system_prompt || '' },
    { key: 'fpa_user_prompt', label: 'FPA 用户提示词', value: cfg.fpa_user_prompt || '' },
    { key: 'fpa_base_profile', label: 'FPA 基准方案', value: cfg.fpa_base_profile || '' },
    { key: 'fpa_confirmation_mode', label: 'FPA 生成模式', value: cfg.fpa_confirmation_mode || '' },
    { key: 'clean', label: '清理输出目录', value: cfg.clean ? '是' : '否' },
  ]
})

const runStateClass = computed(() => {
  return TASK_STATUS_BADGE_CLASSES[runStatusDisplay.value.tone]
})

const runDotClass = computed(() => {
  return TASK_STATUS_DOT_CLASSES[runStatusDisplay.value.tone]
})

async function loadDetail() {
  if (!sessionId.value) return
  loading.value = true
  error.value = ''
  logNotice.value = ''
  await Promise.all([loadHistoryItem(), loadSessionStatus(), loadLogs()])
  connectIfRunning()
  loading.value = false
}

async function loadHistoryItem() {
  try {
    historyItem.value = await apiFetch<HistoryItem>(`/api/history/${sessionId.value}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      historyItem.value = null
      return
    }
    error.value = normalizeApiError(err)
  }
}

async function loadSessionStatus() {
  try {
    sessionStatus.value = await apiFetch<SessionStatusResponse>(`/api/sessions/${sessionId.value}`)
    sessionAvailable.value = true
  } catch (err) {
    sessionStatus.value = null
    sessionAvailable.value = false
    if (!(err instanceof ApiError && err.status === 404)) {
      error.value = normalizeApiError(err)
    }
  }
}

async function loadLogs() {
  try {
    const data = await apiFetch<{ entries?: RawLogEvent[] }>(`/api/sessions/${sessionId.value}/logs`)
    logEntries.value = (data.entries || []).map(formatLogEvent)
  } catch (err) {
    if (!(err instanceof ApiError && err.status === 404)) {
      error.value = normalizeApiError(err)
    }
  }
}

function connectIfRunning() {
  if (sessionStatus.value?.run_state !== 'running') return
  if (eventSource) return
  eventSource = new EventSource(`/api/log-stream?session=${sessionId.value}`)
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as RawLogEvent
      appendLog(data)
      if (['done', 'error', 'cancelled'].includes(String(data.type || ''))) {
        closeStream()
        loadSessionStatus()
        loadHistoryItem()
      }
    } catch {
      /* heartbeat */
    }
  }
  eventSource.onerror = () => {
    closeStream()
  }
}

function closeStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

function appendLog(event: RawLogEvent) {
  logEntries.value = [...logEntries.value, formatLogEvent(event)]
}

function formatLogEvent(event: RawLogEvent): DisplayLogEntry {
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

function normalizeSteps(progressSteps: Record<string, StepProgress> | undefined): StepProgress[] {
  const labels: Record<string, string> = {
    basedata: '读取基础数据',
    fpa: '生成 FPA',
    spec: '生成需求说明书',
    cosmic: '生成 COSMIC',
    list: '生成需求清单',
  }
  const order = ['basedata', 'fpa', 'spec', 'cosmic', 'list']
  return order.map((key) => ({
    key,
    label: labels[key],
    status: 'pending',
    current_action: '',
    started_at: null,
    finished_at: null,
    error: '',
    ...(progressSteps?.[key] || {}),
    activity_payloads: progressSteps?.[key]?.activity_payloads || [],
    artifacts: progressSteps?.[key]?.artifacts || [],
  }))
}

async function rerun() {
  if (!historyItem.value || !canRerun.value) return
  actionLoading.value = true
  error.value = ''
  notice.value = ''
  logNotice.value = ''
  try {
    const data = await apiFetch<{ session_id: string }>(`/api/tasks/${historyItem.value.run_id}/rerun`, { method: 'POST' })
    await router.push(`/tasks/${data.session_id}`)
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionLoading.value = false
  }
}

async function cancelTask() {
  if (!sessionId.value || !canCancel.value || isStopping.value) return
  isStopping.value = true
  actionLoading.value = true
  error.value = ''
  notice.value = ''
  stopNotice.value = '正在停止任务，如当前有 AI 调用正在执行，需等待其完成后停止'
  logNotice.value = ''
  try {
    await apiFetch(`/api/cancel/${sessionId.value}`, { method: 'POST' })
    closeStream()
    await Promise.all([loadSessionStatus(), loadHistoryItem(), loadLogs()])
  } catch (err) {
    error.value = normalizeApiError(err)
    stopNotice.value = ''
  } finally {
    actionLoading.value = false
    if (!canCancel.value) {
      isStopping.value = false
    }
  }
}

async function restoreTask() {
  if (!historyItem.value || !canRestore.value) return
  actionLoading.value = true
  error.value = ''
  notice.value = ''
  logNotice.value = ''
  try {
    await apiFetch(`/api/tasks/${historyItem.value.run_id}/restore`, { method: 'POST' })
    notice.value = '任务已恢复到任务列表'
    await loadHistoryItem()
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionLoading.value = false
  }
}

async function copyLogs() {
  if (!logText.value) return
  try {
    await navigator.clipboard.writeText(logText.value)
    logNotice.value = '日志已复制'
  } catch {
    error.value = '复制失败，请手动选择日志内容复制'
  }
}

async function openFolder() {
  try {
    if (historyItem.value?.run_id) {
      await apiFetch(`/api/history/${historyItem.value.run_id}/open-folder`, { method: 'POST' })
      return
    }
    await apiFetch(`/api/open-folder?session=${sessionId.value}`)
  } catch (err) {
    error.value = normalizeApiError(err)
  }
}

function download() {
  if (historyItem.value?.run_id && historyItem.value.download_available) {
    window.location.href = `/api/history/${historyItem.value.run_id}/download`
    return
  }
  window.location.href = `/api/download/${sessionId.value}`
}

function levelColor(level: string) {
  const map: Record<string, string> = {
    INFO: 'text-blue-400',
    DEBUG: 'text-slate-400',
    WARNING: 'text-yellow-400',
    ERROR: 'text-red-400',
    DONE: 'text-green-400',
  }
  return map[level] || 'text-slate-300'
}

function formatTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

watch(sessionId, () => {
  closeStream()
  loadDetail()
})

watch(effectiveRunState, (state) => {
  if (!['queued', 'running'].includes(String(state))) {
    isStopping.value = false
    if (state === 'cancelled') {
      stopNotice.value = '任务已进入停止状态'
    }
  }
})

onMounted(() => {
  loadDetail()
  pollTimer = window.setInterval(() => {
    if (sessionStatus.value?.run_state === 'queued' || sessionStatus.value?.run_state === 'running') {
      loadSessionStatus().then(() => {
        if (sessionStatus.value?.run_state === 'running') connectIfRunning()
      })
    }
  }, 5000)
})

onUnmounted(() => {
  closeStream()
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>
