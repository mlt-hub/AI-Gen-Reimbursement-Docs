<template>
  <div class="mx-auto box-border w-full max-w-3xl space-y-8 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold">环境诊断</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">检查后端连接、版本、工作模式和关键能力状态。</p>
        </div>
        <button class="btn-secondary w-fit" :disabled="healthLoading" @click="refreshHealth">
          {{ healthLoading ? '检查中...' : '重新检查' }}
        </button>
      </div>

      <div class="grid min-w-0 gap-3 sm:grid-cols-2">
        <div v-for="item in diagnosticItems" :key="item.label" class="min-w-0 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2">
          <div class="flex min-w-0 items-center justify-between gap-3">
            <span class="min-w-0 text-sm text-[var(--color-ink-muted)]">{{ item.label }}</span>
            <span :class="['shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold', item.className]">{{ item.value }}</span>
          </div>
        </div>
      </div>

      <p v-if="healthError" class="mt-3 text-sm text-[var(--color-warning)]">{{ healthError }}</p>
      <p v-else-if="healthCheckedAt" class="mt-3 text-xs text-[var(--color-ink-soft)]">最近检查：{{ healthCheckedAt }}</p>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">AI 配置</p>
          <h2 class="mt-1 text-lg font-semibold">模型与凭据</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="webConfigLoading || webConfigSaving" @click="loadWebConfig">
          {{ webConfigLoading ? '加载中...' : '刷新配置' }}
        </button>
      </div>

      <p v-if="webConfigError" class="text-sm text-[var(--color-warning)]">{{ webConfigError }}</p>
      <div v-else-if="webConfig" class="space-y-4">
        <div class="grid gap-3 md:grid-cols-2">
          <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-2">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-[var(--color-ink-muted)]">API Key</span>
              <span :class="['rounded-md px-2 py-0.5 text-xs font-semibold', webConfig.ai.api_key_configured ? statusClass.ok : statusClass.warn]">
                {{ webConfig.ai.api_key_configured ? '已配置' : '未配置' }}
              </span>
            </div>
            <p class="mt-1 text-xs text-[var(--color-ink-soft)]">来源：{{ sourceLabel(webConfig.ai.api_key_source) }}</p>
          </div>

          <ConfigValueCard label="接口地址" :field="webConfig.ai.base_url" />
          <ConfigValueCard label="模型" :field="webConfig.ai.model" />
          <ConfigValueCard label="最大 Token 数" :field="webConfig.ai.max_tokens" />
          <ConfigValueCard label="共享系统 API Key" :field="webConfig.ai.allow_shared_ai_credentials" :format="formatEnabled" />
        </div>

        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <label for="web-api-key" class="field-label text-xs">API Key</label>
              <input
                id="web-api-key"
                ref="webApiKeyInput"
                v-model.trim="webAiForm.apiKey"
                type="password"
                placeholder="留空保留已保存的 API Key"
                autocomplete="new-password"
                autocapitalize="off"
                autocorrect="off"
                spellcheck="false"
                data-lpignore="true"
                data-1p-ignore="true"
                :name="webApiKeyInputName"
                :readonly="webApiKeyReadonly"
                class="field-control"
                :disabled="webAiForm.clearApiKey"
                @focus="activateWebApiKeyInput"
                @pointerdown="activateWebApiKeyInput"
              />
            </div>

            <div>
              <label for="web-base-url" class="field-label text-xs">接口地址</label>
              <input id="web-base-url" v-model.trim="webAiForm.baseUrl" type="text" class="field-control" />
            </div>

            <div>
              <label for="web-model" class="field-label text-xs">模型</label>
              <input id="web-model" v-model.trim="webAiForm.model" type="text" class="field-control" />
            </div>

            <div>
              <label for="web-max-tokens" class="field-label text-xs">最大 Token 数</label>
              <input id="web-max-tokens" v-model.trim="webAiForm.maxTokens" type="text" class="field-control" />
            </div>

            <label class="flex cursor-pointer items-center gap-2 self-end text-sm text-[var(--color-ink-muted)]">
              <input
                v-model="webAiForm.clearApiKey"
                type="checkbox"
                class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
                @change="handleClearWebApiKeyChange"
              />
              清空已保存的 API Key
            </label>

            <label v-if="webConfig.scope.mode === 'local'" class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)] md:col-span-2">
              <input
                v-model="webAiForm.allowSharedAiCredentials"
                type="checkbox"
                class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
              />
              允许远程用户使用共享系统 API Key
            </label>
          </div>

          <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', webConfigSaveStatusClass]">{{ webConfigSaveStatusText }}</span>
            <button class="btn-primary w-fit" :disabled="webConfigSaving || !hasWebConfigChanges" @click="saveWebConfig">
              {{ webConfigSaving ? '保存中...' : '保存 AI 配置' }}
            </button>
          </div>
          <p v-if="webConfigSaveMsg" :class="['mt-2 text-sm', webConfigSaveOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ webConfigSaveMsg }}</p>
        </div>
      </div>
      <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中...</p>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">模板配置</p>
        <h2 class="mt-1 text-lg font-semibold">输出与下载模板</h2>
      </div>
      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-4">
          <TemplateUpload />
        </div>
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-4">
          <TemplateDownload />
        </div>
      </div>
    </section>

    <nav class="flex flex-wrap gap-2 border-b border-[var(--color-rule)] pb-3" aria-label="配置分区">
      <button
        v-for="tab in configTabs"
        :key="tab.key"
        type="button"
        :class="['nav-link', activeTab === tab.key ? 'nav-link-active' : '']"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- 个人配置（可编辑，远程模式） -->
    <template v-if="showUserConfig">
      <section v-if="activeTab === 'personal'">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 class="text-lg font-semibold">个人配置</h2>
            <p class="mt-1 text-xs text-[var(--color-ink-soft)]">~/.ai-gen-reimbursement-docs/users/{{ auth.username }}/</p>
          </div>
          <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', saveStatusClass]">{{ saveStatusText }}</span>
        </div>
        <!-- .env -->
        <div class="surface mb-4 space-y-3 rounded-lg p-5">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-sm font-medium text-[var(--color-ink-muted)]">环境变量 .env</h3>
          </div>
          <div>
            <label class="field-label text-xs">ANTHROPIC_BASE_URL</label>
            <input v-model="envFields.baseUrl" type="text"
              class="field-control" />
          </div>
          <div>
            <label class="field-label text-xs">ANTHROPIC_MODEL</label>
            <input v-model="envFields.model" type="text"
              class="field-control" />
          </div>
        </div>

        <!-- system_config.yaml -->
        <div class="surface mb-4 space-y-4 rounded-lg p-5">
          <h3 class="text-sm font-medium text-[var(--color-ink-muted)]">system_config.yaml</h3>

          <!-- 布尔字段：4 列 grid -->
          <div class="grid grid-cols-4 gap-x-4 gap-y-2">
            <label v-for="f in boolFields" :key="f.key"
              class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)]">
              <input type="checkbox" v-model="f.value" class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]" />
              {{ f.key }}
            </label>
          </div>

          <hr class="border-[var(--color-rule)]" />

          <!-- 枚举/数字/文本：2 列 grid -->
          <div class="grid grid-cols-2 gap-4">
            <div v-for="f in scalarFields" :key="f.key">
              <label class="field-label text-xs">{{ f.key }}</label>
              <select v-if="f.type === 'select'" v-model="f.value"
                class="field-control">
                <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <input v-else-if="f.type === 'number'" v-model.number="f.value" type="number"
                class="field-control" />
              <input v-else v-model="f.value" type="text"
                class="field-control" />
            </div>
          </div>

          <!-- 嵌套对象：textarea -->
          <template v-if="nestedFields.length">
            <hr class="border-[var(--color-rule)]" />
            <div v-for="f in nestedFields" :key="f.key">
              <label class="field-label text-xs">{{ f.key }}</label>
              <textarea v-model="f.yamlText" rows="6"
                class="field-control font-mono"></textarea>
            </div>
          </template>
        </div>

        <div class="flex gap-3">
          <button @click="saveUserConfig" :disabled="saving || !hasUnsavedChanges"
            class="btn-primary">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button @click="exportSettings"
            class="btn-secondary">
            导出
          </button>
          <button @click="importSettings"
            class="btn-secondary">
            导入
          </button>
        </div>
        <p v-if="saveMsg" :class="['mt-2 text-sm', saveOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ saveMsg }}</p>
        <p v-if="lastSavedAt" class="mt-2 text-xs text-[var(--color-ink-soft)]">上次保存：{{ lastSavedAt }}</p>
      </section>

      <!-- 服务端全局默认（只读参考） -->
      <section v-if="activeTab === 'global' && globalSystemConfig">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (system_config.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读参考，文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ globalSystemConfig || '（空）' }}</pre>
      </section>
      <section v-if="activeTab === 'global' && globalEnvContent">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (.env)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读参考，敏感值已遮罩</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ globalEnvContent || '（空）' }}</pre>
      </section>
      <section v-if="activeTab === 'rules' && businessRules !== null">
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ businessRules || '（空）' }}</pre>
      </section>
    </template>

    <!-- 本机模式：只读 -->
    <template v-else>
      <section v-if="activeTab === 'env'">
        <h2 class="text-lg font-semibold mb-4">环境变量 (.env)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/.env</p>
        <pre v-if="envContent !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ envContent || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
      <section v-if="activeTab === 'system'">
        <h2 class="text-lg font-semibold mb-4">系统配置 (system_config.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre v-if="systemConfig !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ systemConfig || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
      <section v-if="activeTab === 'rules'">
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/business_rules.yaml</p>
        <pre v-if="businessRules !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ businessRules || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { defineComponent, h, ref, computed, onMounted, reactive, type PropType } from 'vue'
import { useAuthStore } from '@/stores/auth.ts'
import { normalizeApiKeyInput, useConfigStore } from '@/stores/config.ts'
import { useSensitiveInputGuard } from '@/composables/useSensitiveInputGuard.ts'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import TemplateDownload from '@/components/TemplateDownload.vue'
import TemplateUpload from '@/components/TemplateUpload.vue'

// ── 类型 ──────────────────────────────────────────────────

type FieldType = 'bool' | 'number' | 'select' | 'text'

interface ScalarField {
  key: string
  type: FieldType
  value: any
  options?: string[]
}

interface NestedField {
  key: string
  yamlText: string
}

interface ConfigReadResponse {
  env?: string
  system_config?: string
  business_rules?: string
  global_env?: string
  global_system?: string
}

interface UserConfigResponse {
  _system?: Record<string, any>
}

interface HealthResponse {
  ok?: boolean
  version?: string
  work_mode?: string
  api?: Record<string, boolean | null>
  paths?: Record<string, boolean | null>
  features?: Record<string, boolean | null>
}

type ConfigSource = 'personal' | 'global' | 'default'

interface WebConfigField<T = unknown> {
  value: T
  source: ConfigSource
}

interface WebConfigResponse {
  scope: {
    mode: 'local' | 'remote'
    username: string
  }
  ai: {
    api_key_configured: boolean
    api_key_source: ConfigSource
    base_url: WebConfigField<string>
    model: WebConfigField<string>
    max_tokens: WebConfigField<string | number>
    allow_shared_ai_credentials: WebConfigField<boolean>
  }
  templates: {
    out_templates: WebConfigField<Record<string, string>>
  }
  run_defaults: Record<string, WebConfigField<unknown>>
}

// ── stores ────────────────────────────────────────────────

const auth = useAuthStore()
const configStore = useConfigStore()

const showUserConfig = computed(() => auth.isRemote)
type ConfigTabKey = 'personal' | 'global' | 'env' | 'system' | 'rules'
const activeTab = ref<ConfigTabKey>(showUserConfig.value ? 'personal' : 'env')
const configTabs = computed<{ key: ConfigTabKey; label: string }[]>(() => {
  if (showUserConfig.value) {
    return [
      { key: 'personal', label: '个人配置' },
      { key: 'global', label: '全局默认' },
      { key: 'rules', label: '业务规则' },
    ]
  }
  return [
    { key: 'env', label: '环境变量' },
    { key: 'system', label: '系统配置' },
    { key: 'rules', label: '业务规则' },
  ]
})

// ── 只读内容 ──────────────────────────────────────────────

const envContent = ref<string | null>(null)
const systemConfig = ref<string | null>(null)
const businessRules = ref<string | null>(null)
const globalEnvContent = ref('')
const globalSystemConfig = ref('')

// ── 可编辑字段 ────────────────────────────────────────────

const envFields = reactive({ baseUrl: '', model: '' })
const boolFields = ref<ScalarField[]>([])
const scalarFields = ref<ScalarField[]>([])
const nestedFields = ref<NestedField[]>([])
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)
const savedSnapshot = ref('')
const lastSavedAt = ref('')
const health = ref<HealthResponse | null>(null)
const healthLoading = ref(false)
const healthError = ref('')
const healthCheckedAt = ref('')
const webConfig = ref<WebConfigResponse | null>(null)
const webConfigLoading = ref(false)
const webConfigError = ref('')
const webConfigSaving = ref(false)
const webConfigSaveMsg = ref('')
const webConfigSaveOk = ref(false)
const webConfigSnapshot = ref('')
const webAiForm = reactive({
  apiKey: '',
  baseUrl: '',
  model: '',
  maxTokens: '',
  allowSharedAiCredentials: false,
  clearApiKey: false,
})
const webApiKeyInput = ref<HTMLInputElement | null>(null)
const {
  inputName: webApiKeyInputName,
  readonly: webApiKeyReadonly,
  activateSensitiveInput: activateWebApiKeyInput,
} = useSensitiveInputGuard('web-api-key', {
  inputRef: webApiKeyInput,
  getValue: () => webAiForm.apiKey,
  setValue: value => { webAiForm.apiKey = value },
})

