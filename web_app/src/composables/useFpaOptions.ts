import { computed, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

export interface FpaProfileOption {
  name: string
  label: string
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
  rule_sets: FpaRuleSetOption[]
}

const fallbackOptions: FpaOptions = {
  default_profile: 'custom_rules',
  profiles: [
    { name: 'custom_rules', label: '用户自定义规则口径', strategy: 'rules_first', rule_set: 'custom_rules_default' },
    { name: 'strict_fpa', label: '严格 FPA 口径', strategy: 'ai_first', rule_set: 'strict_fpa_default' },
  ],
  strategies: [
    { name: 'rules_first', label: '规则优先' },
    { name: 'ai_first', label: 'AI 优先' },
    { name: 'rules_only', label: '仅规则' },
    { name: 'ai_only', label: '仅 AI' },
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

