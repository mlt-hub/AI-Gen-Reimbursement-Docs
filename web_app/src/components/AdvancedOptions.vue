<template>
  <details class="group">
    <summary class="subtle-link cursor-pointer select-none text-sm">高级选项</summary>
    <div class="mt-3 flex flex-col gap-3 border-t border-[var(--color-rule)] pt-3">
      <div>
        <label for="api-key" class="field-label text-xs">API Key（留空使用系统配置）</label>
        <input id="api-key" ref="apiKeyInput" type="password" v-model.trim="config.apiKey"
          placeholder="留空使用系统配置" autocomplete="new-password" autocapitalize="off" autocorrect="off"
          spellcheck="false" data-lpignore="true" data-1p-ignore="true" :name="apiKeyInputName"
          :readonly="apiKeyReadonly" @focus="activateApiKeyInput" @pointerdown="activateApiKeyInput"
          class="field-control" />
      </div>
      <div>
        <label for="base-url" class="field-label text-xs">接口地址</label>
        <input id="base-url" type="text" v-model="config.baseUrl" placeholder="https://api.deepseek.com/anthropic"
          class="field-control" />
      </div>
      <div>
        <label for="model" class="field-label text-xs">模型</label>
        <input id="model" type="text" v-model="config.model" placeholder="deepseek-v4-flash[1m]"
          class="field-control" />
      </div>
      <div>
        <label for="max-tokens" class="field-label text-xs">最大 Token 数</label>
        <input id="max-tokens" type="text" v-model="config.maxTokens" placeholder="留空使用默认"
          class="field-control" />
      </div>
      <div>
        <label for="project-name" class="field-label text-xs">项目名称（留空自动读取）</label>
        <input id="project-name" type="text" v-model="config.projectName" placeholder="自动从 xlsx 读取"
          class="field-control" />
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
        <div v-if="fpaOptionsError" class="mt-1 text-xs text-[var(--color-warning)]">{{ fpaOptionsError }}</div>
      </div>
      <div class="flex items-end pb-2">
        <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)]">
          <input type="checkbox" v-model="config.clean" class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]" />
          删除旧交付物输出目录
        </label>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useConfigStore } from '@/stores/config.ts'
import { useSensitiveInputGuard } from '@/composables/useSensitiveInputGuard.ts'
import { useFpaOptions } from '@/composables/useFpaOptions.ts'

const config = useConfigStore()
const { fpaOptions, fpaOptionsError, loadFpaOptions } = useFpaOptions()
const apiKeyInput = ref<HTMLInputElement | null>(null)
const {
  inputName: apiKeyInputName,
  readonly: apiKeyReadonly,
  activateSensitiveInput: activateApiKeyInput,
} = useSensitiveInputGuard('api-key', {
  inputRef: apiKeyInput,
  getValue: () => config.apiKey,
  setValue: value => { config.apiKey = value },
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
</script>