const statusClass = {
  ok: 'bg-[var(--color-success-soft)] text-[var(--color-success)]',
  warn: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  neutral: 'bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]',
}

const diagnosticItems = computed(() => {
  const data = health.value
  return [
    {
      label: '后端连接',
      value: data ? (data.ok === false ? '部分异常' : '正常') : '未连接',
      className: data ? (data.ok === false ? statusClass.warn : statusClass.ok) : statusClass.warn,
    },
    {
      label: '后端版本',
      value: data?.version || '未知',
      className: data?.version ? statusClass.neutral : statusClass.warn,
    },
    {
      label: '工作模式',
      value: data?.work_mode === 'remote' ? '远程服务' : data?.work_mode === 'local' ? '本机模式' : '未知',
      className: data?.work_mode ? statusClass.neutral : statusClass.warn,
    },
    {
      label: '模板目录',
      value: formatStatus(data?.paths?.templates_readable),
      className: statusClassFor(data?.paths?.templates_readable),
    },
    {
      label: '配置接口',
      value: formatStatus(data?.api?.config),
      className: statusClassFor(data?.api?.config),
    },
    {
      label: '提示词调试',
      value: formatStatus(data?.features?.prompt_debug),
      className: statusClassFor(data?.features?.prompt_debug),
    },
  ]
})

