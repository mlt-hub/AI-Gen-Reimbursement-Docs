<template>
  <div class="flex h-full">
    <!-- 左侧配置面板 -->
    <aside class="w-[380px] shrink-0 bg-white border-r border-gray-200 p-5 overflow-y-auto">
      <ConfigPanel @start="startTask" />
    </aside>

    <!-- 右侧日志区 -->
    <div class="flex-1 flex flex-col min-w-0">
      <StepsBar v-if="session.isRunning || session.isDone" />
      <LogViewer />
      <ActionBar @ai="openAIModal" @reset="resetTask" />
    </div>

    <!-- AI 交互弹窗 -->
    <Teleport to="body">
      <div v-if="aiModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="closeAIModal">
        <div class="bg-white rounded-xl shadow-2xl w-[90vw] max-w-4xl h-[85vh] flex flex-col">
          <div class="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold">AI 交互记录</h3>
            <button @click="closeAIModal" class="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
          </div>
          <div class="flex border-b border-gray-200 px-5">
            <button v-for="tab in ['list', 'combined']" :key="tab"
              @click="aiTab = tab"
              :class="['py-2 px-4 text-sm border-b-2 transition-colors',
                aiTab === tab ? 'border-primary-500 text-primary-600 font-medium' : 'border-transparent text-gray-500 hover:text-gray-700']">
              {{ tab === 'list' ? '交互列表' : '合并日志' }}
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-5">
            <div v-if="aiLoading" class="flex items-center justify-center h-full text-gray-400">加载中...</div>
            <div v-else-if="aiTab === 'list' && aiInteractions.length === 0" class="flex items-center justify-center h-full text-gray-400">暂无 AI 交互记录</div>
            <template v-else-if="aiTab === 'list'">
              <div v-for="item in aiInteractions" :key="item.name"
                class="border border-gray-200 rounded-lg mb-3 overflow-hidden">
                <div @click="item.expanded = !item.expanded"
                  class="px-4 py-2 bg-gray-50 flex items-center justify-between cursor-pointer hover:bg-gray-100 select-none">
                  <span class="flex items-center gap-2 text-sm">
                    <span :class="['text-xs px-1.5 py-0.5 rounded font-bold', item.type === 'prompt' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700']">
                      {{ item.type === 'prompt' ? 'P' : 'R' }}
                    </span>
                    {{ item.name }}
                  </span>
                  <span class="text-xs text-gray-400">点击展开</span>
                </div>
                <pre v-show="item.expanded" class="p-4 bg-gray-900 text-gray-300 text-xs leading-relaxed overflow-x-auto max-h-96 overflow-y-auto m-0 whitespace-pre-wrap">{{ item.content }}</pre>
              </div>
            </template>
            <pre v-else class="bg-gray-900 text-gray-300 text-xs p-4 rounded-lg leading-relaxed whitespace-pre-wrap overflow-x-auto">{{ aiCombinedLog }}</pre>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useLogStore } from '@/stores/log'
import { useStepsStore } from '@/stores/steps'
import { useToastStore } from '@/stores/toast'
import ConfigPanel from '@/components/ConfigPanel.vue'
import StepsBar from '@/components/StepsBar.vue'
import LogViewer from '@/components/LogViewer.vue'
import ActionBar from '@/components/ActionBar.vue'

const session = useSessionStore()
const config = useConfigStore()
const log = useLogStore()
const toast = useToastStore()

// ── 任务启动 ──
async function startTask() {
  const mode = config.pipelineMode
  const body = new FormData()
  body.append('mode', mode)
  if (config.apiKey) body.append('api_key', config.apiKey)
  if (config.model) body.append('model', config.model)
  if (config.baseUrl) body.append('base_url', config.baseUrl)
  if (config.maxTokens) body.append('max_tokens', config.maxTokens)
  if (config.projectName) body.append('project_name', config.projectName)
  if (config.clean) body.append('clean', '1')

  let url: string
  if (config.workMode === 'local') {
    if (!config.xlsxPath.trim()) {
      toast.show('error', '请输入功能清单 .xlsx 路径')
      return
    }
    url = '/api/run-local'
    body.append('xlsx_path', config.xlsxPath)
    body.append('output_dir', config.outputDir)
  } else {
    if (!config.selectedFile) {
      toast.show('error', '请选择要上传的 .xlsx 文件')
      return
    }
    url = '/api/run-upload'
    body.append('file', config.selectedFile)
  }

  log.clear()
  session.reset()
  useStepsStore().reset()
  session.start('pending...', '')

  try {
    const resp = await fetch(url, { method: 'POST', body })
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || `请求失败 (${resp.status})`)
    }
    const data = await resp.json()
    session.start(data.session_id, data.output_dir || '')
    log.connect()
  } catch (e: any) {
    toast.show('error', e.message)
    session.setError()
  }
}

// ── AI 交互弹窗 ──
const aiModalOpen = ref(false)
const aiTab = ref('list')
const aiLoading = ref(false)
const aiInteractions = ref<any[]>([])
const aiCombinedLog = ref('')

async function openAIModal() {
  if (!session.sessionId) return
  aiModalOpen.value = true
  await loadAIList()
}

function closeAIModal() { aiModalOpen.value = false }

async function loadAIList() {
  if (!session.sessionId) return
  aiLoading.value = true
  try {
    const resp = await fetch('/api/ai-interactions/' + session.sessionId)
    if (!resp.ok) throw new Error((await resp.json()).detail)
    const data = await resp.json()
    aiInteractions.value = (data.interactions || []).map((i: any) => ({ ...i, expanded: false }))
  } catch (e: any) {
    aiInteractions.value = []
  }
  aiLoading.value = false
}

async function loadAICombined() {
  if (!session.sessionId) return
  aiLoading.value = true
  try {
    const resp = await fetch('/api/ai-log/' + session.sessionId)
    if (!resp.ok) throw new Error((await resp.json()).detail)
    const data = await resp.json()
    aiCombinedLog.value = data.content || ''
  } catch (e: any) {
    aiCombinedLog.value = '加载失败: ' + e.message
  }
  aiLoading.value = false
}

// React to tab changes
import { watch } from 'vue'
watch(aiTab, (t) => {
  if (t === 'list') loadAIList()
  else loadAICombined()
})

function resetTask() {
  session.reset()
  log.clear()
}
</script>
