<template>
  <PreviewLayout title="SPEC 预览">
    <template #controls>
      <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-ink-muted)]">
        SPEC 预览能力待接入。当前可先使用生成任务和历史记录查看交付物。
      </div>
    </template>

    <div class="flex h-full min-h-[360px] items-center justify-center p-5">
      <div class="max-w-md text-center">
        <p class="text-sm font-semibold text-[var(--color-ink)]">等待 SPEC 预览流程</p>
        <p class="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">
          后续接入 SPEC 生成器后，这里会承载需求说明书预览、审阅和交付确认。
        </p>
      </div>
    </div>
  </PreviewLayout>
</template>

<script setup lang="ts">
import PreviewLayout from '@/components/PreviewLayout.vue'
</script>