const currentConfigSnapshot = computed(() => JSON.stringify({
  env: {
    baseUrl: envFields.baseUrl,
    model: envFields.model,
  },
  boolFields: boolFields.value.map(f => ({ key: f.key, value: f.value })),
  scalarFields: scalarFields.value.map(f => ({ key: f.key, value: f.value })),
  nestedFields: nestedFields.value.map(f => ({ key: f.key, yamlText: f.yamlText })),
}))

const hasUnsavedChanges = computed(() => {
  return showUserConfig.value && savedSnapshot.value !== '' && currentConfigSnapshot.value !== savedSnapshot.value
})

const saveStatusText = computed(() => {
  if (saving.value) return '保存中'
  if (saveMsg.value && !saveOk.value) return '保存失败'
  if (hasUnsavedChanges.value) return '有未保存修改'
  return '已保存'
})

const saveStatusClass = computed(() => {
  if (saving.value) return statusClass.neutral
  if (saveMsg.value && !saveOk.value) return statusClass.warn
  if (hasUnsavedChanges.value) return statusClass.warn
  return statusClass.ok
})

const webConfigFormSnapshot = computed(() => JSON.stringify({
  apiKey: normalizeApiKeyInput(webAiForm.apiKey),
  baseUrl: webAiForm.baseUrl,
  model: webAiForm.model,
  maxTokens: webAiForm.maxTokens,
  allowSharedAiCredentials: webAiForm.allowSharedAiCredentials,
  clearApiKey: webAiForm.clearApiKey,
}))

