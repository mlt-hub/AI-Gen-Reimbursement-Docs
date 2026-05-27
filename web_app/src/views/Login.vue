<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="bg-white rounded-xl shadow-lg p-8 w-full max-w-sm">
      <h1 class="text-xl font-semibold text-center text-gray-800 mb-6">AI 生成项目报账文档</h1>

      <div class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-600 mb-1">用户名</label>
          <input id="username" v-model="user" type="text" @keyup.enter="isRegister ? doRegister() : doLogin()"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-600 mb-1">密码</label>
          <input id="password" v-model="pwd" type="password" @keyup.enter="isRegister ? doRegister() : doLogin()"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>

        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>

        <button v-if="!isRegister" @click="doLogin" :disabled="loading"
          class="w-full py-2.5 bg-primary-500 text-white font-semibold rounded-lg hover:bg-primary-600 disabled:bg-primary-300 transition-colors">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <template v-if="isRegister">
          <button @click="doRegister" :disabled="loading"
            class="w-full py-2.5 bg-primary-500 text-white font-semibold rounded-lg hover:bg-primary-600 disabled:bg-primary-300 transition-colors">
            {{ loading ? '注册中...' : '注册' }}
          </button>
          <button @click="isRegister = false; error = ''"
            class="w-full py-2 text-sm text-gray-500 hover:text-primary-600">
            已有账号？去登录
          </button>
        </template>

        <button v-if="!isRegister && allowRegister" @click="isRegister = true; error = ''"
          class="w-full py-2 text-sm text-gray-500 hover:text-primary-600">
          没有账号？注册
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
