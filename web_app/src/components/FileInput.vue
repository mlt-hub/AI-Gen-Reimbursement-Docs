<template>
  <div class="space-y-3">
    <!-- 本机模式 -->
    <div v-if="config.workMode === 'local'" id="generation-input-control" data-focus-target="input">
      <label for="xlsx-path" class="field-label">功能清单 .xlsx 路径（或项目目录）</label>
      <input id="xlsx-path" type="text" v-model="config.xlsxPath"
        placeholder="C:\...\功能清单.xlsx  或  C:\...\项目目录\"
        class="field-control" />
      <p class="mt-1 text-xs leading-5 text-[var(--color-ink-soft)]">可填写单个功能清单文件，也可填写包含项目资料的目录。</p>
    </div>
    <!-- 远程模式 -->
    <div v-else id="generation-input-control" data-focus-target="input">
      <label class="field-label">上传功能清单 .xlsx</label>
      <div class="relative rounded-lg border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface)] p-3">
        <input type="file" accept=".xlsx" @change="onFileChange"
          class="w-full text-sm text-[var(--color-ink-muted)] file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-accent-soft)] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-[var(--color-accent-strong)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      <div v-if="selectedName || config.remoteInputName" class="mt-2 rounded-md border border-[var(--color-accent)] bg-[var(--color-accent-soft)] px-3 py-2 text-xs text-[var(--color-accent-strong)]">
        <div class="font-semibold">{{ selectedName ? '已选择功能清单' : '已恢复任务输入' }}</div>
        <div class="mt-0.5 break-all">{{ selectedName || config.remoteInputName }}</div>
        <div v-if="!selectedName && config.remoteInputName" class="mt-1 text-[var(--color-accent-strong)] opacity-80">
          继续任务可查看进度；重新提交需重新选择文件。
        </div>
      </div>
      <p v-else class="mt-2 text-xs leading-5 text-[var(--color-ink-soft)]">仅支持 `.xlsx` 功能清单文件。</p>
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
    config.remoteInputName = ''
  }
}
</script>
