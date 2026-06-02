<template>
  <div class="flex h-full min-h-0 flex-col">
    <div class="border-b border-[var(--color-rule)] px-5 py-4">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_180px_160px_180px]">
          <div>
            <label for="fpa-preview-module" class="field-label text-xs">三级模块</label>
            <select
              id="fpa-preview-module"
              v-model="selectedModuleIndex"
              class="field-control"
              :disabled="!modules.length || modulesLoading || previewLoading"
            >
              <option value="">请先生成基础数据</option>
              <option v-for="module in modules" :key="module.index" :value="String(module.index)">
                {{ module.label }}
              </option>
            </select>
          </div>
          <div>
            <label for="fpa-preview-profile" class="field-label text-xs">FPA 方案</label>
            <select id="fpa-preview-profile" v-model="config.fpaProfile" class="field-control">
              <option v-for="profile in fpaOptions.profiles" :key="profile.name" :value="profile.name">
                {{ profile.label }}
              </option>
            </select>
          </div>
          <div>
            <label for="fpa-preview-strategy" class="field-label text-xs">执行策略</label>
            <select id="fpa-preview-strategy" v-model="config.fpaStrategy" class="field-control">
              <option value="">{{ defaultStrategyLabel }}</option>
              <option v-for="strategy in fpaOptions.strategies" :key="strategy.name" :value="strategy.name">
                {{ strategy.label }}
              </option>
            </select>
          </div>
          <div>
            <label for="fpa-preview-rule-set" class="field-label text-xs">规则集</label>
            <select id="fpa-preview-rule-set" v-model="config.fpaRuleSet" class="field-control">
              <option value="">{{ defaultRuleSetLabel }}</option>
              <option v-for="ruleSet in fpaOptions.rule_sets" :key="ruleSet.name" :value="ruleSet.name">
                {{ ruleSet.label }}
              </option>
            </select>
          </div>
        </div>
        <div v-if="fpaOptionsError" class="text-xs text-[var(--color-warning)]">{{ fpaOptionsError }}</div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-h-5 text-xs text-[var(--color-ink-soft)]">
            <span v-if="modules.length">已生成 {{ modules.length }} 个三级模块，可从下拉框选择。</span>
            <span v-else>先生成基础数据，再选择三级模块预览 FPA 行。</span>
          </div>
          <div class="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              class="btn-secondary inline-flex shrink-0 items-center justify-center gap-2 px-5"
              :disabled="!canLoadModules || modulesLoading"
              @click="loadModules"
            >
              <ArrowPathIcon class="h-4 w-4" />
              {{ modulesLoading ? '生成中...' : '生成基础数据' }}
            </button>
            <button
              type="button"
              class="btn-primary inline-flex shrink-0 items-center justify-center gap-2 px-5"
              :disabled="!canPreview || previewLoading"
              @click="runPreview"
            >
              <MagnifyingGlassIcon class="h-4 w-4" />
              {{ previewLoading ? '生成中...' : '生成预览' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto p-5">
      <div v-if="!config.isValid" class="rounded-lg border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-[var(--color-warning)]">
        请先在输入设置中选择功能清单输入来源。
      </div>

      <div v-else-if="!modules.length" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-ink-muted)]">
        点击“生成基础数据”后，系统会解析功能清单并列出可预览的三级模块。
      </div>

      <div v-else-if="!selectedModuleIndex" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-ink-muted)]">
        从下拉框选择一个三级模块后生成预览。
      </div>

      <div v-if="error" class="mt-4 rounded-md border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-3 py-2 text-sm text-[var(--color-danger)]">
        {{ error }}
      </div>

      <div v-if="moduleWarnings.length" class="mt-4 rounded-md border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-xs text-[var(--color-warning)]">
        <div v-for="item in moduleWarnings" :key="item" class="leading-5">{{ item }}</div>
      </div>

      <div v-if="result" class="mt-5 space-y-3">
        <div class="flex items-center justify-between gap-3 rounded-md border border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-3">
          <div class="min-w-0 leading-tight">
            <div class="text-sm font-semibold text-[var(--color-ink)]">FPA 功能点估算</div>
            <div class="mt-1 truncate text-xs font-semibold text-[var(--color-ink-muted)]">{{ result.module.l3 }}</div>
            <div class="text-xs text-[var(--color-ink-soft)]">{{ result.module.process_count }} 个功能过程 · {{ profileLabel(result.profile) }} · {{ strategyLabel(result.strategy) }}</div>
          </div>
          <span :class="['shrink-0 rounded px-2 py-1 text-xs font-semibold', result.used_ai ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]' : 'bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]']">
            {{ result.used_ai ? 'AI' : '兜底' }}
          </span>
        </div>

        <div class="overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)]">
          <div class="divide-y divide-[var(--color-rule)] md:hidden">
            <article v-for="(row, idx) in result.rows" :key="idx" class="px-3 py-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-xs font-semibold text-[var(--color-ink-soft)]">新增/修改功能点 #{{ idx + 1 }}</div>
                  <div class="mt-1 break-words text-sm font-semibold leading-5 text-[var(--color-ink)]">{{ row.name }}</div>
                </div>
                <span class="shrink-0 rounded bg-[var(--color-accent-soft)] px-2 py-1 text-xs font-semibold text-[var(--color-accent-strong)]">{{ row.type }}</span>
              </div>

              <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div class="rounded-md bg-[var(--color-surface-muted)] px-2 py-1.5">
                  <div class="text-[var(--color-ink-soft)]">类型</div>
                  <div class="mt-0.5 font-semibold text-[var(--color-ink)]">{{ row.type }}</div>
                </div>
                <div class="rounded-md bg-[var(--color-surface-muted)] px-2 py-1.5">
                  <div class="text-[var(--color-ink-soft)]">生成方式</div>
                  <div class="mt-0.5 font-semibold text-[var(--color-ink)]">{{ row.generation }}</div>
                </div>
              </div>

              <div class="mt-3 text-xs leading-5 text-[var(--color-ink-muted)]">
                <div class="font-semibold text-[var(--color-ink)]">计算依据归类</div>
                <div class="mt-1 break-words">{{ row.classification_basis || '-' }}</div>
              </div>

              <details v-if="row.explanation" class="mt-3 rounded-md border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-2">
                <summary class="subtle-link cursor-pointer select-none text-xs">计算依据说明</summary>
                <div class="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-[var(--color-ink-muted)]">{{ row.explanation }}</div>
              </details>
            </article>
          </div>

          <div class="hidden overflow-x-auto md:block">
            <table class="w-full min-w-[760px] text-left text-xs">
              <thead class="bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]">
                <tr>
                  <th class="w-12 px-3 py-2 font-semibold">#</th>
                  <th class="px-3 py-2 font-semibold">新增/修改功能点</th>
                  <th class="w-16 px-3 py-2 font-semibold">类型</th>
                  <th class="w-20 px-3 py-2 font-semibold">生成方式</th>
                  <th class="px-3 py-2 font-semibold">计算依据归类</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in result.rows" :key="idx" class="border-t border-[var(--color-rule)] align-top">
                  <td class="px-3 py-2 text-[var(--color-ink-soft)]">{{ idx + 1 }}</td>
                  <td class="px-3 py-2">
                    <div class="font-medium text-[var(--color-ink)]">{{ row.name }}</div>
                    <div v-if="row.explanation" class="mt-2 text-[var(--color-ink-soft)]">
                      <span class="font-semibold text-[var(--color-ink-muted)]">计算依据说明：</span>
                      <span class="whitespace-pre-wrap leading-5">{{ row.explanation }}</span>
                    </div>
                  </td>
                  <td class="px-3 py-2">
                    <span class="inline-flex rounded bg-[var(--color-accent-soft)] px-2 py-1 font-semibold text-[var(--color-accent-strong)]">{{ row.type }}</span>
                  </td>
                  <td class="px-3 py-2 text-[var(--color-ink-soft)]">{{ row.generation }}</td>
                  <td class="px-3 py-2 text-[var(--color-ink-muted)]">{{ row.classification_basis || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="previewWarnings.length" class="border-t border-[var(--color-rule)] px-3 py-2 text-xs text-[var(--color-warning)]">
            <div v-for="item in previewWarnings" :key="item" class="leading-5">{{ item }}</div>
          </div>

          <div v-if="result.audit" class="border-t border-[var(--color-rule)] px-3 py-2">
            <details open>
              <summary class="subtle-link cursor-pointer select-none text-xs">审核信息</summary>
              <div class="mt-3 grid grid-cols-2 gap-3 text-xs md:grid-cols-3">
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="text-[var(--color-ink-soft)]">功能过程覆盖</div>
                  <div class="mt-1 text-base font-semibold text-[var(--color-ink)]">{{ result.audit.coverage.covered_count }}/{{ result.audit.coverage.process_total }}</div>
                </div>
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="text-[var(--color-ink-soft)]">未覆盖</div>
                  <div class="mt-1 text-base font-semibold text-[var(--color-ink)]">{{ result.audit.coverage.missing_count }}</div>
                </div>
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="text-[var(--color-ink-soft)]">规则集</div>
                  <div class="mt-1 truncate font-semibold text-[var(--color-ink)]">{{ result.audit.rule_set }}</div>
                </div>
              </div>

              <div class="mt-3 grid gap-3 text-xs md:grid-cols-2">
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">生成方式</div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span v-for="item in generationCountEntries" :key="item[0]" class="rounded bg-[var(--color-surface)] px-2 py-1 text-[var(--color-ink-muted)]">
                      {{ item[0] }}: {{ item[1] }}
                    </span>
                  </div>
                </div>
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">缺失功能过程</div>
                  <div v-if="result.audit.coverage.missing_processes.length" class="mt-2 space-y-1 text-[var(--color-warning)]">
                    <div v-for="item in result.audit.coverage.missing_processes" :key="item">{{ item }}</div>
                  </div>
                  <div v-else class="mt-2 text-[var(--color-ink-muted)]">无</div>
                </div>
              </div>
            </details>
          </div>

          <div v-if="result.debug" class="border-t border-[var(--color-rule)] px-3 py-2">
            <details>
              <summary class="subtle-link cursor-pointer select-none text-xs">
                AI 调试信息
                <span class="ml-2 text-[var(--color-ink-soft)]">{{ result.debug.ai_called ? '已调用 AI' : debugReasonLabel(result.debug.reason) }}</span>
              </summary>
              <div class="mt-3 space-y-3 text-xs">
                <div v-if="result.debug.error" class="rounded-md border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-[var(--color-warning)]">
                  {{ result.debug.error }}
                </div>
                <div v-if="result.debug.system_prompt" class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-[var(--color-ink)]">系统提示词</span>
                    <span class="text-[var(--color-ink-soft)]">{{ result.debug.system_prompt_source || '未配置' }}</span>
                  </div>
                  <pre class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ result.debug.system_prompt }}</pre>
                </div>
                <div v-if="result.debug.user_prompt" class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-[var(--color-ink)]">用户提示词</span>
                    <span class="text-[var(--color-ink-soft)]">{{ result.debug.user_prompt_source || '未配置' }}</span>
                  </div>
                  <pre class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ result.debug.user_prompt }}</pre>
                </div>
                <div v-if="result.debug.ai_prompt" class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">AI Prompts</div>
                  <pre class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ result.debug.ai_prompt }}</pre>
                </div>
                <div v-if="result.debug.raw_response" class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">AI Responses</div>
                  <pre class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ result.debug.raw_response }}</pre>
                </div>
                <div class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">AI Thinking</div>
                  <pre v-if="result.debug.thinking" class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ result.debug.thinking }}</pre>
                  <div v-else class="mt-2 text-[var(--color-ink-soft)]">当前模型未返回思考过程</div>
                </div>
                <div v-if="result.debug.parsed_rows.length" class="rounded-md bg-[var(--color-surface-muted)] p-3">
                  <div class="font-semibold text-[var(--color-ink)]">解析结果</div>
                  <pre class="mt-2 whitespace-pre-wrap break-words font-mono leading-5 text-[var(--color-ink-muted)]">{{ stringifyDebug(result.debug.parsed_rows) }}</pre>
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowPathIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import { useConfigStore } from '@/stores/config.ts'
import { useSessionStore } from '@/stores/session.ts'
import { useToastStore } from '@/stores/toast.ts'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import { useFpaOptions } from '@/composables/useFpaOptions.ts'

