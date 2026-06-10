<template>
  <div class="box-border flex h-full max-w-full min-w-0 flex-col gap-4 overflow-x-hidden overflow-y-auto p-4 xl:p-5">
    <!-- 主操作区 -->
    <section class="surface min-h-0 w-full max-w-full min-w-0 rounded-xl p-4">
      <div class="mb-5 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">主操作区</p>
        <h2 class="mt-1 text-xl font-bold text-[var(--color-ink)]">生成任务</h2>
        <p class="mt-1 text-sm text-[var(--color-ink-muted)]">选择生成内容，填写功能清单路径，然后启动生成任务。</p>
      </div>
      <ConfigPanel @start="startTask" />
      <div class="mt-4 border-t border-[var(--color-rule)] pt-4">
        <FpaRunSettingsSection :default-open="false" />
      </div>
    </section>

    <section class="surface flex min-h-[280px] min-w-0 flex-col overflow-hidden rounded-xl">
      <div class="border-b border-[var(--color-rule)] px-5 py-4">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="min-w-0">
            <p class="text-xs font-semibold text-[var(--color-ink-soft)]">执行监控</p>
            <h2 class="mt-1 truncate text-lg font-bold text-[var(--color-ink)]">{{ runTitle }}</h2>
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
            <RouterLink
              v-if="session.sessionId"
              :to="`/tasks/${session.sessionId}`"
              class="btn-secondary w-fit"
            >
              运行详情 / 排错信息
            </RouterLink>
            <span
              v-else
              class="inline-flex w-fit cursor-not-allowed rounded-md border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
              title="任务启动后可查看"
            >
              运行详情 / 排错信息
            </span>
            <div :class="['inline-flex w-fit items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold', runStateClass]">
              <span class="h-2 w-2 rounded-full" :class="runDotClass" />
              {{ runStateText }}
            </div>
          </div>
        </div>
      </div>
      <div v-if="startupError" class="border-b border-[var(--color-rule)] bg-[var(--color-danger-soft)] px-5 py-4 text-sm text-[var(--color-danger)]">
        <div class="font-semibold">{{ startupError.title }}</div>
        <p class="mt-1 whitespace-pre-wrap break-words leading-6">{{ startupError.detail }}</p>
        <p v-if="startupError.nextStep" class="mt-2 leading-6">{{ startupError.nextStep }}</p>
      </div>
      <GenerationProgress v-if="session.isRunning || session.isDone || session.runState === 'cancelled' || steps.hasProgress" />
      <div v-else class="flex min-h-[160px] flex-1 items-center justify-center bg-[var(--color-page)] p-5 text-center">
        <div>
          <p class="text-sm font-semibold text-[var(--color-ink)]">{{ startupError ? '任务未启动' : '等待任务启动' }}</p>
          <p class="mt-1 text-xs leading-5 text-[var(--color-ink-muted)]">
            {{ startupError ? '请处理上方错误后重新启动生成任务。' : '任务开始后，这里会显示阶段进展、日志入口和交付物操作。' }}
          </p>
        </div>
      </div>
      <details class="border-t border-[var(--color-rule)] bg-[var(--color-surface-raised)]">
        <summary class="cursor-pointer select-none px-5 py-3 text-sm font-semibold text-[var(--color-ink-muted)]">
          运行详情 / 排错信息
        </summary>
        <div class="h-80 border-t border-[var(--color-rule)]">
          <LogViewer />
        </div>
      </details>
      <ActionBar @ai="openAIModal" @reset="resetTask" />
    </section>

    <!-- FPA核减后的工作量输入弹窗 -->
    <Teleport to="body">
      <div v-if="session.inputPrompt" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="surface max-h-[calc(100vh-2rem)] w-full max-w-[420px] overflow-y-auto rounded-xl p-5 sm:p-6">
          <h3 class="mb-2 text-lg font-semibold">FPA 核减后的工作量确认</h3>
          <p class="mb-4 text-sm text-[var(--color-ink-muted)]">请输入FPA核减后的工作量（人/天），或直接确认使用默认值。</p>
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
          <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <button @click="cancelTask" class="btn-quiet">取消任务</button>
            <button @click="submitFpaInput" class="btn-primary">确认继续</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 送审工作量和功能点确认弹窗 -->
    <Teleport to="body">
      <div v-if="session.listPrompt" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="surface max-h-[calc(100vh-2rem)] w-full max-w-[420px] overflow-y-auto rounded-xl p-5 sm:p-6">
          <h3 class="mb-2 text-lg font-semibold">送审确认</h3>
          <p class="mb-4 text-sm text-[var(--color-ink-muted)]">请确认送审工作量和送审功能点，或直接使用默认值。</p>
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
          <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <button @click="cancelTask" class="btn-quiet">取消任务</button>
            <button @click="submitListInput" class="btn-primary">确认继续</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 批量 FPA 计量口径确认弹窗 -->
    <Teleport to="body">
      <div v-if="session.fpaConfirmationPrompt" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="surface flex max-h-[calc(100vh-2rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl">
          <div class="border-b border-[var(--color-rule)] px-5 py-4">
            <p class="text-xs font-semibold text-[var(--color-ink-soft)]">确认计量口径</p>
            <h3 class="mt-1 text-lg font-semibold text-[var(--color-ink)]">{{ fpaConfirmationTitle }}</h3>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto p-5">
            <div class="grid gap-3">
              <article
                v-for="question in session.fpaConfirmationPrompt.questions"
                :key="question.id"
                class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-4"
              >
                <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div class="min-w-0">
                    <p class="text-xs font-semibold text-[var(--color-accent-strong)]">{{ question.topic }}</p>
                    <p class="mt-1 text-sm font-semibold leading-6 text-[var(--color-ink)]">{{ question.question }}</p>
                  </div>
                  <span class="shrink-0 rounded-md bg-[var(--color-accent-soft)] px-2 py-1 text-xs font-semibold text-[var(--color-accent-strong)]">
                    推荐 {{ optionLabel(question, question.recommendation) }}
                  </span>
                </div>
                <p class="mt-2 text-xs leading-5 text-[var(--color-ink-muted)]">{{ question.reason }}</p>
                <div class="mt-3 grid gap-2 sm:grid-cols-2">
                  <label
                    v-for="option in question.options"
                    :key="option.value"
                    class="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm"
                    :class="fpaConfirmationSelections[question.id] === option.value ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]' : 'border-[var(--color-rule)] bg-[var(--color-surface)] text-[var(--color-ink)]'"
                  >
                    <input
                      v-model="fpaConfirmationSelections[question.id]"
                      class="h-4 w-4"
                      type="radio"
                      :name="question.id"
                      :value="option.value"
                    />
                    <span>{{ option.label }}</span>
                  </label>
                </div>
              </article>
            </div>
          </div>
          <div class="flex flex-col gap-3 border-t border-[var(--color-rule)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div class="inline-flex w-fit rounded-md border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-1 text-xs font-semibold">
              <button
                type="button"
                :class="['rounded px-3 py-1.5', fpaConfirmationScope === 'current_run' ? 'bg-[var(--color-surface)] text-[var(--color-ink)] shadow-sm' : 'text-[var(--color-ink-muted)]']"
                @click="fpaConfirmationScope = 'current_run'"
              >
                仅本次使用
              </button>
              <button
                type="button"
                :class="['rounded px-3 py-1.5', fpaConfirmationScope === 'project_profile' ? 'bg-[var(--color-surface)] text-[var(--color-ink)] shadow-sm' : 'text-[var(--color-ink-muted)]']"
                @click="fpaConfirmationScope = 'project_profile'"
              >
                保存为项目默认口径
              </button>
            </div>
            <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <button @click="cancelTask" class="btn-quiet">取消任务</button>
              <button @click="submitFpaConfirmation" class="btn-primary" :disabled="!canSubmitFpaConfirmation">确认继续</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- AI 交互弹窗 -->
    <Teleport to="body">
      <div v-if="aiModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeAIModal">
        <div class="surface flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl sm:w-[92vw]">
          <div class="flex items-center justify-between gap-3 border-b border-[var(--color-rule)] px-4 py-3 sm:px-5">
            <h3 class="min-w-0 truncate text-lg font-semibold">AI 交互记录</h3>
            <button @click="closeAIModal" class="btn-quiet min-h-0 px-2 py-1 text-xl leading-none">&times;</button>
          </div>
          <div class="flex overflow-x-auto border-b border-[var(--color-rule)] px-4 sm:px-5">
            <button v-for="tab in ['list', 'combined']" :key="tab"
              @click="aiTab = tab"
              :class="['shrink-0 border-b-2 px-4 py-2 text-sm transition-colors',
                aiTab === tab ? 'border-[var(--color-accent)] text-[var(--color-accent-strong)] font-medium' : 'border-transparent text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]']">
              {{ tab === 'list' ? '交互列表' : '合并日志' }}
            </button>
          </div>
          <div class="flex-1 overflow-y-auto bg-[var(--color-page)] p-4 sm:p-5">
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
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session.ts'
import type { DoneFile, FpaConfirmationQuestion, RunState } from '@/stores/session.ts'
import { useConfigStore } from '@/stores/config.ts'
import { useLogStore } from '@/stores/log.ts'
import { useStepsStore } from '@/stores/steps.ts'
import { useToastStore } from '@/stores/toast.ts'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import ConfigPanel from '@/components/ConfigPanel.vue'
import GenerationProgress from '@/components/GenerationProgress.vue'
import LogViewer from '@/components/LogViewer.vue'
import ActionBar from '@/components/ActionBar.vue'
import FpaRunSettingsSection from '@/components/run/FpaRunSettingsSection.vue'
import type { StepProgress } from '@/stores/steps.ts'

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
  progress_steps?: Record<string, StepProgress>
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

