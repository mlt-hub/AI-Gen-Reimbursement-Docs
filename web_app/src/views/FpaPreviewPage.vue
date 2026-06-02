<template>
  <PreviewLayout title="FPA 预览">
    <template #controls>
      <div class="flex flex-col gap-5">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">输入设置</p>
          <h3 class="mt-1 text-lg font-bold text-[var(--color-ink)]">选择功能清单</h3>
          <p class="mt-1 text-xs leading-5 text-[var(--color-ink-muted)]">填写输入来源后，在右侧生成基础数据并选择三级模块预览。</p>
        </div>
        <FileInput />
        <div class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3">
          <AdvancedOptions />
        </div>
      </div>
    </template>

    <FpaPreview />
  </PreviewLayout>
</template>

<script setup lang="ts">
import PreviewLayout from '@/components/PreviewLayout.vue'
import FileInput from '@/components/FileInput.vue'
import AdvancedOptions from '@/components/AdvancedOptions.vue'
import FpaPreview from '@/components/FpaPreview.vue'
</script>
