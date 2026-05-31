<template>
  <details class="group">
    <summary class="subtle-link cursor-pointer select-none text-sm">高级选项</summary>
    <div class="mt-3 flex flex-col gap-3 border-t border-[var(--color-rule)] pt-3">
      <div>
        <label for="api-key" class="field-label text-xs">API Key（留空使用系统配置）</label>
        <input id="api-key" type="password" v-model.trim="config.apiKey" placeholder="留空使用系统配置" autocomplete="off"
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
          <option value="custom_rules">用户自定义规则口径</option>
          <option value="strict_fpa">严格 FPA 口径</option>
        </select>
      </div>
      <div>
        <label for="fpa-strategy" class="field-label text-xs">FPA 执行策略</label>
        <select id="fpa-strategy" v-model="config.fpaStrategy" class="field-control">
          <option value="">跟随方案默认</option>
          <option value="rules_first">规则优先</option>
          <option value="ai_first">AI 优先</option>
          <option value="rules_only">仅规则</option>
          <option value="ai_only">仅 AI</option>
        </select>
      </div>
      <div>
        <label for="fpa-rule-set" class="field-label text-xs">FPA 规则集</label>
        <input id="fpa-rule-set" type="text" v-model.trim="config.fpaRuleSet" placeholder="留空使用方案默认规则集"
          class="field-control" />
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
import { useConfigStore } from '@/stores/config.ts'
const config = useConfigStore()
</script>