type FpaConfirmationScope = 'current_run' | 'project_profile'

interface StartupErrorMessage {
  title: string
  detail: string
  nextStep?: string
}

const session = useSessionStore()
const config = useConfigStore()
const log = useLogStore()
const toast = useToastStore()
const steps = useStepsStore()
const route = useRoute()
const LAST_SESSION_KEY = 'ard:lastSessionId'
const UNRECOVERABLE_SESSION_MESSAGE = '会话已结束或服务已重启，无法继续当前执行'
const startupError = ref<StartupErrorMessage | null>(null)
const FOCUS_HIGHLIGHT_CLASSES = [
  'outline',
  'outline-2',
  'outline-offset-4',
  'outline-[var(--color-focus)]',
  'rounded-lg',
]

const runStateLabels = { idle: '就绪', running: '运行中', done: '已完成', error: '出错', cancelled: '已停止' }
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
    cancelled: 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  }
  return map[session.runState]
})
const runDotClass = computed(() => {
  const map = {
    idle: 'bg-[var(--color-ink-soft)]',
    running: 'bg-[var(--color-accent)]',
    done: 'bg-[var(--color-success)]',
    error: 'bg-[var(--color-danger)]',
    cancelled: 'bg-[var(--color-warning)]',
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

// ── 批量 FPA 计量口径确认 ──
const fpaConfirmationSelections = ref<Record<string, string>>({})
const fpaConfirmationScope = ref<FpaConfirmationScope>('current_run')
const fpaConfirmationTitle = computed(() => {
  const prompt = session.fpaConfirmationPrompt
  if (!prompt) return ''
  const moduleName = prompt.module.l3 || '当前三级模块'
  const index = prompt.module.index && prompt.module.total
    ? `（${prompt.module.index}/${prompt.module.total}）`
    : ''
  return `${moduleName}${index}`
})
const canSubmitFpaConfirmation = computed(() => {
  const questions = session.fpaConfirmationPrompt?.questions ?? []
  return questions.length > 0 && questions.every(question => Boolean(fpaConfirmationSelections.value[question.id]))
})

watch(() => session.fpaConfirmationPrompt, (prompt) => {
  fpaConfirmationSelections.value = {}
  fpaConfirmationScope.value = 'current_run'
  for (const question of prompt?.questions ?? []) {
    fpaConfirmationSelections.value[question.id] = question.recommendation
  }
})

function optionLabel(question: FpaConfirmationQuestion, value: string) {
  return question.options.find(option => option.value === value)?.label || value
}

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

async function submitFpaConfirmation() {
  if (!session.sessionId || !session.fpaConfirmationPrompt || !canSubmitFpaConfirmation.value) return
  const confirmedDecisions: Record<string, { value: string; scope: FpaConfirmationScope }> = {}
  for (const question of session.fpaConfirmationPrompt.questions) {
    confirmedDecisions[question.id] = {
      value: fpaConfirmationSelections.value[question.id],
      scope: fpaConfirmationScope.value,
    }
  }
  try {
    await apiFetch('/api/continue/' + session.sessionId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'fpa_confirmation',
        confirmed_decisions: confirmedDecisions,
      }),
    })
  } catch (e) {
    toast.show('error', normalizeApiError(e))
    return
  }
  session.fpaConfirmationPrompt = null
}

