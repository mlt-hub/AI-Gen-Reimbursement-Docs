import { computed, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

export interface FpaProfileOption {
  name: string
  label: string
  kind: string
  strategy: string
  rule_set: string
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
  kinds: FpaNamedOption[]
  rule_sets: FpaRuleSetOption[]
}

const fallbackOptions: FpaOptions = {
  default_profile: 'strict_fpa',
  profiles: [
    { name: 'strict_fpa', label: '严格 FPA 口径', kind: 'strict_fpa', strategy: 'ai_first', rule_set: 'strict_fpa_rs' },
    { name: 'unified_ui', label: '统一界面口径', kind: 'unified_ui', strategy: 'rules_first', rule_set: 'unified_ui_rs' },
    { name: 'multi_uis', label: '多界面口径', kind: 'unified_ui', strategy: 'rules_first', rule_set: 'multi_uis_rs' },
    { name: 'ui_api_mapping', label: '界面接口映射口径', kind: 'ui_api_mapping', strategy: 'rules_first', rule_set: 'ui_api_mapping_rs' },
  ],
  strategies: [
    { name: 'rules_first', label: '规则优先' },
    { name: 'ai_first', label: 'AI 优先' },
    { name: 'rules_only', label: '仅规则' },
    { name: 'ai_only', label: '仅 AI' },
  ],
  kinds: [
    { name: 'strict_fpa', label: 'strict_fpa' },
    { name: 'unified_ui', label: 'unified_ui' },
    { name: 'ui_api_mapping', label: 'ui_api_mapping' },
  ],
  rule_sets: [],
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
          kinds: data.kinds?.length ? data.kinds : fallbackOptions.kinds,
          rule_sets: data.rule_sets ?? [],
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
