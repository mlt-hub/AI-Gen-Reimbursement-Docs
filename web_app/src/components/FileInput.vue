<template>
  <div class="space-y-3">
    <!-- 本机模式 -->
    <div v-if="config.workMode === 'local'">
      <label for="xlsx-path" class="block text-sm font-medium text-gray-600 mb-1">功能清单 .xlsx 路径（或项目目录）</label>
      <input id="xlsx-path" type="text" v-model="config.xlsxPath"
        placeholder="C:\...\功能清单.xlsx  或  C:\...\项目目录\"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-shadow" />
      <div class="mt-3">
        <label for="output-dir" class="block text-sm font-medium text-gray-600 mb-1">交付物输出目录（默认 xlsx 同级，目录模式为 目录/项目名/）</label>
        <input id="output-dir" type="text" v-model="config.outputDir"
          placeholder="留空使用默认"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-shadow" />
      </div>
    </div>
    <!-- 远程模式 -->
    <div v-else>
      <label class="block text-sm font-medium text-gray-600 mb-1">上传功能清单 .xlsx</label>
      <div class="relative">
        <input type="file" accept=".xlsx" @change="onFileChange"
          class="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100" />
      </div>
      <p v-if="selectedName" class="text-xs text-primary-500 mt-1">已选: {{ selectedName }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useConfigStore } from '@/stores/config'

const config = useConfigStore()
const selectedName = ref('')

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    config.selectedFile = input.files[0]
    selectedName.value = input.files[0].name
  }
}
</script>
