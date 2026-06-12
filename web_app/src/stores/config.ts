import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'

export type WorkMode = 'local' | 'remote'
export type BackendStatus = 'checking' | 'connected' | 'degraded' | 'offline'
export type PipelineMode = 'from-excel-gen-all' | 'from-excel-gen-basedata' |
  'from-excel-gen-fpa' | 'from-excel-gen-cosmic' |
  'from-excel-gen-list' | 'from-excel-gen-spec'
export type FpaConfirmationMode = 'auto' | 'cautious' | 'strict'

// ── 浏览器端配置持久化 ───────────────────────────────────

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

function removeLocalStr(key: string) {
  try { localStorage.removeItem(key) } catch { /* 忽略 */ }
}

function removeSessionStr(key: string) {
  try { sessionStorage.removeItem(key) } catch { /* 忽略 */ }
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
  model: string
  baseUrl: string
  maxTokens: string
  projectName: string
  fpaProfile: string
  fpaStrategy: string
  fpaRuleSet: string
  fpaCoreRules: string
  fpaSystemPrompt: string
  fpaUserPrompt: string
  fpaBaseProfile: string
  fpaConfirmationMode: FpaConfirmationMode
  pipelineMode: PipelineMode
  clean: boolean
}

interface ImportedUserSettings extends Partial<UserSettings> {
  apiKey?: string
}

