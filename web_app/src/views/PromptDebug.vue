<template>
  <div class="flex h-full">
    <!-- 左侧：通用提示词调试器 -->
    <div class="flex-1 flex flex-col p-5 bg-white min-w-0 overflow-y-auto">
      <h2 class="text-base font-semibold mb-4">通用提示词调试</h2>

      <label class="text-sm font-medium text-gray-500 mb-1">
        系统提示词 <span class="font-normal text-xs text-gray-400 ml-1">{{ systemPrompt.length }} 字</span>
      </label>
      <textarea v-model="systemPrompt"
        placeholder="可选，系统级指令（角色设定、输出格式等）"
        class="flex-1 min-h-[120px] p-3 border border-gray-300 rounded-lg text-sm font-mono leading-relaxed resize-y bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:bg-white transition" />

      <label class="text-sm font-medium text-gray-500 mt-4 mb-1">
        用户提示词 <span class="font-normal text-xs text-gray-400 ml-1">{{ userPrompt.length }} 字</span>
      </label>
      <textarea v-model="userPrompt"
        placeholder="可选，具体的任务描述或问题"
        class="flex-1 min-h-[120px] p-3 border border-gray-300 rounded-lg text-sm font-mono leading-relaxed resize-y bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:bg-white transition"
        @keydown="onKeydown" />

      <div class="flex items-center gap-3 mt-4">
        <button @click="submitPrompt" :disabled="running"
          class="px-6 py-2 bg-primary-500 text-white text-sm font-semibold rounded-lg hover:bg-primary-600 disabled:bg-primary-300 disabled:cursor-not-allowed transition-colors">
          发送给 AI
        </button>
        <button @click="clearAll" class="px-4 py-2 bg-gray-100 text-gray-600 text-sm rounded-lg hover:bg-gray-200 transition-colors">清空</button>
        <span :class="['text-sm font-medium ml-auto',
          runState === 'idle' ? 'text-gray-400' : runState === 'running' ? 'text-primary-500' : runState === 'done' ? 'text-green-500' : 'text-red-500']">
          {{ { idle: '就绪', running: '请求中...', done: '完成', error: '失败' }[runState] }}
        </span>
      </div>

      <details class="mt-4">
        <summary class="text-sm text-primary-600 cursor-pointer select-none font-medium">高级选项</summary>
        <div class="flex gap-3 mt-3 pt-3 border-t border-gray-100">
          <input type="password" v-model="apiKey" placeholder="API Key（留空使用系统配置）" autocomplete="off"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          <input type="text" v-model="model" placeholder="模型（默认 deepseek-v4-flash）"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          <input type="text" v-model="baseUrl" placeholder="API 端点（留空使用默认）"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
      </details>
    </div>

    <!-- 右侧：结果 + 快捷测试 -->
    <div class="w-[45%] min-w-[320px] flex flex-col bg-gray-900 overflow-hidden">
      <!-- 快捷测试工具 -->
      <details class="border-b border-gray-700">
        <summary class="px-4 py-2 text-sm text-gray-400 cursor-pointer select-none hover:text-gray-300">快捷测试工具</summary>
        <div class="px-4 pb-4 space-y-3">
          <!-- 可靠性描述测试 -->
          <div class="bg-gray-800 rounded-lg p-3">
            <h4 class="text-xs text-gray-400 mb-2 font-medium">调整因子 — 可靠性描述 AI 生成</h4>
            <div class="flex gap-2">
              <input v-model="quickXlsx" type="text" placeholder="功能清单 .xlsx 路径（留空自动搜索）"
                class="flex-1 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-primary-500" />
              <button @click="runQuickTest('reliability')" :disabled="quickRunning"
                class="px-3 py-1.5 bg-primary-500 text-white text-xs rounded hover:bg-primary-600 disabled:bg-primary-800 whitespace-nowrap transition-colors">
                {{ quickRunning ? '...' : '执行' }}
              </button>
            </div>
          </div>
          <!-- 元数据测试 -->
          <div class="bg-gray-800 rounded-lg p-3">
            <h4 class="text-xs text-gray-400 mb-2 font-medium">元数据 #AI生成# 字段测试</h4>
            <div class="flex gap-2">
              <input v-model="quickXlsx" type="text" placeholder="功能清单 .xlsx 路径"
                class="flex-1 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-primary-500" />
              <input v-model="quickField" type="text" placeholder="字段 key"
                class="w-32 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-primary-500" />
              <button @click="runQuickTest('metadata')" :disabled="quickRunning"
                class="px-3 py-1.5 bg-purple-500 text-white text-xs rounded hover:bg-purple-600 disabled:bg-purple-800 whitespace-nowrap transition-colors">
                {{ quickRunning ? '...' : '执行' }}
              </button>
            </div>
          </div>
          <!-- 快捷测试结果 -->
          <pre v-if="quickResult" class="text-xs text-gray-300 bg-gray-800 p-3 rounded-lg max-h-48 overflow-y-auto whitespace-pre-wrap">{{ quickResult }}</pre>
        </div>
      </details>

      <!-- 结果区 -->
      <h3 class="px-5 pt-4 text-xs text-gray-500 font-medium">AI 返回结果</h3>
      <div class="flex-1 overflow-y-auto p-5">
        <div v-if="!resultText && !running" class="flex items-center justify-center h-full text-gray-600 text-sm">
          提交提示词后，AI 返回结果将显示在此处
        </div>
        <div v-else-if="running" class="flex items-center justify-center h-full text-gray-500 text-sm">
          等待 AI 响应...
        </div>
        <div v-else class="space-y-3">
          <!-- 折叠块 -->
          <div v-if="resultSysPrompt" class="border border-gray-700 rounded-lg overflow-hidden">
            <div @click="fold.sys = !fold.sys"
              :class="['px-4 py-2 bg-gray-800 text-gray-400 text-sm cursor-pointer select-none hover:bg-gray-700 flex items-center gap-2', fold.sys ? 'collapsed' : '']">
              <span class="text-xs transition-transform" :class="fold.sys ? '-rotate-90' : ''">▼</span>
              系统提示词（{{ resultSysPrompt.length }} 字）
            </div>
            <pre v-show="!fold.sys" class="p-3 text-sm text-gray-300 leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">{{ resultSysPrompt }}</pre>
          </div>
          <div v-if="resultUserPrompt" class="border border-gray-700 rounded-lg overflow-hidden">
            <div @click="fold.user = !fold.user"
              :class="['px-4 py-2 bg-gray-800 text-gray-400 text-sm cursor-pointer select-none hover:bg-gray-700 flex items-center gap-2', fold.user ? 'collapsed' : '']">
              <span class="text-xs transition-transform" :class="fold.user ? '-rotate-90' : ''">▼</span>
              用户提示词（{{ resultUserPrompt.length }} 字）
            </div>
            <pre v-show="!fold.user" class="p-3 text-sm text-gray-300 leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">{{ resultUserPrompt }}</pre>
          </div>
          <div v-if="resultThinking" class="border border-gray-700 rounded-lg overflow-hidden">
            <div @click="fold.thinking = !fold.thinking"
              :class="['px-4 py-2 bg-gray-800 text-gray-400 text-sm cursor-pointer select-none hover:bg-gray-700 flex items-center gap-2']">
              <span class="text-xs">▼</span>
              思考过程（{{ resultThinking.length }} 字）
            </div>
            <pre class="p-3 text-sm text-gray-300 leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">{{ resultThinking }}</pre>
          </div>
          <!-- 最终结果 -->
          <div>
            <h4 class="text-xs text-gray-500 mb-2 font-medium">AI 返回结果（{{ resultText.length }} 字）</h4>
            <div class="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">{{ resultText }}</div>
          </div>
          <p class="text-xs text-gray-600 text-right">结果 {{ resultText.length }} 字</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'