const hasWebConfigChanges = computed(() => (
  webConfigSnapshot.value !== '' && webConfigFormSnapshot.value !== webConfigSnapshot.value
))

const webConfigSaveStatusText = computed(() => {
  if (webConfigSaving.value) return '保存中'
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return '保存失败'
  if (hasWebConfigChanges.value) return '有未保存修改'
  return '已保存'
})

const webConfigSaveStatusClass = computed(() => {
  if (webConfigSaving.value) return statusClass.neutral
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return statusClass.warn
  if (hasWebConfigChanges.value) return statusClass.warn
  return statusClass.ok
})

// ── 初始化 ────────────────────────────────────────────────

onMounted(async () => {
  await refreshHealth()
  await loadWebConfig()
  if (showUserConfig.value) {
    await loadUserConfig()
  } else {
    await loadLocalConfig()
  }
})

const ConfigValueCard = defineComponent({
  name: 'ConfigValueCard',
  props: {
    label: { type: String, required: true },
    field: { type: Object as PropType<WebConfigField>, required: true },
    format: { type: Function as PropType<(value: unknown) => string>, default: null },
  },
  setup(props) {
    return () => h('div', { class: 'rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-2' }, [
      h('div', { class: 'flex items-center justify-between gap-3' }, [
        h('span', { class: 'text-sm text-[var(--color-ink-muted)]' }, props.label),
        h('span', { class: 'min-w-0 truncate text-sm font-semibold text-[var(--color-ink)]' }, formatConfigValue(props.field.value, props.format)),
      ]),
      h('p', { class: 'mt-1 text-xs text-[var(--color-ink-soft)]' }, `来源：${sourceLabel(props.field.source)}`),
    ])
  },
})