interface FpaPreviewRow {
  name: string
  type: string
  type_reason: string
  classification_basis: string
  classification_basis_index: number | null
  explanation: string
  source_processes: string[]
  generation: string
}

interface FpaPreviewDebug {
  ai_called: boolean
  reason?: string
  model?: string
  system_prompt: string
  system_prompt_source: string
  user_prompt: string
  user_prompt_source: string
  ai_prompt: string
  raw_response: string
  thinking: string
  parsed_rows: unknown[]
  final_rows: FpaPreviewRow[]
  error?: string
}

interface FpaPreviewResult {
  module: {
    index: number
    client_type: string
    l1: string
    l2: string
    l3: string
    process_count: number
  }
  rows: FpaPreviewRow[]
  warnings: string[]
  used_ai: boolean
  profile: string
  profile_version: string
  strategy: string
  rule_set: string
  audit?: FpaAuditReport
  debug?: FpaPreviewDebug
}

interface FpaAuditReport {
  profile: string
  profile_version: string
  strategy: string
  rule_set: string
  coverage: {
    process_total: number
    covered_count: number
    missing_count: number
    covered_processes: string[]
    missing_processes: string[]
  }
  generation_counts: Record<string, number>
  warnings: string[]
}

interface FpaPreviewModule {
  index: number
  client_type: string
  l1: string
  l2: string
  l3: string
  l3_desc: string
  process_count: number
  label: string
}

