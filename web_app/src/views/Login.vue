<template>
  <div class="app-chrome flex min-h-screen items-center justify-center p-4">
    <div class="surface w-full max-w-sm rounded-lg p-8">
      <h1 class="mb-6 text-center text-xl font-semibold text-[var(--color-ink)]">AI 生成项目报账文档</h1>

      <div v-if="mustChangePassword" class="space-y-4">
        <div class="rounded-lg border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-3 py-2 text-sm text-[var(--color-warning)]">
          管理员初始密码必须先修改。
        </div>
        <div>
          <label for="current-password" class="field-label">当前密码</label>
          <input id="current-password" v-model="currentPwd" type="password" @keyup.enter="doChangePassword"
            class="field-control" />
        </div>
        <div>
          <label for="new-password" class="field-label">新密码</label>
          <input id="new-password" v-model="newPwd" type="password" @keyup.enter="doChangePassword"
            class="field-control" />
        </div>
        <div>
          <label for="confirm-password" class="field-label">确认新密码</label>
          <input id="confirm-password" v-model="confirmPwd" type="password" @keyup.enter="doChangePassword"
            class="field-control" />
        </div>
        <p v-if="error" class="text-sm text-[var(--color-danger)]">{{ error }}</p>
        <button @click="doChangePassword" :disabled="loading" class="btn-primary w-full">
          {{ loading ? '修改中...' : '修改密码' }}
        </button>
        <button @click="doLogout" :disabled="loading" class="btn-quiet w-full">
          退出登录
        </button>
      </div>

      <div v-else class="space-y-4">
        <div>
          <label for="username" class="field-label">用户名</label>
          <input id="username" v-model="user" type="text" @keyup.enter="isRegister ? doRegister() : doLogin()"
            class="field-control" />
        </div>
        <div>
          <label for="password" class="field-label">密码</label>
          <input id="password" v-model="pwd" type="password" @keyup.enter="isRegister ? doRegister() : doLogin()"
            class="field-control" />
        </div>
        <div v-if="isRegister">
          <label for="invite-code" class="field-label">邀请码</label>
          <input id="invite-code" v-model="inviteCode" type="text" @keyup.enter="doRegister"
            class="field-control font-mono" />
        </div>

        <label v-if="!isRegister" class="flex items-center gap-2 text-sm text-[var(--color-ink-muted)]">
          <input v-model="rememberMe" type="checkbox" class="h-4 w-4 rounded border-[var(--color-rule-strong)]" />
          <span>记住我</span>
        </label>

        <p v-if="error" class="text-sm text-[var(--color-danger)]">{{ error }}</p>

        <button v-if="!isRegister" @click="doLogin" :disabled="loading"
          class="btn-primary w-full">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <template v-if="isRegister">
          <button @click="doRegister" :disabled="loading"
            class="btn-primary w-full">
            {{ loading ? '注册中...' : '注册' }}
          </button>
          <button @click="isRegister = false; error = ''"
            class="btn-quiet w-full">
            已有账号？去登录
          </button>
        </template>

        <button v-if="!isRegister" @click="isRegister = true; error = ''"
          class="btn-quiet w-full">
          使用邀请码注册
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.ts'

const router = useRouter()
const auth = useAuthStore()

const user = ref('')
const pwd = ref('')
const inviteCode = ref('')
const rememberMe = ref(false)
const currentPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)
const mustChangePassword = ref(false)

onMounted(async () => {
  await auth.init()
  if (auth.isLocal || (auth.isLoggedIn && !auth.mustChangePassword)) {
    router.replace('/')
    return
  }
  if (auth.mustChangePassword) {
    mustChangePassword.value = true
    user.value = auth.username
    return
  }
  user.value = auth.rememberedUsername()
  rememberMe.value = !!user.value
})

async function doLogin() {
  error.value = ''
  if (!user.value.trim() || !pwd.value) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    const result = await auth.login(user.value, pwd.value, rememberMe.value)
    if (result.must_change_password) {
      mustChangePassword.value = true
      currentPwd.value = pwd.value
      pwd.value = ''
      loading.value = false
      return
    }
    router.replace('/')
  } catch (e: any) {
    error.value = e.message
  }
  loading.value = false
}

async function doRegister() {
  error.value = ''
  if (!user.value.trim() || pwd.value.length < 6) {
    error.value = '用户名不能为空，密码至少6位'
    return
  }
  if (!inviteCode.value.trim()) {
    error.value = '请填写邀请码'
    return
  }
  loading.value = true
  try {
    await auth.register(user.value, pwd.value, inviteCode.value)
    const result = await auth.login(user.value, pwd.value, rememberMe.value)
    if (result.must_change_password) {
      mustChangePassword.value = true
      currentPwd.value = pwd.value
      pwd.value = ''
      loading.value = false
      return
    }
    router.replace('/')
  } catch (e: any) {
    error.value = e.message
  }
  loading.value = false
}

async function doChangePassword() {
  error.value = ''
  if (!currentPwd.value || newPwd.value.length < 6) {
    error.value = '当前密码不能为空，新密码至少6位'
    return
  }
  if (newPwd.value !== confirmPwd.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  if (newPwd.value === currentPwd.value) {
    error.value = '新密码不能与当前密码相同'
    return
  }
  loading.value = true
  try {
    await auth.changePassword(currentPwd.value, newPwd.value)
    mustChangePassword.value = false
    router.replace('/')
  } catch (e: any) {
    error.value = e.message
  }
  loading.value = false
}

async function doLogout() {
  loading.value = true
  try {
    await auth.logout()
    mustChangePassword.value = false
    currentPwd.value = ''
    newPwd.value = ''
    confirmPwd.value = ''
  } finally {
    loading.value = false
  }
}
</script>