function formatStatus(value: boolean | null | undefined): string {
  if (value === true) return '正常'
  if (value === false) return '异常'
  return '未检测'
}

function statusClassFor(value: boolean | null | undefined): string {
  if (value === true) return statusClass.ok
  if (value === false) return statusClass.warn
  return statusClass.neutral
}

async function refreshHealth() {
  healthLoading.value = true
  healthError.value = ''
  try {
    health.value = await apiFetch<HealthResponse>('/api/health')
    healthCheckedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    health.value = null
    healthError.value = `后端服务未连接：${normalizeApiError(e)}`
    healthCheckedAt.value = new Date().toLocaleTimeString()
  } finally {
    healthLoading.value = false
  }
}

async function loadWebConfig() {
  webConfigLoading.value = true
  webConfigError.value = ''
  try {
    webConfig.value = await apiFetch<WebConfigResponse>('/api/web-config')
    applyWebConfigToForm(webConfig.value)
  } catch (e) {
    webConfig.value = null
    webConfigError.value = normalizeApiError(e)
  } finally {
    webConfigLoading.value = false
  }
}

function applyWebConfigToForm(data: WebConfigResponse) {
  webAiForm.apiKey = ''
  webAiForm.baseUrl = String(data.ai.base_url.value || '')
  webAiForm.model = String(data.ai.model.value || '')
  webAiForm.maxTokens = String(data.ai.max_tokens.value || '')
  webAiForm.allowSharedAiCredentials = Boolean(data.ai.allow_shared_ai_credentials.value)
  webAiForm.clearApiKey = false
  webConfigSaveMsg.value = ''
  webConfigSaveOk.value = true
  webConfigSnapshot.value = webConfigFormSnapshot.value
}

