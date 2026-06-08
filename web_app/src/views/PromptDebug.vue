<template>
  <div class="flex h-full min-w-0 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
    <!-- 左侧：通用提示词调试器 -->
    <div class="flex min-h-[520px] min-w-0 flex-1 flex-col bg-[var(--color-surface-raised)] p-4 sm:p-5 lg:min-h-0 lg:overflow-y-auto">
      <h2 class="mb-4 text-base font-semibold text-[var(--color-ink)]">通用提示词调试</h2>

      <label class="mb-1 text-sm font-medium text-[var(--color-ink-muted)]">
        系统提示词 <span class="ml-1 text-xs font-normal text-[var(--color-ink-soft)]">{{ systemPrompt.length }} 字</span>
      </label>
      <textarea v-model="systemPrompt"
        placeholder="可选，系统级指令（角色设定、输出格式等）"
        class="field-control min-h-[140px] resize-y font-mono leading-relaxed lg:flex-1" />

      <label class="mb-1 mt-4 text-sm font-medium text-[var(--color-ink-muted)]">
        用户提示词 <span class="ml-1 text-xs font-normal text-[var(--color-ink-soft)]">{{ userPrompt.length }} 字</span>
      </label>
      <textarea v-model="userPrompt"
        placeholder="可选，具体的任务描述或问题"
        class="field-control min-h-[140px] resize-y font-mono leading-relaxed lg:flex-1"
        @keydown="onKeydown" />

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <button @click="submitPrompt" :disabled="running"
          class="btn-primary">
          发送给 AI
        </button>
        <button @click="clearAll" class="btn-secondary">清空</button>
        <span :class="['text-sm font-medium sm:ml-auto',
          runState === 'idle' ? 'text-[var(--color-ink-soft)]' : runState === 'running' ? 'text-[var(--color-accent-strong)]' : runState === 'done' ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">
          {{ { idle: '就绪', running: '请求中...', done: '完成', error: '失败' }[runState] }}
        </span>
      </div>

      <details class="mt-4">
        <summary class="subtle-link cursor-pointer select-none text-sm">高级选项</summary>
        <div class="mt-3 grid grid-cols-1 gap-3 border-t border-[var(--color-rule)] pt-3 xl:grid-cols-3">
          <input ref="apiKeyInput" type="password" v-model.trim="apiKey"
            placeholder="API Key（留空使用系统配置）" autocomplete="new-password" autocapitalize="off"
            autocorrect="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true"
            :name="apiKeyInputName" :readonly="apiKeyReadonly" @focus="activateApiKeyInput"
            @pointerdown="activateApiKeyInput"
            class="field-control min-w-0" />
          <input type="text" v-model="model" placeholder="模型（默认 deepseek-v4-flash）"
            class="field-control min-w-0" />
          <input type="text" v-model="baseUrl" placeholder="API 端点（留空使用默认）"
            class="field-control min-w-0" />
        </div>
      </details>
    </div>

    <!-- 右侧：结果 + 快捷测试 -->
    <div class="flex min-h-[520px] min-w-0 flex-none flex-col overflow-hidden bg-[var(--color-console)] lg:min-h-0 lg:w-[45%] lg:min-w-[320px]">
      <!-- 快捷测试工具 -->
      <details class="border-b border-[var(--color-console-line)]">
        <summary class="cursor-pointer select-none px-4 py-2 text-sm text-slate-400 hover:text-slate-300">快捷测试工具</summary>
        <div class="space-y-3 px-4 pb-4">
          <!-- 可靠性描述测试 -->
          <div class="rounded-lg bg-[var(--color-console-line)] p-3">
            <h4 class="mb-2 text-xs font-medium text-slate-400">调整因子 — 可靠性描述 AI 生成</h4>
            <div class="flex min-w-0 flex-col gap-2 sm:flex-row">
              <input v-model="quickXlsx" type="text" placeholder="功能清单 .xlsx 路径（留空自动搜索）"
                class="min-w-0 flex-1 rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 focus:border-[var(--color-focus)] focus:outline-none" />
              <button @click="runQuickTest('reliability')" :disabled="quickRunning"
                class="btn-secondary min-h-0 whitespace-nowrap px-3 py-1.5 text-xs">
                {{ quickRunning ? '...' : '执行' }}
              </button>
            </div>
          </div>
          <!-- 元数据测试 -->
          <div class="rounded-lg bg-[var(--color-console-line)] p-3">
            <h4 class="mb-2 text-xs font-medium text-slate-400">元数据 #AI生成# 字段测试</h4>
            <div class="flex min-w-0 flex-col gap-2 sm:flex-row">
              <input v-model="quickXlsx" type="text" placeholder="功能清单 .xlsx 路径"
                class="min-w-0 flex-1 rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 focus:border-[var(--color-focus)] focus:outline-none" />
              <input v-model="quickField" type="text" placeholder="字段 key"
                class="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 focus:border-[var(--color-focus)] focus:outline-none sm:w-32" />
              <button @click="runQuickTest('metadata')" :disabled="quickRunning"
                class="btn-secondary min-h-0 whitespace-nowrap px-3 py-1.5 text-xs">
                {{ quickRunning ? '...' : '执行' }}
              </button>
            </div>
          </div>
          <!-- 快捷测试结果 -->
          <pre v-if="quickResult" class="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console-line)] p-3 text-xs text-slate-300">{{ quickResult }}</pre>
        </div>
      </details>

      <!-- 结果区 -->
      <h3 class="px-5 pt-4 text-xs font-medium text-slate-500">AI 返回结果</h3>
      <div class="flex-1 overflow-y-auto p-5">
        <div v-if="!resultText && !running" class="flex h-full items-center justify-center text-sm text-slate-500">
          提交提示词后，AI 返回结果将显示在此处
        </div>
        <div v-else-if="running" class="flex h-full items-center justify-center text-sm text-slate-500">
          等待 AI 响应...
        </div>
        <div v-else class="space-y-3">
          <!-- 折叠块 -->
          <div v-if="resultSysPrompt" class="overflow-hidden rounded-lg border border-[var(--color-console-line)]">
            <div @click="fold.sys = !fold.sys"
              :class="['flex cursor-pointer select-none items-center gap-2 bg-[var(--color-console-line)] px-4 py-2 text-sm text-slate-400 hover:text-slate-300', fold.sys ? 'collapsed' : '']">
              <span class="text-xs transition-transform" :class="fold.sys ? '-rotate-90' : ''">▼</span>
              系统提示词（{{ resultSysPrompt.length }} 字）
            </div>
            <pre v-show="!fold.sys" class="max-h-60 overflow-y-auto whitespace-pre-wrap p-3 text-sm leading-relaxed text-slate-300">{{ resultSysPrompt }}</pre>
          </div>
          <div v-if="resultUserPrompt" class="overflow-hidden rounded-lg border border-[var(--color-console-line)]">
            <div @click="fold.user = !fold.user"
              :class="['flex cursor-pointer select-none items-center gap-2 bg-[var(--color-console-line)] px-4 py-2 text-sm text-slate-400 hover:text-slate-300', fold.user ? 'collapsed' : '']">
              <span class="text-xs transition-transform" :class="fold.user ? '-rotate-90' : ''">▼</span>
              用户提示词（{{ resultUserPrompt.length }} 字）
            </div>
            <pre v-show="!fold.user" class="max-h-60 overflow-y-auto whitespace-pre-wrap p-3 text-sm leading-relaxed text-slate-300">{{ resultUserPrompt }}</pre>
          </div>
          <div v-if="resultThinking" class="overflow-hidden rounded-lg border border-[var(--color-console-line)]">
            <div @click="fold.thinking = !fold.thinking"
              :class="['flex cursor-pointer select-none items-center gap-2 bg-[var(--color-console-line)] px-4 py-2 text-sm text-slate-400 hover:text-slate-300']">
              <span class="text-xs">▼</span>
              思考过程（{{ resultThinking.length }} 字）
            </div>
            <pre class="max-h-60 overflow-y-auto whitespace-pre-wrap p-3 text-sm leading-relaxed text-slate-300">{{ resultThinking }}</pre>
          </div>
          <!-- 最终结果 -->
          <div>
            <h4 class="mb-2 text-xs font-medium text-slate-500">AI 返回结果（{{ resultText.length }} 字）</h4>
            <div class="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{{ resultText }}</div>
          </div>
          <p class="text-right text-xs text-slate-600">结果 {{ resultText.length }} 字</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import { useSensitiveInputGuard } from '@/composables/useSensitiveInputGuard.ts'
