import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'

export type WorkMode = 'local' | 'remote'
export type BackendStatus = 'checking' | 'connected' | 'degraded' | 'offline'
export type PipelineMode = 'from-excel-gen-all' | 'from-excel-gen-basedata' |
  'from-excel-gen-fpa' | 'from-excel-gen-cosmic' |
  'from-excel-gen-list' | 'from-excel-gen-spec'

// ── localStorage 持久化 ───────────────────────────────────

function loadStr(key: string, fallback: string): string {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}

function saveStr(key: string, val: string) {
  try { localStorage.setItem(key, val) } catch { /* 忽略 */ }
}

function loadBool(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v === 'true'
  } catch { return fallback }
}

function saveBool(key: string, val: boolean) {
  try { localStorage.setItem(key, String(val)) } catch { /* 忽略 */ }
}

const API_KEY_PLACEHOLDERS = new Set([
  'sk-...',
  'sk-',
  'your-api-key',
  'your_api_key',
  'api-key',
  'api_key',
  'here',
  '****here',
])

export function normalizeApiKeyInput(value: string): string {
  const v = value.trim()
  if (!v) return ''
  if (API_KEY_PLACEHOLDERS.has(v.toLowerCase())) return ''
  return v
}

// ── 导出/导入 ─────────────────────────────────────────────

export interface UserSettings {
  apiKey: string
  model: string
  baseUrl: string
  maxTokens: string
  projectName: string
  fpaProfile: string
  fpaStrategy: string
  fpaRuleSet: string
  pipelineMode: PipelineMode
  clean: boolean
}

export const useConfigStore = defineStore('config', () => {
  const workMode = ref<WorkMode>('local')
  const backendStatus = ref<BackendStatus>('checking')
  const pipelineMode = ref<PipelineMode>(loadStr('pipelineMode', 'from-excel-gen-all') as PipelineMode)
  const xlsxPath = ref('')
  const outputDir = ref('')
  const apiKey = ref(normalizeApiKeyInput(loadStr('apiKey', '')))
  const model = ref(loadStr('model', ''))
  const baseUrl = ref(loadStr('baseUrl', ''))
  const maxTokens = ref(loadStr('maxTokens', ''))
  const projectName = ref(loadStr('projectName', ''))
  const fpaProfile = ref(normalizeFpaProfile(loadStr('fpaProfile', 'custom_rules')))
  const fpaStrategy = ref(normalizeFpaStrategy(loadStr('fpaStrategy', '')))
  const fpaRuleSet = ref(loadStr('fpaRuleSet', ''))
  const clean = ref(loadBool('clean', false))
  const selectedFile = ref<File | null>(null)

  // ── 自动持久化 ──
  watch(apiKey, v => saveStr('apiKey', normalizeApiKeyInput(v)))
  watch(model, v => saveStr('model', v))
  watch(baseUrl, v => saveStr('baseUrl', v))
  watch(maxTokens, v => saveStr('maxTokens', v))
  watch(projectName, v => saveStr('projectName', v))
  watch(fpaProfile, v => saveStr('fpaProfile', normalizeFpaProfile(v)))
  watch(fpaStrategy, v => saveStr('fpaStrategy', normalizeFpaStrategy(v)))
  watch(fpaRuleSet, v => saveStr('fpaRuleSet', v))
  watch(pipelineMode, v => saveStr('pipelineMode', v))
  watch(clean, v => saveBool('clean', v))

  const isValid = computed(() => {
    if (workMode.value === 'local') return xlsxPath.value.trim().length > 0
    return selectedFile.value !== null
  })

  function reset() {
    xlsxPath.value = ''
    outputDir.value = ''
    apiKey.value = ''
    model.value = ''
    baseUrl.value = ''
    maxTokens.value = ''
    projectName.value = ''
    fpaProfile.value = 'custom_rules'
    fpaStrategy.value = ''
    fpaRuleSet.value = ''
    clean.value = false
    selectedFile.value = null
  }

  /** 导出用户设置为 JSON 字符串。 */
  function exportSettings(): string {
    const data: UserSettings = {
      apiKey: normalizeApiKeyInput(apiKey.value),
      model: model.value,
      baseUrl: baseUrl.value,
      maxTokens: maxTokens.value,
      projectName: projectName.value,
      fpaProfile: fpaProfile.value,
      fpaStrategy: fpaStrategy.value,
      fpaRuleSet: fpaRuleSet.value,
      pipelineMode: pipelineMode.value,
      clean: clean.value,
    }
    return JSON.stringify(data, null, 2)
  }

  /** 从 JSON 字符串导入用户设置。 */
  function importSettings(json: string) {
    try {
      const data = JSON.parse(json) as Partial<UserSettings>
      if (data.apiKey !== undefined) apiKey.value = normalizeApiKeyInput(data.apiKey)
      if (data.model !== undefined) model.value = data.model
      if (data.baseUrl !== undefined) baseUrl.value = data.baseUrl
      if (data.maxTokens !== undefined) maxTokens.value = data.maxTokens
      if (data.projectName !== undefined) projectName.value = data.projectName
      if (data.fpaProfile !== undefined) fpaProfile.value = normalizeFpaProfile(data.fpaProfile)
      if (data.fpaStrategy !== undefined) fpaStrategy.value = normalizeFpaStrategy(data.fpaStrategy)
      if (data.fpaRuleSet !== undefined) fpaRuleSet.value = data.fpaRuleSet
      if (data.pipelineMode !== undefined) pipelineMode.value = data.pipelineMode
      if (data.clean !== undefined) clean.value = data.clean
      return true
    } catch {
      return false
    }
  }

  const apiKeyForRequest = computed(() => normalizeApiKeyInput(apiKey.value))

  return { workMode, backendStatus, pipelineMode, xlsxPath, outputDir, apiKey, apiKeyForRequest, model, baseUrl,
           maxTokens, projectName, fpaProfile, fpaStrategy, fpaRuleSet, clean, selectedFile, isValid, reset,
           exportSettings, importSettings }
})

function normalizeFpaProfile(value: string): string {
  return value === 'strict_fpa' ? 'strict_fpa' : 'custom_rules'
}

function normalizeFpaStrategy(value: string): string {
  const v = value.trim()
  return ['', 'rules_first', 'ai_first', 'rules_only', 'ai_only'].includes(v) ? v : ''
}
