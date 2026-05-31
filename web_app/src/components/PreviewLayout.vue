<template>
  <div class="box-border flex h-full max-w-full flex-col gap-4 overflow-x-hidden overflow-y-auto p-4 lg:p-5">
    <section class="surface shrink-0 rounded-xl p-4">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="min-w-0">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">预览中心</p>
          <h2 class="mt-1 text-xl font-bold text-[var(--color-ink)]">{{ title }}</h2>
        </div>
        <nav class="flex flex-wrap gap-2 text-sm">
          <router-link to="/preview/fpa" class="nav-link" active-class="nav-link-active">FPA</router-link>
          <span class="nav-link cursor-not-allowed opacity-50">COSMIC</span>
          <span class="nav-link cursor-not-allowed opacity-50">SPEC</span>
        </nav>
      </div>
    </section>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <aside class="surface min-h-0 overflow-y-auto rounded-xl p-4">
        <slot name="controls" />
      </aside>
      <section class="surface min-h-[520px] overflow-hidden rounded-xl">
        <slot />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>