import { normalizeApiKeyInput } from '@/stores/config.ts'

interface PromptTestResponse {
  system_prompt?: string
  user_prompt?: string
  thinking?: string
  result?: string
}

interface QuickTestResponse {
  result?: string
  detail?: string
}

// ── 通用提示词调试 ──
const systemPrompt = ref('')
const userPrompt = ref('')
const apiKey = ref('')
const model = ref('')
const baseUrl = ref('')
const apiKeyInput = ref<HTMLInputElement | null>(null)
const {
  inputName: apiKeyInputName,
  readonly: apiKeyReadonly,
  activateSensitiveInput: activateApiKeyInput,
} = useSensitiveInputGuard('prompt-api-key', {
  inputRef: apiKeyInput,
  getValue: () => apiKey.value,
  setValue: value => { apiKey.value = value },
})
const running = ref(false)
const runState = ref<'idle' | 'running' | 'done' | 'error'>('idle')

const resultText = ref('')
const resultSysPrompt = ref('')
const resultUserPrompt = ref('')
const resultThinking = ref('')
const fold = reactive({ sys: true, user: true, thinking: false })

async function submitPrompt() {
  if (!systemPrompt.value.trim() && !userPrompt.value.trim()) {
    alert('请至少输入系统提示词或用户提示词')
    return
  }
  running.value = true
  runState.value = 'running'
  resultText.value = ''; resultSysPrompt.value = ''; resultUserPrompt.value = ''; resultThinking.value = ''

  try {
    const data = await apiFetch<PromptTestResponse>('/api/test-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system_prompt: systemPrompt.value.trim(),
        user_prompt: userPrompt.value.trim(),
        api_key: normalizeApiKeyInput(apiKey.value),
        model: model.value.trim(),
        base_url: baseUrl.value.trim(),
      }),
    })

    resultSysPrompt.value = data.system_prompt || ''
    resultUserPrompt.value = data.user_prompt || ''
    resultThinking.value = data.thinking || ''
    resultText.value = data.result || ''
    runState.value = 'done'
  } catch (e) {
    resultText.value = '错误: ' + normalizeApiError(e)
    runState.value = 'error'
  } finally {
    running.value = false
  }
}

function clearAll() {
  systemPrompt.value = ''
  userPrompt.value = ''
  resultText.value = ''
  resultSysPrompt.value = ''
  resultUserPrompt.value = ''
  resultThinking.value = ''
  runState.value = 'idle'
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    submitPrompt()
  }
}

// ── 快捷测试工具 ──
const quickXlsx = ref('')
const quickField = ref('')
const quickRunning = ref(false)
const quickResult = ref('')

async function runQuickTest(type: 'reliability' | 'metadata') {
  quickRunning.value = true
  quickResult.value = ''
  try {
    const body = new FormData()
    body.append('xlsx_path', quickXlsx.value)
    if (type === 'metadata') body.append('field_key', quickField.value)
    const url = type === 'reliability' ? '/api/test-ai-reliability-desc' : '/api/test-ai-metadata'
    const data = await apiFetch<QuickTestResponse>(url, { method: 'POST', body })
    quickResult.value = data.result || data.detail || '（无结果）'
  } catch (e) {
    quickResult.value = '请求失败: ' + normalizeApiError(e)
  }
  quickRunning.value = false
}
</script>
