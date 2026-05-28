<template>
  <div class="app-chrome flex min-h-screen items-center justify-center p-4">
    <div class="surface w-full max-w-sm rounded-lg p-8">
      <h1 class="mb-6 text-center text-xl font-semibold text-[var(--color-ink)]">AI 生成项目报账文档</h1>

      <div class="space-y-4">
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

        <button v-if="!isRegister && allowRegister" @click="isRegister = true; error = ''"
          class="btn-quiet w-full">
          没有账号？注册
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
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)
const allowRegister = ref(true)

onMounted(async () => {
  await auth.init()
  if (auth.isLocal || auth.isLoggedIn) {
    router.replace('/')
    return
  }
  allowRegister.value = auth.allowRegister
})

async function doLogin() {
  error.value = ''
  if (!user.value.trim() || !pwd.value) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(user.value, pwd.value)
    router.replace('/')
  } catch (e: any) {
    error.value = e.message
  }
  loading.value = false
}

async function doRegister() {
  error.value = ''
  if (!user.value.trim() || pwd.value.length < 4) {
    error.value = '用户名不能为空，密码至少4位'
    return
  }
  loading.value = true
  try {
    await auth.register(user.value, pwd.value)
    await auth.login(user.value, pwd.value)
    router.replace('/')
  } catch (e: any) {
    error.value = e.message
  }
  loading.value = false
}
</script>