function handleClearWebApiKeyChange() {
  if (webAiForm.clearApiKey) {
    webAiForm.apiKey = ''
  }
}

async function saveWebConfig() {
  webConfigSaving.value = true
  webConfigSaveMsg.value = ''

  const ai: Record<string, unknown> = {
    base_url: { value: webAiForm.baseUrl },
    model: { value: webAiForm.model },
    max_tokens: { value: webAiForm.maxTokens },
  }
  const apiKey = normalizeApiKeyInput(webAiForm.apiKey)
  if (apiKey) ai.api_key = apiKey
  if (webAiForm.clearApiKey) ai.clear_api_key = true
  if (webConfig.value?.scope.mode === 'local') {
    ai.allow_shared_ai_credentials = { value: webAiForm.allowSharedAiCredentials }
  }

  try {
    const data = await apiFetch<WebConfigResponse>('/api/web-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai }),
    })
    webConfig.value = data
    configStore.baseUrl = String(data.ai.base_url.value || '')
    configStore.model = String(data.ai.model.value || '')
    configStore.maxTokens = String(data.ai.max_tokens.value || '')
    applyWebConfigToForm(data)
    webConfigSaveOk.value = true
    webConfigSaveMsg.value = '保存成功'
    await loadLocalConfig()
    if (showUserConfig.value) {
      await loadUserConfig()
    }
  } catch (e) {
    webConfigSaveOk.value = false
    webConfigSaveMsg.value = normalizeApiError(e)
  } finally {
    webConfigSaving.value = false
  }
}

function sourceLabel(source: ConfigSource | string): string {
  const labels: Record<string, string> = {
    personal: '个人配置',
    global: '全局配置',
    default: '系统默认',
  }
  return labels[source] || source
}

function formatEnabled(value: unknown): string {
  return value ? '开启' : '关闭'
}

function formatConfigValue(value: unknown, formatter?: ((value: unknown) => string) | null): string {
  if (formatter) return formatter(value)
  if (value === null || value === undefined || value === '') return '未设置'
  if (typeof value === 'boolean') return formatEnabled(value)
  return String(value)
}

async function loadLocalConfig() {
  try {
    const data = await apiFetch<ConfigReadResponse>('/api/config-read')
    envContent.value = data.env || ''
    systemConfig.value = data.system_config || ''
    businessRules.value = data.business_rules || ''
  } catch (e) {
    const msg = normalizeApiError(e)
    envContent.value = '读取失败'
    systemConfig.value = msg
    businessRules.value = msg
  }
}

async function loadUserConfig() {
  // 加载原始文本（用于 nested textarea 和 全局参考）
  const [readResult, cfgResult] = await Promise.allSettled([
    apiFetch<ConfigReadResponse>('/api/config-read'),
    apiFetch<UserConfigResponse>('/api/user/config'),
  ])

  if (readResult.status === 'fulfilled') {
    const d = readResult.value
    globalEnvContent.value = d.global_env || ''
    globalSystemConfig.value = d.global_system || ''
    businessRules.value = d.business_rules || ''
    // 解析个人 env
    if (d.env) {
      for (const line of d.env.split('\n')) {
        const m = line.match(/^(\w+)=(.+)/)
        if (m) {
          const k = m[1].trim()
          const v = m[2].trim()
          if (k === 'ANTHROPIC_BASE_URL') envFields.baseUrl = v
          else if (k === 'ANTHROPIC_MODEL') envFields.model = v
        }
      }
    }
  }

  if (cfgResult.status === 'fulfilled') {
    const data = cfgResult.value
    const sys = data._system || {}
    buildFormFields(sys)
  }

  savedSnapshot.value = currentConfigSnapshot.value
}

// ── 从 YAML dict 构建表单字段 ──────────────────────────────

const SELECT_OPTIONS: Record<string, string[]> = {
  web_work_mode: ['auto', 'local', 'remote'],
  log_level: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
}

const NESTED_KEYS = new Set(['sheets', 'out_templates'])