async function cancelTask() {
  if (!session.sessionId) return
  try {
    await apiFetch('/api/cancel/' + session.sessionId, { method: 'POST' })
  } catch { /* ignore */ }
}

// ── 任务启动 ──
async function startTask() {
  startupError.value = null
  const mode = config.pipelineMode
  const body = new FormData()
  body.append('mode', mode)
  if (config.apiKeyForRequest) body.append('api_key', config.apiKeyForRequest)
  if (config.model) body.append('model', config.model)
  if (config.baseUrl) body.append('base_url', config.baseUrl)
  if (config.maxTokens) body.append('max_tokens', config.maxTokens)
  if (config.projectName) body.append('project_name', config.projectName)
  if (config.fpaProfile) body.append('fpa_profile', config.fpaProfile)
  if (config.fpaStrategy) body.append('fpa_strategy', config.fpaStrategy)
  if (config.fpaRuleSet) body.append('fpa_rule_set', config.fpaRuleSet)
  if (config.fpaConfirmationMode) body.append('fpa_confirmation_mode', config.fpaConfirmationMode)
  if (config.clean) body.append('clean', '1')

  let url: string
  if (config.workMode === 'local') {
    if (!config.xlsxPath.trim()) {
      const msg = '请输入功能清单 .xlsx 路径'
      startupError.value = {
        title: '任务启动失败',
        detail: msg,
        nextStep: '请检查主操作区中的功能清单路径，然后重新启动生成任务。',
      }
      toast.show('error', msg)
      return
    }
    url = '/api/run-local'
    body.append('xlsx_path', config.xlsxPath)
    body.append('output_dir', config.outputDir)
  } else {
    if (!config.selectedFile) {
      const msg = '请选择要上传的 .xlsx 文件'
      startupError.value = {
        title: '任务启动失败',
        detail: msg,
        nextStep: '请在主操作区选择功能清单 .xlsx 文件，然后重新启动生成任务。',
      }
      toast.show('error', msg)
      return
    }
    url = '/api/run-upload'
    body.append('file', config.selectedFile)
  }

  log.clear()
  session.reset()
  steps.reset()

  try {
    const data = await apiFetch<RunTaskResponse>(url, { method: 'POST', body })
    session.start(data.session_id, data.output_dir || '')
    startupError.value = null
    localStorage.setItem(LAST_SESSION_KEY, data.session_id)
    log.connect()
  } catch (e) {
    const msg = normalizeApiError(e)
    startupError.value = {
      title: '任务启动失败',
      detail: msg,
      nextStep: config.workMode === 'local'
        ? '请检查主操作区中的功能清单路径，然后重新启动生成任务。'
        : '请检查主操作区中的上传文件，然后重新启动生成任务。',
    }
    log.append({ level: 'ERROR', msg: msg, time: '' })
    toast.show('error', msg)
    session.setError()
  }
}

