import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { apiFetch } from '@/lib/api.ts'

interface AuthMeResponse {
  username?: string
  is_local: boolean
  allow_register: boolean
}

interface LoginResponse {
  username: string
}

export const useAuthStore = defineStore('auth', () => {
  const username = ref('')
  const isLocal = ref(true)
  const allowRegister = ref(true)
  const loading = ref(true)

  const isLoggedIn = computed(() => !!username.value)
  const isRemote = computed(() => !isLocal.value)

  async function init() {
    try {
      const data = await apiFetch<AuthMeResponse>('/api/auth/me')
      username.value = data.username || ''
      isLocal.value = data.is_local
      allowRegister.value = data.allow_register
    } catch { /* 忽略 */ }
    loading.value = false
  }

  async function login(user: string, password: string) {
    const data = await apiFetch<LoginResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password }),
    })
    username.value = data.username
    return data
  }

  async function register(user: string, password: string) {
    await apiFetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password }),
    })
  }

  async function logout() {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    username.value = ''
  }

  return { username, isLocal, allowRegister, loading, isLoggedIn, isRemote, init, login, register, logout }
})
