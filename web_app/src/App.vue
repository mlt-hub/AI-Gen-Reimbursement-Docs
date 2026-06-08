<template>
  <AppShell
    v-if="usesShell"
    :mode-label="modeLabel"
    :version="version"
    :backend-status-text="backendStatusText"
    :backend-status-class="backendStatusClass"
    :backend-dot-class="backendDotClass"
    :backend-offline="config.backendStatus === 'offline'"
    :show-prompt-debug="auth.isLocal"
    :show-admin-tools="auth.isAdmin && !auth.mustChangePassword"
    :show-user-actions="auth.isRemote && auth.isLoggedIn"
    :username="auth.username"
    @logout="doLogout"
  >
    <router-view />
  </AppShell>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/config.ts'
import { useAuthStore } from '@/stores/auth.ts'
import { apiFetch } from '@/lib/api.ts'
import AppShell from '@/components/layout/AppShell.vue'

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

const usesShell = computed(() => route.meta.shell !== false)
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
  } else if (auth.isRemote && auth.mustChangePassword && route.path !== '/login') {
    router.replace('/login')
  }
})

// 监听路由变化，保护需要登录的页面
watch(() => route.path, (path) => {
  if (path !== '/login' && auth.isRemote && !auth.isLoggedIn) {
    router.replace('/login')
  } else if (path !== '/login' && auth.isRemote && auth.mustChangePassword) {
    router.replace('/login')
  }
})

async function doLogout() {
  await auth.logout()
  router.replace('/login')
}
</script>
