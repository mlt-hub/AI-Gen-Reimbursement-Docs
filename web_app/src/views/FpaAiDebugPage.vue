<template>
  <div class="box-border h-full overflow-y-auto px-4 py-6 sm:px-6">
    <div class="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <section class="surface rounded-lg p-5">
        <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0">
            <p class="text-xs font-semibold text-[var(--color-ink-soft)]">FPA 预览</p>
            <h2 class="mt-1 truncate text-lg font-semibold text-[var(--color-ink)]">AI 调试信息</h2>
            <p class="mt-1 text-sm text-[var(--color-ink-muted)]">
              {{ sessionId ? `Session ${sessionId}` : '请先从 FPA 预览或历史任务进入' }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <RouterLink to="/preview/fpa" class="btn-secondary w-fit">返回 FPA 预览</RouterLink>
            <button class="btn-secondary w-fit" :disabled="!sessionId || loading" @click="loadDebug">
              {{ loading ? '刷新中...' : '刷新' }}
            </button>
          </div>
        </div>

        <div v-if="!sessionId" class="mt-5 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-6 text-sm text-[var(--color-ink-muted)]">
          请先从 FPA 预览或历史任务进入 AI 调试信息页。
        </div>

        <div v-else-if="error" class="mt-5 rounded-md border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-sm text-[var(--color-warning)]">
          {{ error }}
        </div>

        <div v-else-if="status" class="mt-5 grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
          <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
            <div class="text-[var(--color-ink-soft)]">状态</div>
            <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ stateLabel(status.run_state) }}</div>
          </div>
          <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
            <div class="text-[var(--color-ink-soft)]">运行模式</div>
            <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ status.mode === 'local' ? '本机' : '远程' }}</div>
          </div>
          <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
            <div class="text-[var(--color-ink-soft)]">交互记录</div>
            <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ interactions.length }}</div>
          </div>
          <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
            <div class="text-[var(--color-ink-soft)]">合并日志</div>
            <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ combinedLog ? '可查看' : '暂无' }}</div>
          </div>
        </div>
      </section>

      <section v-if="sessionId" class="surface overflow-hidden rounded-lg">
        <div class="flex overflow-x-auto border-b border-[var(--color-rule)] px-4">
          <button
            type="button"
            :class="tabClass('list')"
            @click="activeTab = 'list'"
          >
            交互列表
          </button>
          <button
            type="button"
            :class="tabClass('structured')"
            @click="activeTab = 'structured'"
          >
            结构化记录
          </button>
          <button
            type="button"
            :class="tabClass('combined')"
            @click="activeTab = 'combined'"
          >
            合并日志
          </button>
        </div>

        <div class="min-h-[28rem] bg-[var(--color-page)] p-4 sm:p-5">
          <div v-if="loading" class="flex min-h-[20rem] items-center justify-center text-sm text-[var(--color-ink-soft)]">
            加载中...
          </div>

          <template v-else-if="activeTab === 'list'">
            <div v-if="!interactions.length" class="flex min-h-[20rem] items-center justify-center text-sm text-[var(--color-ink-soft)]">
              暂无 AI 交互记录
            </div>
            <div v-else class="space-y-3">
              <article
                v-for="item in interactions"
                :key="item.name"
                class="overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)]"
              >
                <button
                  type="button"
                  class="flex w-full cursor-pointer select-none items-center justify-between gap-3 bg-[var(--color-surface)] px-4 py-2 text-left hover:bg-[var(--color-surface-muted)]"
                  @click="item.expanded = !item.expanded"
                >
                  <span class="flex min-w-0 items-center gap-2 text-sm">
                    <span :class="['rounded px-1.5 py-0.5 text-xs font-bold', aiInteractionBadgeClass(item.type)]">
                      {{ aiInteractionBadgeLabel(item.type) }}
                    </span>
                    <span class="truncate">{{ item.name }}</span>
                  </span>
                  <span class="shrink-0 text-xs text-[var(--color-ink-soft)]">{{ item.expanded ? '收起' : '展开' }}</span>
                </button>
                <pre v-show="item.expanded" class="m-0 max-h-[32rem] overflow-auto whitespace-pre-wrap bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300">{{ item.content }}</pre>
              </article>
            </div>
          </template>

          <template v-else-if="activeTab === 'structured'">
            <div v-if="!structuredRecords.length" class="flex min-h-[20rem] items-center justify-center text-sm text-[var(--color-ink-soft)]">
              暂无结构化调试记录
            </div>
            <div v-else class="space-y-4">
              <div class="grid gap-3 md:grid-cols-4">
                <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                  <div class="text-xs text-[var(--color-ink-soft)]">结构化记录</div>
                  <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ filteredRecords.length }}</div>
                </div>
                <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                  <div class="text-xs text-[var(--color-ink-soft)]">筛选模型</div>
                  <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ recordFilters.model || '全部' }}</div>
                </div>
                <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                  <div class="text-xs text-[var(--color-ink-soft)]">筛选功能点</div>
                  <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ recordFilters.functionPoint || '全部' }}</div>
                </div>
                <div class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                  <div class="text-xs text-[var(--color-ink-soft)]">筛选模块</div>
                  <div class="mt-1 font-semibold text-[var(--color-ink)]">{{ recordFilters.module || '全部' }}</div>
                </div>
              </div>

              <div class="grid gap-3 md:grid-cols-3">
                <div>
                  <label class="field-label text-xs">模型</label>
                  <select v-model="recordFilters.model" class="field-control">
                    <option value="">全部</option>
                    <option v-for="option in structuredFilters.models" :key="option" :value="option">{{ option }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label text-xs">功能点</label>
                  <select v-model="recordFilters.functionPoint" class="field-control">
                    <option value="">全部</option>
                    <option v-for="option in structuredFilters.function_points" :key="option" :value="option">{{ option }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label text-xs">模块</label>
                  <select v-model="recordFilters.module" class="field-control">
                    <option value="">全部</option>
                    <option v-for="option in structuredFilters.modules" :key="option" :value="option">{{ option }}</option>
                  </select>
                </div>
              </div>

              <div class="space-y-3">
                <article
                  v-for="record in filteredRecords"
                  :key="record.id"
                  class="overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)]"
                >
                  <button
                    type="button"
                    class="flex w-full items-center justify-between gap-3 bg-[var(--color-surface)] px-4 py-3 text-left hover:bg-[var(--color-surface-muted)]"
                    @click="toggleRecord(record.id)"
                  >
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--color-ink)]">
                        <span>{{ record.module || record.id }}</span>
                        <span class="rounded px-1.5 py-0.5 text-xs font-bold bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]">
                          {{ record.ai_called ? 'AI' : '规则' }}
                        </span>
                        <span v-if="record.model" class="text-xs font-normal text-[var(--color-ink-soft)]">{{ record.model }}</span>
                      </div>
                      <div class="mt-1 text-xs text-[var(--color-ink-soft)]">
                        原因：{{ record.reason || '未记录' }}
                        <span v-if="record.function_points.length"> · 功能点：{{ record.function_points.join(' / ') }}</span>
                      </div>
                    </div>
                    <span class="shrink-0 text-xs text-[var(--color-ink-soft)]">{{ record.expanded ? '收起' : '展开' }}</span>
                  </button>
                  <div v-show="record.expanded" class="space-y-3 border-t border-[var(--color-rule)] p-4">
                    <div class="grid gap-3 md:grid-cols-3">
                      <div>
                        <div class="text-xs font-semibold text-[var(--color-ink-soft)]">Prompt 文件</div>
                        <pre class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ record.prompt || '（空）' }}</pre>
                      </div>
                      <div>
                        <div class="text-xs font-semibold text-[var(--color-ink-soft)]">Response 文件</div>
                        <pre class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ record.response || '（空）' }}</pre>
                      </div>
                      <div>
                        <div class="text-xs font-semibold text-[var(--color-ink-soft)]">Thinking 文件</div>
                        <pre class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ record.thinking || '（空）' }}</pre>
                      </div>
                    </div>
                    <div class="grid gap-3 md:grid-cols-2">
                      <div>
                        <div class="text-xs font-semibold text-[var(--color-ink-soft)]">Parsed Rows</div>
                        <pre class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ formatJson(record.parsed_rows) }}</pre>
                      </div>
                      <div>
                        <div class="text-xs font-semibold text-[var(--color-ink-soft)]">Quality Review</div>
                        <pre class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ formatJson(record.quality_review) }}</pre>
                      </div>
                    </div>
                    <div v-if="record.error" class="rounded-md border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-sm text-[var(--color-warning)]">
                      {{ record.error }}
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </template>

          <template v-else>
            <pre v-if="combinedLog" class="m-0 min-h-[20rem] overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300">{{ combinedLog }}</pre>
            <div v-else class="flex min-h-[20rem] items-center justify-center text-sm text-[var(--color-ink-soft)]">
              暂无合并日志
            </div>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import type { RunState } from '@/stores/session.ts'