function buildFormFields(sys: Record<string, any>) {
  const bools: ScalarField[] = []
  const scalars: ScalarField[] = []
  const nesteds: NestedField[] = []

  for (const [key, val] of Object.entries(sys)) {
    if (typeof val === 'boolean') {
      bools.push({ key, type: 'bool', value: val })
    } else if (NESTED_KEYS.has(key) || typeof val === 'object') {
      nesteds.push({ key, yamlText: toYamlLike(val) })
    } else if (SELECT_OPTIONS[key]) {
      scalars.push({ key, type: 'select', value: String(val), options: SELECT_OPTIONS[key] })
    } else if (typeof val === 'number') {
      scalars.push({ key, type: 'number', value: val })
    } else {
      scalars.push({ key, type: 'text', value: String(val) })
    }
  }

  boolFields.value = bools
  scalarFields.value = scalars
  nestedFields.value = nesteds
}

/** 把对象转成接近 YAML 风格的纯文本（缩进 2 空格）。 */
function toYamlLike(obj: any, indent = 0): string {
  if (obj === null || obj === undefined) return ''
  if (typeof obj !== 'object') return String(obj)
  const pad = '  '.repeat(indent)
  const lines: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'object' && v !== null) {
      lines.push(`${pad}${k}:`)
      lines.push(toYamlLike(v, indent + 1))
    } else {
      lines.push(`${pad}${k}: ${v}`)
    }
  }
  return lines.join('\n')
}

/** 把 textarea 的 YAML 风格文本解析回对象。 */
function fromYamlLike(text: string): any {
  // 简单解析 — 仅支持嵌套 dict，值均为字符串
  const result: Record<string, any> = {}
  const stack: { indent: number; obj: Record<string, any> }[] = [{ indent: -1, obj: result }]

  for (const line of text.split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue
    const indent = line.search(/\S/)
    const content = line.trim()
    const colonIdx = content.indexOf(':')

    // 回退栈
    while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
      stack.pop()
    }

    if (colonIdx > 0) {
      const key = content.substring(0, colonIdx).trim()
      const val = content.substring(colonIdx + 1).trim()
      if (val) {
        stack[stack.length - 1].obj[key] = val
      } else {
        // 嵌套对象开始
        const child: Record<string, any> = {}
        stack[stack.length - 1].obj[key] = child
        stack.push({ indent, obj: child })
      }
    }
  }
  return result
}

// ── 保存 ──────────────────────────────────────────────────

async function saveUserConfig() {
  saving.value = true
  saveMsg.value = ''

  // 构建 _env
  const env: Record<string, string> = {}
  if (envFields.baseUrl) env['ANTHROPIC_BASE_URL'] = envFields.baseUrl
  if (envFields.model) env['ANTHROPIC_MODEL'] = envFields.model

  // 构建 _system
  const system: Record<string, any> = {}

  for (const f of boolFields.value) {
    system[f.key] = f.value
  }
  for (const f of scalarFields.value) {
    if (f.type === 'number') {
      system[f.key] = Number(f.value)
    } else {
      system[f.key] = f.value
    }
  }
  for (const f of nestedFields.value) {
    try {
      system[f.key] = fromYamlLike(f.yamlText)
    } catch {
      saveOk.value = false
      saveMsg.value = `${f.key} 格式错误，请检查`
      saving.value = false
      return
    }
  }

  try {
    await apiFetch('/api/user/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ _env: env, _system: system }),
    })
    saveOk.value = true
    saveMsg.value = '保存成功'
    savedSnapshot.value = currentConfigSnapshot.value
    lastSavedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    saveOk.value = false
    saveMsg.value = normalizeApiError(e)
  }
  saving.value = false
}

// ── 导出/导入 ─────────────────────────────────────────────

function exportSettings() {
  const json = configStore.exportSettings()
  const blob = new Blob([json], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `ard-settings-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function importSettings() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e: any) => {
    const file = e.target?.files?.[0]
    if (!file) return
    const text = await file.text()
    if (configStore.importSettings(text)) {
      saveMsg.value = '导入成功，请点保存'
      saveOk.value = true
    } else {
      saveMsg.value = '导入失败：文件格式不正确'
      saveOk.value = false
    }
  }
  input.click()
}
</script>