async function restoreSessionById(sid: string, options: { explicit?: boolean } = {}) {
  startupError.value = null
  const explicit = Boolean(options.explicit)
  if (session.sessionId) {
    if (!explicit || session.sessionId === sid) return
    log.close()
    session.reset()
    steps.reset()
  }
  try {
    const data = await apiFetch<SessionStatusResponse>('/api/sessions/' + sid)
    config.workMode = data.mode
    session.restore({
      session_id: data.session_id,
      run_state: data.run_state,
      output_dir: data.output_dir || '',
      done_files: data.done_files || [],
    })
    steps.applySnapshot(data.progress_steps)
    log.clear()
    localStorage.setItem(LAST_SESSION_KEY, data.session_id)
    if (data.run_state === 'running') {
      log.append({ level: 'INFO', msg: '已恢复正在运行的任务，继续接收后续日志', time: '' })
      log.connect()
    } else if (data.run_state === 'done') {
      log.append({ level: 'DONE', msg: '已恢复已完成的任务，可下载交付物', time: '' })
      steps.finishAll()
    } else if (data.run_state === 'cancelled') {
      log.append({ level: 'WARNING', msg: '已恢复已停止的任务', time: '' })
    } else {
      log.append({ level: 'ERROR', msg: '已恢复出错的任务', time: '' })
    }
  } catch {
    if (explicit) {
      session.reset()
      steps.reset()
      log.clear()
      log.append({ level: 'WARNING', msg: UNRECOVERABLE_SESSION_MESSAGE, time: '' })
      toast.show('warning', UNRECOVERABLE_SESSION_MESSAGE, 10000)
    }
    if (localStorage.getItem(LAST_SESSION_KEY) === sid) {
      localStorage.removeItem(LAST_SESSION_KEY)
    }
  }
}