interface FpaPreviewModulesResult {
  modules: FpaPreviewModule[]
  warnings: string[]
}

const config = useConfigStore()
const session = useSessionStore()
const toast = useToastStore()
const { fpaOptions, fpaOptionsError, loadFpaOptions } = useFpaOptions()

const modules = ref<FpaPreviewModule[]>([])
const moduleWarnings = ref<string[]>([])
const selectedModuleIndex = ref('')
const modulesLoading = ref(false)
const previewLoading = ref(false)
const error = ref('')
const result = ref<FpaPreviewResult | null>(null)

const previewWarnings = computed(() => result.value?.warnings ?? [])
const generationCountEntries = computed(() => Object.entries(result.value?.audit?.generation_counts ?? {}))
const canLoadModules = computed(() => config.isValid && !session.isRunning && !previewLoading.value)
const canPreview = computed(() => config.isValid && selectedModuleIndex.value !== '' && !session.isRunning && !modulesLoading.value)
const selectedProfile = computed(() => (
  fpaOptions.value.profiles.find(profile => profile.name === config.fpaProfile)
  ?? fpaOptions.value.profiles[0]
))
const defaultStrategyLabel = computed(() => {
  const strategy = fpaOptions.value.strategies.find(item => item.name === selectedProfile.value?.strategy)
  return strategy ? `默认（${strategy.label}）` : '默认'
})
const defaultRuleSetLabel = computed(() => (
  selectedProfile.value?.rule_set ? `默认（${selectedProfile.value.rule_set}）` : '默认'
))

