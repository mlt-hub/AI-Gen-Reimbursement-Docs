<template>
  <div class="app-chrome flex h-screen flex-col">
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
            </div>
          </div>
      </div>
        <nav class="flex flex-wrap items-center gap-1 text-sm">
          <router-link to="/" class="nav-link" active-class="nav-link-active">生成</router-link>
          <router-link to="/config" class="nav-link" active-class="nav-link-active">配置</router-link>
          <router-link to="/prompt-debug" class="nav-link" active-class="nav-link-active">提示词调试</router-link>
          <template v-if="auth.isRemote && auth.isLoggedIn">
            <span class="mx-2 hidden h-5 w-px bg-[var(--color-rule)] md:inline-block" />
            <span class="rounded-md bg-[var(--color-surface-muted)] px-2 py-1 text-xs text-[var(--color-ink-muted)]">{{ auth.username }}</span>
            <button @click="doLogout" class="btn-quiet min-h-0 px-2 py-1 text-xs">退出</button>
        </template>
      </nav>
      </div>
    </header>
    <main class="flex-1 min-h-0">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/config'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const config = useConfigStore()
const auth = useAuthStore()
const version = ref('-')

const modeLabel = computed(() => config.workMode === 'local' ? '本机模式' : '远程服务模式')

onMounted(async () => {
  await auth.init()

  try {
    const [verResp, modeResp, localResp] = await Promise.all([
      fetch('/api/version'),
      fetch('/api/default-work-mode'),
      fetch('/api/is-local')
    ])
    const verData = await verResp.json()
    version.value = verData.version
    const modeData = await modeResp.json()
    if (modeData.work_mode === 'local' || modeData.work_mode === 'remote') {
      config.workMode = modeData.work_mode
    } else {
      const localData = await localResp.json()
      config.workMode = localData.local ? 'local' : 'remote'
    }
  } catch {
    version.value = '-'
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
