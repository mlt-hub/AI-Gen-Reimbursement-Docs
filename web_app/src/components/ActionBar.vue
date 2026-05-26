<template>
  <div class="bg-white border-t border-gray-200 px-6 py-3 flex items-center gap-3">
    <span class="text-sm text-gray-500 flex-1">
      <template v-if="session.outputDir">交付物目录: {{ session.outputDir }}</template>
    </span>
    <button v-if="session.isRunning" @click="cancelTask"
      class="px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 transition-colors flex items-center gap-2">
      <XCircleIcon class="w-4 h-4" />
      停止
    </button>
    <button v-if="config.workMode === 'local'" @click="openFolder"
      :disabled="!session.sessionId"
      class="px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:bg-primary-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
      <FolderOpenIcon class="w-4 h-4" />
      打开交付物目录
    </button>
    <button v-else @click="downloadZip"
      :disabled="!session.sessionId"
      class="px-4 py-2 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600 disabled:bg-green-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
      <ArrowDownTrayIcon class="w-4 h-4" />
      下载交付物 .zip
    </button>
    <button @click="showAI"
      :disabled="!session.isDone"
      class="px-4 py-2 bg-purple-500 text-white text-sm font-medium rounded-lg hover:bg-purple-600 disabled:bg-purple-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
      <ChatBubbleLeftEllipsisIcon class="w-4 h-4" />
      AI 交互
    </button>
    <button v-if="session.isDone" @click="resetTask"
      class="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors">
      新任务
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { FolderOpenIcon, ArrowDownTrayIcon, ChatBubbleLeftEllipsisIcon, XCircleIcon } from '@heroicons/vue/24/outline'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useLogStore } from '@/stores/log'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits<{ ai: [] }>()

const session = useSessionStore()
const config = useConfigStore()
const log = useLogStore()
const toast = useToastStore()

function openFolder() {
  if (!session.sessionId) return
  fetch('/api/open-folder?session=' + session.sessionId).catch(() => {})
}

function downloadZip() {
  if (!session.sessionId) return
  const a = document.createElement('a')
  a.href = '/api/download/' + session.sessionId
  a.click()
}

function showAI() { emit('ai') }

function cancelTask() {
  if (!session.sessionId) return
  fetch('/api/cancel/' + session.sessionId, { method: 'POST' }).catch(() => {})
  toast.show('info', '正在停止任务，如当前有 AI 调用正在执行，需等待其完成后停止', 6000)
}

function resetTask() {
  session.reset()
  log.clear()
}

// ── 本机模式完成提示音 ──
const lastNotifiedSession = ref('')

watch(() => session.isDone, (done) => {
  if (done && config.workMode === 'local' && session.sessionId && session.sessionId !== lastNotifiedSession.value) {
    lastNotifiedSession.value = session.sessionId
    fetch('/api/play-notify', { method: 'POST' }).catch(() => {})
  }
})
</script>