interface SessionStatusResponse {
  session_id: string
  mode: 'local' | 'remote'
  run_state: RunState
}

interface AiInteraction {
  name: string
  type: 'prompt' | 'response' | 'thinking'
  content: string
  expanded?: boolean
}

interface AiInteractionsResponse {
  interactions?: Omit<AiInteraction, 'expanded'>[]
}

interface StructuredFpaDebugRecord {
  id: string
  source: string
  module: string
  model: string
  reason: string
  ai_called: boolean
  prompt_file: string
  response_file: string
  thinking_file: string
  prompt: string
  response: string
  thinking: string
  parsed_rows: unknown[]
  final_rows: unknown[]
  quality_review: Record<string, unknown>
  error: string
  function_points: string[]
  expanded?: boolean
}

interface StructuredFpaDebugResponse {
  session_id?: string
  count?: number
  records?: Omit<StructuredFpaDebugRecord, 'expanded'>[]
  filters?: {
    models?: string[]
    modules?: string[]
    function_points?: string[]
  }
}

interface AiLogResponse {
  content?: string
}

const route = useRoute()
const sessionId = computed(() => String(route.params.sessionId || '').trim())
const loading = ref(false)
const error = ref('')
const activeTab = ref<'list' | 'structured' | 'combined'>('list')
const status = ref<SessionStatusResponse | null>(null)
const interactions = ref<AiInteraction[]>([])
const structuredRecords = ref<StructuredFpaDebugRecord[]>([])
const structuredFilters = ref({
  models: [] as string[],
  modules: [] as string[],
  function_points: [] as string[],
})
const recordFilters = ref({
  model: '',
  module: '',
  functionPoint: '',
})
const combinedLog = ref('')