watch(
  () => [config.workMode, config.xlsxPath, config.selectedFile],
  () => {
    modules.value = []
    moduleWarnings.value = []
    selectedModuleIndex.value = ''
    result.value = null
    error.value = ''
  },
)

watch(
  fpaOptions,
  options => {
    if (config.fpaRuleSet && !options.rule_sets.some(ruleSet => ruleSet.name === config.fpaRuleSet)) {
      config.fpaRuleSet = ''
    }
  },
  { immediate: true },
)

onMounted(loadFpaOptions)

function appendInputSource(body: FormData) {
  if (config.workMode === 'local') {
    body.append('xlsx_path', config.xlsxPath)
  } else if (config.selectedFile) {
    body.append('file', config.selectedFile)
  }
}

async function loadModules() {
  if (!canLoadModules.value) return
  modulesLoading.value = true
  error.value = ''
  result.value = null
  moduleWarnings.value = []
  selectedModuleIndex.value = ''

  const body = new FormData()
  appendInputSource(body)

  try {
    const data = await apiFetch<FpaPreviewModulesResult>('/api/fpa/preview-modules', {
      method: 'POST',
      body,
    })
    modules.value = data.modules ?? []
    moduleWarnings.value = data.warnings ?? []
    selectedModuleIndex.value = modules.value.length ? String(modules.value[0].index) : ''
  } catch (e) {
    const msg = normalizeApiError(e)
    error.value = msg
    toast.show('error', msg)
  } finally {
    modulesLoading.value = false
  }
}

async function runPreview() {
  if (!canPreview.value) return
  previewLoading.value = true
  error.value = ''
  result.value = null

  const body = new FormData()
  body.append('module_index', selectedModuleIndex.value)
  if (config.apiKeyForRequest) body.append('api_key', config.apiKeyForRequest)
  if (config.model) body.append('model', config.model)
  if (config.baseUrl) body.append('base_url', config.baseUrl)
  if (config.fpaProfile) body.append('fpa_profile', config.fpaProfile)
  if (config.fpaStrategy) body.append('fpa_strategy', config.fpaStrategy)
  if (config.fpaRuleSet) body.append('fpa_rule_set', config.fpaRuleSet)
  appendInputSource(body)

  try {
    result.value = await apiFetch<FpaPreviewResult>('/api/fpa/preview-module', {
      method: 'POST',
      body,
    })
  } catch (e) {
    const msg = normalizeApiError(e)
    error.value = msg
    toast.show('error', msg)
  } finally {
    previewLoading.value = false
  }
}

function profileLabel(profile: string) {
  return fpaOptions.value.profiles.find(item => item.name === profile)?.label ?? profile
}

function strategyLabel(strategy: string) {
  return fpaOptions.value.strategies.find(item => item.name === strategy)?.label ?? strategy
}

function debugReasonLabel(reason?: string) {
  const labels: Record<string, string> = {
    rules_first: '规则优先',
    rules_only: '仅规则',
    missing_api_key: '缺少 API Key',
    ai_failed_fallback: 'AI 失败后兜底',
  }
  return labels[reason || ''] ?? '未调用 AI'
}

function stringifyDebug(value: unknown) {
  return JSON.stringify(value, null, 2)
}
</script>
