import { computed, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

export interface FpaProfileOption {
  name: string
  label: string
  kind: string
  strategy: string
  rule_set: string
  core_rules: string
  system_prompt: string
  user_prompt: string
  confirmation_mode: string
  editable: boolean
}

export interface FpaNamedOption {
  name: string
  label: string
}

export interface FpaRuleSetOption extends FpaNamedOption {
  extends: string
}

export interface FpaOptions {
  default_profile: string
  profiles: FpaProfileOption[]
  strategies: FpaNamedOption[]
  confirmation_modes: FpaNamedOption[]
  kinds: FpaNamedOption[]
  rule_sets: FpaRuleSetOption[]
  core_rules: FpaNamedOption[]
  system_prompt_sets: FpaNamedOption[]
  user_prompt_sets: FpaNamedOption[]
}

const fallbackOptions: FpaOptions = {
  default_profile: 'strict_fpa',
  profiles: [
    { name: 'strict_fpa', label: '严格 FPA 口径', kind: 'strict_fpa', strategy: 'ai_first', rule_set: 'strict_fpa_rs', core_rules: 'strict_fpa_cr', system_prompt: 'strict_fpa_sp', user_prompt: 'strict_fpa_up', confirmation_mode: 'auto', editable: false },
    { name: 'unified_ui', label: '统一界面口径', kind: 'unified_ui', strategy: 'rules_first', rule_set: 'unified_ui_rs', core_rules: 'unified_ui_cr', system_prompt: 'unified_ui_sp', user_prompt: 'unified_ui_up', confirmation_mode: 'auto', editable: false },
    { name: 'multi_ui', label: '多界面口径', kind: 'multi_ui', strategy: 'rules_first', rule_set: 'multi_ui_rs', core_rules: 'multi_ui_cr', system_prompt: 'multi_ui_sp', user_prompt: 'multi_ui_up', confirmation_mode: 'auto', editable: false },
    { name: 'ui_api_mapping', label: '界面接口映射口径', kind: 'ui_api_mapping', strategy: 'rules_first', rule_set: 'ui_api_mapping_rs', core_rules: 'ui_api_mapping_cr', system_prompt: 'ui_api_mapping_sp', user_prompt: 'ui_api_mapping_up', confirmation_mode: 'auto', editable: false },
    { name: 'custom_profile', label: '自定义 FPA 方案', kind: 'unified_ui', strategy: 'rules_first', rule_set: 'unified_ui_rs', core_rules: 'unified_ui_cr', system_prompt: 'unified_ui_sp', user_prompt: 'unified_ui_up', confirmation_mode: 'auto', editable: true },
  ],
  strategies: [
    { name: 'rules_first', label: '规则优先' },
    { name: 'ai_first', label: 'AI 优先' },
    { name: 'rules_only', label: '仅规则' },
    { name: 'ai_only', label: '仅 AI' },
  ],
  confirmation_modes: [
    { name: 'auto', label: '自动模式' },
    { name: 'cautious', label: '审慎模式' },
    { name: 'strict', label: '严格确认模式' },
  ],
  kinds: [
    { name: 'strict_fpa', label: 'strict_fpa' },
    { name: 'unified_ui', label: 'unified_ui' },
    { name: 'multi_ui', label: 'multi_ui' },
    { name: 'ui_api_mapping', label: 'ui_api_mapping' },
  ],
  rule_sets: [],
  core_rules: [],
  system_prompt_sets: [],
  user_prompt_sets: [],
}

const options = ref<FpaOptions | null>(null)
const loading = ref(false)
const error = ref('')
let pending: Promise<void> | null = null

export function useFpaOptions() {
  const fpaOptions = computed(() => options.value ?? fallbackOptions)

  async function loadFpaOptions() {
    if (options.value || pending) return pending

    loading.value = true
    error.value = ''
    pending = apiFetch<FpaOptions>('/api/fpa/options')
      .then(data => {
        options.value = {
          default_profile: data.default_profile || fallbackOptions.default_profile,
          profiles: data.profiles?.length ? data.profiles : fallbackOptions.profiles,
          strategies: data.strategies?.length ? data.strategies : fallbackOptions.strategies,
          confirmation_modes: data.confirmation_modes?.length ? data.confirmation_modes : fallbackOptions.confirmation_modes,
          kinds: data.kinds?.length ? data.kinds : fallbackOptions.kinds,
          rule_sets: data.rule_sets ?? [],
          core_rules: data.core_rules ?? [],
          system_prompt_sets: data.system_prompt_sets ?? [],
          user_prompt_sets: data.user_prompt_sets ?? [],
        }
      })
      .catch(e => {
        error.value = normalizeApiError(e)
      })
      .finally(() => {
        loading.value = false
        pending = null
      })

    return pending
  }

  return {
    fpaOptions,
    fpaOptionsLoading: loading,
    fpaOptionsError: error,
    loadFpaOptions,
  }
}