export const useConfigStore = defineStore('config', () => {
  removeLocalStr('apiKey')
  removeSessionStr('apiKey')

  const workMode = ref<WorkMode>('local')
  const backendStatus = ref<BackendStatus>('checking')
  const pipelineMode = ref<PipelineMode>(loadStr('pipelineMode', 'from-excel-gen-all') as PipelineMode)
  const xlsxPath = ref('')
  const outputDir = ref('')
  const apiKey = ref('')
  const model = ref(loadStr('model', ''))
  const baseUrl = ref(loadStr('baseUrl', ''))
  const maxTokens = ref(loadStr('maxTokens', ''))
  const projectName = ref(loadStr('projectName', ''))
  const fpaProfile = ref(normalizeFpaProfile(loadStr('fpaProfile', 'strict_fpa')))
  const fpaStrategy = ref(normalizeFpaStrategy(loadStr('fpaStrategy', '')))
  const fpaRuleSet = ref(loadStr('fpaRuleSet', ''))
  const fpaCoreRules = ref(loadStr('fpaCoreRules', ''))
  const fpaSystemPrompt = ref(loadStr('fpaSystemPrompt', ''))
  const fpaUserPrompt = ref(loadStr('fpaUserPrompt', ''))
  const fpaBaseProfile = ref(normalizeFpaProfile(loadStr('fpaBaseProfile', 'strict_fpa')))
  const fpaConfirmationMode = ref<FpaConfirmationMode>(normalizeFpaConfirmationMode(loadStr('fpaConfirmationMode', 'auto')))
  const clean = ref(loadBool('clean', false))
  const selectedFile = ref<File | null>(null)

  // ── 自动持久化 ──
  watch(model, v => saveStr('model', v))
  watch(baseUrl, v => saveStr('baseUrl', v))
  watch(maxTokens, v => saveStr('maxTokens', v))
  watch(projectName, v => saveStr('projectName', v))
  watch(fpaProfile, v => saveStr('fpaProfile', normalizeFpaProfile(v)))
  watch(fpaStrategy, v => saveStr('fpaStrategy', normalizeFpaStrategy(v)))
  watch(fpaRuleSet, v => saveStr('fpaRuleSet', v))
  watch(fpaCoreRules, v => saveStr('fpaCoreRules', v))
  watch(fpaSystemPrompt, v => saveStr('fpaSystemPrompt', v))
  watch(fpaUserPrompt, v => saveStr('fpaUserPrompt', v))
  watch(fpaBaseProfile, v => saveStr('fpaBaseProfile', normalizeFpaProfile(v)))
  watch(fpaConfirmationMode, v => saveStr('fpaConfirmationMode', normalizeFpaConfirmationMode(v)))
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
    fpaProfile.value = 'strict_fpa'
    fpaStrategy.value = ''
    fpaRuleSet.value = ''
    fpaCoreRules.value = ''
    fpaSystemPrompt.value = ''
    fpaUserPrompt.value = ''
    fpaBaseProfile.value = 'strict_fpa'
    fpaConfirmationMode.value = 'auto'
    clean.value = false
    selectedFile.value = null
  }

  /** 导出用户设置为 JSON 字符串。 */
  function exportSettings(): string {
    const data: UserSettings = {
      model: model.value,
      baseUrl: baseUrl.value,
      maxTokens: maxTokens.value,
      projectName: projectName.value,
      fpaProfile: fpaProfile.value,
      fpaStrategy: fpaStrategy.value,
      fpaRuleSet: fpaRuleSet.value,
      fpaCoreRules: fpaCoreRules.value,
      fpaSystemPrompt: fpaSystemPrompt.value,
      fpaUserPrompt: fpaUserPrompt.value,
      fpaBaseProfile: fpaBaseProfile.value,
      fpaConfirmationMode: fpaConfirmationMode.value,
      pipelineMode: pipelineMode.value,
      clean: clean.value,
    }
    return JSON.stringify(data, null, 2)
  }

  /** 从 JSON 字符串导入用户设置。 */
  function importSettings(json: string) {
    try {
      const data = JSON.parse(json) as ImportedUserSettings
      if (data.apiKey !== undefined) apiKey.value = normalizeApiKeyInput(data.apiKey)
      if (data.model !== undefined) model.value = data.model
      if (data.baseUrl !== undefined) baseUrl.value = data.baseUrl
      if (data.maxTokens !== undefined) maxTokens.value = data.maxTokens
      if (data.projectName !== undefined) projectName.value = data.projectName
      if (data.fpaProfile !== undefined) fpaProfile.value = normalizeFpaProfile(data.fpaProfile)
      if (data.fpaStrategy !== undefined) fpaStrategy.value = normalizeFpaStrategy(data.fpaStrategy)
      if (data.fpaRuleSet !== undefined) fpaRuleSet.value = data.fpaRuleSet
      if (data.fpaCoreRules !== undefined) fpaCoreRules.value = data.fpaCoreRules
      if (data.fpaSystemPrompt !== undefined) fpaSystemPrompt.value = data.fpaSystemPrompt
      if (data.fpaUserPrompt !== undefined) fpaUserPrompt.value = data.fpaUserPrompt
      if (data.fpaBaseProfile !== undefined) fpaBaseProfile.value = normalizeFpaProfile(data.fpaBaseProfile)
      if (data.fpaConfirmationMode !== undefined) fpaConfirmationMode.value = normalizeFpaConfirmationMode(data.fpaConfirmationMode)
      if (data.pipelineMode !== undefined) pipelineMode.value = data.pipelineMode
      if (data.clean !== undefined) clean.value = data.clean
      return true
    } catch {
      return false
    }
  }

  const apiKeyForRequest = computed(() => normalizeApiKeyInput(apiKey.value))

  return { workMode, backendStatus, pipelineMode, xlsxPath, outputDir, apiKey, apiKeyForRequest, model, baseUrl,
           maxTokens, projectName, fpaProfile, fpaStrategy, fpaRuleSet, fpaCoreRules, fpaSystemPrompt, fpaUserPrompt,
           fpaBaseProfile, fpaConfirmationMode, clean, selectedFile, isValid, reset,
           exportSettings, importSettings }
})

function normalizeFpaProfile(value: string): string {
  const v = value.trim()
  return v || 'strict_fpa'
}

function normalizeFpaStrategy(value: string): string {
  const v = value.trim()
  return ['', 'rules_first', 'ai_first', 'rules_only', 'ai_only'].includes(v) ? v : ''
}

function normalizeFpaConfirmationMode(value: string): FpaConfirmationMode {
  const v = value.trim()
  return v === 'cautious' || v === 'strict' ? v : 'auto'
}
