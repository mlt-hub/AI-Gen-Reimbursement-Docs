<template>
  <div class="app-chrome flex h-screen w-full max-w-full flex-col overflow-x-hidden">
    <header class="topbar shrink-0 px-4 py-3 md:px-6">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] text-sm font-black text-[var(--color-accent-strong)]">
            ARD
          </div>
          <div class="min-w-0">
            <h1 class="truncate text-base font-bold text-[var(--color-ink)] md:text-lg">AI 生成项目报账文档</h1>
            <div class="mt-0.5 flex items-center gap-2 text-xs text-[var(--color-ink-soft)]">
              <span>{{ modeLabel }}</span>
              <span class="h-1 w-1 rounded-full bg-[var(--color-rule-strong)]" />
              <span>v{{ version }}</span>
              <span class="h-1 w-1 rounded-full bg-[var(--color-rule-strong)]" />
              <span :class="['inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold', backendStatusClass]">
                <span class="h-1.5 w-1.5 rounded-full" :class="backendDotClass" />
                {{ backendStatusText }}
              </span>
            </div>
          </div>
      </div>
        <nav class="flex flex-wrap items-center gap-1 text-sm">
          <router-link to="/" class="nav-link" active-class="nav-link-active">生成</router-link>
          <router-link to="/config" class="nav-link" active-class="nav-link-active">配置</router-link>
          <router-link to="/license" class="nav-link" active-class="nav-link-active">授权</router-link>
          <router-link to="/prompt-debug" class="nav-link" active-class="nav-link-active">提示词调试</router-link>
          <template v-if="auth.isRemote && auth.isLoggedIn">
            <span class="mx-2 hidden h-5 w-px bg-[var(--color-rule)] md:inline-block" />
            <span class="rounded-md bg-[var(--color-surface-muted)] px-2 py-1 text-xs text-[var(--color-ink-muted)]">{{ auth.username }}</span>
            <button @click="doLogout" class="btn-quiet min-h-0 px-2 py-1 text-xs">退出</button>
        </template>
      </nav>
      </div>
    </header>
    <main class="min-h-0 min-w-0 flex-1 overflow-x-hidden">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/config.ts'
import { useAuthStore } from '@/stores/auth.ts'
import { apiFetch } from '@/lib/api.ts'

interface VersionResponse {
  version?: string
}

interface WorkModeResponse {
  work_mode?: string
}

interface IsLocalResponse {
  local?: boolean
}

interface HealthResponse {
  ok?: boolean
  version?: string
  work_mode?: string
}

const router = useRouter()
const route = useRoute()
const config = useConfigStore()
const auth = useAuthStore()
const version = ref('-')

const modeLabel = computed(() => config.workMode === 'local' ? '本机模式' : '远程服务模式')
const backendStatusText = computed(() => {
  const map = {
    checking: '检查服务中',
    connected: '后端已连接',
    degraded: '后端部分异常',
    offline: '后端未连接',
  }
  return map[config.backendStatus]
})
const backendStatusClass = computed(() => {
  const map = {
    checking: 'bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]',
    connected: 'bg-[var(--color-success-soft)] text-[var(--color-success)]',
    degraded: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
    offline: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  }
  return map[config.backendStatus]
})
const backendDotClass = computed(() => {
  const map = {
    checking: 'bg-[var(--color-ink-soft)]',
    connected: 'bg-[var(--color-success)]',
    degraded: 'bg-[var(--color-warning)]',
    offline: 'bg-[var(--color-warning)]',
  }
  return map[config.backendStatus]
})

function applyWorkMode(mode?: string) {
  if (mode === 'local' || mode === 'remote') {
    config.workMode = mode
    return true
  }
  return false
}

async function loadLegacyBackendState() {
  const [versionResult, modeResult, localResult] = await Promise.allSettled([
    apiFetch<VersionResponse>('/api/version'),
    apiFetch<WorkModeResponse>('/api/default-work-mode'),
    apiFetch<IsLocalResponse>('/api/is-local'),
  ])

  config.backendStatus = [versionResult, modeResult, localResult].some(result => result.status === 'fulfilled')
    ? 'connected'
    : 'offline'

  if (versionResult.status === 'fulfilled') {
    version.value = versionResult.value.version || '-'
  } else {
    version.value = '-'
  }

  if (modeResult.status === 'fulfilled') {
    const modeData = modeResult.value
    if (!applyWorkMode(modeData.work_mode) && localResult.status === 'fulfilled') {
      config.workMode = localResult.value.local ? 'local' : 'remote'
    }
  } else if (localResult.status === 'fulfilled') {
    config.workMode = localResult.value.local ? 'local' : 'remote'
  }
}

onMounted(async () => {
  await auth.init()

  try {
    const health = await apiFetch<HealthResponse>('/api/health')
    config.backendStatus = health.ok === false ? 'degraded' : 'connected'
    version.value = health.version || '-'
    if (!applyWorkMode(health.work_mode)) {
      await loadLegacyBackendState()
    }
  } catch {
    await loadLegacyBackendState()
  }

  // 路由守卫：远程模式未登录 → 跳转登录页
  if (auth.isRemote && !auth.isLoggedIn && route.path !== '/login') {
    router.replace('/login')
  }
})

// 监听路由变化，保护需要登录的页面
watch(() => route.path, (path) => {
  if (path !== '/login' && auth.isRemote && !auth.isLoggedIn) {
    router.replace('/login')
  }
})

async function doLogout() {
  await auth.logout()
  router.replace('/login')
}
</script>