// ── 通用提示词调试 ──
const systemPrompt = ref('')
const userPrompt = ref('')
const apiKey = ref('')
const model = ref('')
const baseUrl = ref('')
const running = ref(false)
const runState = ref<'idle' | 'running' | 'done' | 'error'>('idle')

const resultText = ref('')
const resultSysPrompt = ref('')
const resultUserPrompt = ref('')
const resultThinking = ref('')
const fold = reactive({ sys: true, user: true, thinking: false })

async function submitPrompt() {
  if (!systemPrompt.value.trim() && !userPrompt.value.trim()) {
    alert('请至少输入系统提示词或用户提示词')
    return
  }
  running.value = true
  runState.value = 'running'
  resultText.value = ''; resultSysPrompt.value = ''; resultUserPrompt.value = ''; resultThinking.value = ''

  try {
    const resp = await fetch('/api/test-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system_prompt: systemPrompt.value.trim(),
        user_prompt: userPrompt.value.trim(),
        api_key: apiKey.value.trim(),
        model: model.value.trim(),
        base_url: baseUrl.value.trim(),
      }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '请求失败')

    resultSysPrompt.value = data.system_prompt || ''
    resultUserPrompt.value = data.user_prompt || ''
    resultThinking.value = data.thinking || ''
    resultText.value = data.result || ''
    runState.value = 'done'
  } catch (e: any) {
    resultText.value = '错误: ' + e.message
    runState.value = 'error'
  } finally {
    running.value = false
  }
}

function clearAll() {
  systemPrompt.value = ''
  userPrompt.value = ''
  resultText.value = ''
  resultSysPrompt.value = ''
  resultUserPrompt.value = ''
  resultThinking.value = ''
  runState.value = 'idle'
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    submitPrompt()
  }
}

// ── 快捷测试工具 ──
const quickXlsx = ref('')
const quickField = ref('')
const quickRunning = ref(false)
const quickResult = ref('')

async function runQuickTest(type: 'reliability' | 'metadata') {
  quickRunning.value = true
  quickResult.value = ''
  try {
    const body = new FormData()
    body.append('xlsx_path', quickXlsx.value)
    if (type === 'metadata') body.append('field_key', quickField.value)
    const url = type === 'reliability' ? '/api/test-ai-reliability-desc' : '/api/test-ai-metadata'
    const resp = await fetch(url, { method: 'POST', body })
    const data = await resp.json()
    quickResult.value = data.result || data.detail || '（无结果）'
  } catch (e: any) {
    quickResult.value = '请求失败: ' + e.message
  }
  quickRunning.value = false
}
</script>
