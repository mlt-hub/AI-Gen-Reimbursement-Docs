<template>
  <details id="advanced-run-settings" :open="defaultOpen" class="surface rounded-lg" data-focus-target="advanced">
    <summary class="flex cursor-pointer select-none flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span class="min-w-0">
        <span class="block text-xs font-semibold text-[var(--color-ink-soft)]">高级参数</span>
        <span class="mt-1 block text-base font-bold text-[var(--color-ink)]">FPA 策略与运行参数</span>
      </span>
      <span class="min-w-0 text-left text-xs leading-5 text-[var(--color-ink-muted)] sm:max-w-[60%] sm:text-right">
        {{ settingsSummary }}
      </span>
    </summary>

    <div class="border-t border-[var(--color-rule)] p-4">
      <div class="grid gap-4 md:grid-cols-2">
        <div>
          <label for="project-name" class="field-label text-xs">项目名称（留空自动读取）</label>
          <input
            id="project-name"
            v-model="config.projectName"
            type="text"
            placeholder="自动从 xlsx 读取"
            class="field-control"
          />
        </div>

        <div v-if="config.workMode === 'local'">
          <label for="output-dir" class="field-label text-xs">交付物输出目录</label>
          <input
            id="output-dir"
            v-model="config.outputDir"
            type="text"
            placeholder="留空使用默认：xlsx 同级或目录/项目名"
            class="field-control"
          />
        </div>

        <div>
          <label for="fpa-profile" class="field-label text-xs">FPA 方案</label>
          <select id="fpa-profile" v-model="config.fpaProfile" class="field-control">
            <option v-for="profile in fpaOptions.profiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </div>

        <div>
          <label for="fpa-strategy" class="field-label text-xs">FPA 执行策略</label>
          <select id="fpa-strategy" v-model="config.fpaStrategy" class="field-control">
            <option value="">{{ defaultStrategyLabel }}</option>
            <option v-for="strategy in fpaOptions.strategies" :key="strategy.name" :value="strategy.name">
              {{ strategy.label }}
            </option>
          </select>
        </div>

        <div>
          <label for="fpa-rule-set" class="field-label text-xs">FPA 规则集</label>
          <select id="fpa-rule-set" v-model="config.fpaRuleSet" class="field-control">
            <option value="">{{ defaultRuleSetLabel }}</option>
            <option v-for="ruleSet in fpaOptions.rule_sets" :key="ruleSet.name" :value="ruleSet.name">
              {{ ruleSet.label }}
            </option>
          </select>
          <div v-if="fpaOptionsError" class="mt-1 text-xs text-[var(--color-ink-soft)]">{{ friendlyFpaOptionsError }}</div>
        </div>

        <div>
          <label for="fpa-confirmation-mode" class="field-label text-xs">FPA 生成模式</label>
          <select id="fpa-confirmation-mode" v-model="config.fpaConfirmationMode" class="field-control">
            <option v-for="mode in fpaOptions.confirmation_modes" :key="mode.name" :value="mode.name">
              {{ mode.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="mt-4 flex flex-col gap-3 border-t border-[var(--color-rule)] pt-4 sm:flex-row sm:items-center sm:justify-between">
        <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)]">
          <input
            v-model="config.clean"
            type="checkbox"
            class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
          />
          删除旧交付物输出目录
        </label>
        <router-link to="/prompt-debug" class="subtle-link text-sm">打开提示词调试</router-link>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useConfigStore } from '@/stores/config.ts'
import { useFpaOptions } from '@/composables/useFpaOptions.ts'
import { isBackendUnavailableMessage } from '@/lib/api.ts'

const config = useConfigStore()
const { fpaOptions, fpaOptionsError, loadFpaOptions } = useFpaOptions()

withDefaults(defineProps<{ defaultOpen?: boolean }>(), {
  defaultOpen: true,
})

const selectedProfile = computed(() => (
  fpaOptions.value.profiles.find(profile => profile.name === config.fpaProfile)
  ?? fpaOptions.value.profiles[0]
))
const defaultStrategyLabel = computed(() => {
  const strategy = fpaOptions.value.strategies.find(item => item.name === selectedProfile.value?.strategy)
  return strategy ? `跟随方案默认（${strategy.label}）` : '跟随方案默认'
})
const defaultRuleSetLabel = computed(() => (
  selectedProfile.value?.rule_set ? `跟随方案默认（${selectedProfile.value.rule_set}）` : '跟随方案默认'
))
const selectedStrategyLabel = computed(() => {
  const current = config.fpaStrategy || selectedProfile.value?.strategy || ''
  const strategy = fpaOptions.value.strategies.find(item => item.name === current)
  return strategy?.label || '跟随方案默认'
})
const selectedRuleSetLabel = computed(() => (
  config.fpaRuleSet || selectedProfile.value?.rule_set || '跟随方案默认'
))
const selectedConfirmationLabel = computed(() => (
  fpaOptions.value.confirmation_modes.find(mode => mode.name === config.fpaConfirmationMode)?.label || '审慎模式'
))
const settingsSummary = computed(() => [
  selectedProfile.value?.label || config.fpaProfile,
  selectedStrategyLabel.value,
  selectedRuleSetLabel.value,
  selectedConfirmationLabel.value,
].filter(Boolean).join(' / '))
const friendlyFpaOptionsError = computed(() => (
  config.backendStatus === 'offline' || isBackendUnavailableMessage(fpaOptionsError.value)
    ? '等待后端连接后加载'
    : fpaOptionsError.value
))

watch(
  fpaOptions,
  options => {
    if (config.fpaRuleSet && !options.rule_sets.some(ruleSet => ruleSet.name === config.fpaRuleSet)) {
      config.fpaRuleSet = ''
    }
    if (!options.confirmation_modes.some(mode => mode.name === config.fpaConfirmationMode)) {
      config.fpaConfirmationMode = 'cautious'
    }
  },
  { immediate: true },
)

onMounted(loadFpaOptions)
</script>