async function restoreLastSession() {
  const sid = localStorage.getItem(LAST_SESSION_KEY)
  if (!sid) return
  await restoreSessionById(sid)
}

function focusGenerationField() {
  const rawFocus = route.query.focus
  const focus = Array.isArray(rawFocus) ? rawFocus[0] : rawFocus
  if (!focus) return
  const selectorMap: Record<string, string> = {
    mode: '[data-focus-target="mode"]',
    input: '[data-focus-target="input"]',
    advanced: '[data-focus-target="advanced"]',
    'fpa-profile': '#fpa-profile',
    'fpa-strategy': '#fpa-strategy',
    'fpa-rule-set': '#fpa-rule-set',
    'fpa-confirmation-mode': '#fpa-confirmation-mode',
  }
  const selector = selectorMap[focus]
  if (!selector) return
  nextTick(() => {
    const element = document.querySelector<HTMLElement>(selector)
    if (!element) return
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    element.classList.add(...FOCUS_HIGHLIGHT_CLASSES)
    window.setTimeout(() => {
      element.classList.remove(...FOCUS_HIGHLIGHT_CLASSES)
    }, 1800)
  })
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
  startupError.value = null
  session.reset()
  log.clear()
  steps.reset()
  localStorage.removeItem(LAST_SESSION_KEY)
}

onMounted(() => {
  const requestedSession = route.query.session
  const sid = Array.isArray(requestedSession) ? requestedSession[0] : requestedSession
  if (sid) {
    restoreSessionById(sid, { explicit: true })
  } else {
    restoreLastSession()
  }
  focusGenerationField()
})
</script>
