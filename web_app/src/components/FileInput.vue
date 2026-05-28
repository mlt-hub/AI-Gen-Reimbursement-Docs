<template>
  <div class="space-y-3">
    <!-- 本机模式 -->
    <div v-if="config.workMode === 'local'">
      <label for="xlsx-path" class="field-label">功能清单 .xlsx 路径（或项目目录）</label>
      <input id="xlsx-path" type="text" v-model="config.xlsxPath"
        placeholder="C:\...\功能清单.xlsx  或  C:\...\项目目录\"
        class="field-control" />
      <div class="mt-3">
        <label for="output-dir" class="field-label">交付物输出目录</label>
        <input id="output-dir" type="text" v-model="config.outputDir"
          placeholder="留空使用默认：xlsx 同级或目录/项目名"
          class="field-control" />
      </div>
    </div>
    <!-- 远程模式 -->
    <div v-else>
      <label class="field-label">上传功能清单 .xlsx</label>
      <div class="relative rounded-lg border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface)] p-3">
        <input type="file" accept=".xlsx" @change="onFileChange"
          class="w-full text-sm text-[var(--color-ink-muted)] file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-accent-soft)] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-[var(--color-accent-strong)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      <p v-if="selectedName" class="mt-2 text-xs text-[var(--color-accent-strong)]">已选: {{ selectedName }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useConfigStore } from '@/stores/config.ts'

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