function stateLabel(state: RunState) {
  const map: Record<RunState, string> = {
    idle: '就绪',
    queued: '排队中',
    running: '运行中',
    done: '完成',
    error: '失败',
    cancelled: '已取消',
  }
  return map[state] || state
}

function tabClass(tab: 'list' | 'structured' | 'combined') {
  return [
    'shrink-0 border-b-2 px-4 py-3 text-sm transition-colors',
    activeTab.value === tab
      ? 'border-[var(--color-accent)] font-semibold text-[var(--color-accent-strong)]'
      : 'border-transparent text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]',
  ]
}

function aiInteractionBadgeClass(type: AiInteraction['type']) {
  if (type === 'prompt') return 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
  if (type === 'thinking') return 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]'
  return 'bg-[var(--color-success-soft)] text-[var(--color-success)]'
}

function aiInteractionBadgeLabel(type: AiInteraction['type']) {
  if (type === 'prompt') return 'P'
  if (type === 'thinking') return 'T'
  return 'R'
}

async function loadDebug() {
  if (!sessionId.value) return
  loading.value = true
  error.value = ''
  try {
    const [statusResult, interactionsResult, structuredResult, logResult] = await Promise.allSettled([
      apiFetch<SessionStatusResponse>('/api/sessions/' + sessionId.value),
      apiFetch<AiInteractionsResponse>('/api/ai-interactions/' + sessionId.value),
      apiFetch<StructuredFpaDebugResponse>('/api/sessions/' + sessionId.value + '/fpa/debug-records'),
      apiFetch<AiLogResponse>('/api/ai-log/' + sessionId.value),
    ])

    if (statusResult.status === 'fulfilled') {
      status.value = statusResult.value
    } else {
      throw statusResult.reason
    }

    interactions.value = interactionsResult.status === 'fulfilled'
      ? (interactionsResult.value.interactions || []).map(item => ({ ...item, expanded: false }))
      : []
    structuredRecords.value = structuredResult.status === 'fulfilled'
      ? (structuredResult.value.records || []).map(item => ({ ...item, expanded: false }))
      : []
    structuredFilters.value = structuredResult.status === 'fulfilled'
      ? {
        models: structuredResult.value.filters?.models || [],
        modules: structuredResult.value.filters?.modules || [],
        function_points: structuredResult.value.filters?.function_points || [],
      }
      : { models: [], modules: [], function_points: [] }
    combinedLog.value = logResult.status === 'fulfilled' ? (logResult.value.content || '') : ''
  } catch (err) {
    error.value = normalizeApiError(err)
    interactions.value = []
    structuredRecords.value = []
    combinedLog.value = ''
  } finally {
    loading.value = false
  }
}

const filteredRecords = computed(() => {
  return structuredRecords.value.filter(record => {
    if (recordFilters.value.model && record.model !== recordFilters.value.model) return false
    if (recordFilters.value.module && record.module !== recordFilters.value.module) return false
    if (recordFilters.value.functionPoint && !record.function_points.includes(recordFilters.value.functionPoint)) return false
    return true
  })
})

function toggleRecord(id: string) {
  const record = structuredRecords.value.find(item => item.id === id)
  if (record) {
    record.expanded = !record.expanded
  }
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '（无法显示）'
  }
}

onMounted(loadDebug)
</script>
