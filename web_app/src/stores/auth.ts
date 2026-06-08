import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { apiFetch } from '@/lib/api.ts'

interface AuthMeResponse {
  username?: string
  role?: string
  is_local: boolean
  allow_register: boolean
}

interface LoginResponse {
  username: string
  role: string
}

export const useAuthStore = defineStore('auth', () => {
  const username = ref('')
  const role = ref('')
  const isLocal = ref(true)
  const allowRegister = ref(true)
  const loading = ref(true)

  const isLoggedIn = computed(() => !!username.value)
  const isRemote = computed(() => !isLocal.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function init() {
    try {
      const data = await apiFetch<AuthMeResponse>('/api/auth/me')
      username.value = data.username || ''
      role.value = data.role || ''
      isLocal.value = data.is_local
      allowRegister.value = data.allow_register
    } catch { /* 忽略 */ }
    loading.value = false
  }

  async function login(user: string, password: string, rememberMe = false) {
    const data = await apiFetch<LoginResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password, remember_me: rememberMe }),
    })
    username.value = data.username
    role.value = data.role || ''
    if (rememberMe) {
      window.localStorage.setItem('ard:last_username', data.username)
    } else {
      window.localStorage.removeItem('ard:last_username')
    }
    return data
  }

  async function register(user: string, password: string, inviteCode: string) {
    await apiFetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password, invite_code: inviteCode }),
    })
  }

  async function logout() {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    username.value = ''
    role.value = ''
  }

  function rememberedUsername() {
    return window.localStorage.getItem('ard:last_username') || ''
  }

  return { username, role, isLocal, allowRegister, loading, isLoggedIn, isRemote, isAdmin, init, login, register, logout, rememberedUsername }
})
