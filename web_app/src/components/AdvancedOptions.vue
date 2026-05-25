<template>
  <details class="group">
    <summary class="text-sm text-primary-600 cursor-pointer select-none hover:text-primary-700 font-medium">高级选项</summary>
    <div class="flex flex-col gap-3 mt-3 pt-3 border-t border-gray-100">
      <div>
        <label for="api-key" class="block text-xs text-gray-500 mb-1">API Key（留空使用系统配置）</label>
        <input id="api-key" type="password" v-model="config.apiKey" placeholder="sk-..." autocomplete="off"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
      </div>
      <div>
        <label for="base-url" class="block text-xs text-gray-500 mb-1">BASE URL</label>
        <input id="base-url" type="text" v-model="config.baseUrl" placeholder="https://api.deepseek.com/anthropic"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
      </div>
      <div>
        <label for="model" class="block text-xs text-gray-500 mb-1">MODEL</label>
        <input id="model" type="text" v-model="config.model" placeholder="deepseek-v4-flash[1m]"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
      </div>
      <div>
        <label for="max-tokens" class="block text-xs text-gray-500 mb-1">Max Tokens</label>
        <input id="max-tokens" type="text" v-model="config.maxTokens" placeholder="留空使用默认"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
      </div>
      <div>
        <label for="project-name" class="block text-xs text-gray-500 mb-1">项目名称（留空自动读取）</label>
        <input id="project-name" type="text" v-model="config.projectName" placeholder="自动从 xlsx 读取"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
      </div>
      <div class="flex items-end pb-2">
        <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
          <input type="checkbox" v-model="config.clean" class="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
          删除旧交付物输出目录
        </label>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
import { useConfigStore } from '@/stores/config'
const config = useConfigStore()
</script>
