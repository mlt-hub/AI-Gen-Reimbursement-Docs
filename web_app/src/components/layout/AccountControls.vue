<template>
  <div v-if="showUserActions" :class="compact ? 'flex shrink-0 items-center gap-1' : 'flex min-w-0 items-center gap-2'">
    <span
      v-if="!compact"
      class="min-w-0 truncate rounded-md bg-[var(--color-surface-raised)] px-2 py-1 text-xs text-[var(--color-ink-muted)]"
    >
      {{ username }}
    </span>
    <button type="button" class="btn-quiet min-h-0 shrink-0 px-2 py-1 text-xs" @click="$emit('logout')">退出</button>
  </div>
  <span v-else class="text-xs text-[var(--color-ink-soft)]">本机</span>
</template>

<script setup lang="ts">
defineProps<{
  showUserActions: boolean
  username: string
  compact?: boolean
}>()

defineEmits<{ logout: [] }>()
</script>
