<template>
  <div class="app-chrome flex h-screen w-full max-w-full overflow-hidden">
    <aside class="hidden w-64 shrink-0 border-r border-[var(--color-rule)] bg-[var(--color-surface)] lg:block">
      <SideNav
        :mode-label="modeLabel"
        :version="version"
        :backend-status-text="backendStatusText"
        :backend-status-class="backendStatusClass"
        :backend-dot-class="backendDotClass"
      >
        <template #account>
          <AccountControls
            :show-user-actions="showUserActions"
            :username="username"
            @logout="$emit('logout')"
          />
        </template>
      </SideNav>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <div v-if="backendOffline" class="border-b border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-sm text-[var(--color-warning)]" role="status" aria-live="polite">
        <div class="flex min-w-0 items-start gap-2">
          <span class="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--color-warning)]" />
          <div class="min-w-0">
            <div class="font-semibold">后端未连接</div>
            <div class="mt-0.5 text-xs leading-5">当前只能查看界面。启动后端服务后可运行任务、读取配置和生成预览。</div>
          </div>
        </div>
      </div>

      <header class="topbar shrink-0 px-3 py-2 lg:hidden">
        <div class="flex min-w-0 items-center justify-between gap-3">
          <button class="btn-secondary min-h-0 shrink-0 px-2.5 py-2" type="button" aria-label="打开导航" @click="mobileOpen = true">
            <Bars3Icon class="h-5 w-5" />
          </button>
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-bold text-[var(--color-ink)]">AI 报账文档生成</div>
            <div class="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-[var(--color-ink-soft)]">
              <span class="truncate">{{ modeLabel }}</span>
              <span class="h-1 w-1 shrink-0 rounded-full bg-[var(--color-rule-strong)]" />
              <span :class="['inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold', backendStatusClass]">
                <span class="h-1.5 w-1.5 rounded-full" :class="backendDotClass" />
                {{ backendStatusText }}
              </span>
            </div>
          </div>
          <AccountControls
            :show-user-actions="showUserActions"
            :username="username"
            compact
            @logout="$emit('logout')"
          />
        </div>
      </header>

      <main class="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
        <slot />
      </main>
    </div>

    <div v-if="mobileOpen" class="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
      <button class="absolute inset-0 h-full w-full bg-black/30" type="button" aria-label="关闭导航" @click="mobileOpen = false" />
      <aside class="absolute left-0 top-0 h-full w-[min(20rem,88vw)] border-r border-[var(--color-rule)] bg-[var(--color-surface)] shadow-2xl">
        <div class="flex items-center justify-end border-b border-[var(--color-rule)] px-3 py-2">
          <button class="btn-secondary min-h-0 px-2.5 py-2" type="button" aria-label="关闭导航" @click="mobileOpen = false">
            <XMarkIcon class="h-5 w-5" />
          </button>
        </div>
        <SideNav
          :mode-label="modeLabel"
          :version="version"
          :backend-status-text="backendStatusText"
          :backend-status-class="backendStatusClass"
          :backend-dot-class="backendDotClass"
          @navigate="mobileOpen = false"
        >
          <template #account>
            <AccountControls
              :show-user-actions="showUserActions"
              :username="username"
              @logout="$emit('logout')"
            />
          </template>
        </SideNav>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Bars3Icon, XMarkIcon } from '@heroicons/vue/24/outline'
import AccountControls from './AccountControls.vue'
import SideNav from './SideNav.vue'

defineProps<{
  modeLabel: string
  version: string
  backendStatusText: string
  backendStatusClass: string
  backendDotClass: string
  backendOffline: boolean
  showUserActions: boolean
  username: string
}>()

defineEmits<{ logout: [] }>()

const mobileOpen = ref(false)
</script>
