<template>
  <div class="max-w-3xl mx-auto p-6 space-y-8">
    <!-- 个人配置（可编辑，远程模式） -->
    <template v-if="showUserConfig">
      <section>
        <h2 class="text-lg font-semibold mb-1">个人配置</h2>
        <p class="text-xs text-gray-400 mb-4">~/.ai-gen-reimbursement-docs/users/{{ auth.username }}/</p>

        <!-- .env -->
        <div class="bg-white border border-gray-200 rounded-lg p-5 mb-4 space-y-3">
          <h3 class="text-sm font-medium text-gray-500">.env</h3>
          <div>
            <label class="block text-xs text-gray-500 mb-1">ANTHROPIC_API_KEY</label>
            <input v-model="envFields.apiKey" type="password"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">ANTHROPIC_BASE_URL</label>
            <input v-model="envFields.baseUrl" type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">ANTHROPIC_MODEL</label>
            <input v-model="envFields.model" type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
        </div>

        <!-- system_config.yaml -->
        <div class="bg-white border border-gray-200 rounded-lg p-5 mb-4 space-y-4">
          <h3 class="text-sm font-medium text-gray-500">system_config.yaml</h3>

          <!-- 布尔字段：4 列 grid -->
          <div class="grid grid-cols-4 gap-x-4 gap-y-2">
            <label v-for="f in boolFields" :key="f.key"
              class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" v-model="f.value" class="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
              {{ f.key }}
            </label>
          </div>

          <hr class="border-gray-100" />

          <!-- 枚举/数字/文本：2 列 grid -->
          <div class="grid grid-cols-2 gap-4">
            <div v-for="f in scalarFields" :key="f.key">
              <label class="block text-xs text-gray-500 mb-1">{{ f.key }}</label>
              <select v-if="f.type === 'select'" v-model="f.value"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white">
                <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <input v-else-if="f.type === 'number'" v-model.number="f.value" type="number"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
              <input v-else v-model="f.value" type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>
          </div>

          <!-- 嵌套对象：textarea -->
          <template v-if="nestedFields.length">
            <hr class="border-gray-100" />
            <div v-for="f in nestedFields" :key="f.key">
              <label class="block text-xs text-gray-500 mb-1">{{ f.key }}</label>
              <textarea v-model="f.yamlText" rows="6"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"></textarea>
            </div>
          </template>
        </div>

        <div class="flex gap-3">
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
        <p v-if="saveMsg" :class="['text-sm mt-2', saveOk ? 'text-green-500' : 'text-red-500']">{{ saveMsg }}</p>
      </section>

      <!-- 服务端全局默认（只读参考） -->
      <section v-if="globalSystemConfig">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (system_config.yaml)</h2>
        <p class="text-sm text-gray-500 mb-3">只读参考，文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ globalSystemConfig || '（空）' }}</pre>
      </section>
      <section v-if="globalEnvContent">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (.env)</h2>
        <p class="text-sm text-gray-500 mb-3">只读参考，敏感值已遮罩</p>
        <pre class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ globalEnvContent || '（空）' }}</pre>
      </section>
      <section v-if="businessRules !== null">
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="text-sm text-gray-500 mb-3">只读</p>
        <pre class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ businessRules || '（空）' }}</pre>
      </section>
    </template>

    <!-- 本机模式：只读 -->
    <template v-else>
      <section>
        <h2 class="text-lg font-semibold mb-4">环境变量 (.env)</h2>
        <p class="text-sm text-gray-500 mb-3">~/.ai-gen-reimbursement-docs/.env</p>
        <pre v-if="envContent !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ envContent || '（空）' }}</pre>
        <p v-else class="text-gray-400 text-sm">加载中…</p>
      </section>
      <section>
        <h2 class="text-lg font-semibold mb-4">系统配置 (system_config.yaml)</h2>
        <p class="text-sm text-gray-500 mb-3">~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre v-if="systemConfig !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ systemConfig || '（空）' }}</pre>
        <p v-else class="text-gray-400 text-sm">加载中…</p>
      </section>
      <section>
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="text-sm text-gray-500 mb-3">~/.ai-gen-reimbursement-docs/business_rules.yaml</p>
        <pre v-if="businessRules !== null" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ businessRules || '（空）' }}</pre>
        <p v-else class="text-gray-400 text-sm">加载中…</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'

// ── 类型 ──────────────────────────────────────────────────

type FieldType = 'bool' | 'number' | 'select' | 'text'

interface ScalarField {
  key: string
  type: FieldType
  value: any
  options?: string[]
}

interface NestedField {
  key: string
  yamlText: string
}

// ── stores ────────────────────────────────────────────────

const auth = useAuthStore()
const configStore = useConfigStore()

const showUserConfig = computed(() => auth.isRemote)

// ── 只读内容 ──────────────────────────────────────────────

const envContent = ref<string | null>(null)
const systemConfig = ref<string | null>(null)
const businessRules = ref<string | null>(null)
const globalEnvContent = ref('')
const globalSystemConfig = ref('')

// ── 可编辑字段 ────────────────────────────────────────────

const envFields = reactive({ apiKey: '', baseUrl: '', model: '' })
const boolFields = ref<ScalarField[]>([])
const scalarFields = ref<ScalarField[]>([])
const nestedFields = ref<NestedField[]>([])
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)

