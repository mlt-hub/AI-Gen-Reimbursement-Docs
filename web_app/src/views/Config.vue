<template>
  <div class="max-w-3xl mx-auto p-6 space-y-8">
    <!-- 个人配置（可编辑） -->
    <section v-if="showUserConfig">
      <h2 class="text-lg font-semibold mb-4">个人配置</h2>
      <p class="text-sm text-gray-500 mb-3">
        {{ auth.isRemote ? `文件位置: ~/.ai-gen-reimbursement-docs/users/${auth.username}/` : '文件位置: ~/.ai-gen-reimbursement-docs/' }}
      </p>
      <div class="space-y-4 bg-white border border-gray-200 rounded-lg p-5">
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">ANTHROPIC_API_KEY</label>
          <input v-model="userEnv.apiKey" type="password"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">ANTHROPIC_BASE_URL</label>
          <input v-model="userEnv.baseUrl" type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">ANTHROPIC_MODEL</label>
          <input v-model="userEnv.model" type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div class="flex gap-3 pt-2">
          <button @click="saveUserConfig" :disabled="saving"
            class="px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:bg-primary-300 transition-colors">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button @click="exportSettings"
            class="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors">
            导出
          </button>
          <button @click="importSettings"
            class="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors">
            导入
          </button>
        </div>
        <p v-if="saveMsg" :class="['text-sm', saveOk ? 'text-green-500' : 'text-red-500']">{{ saveMsg }}</p>
      </div>
    </section>

    <!-- 环境变量（本机模式只读） -->
    <section v-if="!showUserConfig">
      <h2 class="text-lg font-semibold mb-4">环境变量 (.env)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/.env</p>
      <pre v-if="envContent !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ envContent || '（空）' }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>

    <!-- 系统配置 -->
    <section>
      <h2 class="text-lg font-semibold mb-4">系统配置 (system_config.yaml)</h2>
      <p class="text-sm text-gray-500 mb-3">{{ showUserConfig ? '个人配置：' : '文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml' }}</p>
      <pre v-if="systemConfig !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ systemConfig || '（空）' }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>

    <!-- 业务规则 -->
    <section>
      <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/business_rules.yaml（只读）</p>
      <pre v-if="businessRules !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ businessRules || '（空）' }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>

    <!-- 全局默认（远程模式参考） -->
    <section v-if="globalSystemConfig">
      <h2 class="text-lg font-semibold mb-4">服务端全局默认 (system_config.yaml)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml（只读参考）</p>
      <pre class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ globalSystemConfig || '（空）' }}</pre>
    </section>

    <section v-if="globalEnvContent">
      <h2 class="text-lg font-semibold mb-4">服务端全局默认 (.env)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/.env（只读参考）</p>
      <pre class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ globalEnvContent || '（空）' }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'

const auth = useAuthStore()
const configStore = useConfigStore()

const showUserConfig = computed(() => auth.isRemote)

const envContent = ref<string | null>(null)
const systemConfig = ref<string | null>(null)
const businessRules = ref<string | null>(null)
const globalEnvContent = ref('')
const globalSystemConfig = ref('')

// 个人可编辑字段
const userEnv = ref({ apiKey: '', baseUrl: '', model: '' })
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)

onMounted(async () => {
  if (showUserConfig.value) {
    await loadUserConfig()
  } else {
    await loadLocalConfig()
  }
})

async function loadLocalConfig() {
  try {
    const resp = await fetch('/api/config-read')
    if (resp.ok) {
      const data = await resp.json()
      envContent.value = data.env || ''
      systemConfig.value = data.system_config || ''
      businessRules.value = data.business_rules || ''
    }
  } catch {
    envContent.value = '读取失败'
    systemConfig.value = '读取失败'
    businessRules.value = '读取失败'
  }
}

async function loadUserConfig() {
  try {
    const resp = await fetch('/api/config-read')
    if (resp.ok) {
      const data = await resp.json()
      systemConfig.value = data.system_config || ''
      businessRules.value = data.business_rules || ''
      globalEnvContent.value = data.global_env || ''
      globalSystemConfig.value = data.global_system || ''
      // 解析个人 env
      if (data.env) {
        for (const line of data.env.split('\n')) {
          const m = line.match(/^(\w+)=(.+)/)
          if (m) {
            const k = m[1].trim()
            const v = m[2].trim()
            if (k === 'ANTHROPIC_API_KEY') userEnv.value.apiKey = v
            else if (k === 'ANTHROPIC_BASE_URL') userEnv.value.baseUrl = v
            else if (k === 'ANTHROPIC_MODEL') userEnv.value.model = v
          }
        }
      }
    }
  } catch {
    systemConfig.value = '读取失败'
  }
}

async function saveUserConfig() {
  saving.value = true
  saveMsg.value = ''
  const env: Record<string, string> = {}
  if (userEnv.value.apiKey) env['ANTHROPIC_API_KEY'] = userEnv.value.apiKey
  if (userEnv.value.baseUrl) env['ANTHROPIC_BASE_URL'] = userEnv.value.baseUrl
  if (userEnv.value.model) env['ANTHROPIC_MODEL'] = userEnv.value.model
  try {
    const resp = await fetch('/api/user/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ _env: env, _system: {} }),
    })
    if (resp.ok) {
      saveOk.value = true
      saveMsg.value = '保存成功'
    } else {
      const err = await resp.json()
      saveOk.value = false
      saveMsg.value = err.detail || '保存失败'
    }
  } catch {
    saveOk.value = false
    saveMsg.value = '保存失败'
  }
  saving.value = false
}

function exportSettings() {
  const json = configStore.exportSettings()
  const blob = new Blob([json], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `ard-settings-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function importSettings() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e: any) => {
    const file = e.target?.files?.[0]
    if (!file) return
    const text = await file.text()
    if (configStore.importSettings(text)) {
      saveMsg.value = '导入成功，请点保存'
      saveOk.value = true
    } else {
      saveMsg.value = '导入失败：文件格式不正确'
      saveOk.value = false
    }
  }
  input.click()
}
</script>
