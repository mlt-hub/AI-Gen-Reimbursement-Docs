<template>
  <PreviewLayout title="FPA 预览">
    <template #controls>
      <div class="flex flex-col gap-5">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">输入设置</p>
          <h3 class="mt-1 text-lg font-bold text-[var(--color-ink)]">选择功能清单</h3>
          <p class="mt-1 text-xs leading-5 text-[var(--color-ink-muted)]">先选输入来源，再到右侧生成基础数据并预览结果。</p>
        </div>
        <FileInput />
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-3 text-xs leading-5 text-[var(--color-ink-muted)]">
          <div class="font-semibold text-[var(--color-ink)]">基础数据状态</div>
          <p class="mt-1">{{ config.isValid ? '等待右侧生成基础数据。' : '请先选择功能清单输入来源。' }}</p>
        </div>
      </div>
    </template>

    <FpaPreview />
  </PreviewLayout>
</template>

<script setup lang="ts">
import { useConfigStore } from '@/stores/config.ts'
import PreviewLayout from '@/components/PreviewLayout.vue'
import FileInput from '@/components/FileInput.vue'
import FpaPreview from '@/components/FpaPreview.vue'

const config = useConfigStore()
</script>