// ── 初始化 ────────────────────────────────────────────────

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
  // 加载原始文本（用于 nested textarea 和 全局参考）
  const [readResp, cfgResp] = await Promise.all([
    fetch('/api/config-read'),
    fetch('/api/user/config'),
  ])

  if (readResp.ok) {
    const d = await readResp.json()
    globalEnvContent.value = d.global_env || ''
    globalSystemConfig.value = d.global_system || ''
    businessRules.value = d.business_rules || ''
    // 解析个人 env
    if (d.env) {
      for (const line of d.env.split('\n')) {
        const m = line.match(/^(\w+)=(.+)/)
        if (m) {
          const k = m[1].trim()
          const v = m[2].trim()
          if (k === 'ANTHROPIC_API_KEY') envFields.apiKey = v
          else if (k === 'ANTHROPIC_BASE_URL') envFields.baseUrl = v
          else if (k === 'ANTHROPIC_MODEL') envFields.model = v
        }
      }
    }
  }

  if (cfgResp.ok) {
    const data = await cfgResp.json()
    const sys = data._system || {}
    buildFormFields(sys)
  }
}

// ── 从 YAML dict 构建表单字段 ──────────────────────────────

const SELECT_OPTIONS: Record<string, string[]> = {
  web_work_mode: ['auto', 'local', 'remote'],
  log_level: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
}

const NESTED_KEYS = new Set(['sheets', 'out_templates'])

function buildFormFields(sys: Record<string, any>) {
  const bools: ScalarField[] = []
  const scalars: ScalarField[] = []
  const nesteds: NestedField[] = []

  for (const [key, val] of Object.entries(sys)) {
    if (typeof val === 'boolean') {
      bools.push({ key, type: 'bool', value: val })
    } else if (NESTED_KEYS.has(key) || typeof val === 'object') {
      nesteds.push({ key, yamlText: toYamlLike(val) })
    } else if (SELECT_OPTIONS[key]) {
      scalars.push({ key, type: 'select', value: String(val), options: SELECT_OPTIONS[key] })
    } else if (typeof val === 'number') {
      scalars.push({ key, type: 'number', value: val })
    } else {
      scalars.push({ key, type: 'text', value: String(val) })
    }
  }

  boolFields.value = bools
  scalarFields.value = scalars
  nestedFields.value = nesteds
}

/** 把对象转成接近 YAML 风格的纯文本（缩进 2 空格）。 */
function toYamlLike(obj: any, indent = 0): string {
  if (obj === null || obj === undefined) return ''
  if (typeof obj !== 'object') return String(obj)
  const pad = '  '.repeat(indent)
  const lines: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'object' && v !== null) {
      lines.push(`${pad}${k}:`)
      lines.push(toYamlLike(v, indent + 1))
    } else {
      lines.push(`${pad}${k}: ${v}`)
    }
  }
  return lines.join('\n')
}

/** 把 textarea 的 YAML 风格文本解析回对象。 */
function fromYamlLike(text: string): any {
  // 简单解析 — 仅支持嵌套 dict，值均为字符串
  const result: Record<string, any> = {}
  const stack: { indent: number; obj: Record<string, any> }[] = [{ indent: -1, obj: result }]

  for (const line of text.split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue
    const indent = line.search(/\S/)
    const content = line.trim()
    const colonIdx = content.indexOf(':')

    // 回退栈
    while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
      stack.pop()
    }

    if (colonIdx > 0) {
      const key = content.substring(0, colonIdx).trim()
      const val = content.substring(colonIdx + 1).trim()
      if (val) {
        stack[stack.length - 1].obj[key] = val
      } else {
        // 嵌套对象开始
        const child: Record<string, any> = {}
        stack[stack.length - 1].obj[key] = child
        stack.push({ indent, obj: child })
      }
    }
  }
  return result
}

// ── 保存 ──────────────────────────────────────────────────

async function saveUserConfig() {
  saving.value = true
  saveMsg.value = ''

  // 构建 _env
  const env: Record<string, string> = {}
  if (envFields.apiKey) env['ANTHROPIC_API_KEY'] = envFields.apiKey
  if (envFields.baseUrl) env['ANTHROPIC_BASE_URL'] = envFields.baseUrl
  if (envFields.model) env['ANTHROPIC_MODEL'] = envFields.model

  // 构建 _system
  const system: Record<string, any> = {}

  for (const f of boolFields.value) {
    system[f.key] = f.value
  }
  for (const f of scalarFields.value) {
    if (f.type === 'number') {
      system[f.key] = Number(f.value)
    } else {
      system[f.key] = f.value
    }
  }
  for (const f of nestedFields.value) {
    try {
      system[f.key] = fromYamlLike(f.yamlText)
    } catch {
      saveOk.value = false
      saveMsg.value = `${f.key} 格式错误，请检查`
      saving.value = false
      return
    }
  }

  try {
    const resp = await fetch('/api/user/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ _env: env, _system: system }),
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
    saveMsg.value = '网络错误'
  }
  saving.value = false
}

// ── 导出/导入 ─────────────────────────────────────────────

function exportSettings() {
  const json = configStore.exportSettings()
  const blob = new Blob([json], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `ard-settings-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function importSettings() {
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
