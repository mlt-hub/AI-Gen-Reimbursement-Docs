<template>
  <div class="border-t border-[var(--color-rule)] bg-[var(--color-surface-raised)]">
    <!-- 文件摘要（任务完成后显示） -->
    <div v-if="session.isDone && session.doneFiles.length" class="border-b border-[var(--color-rule)] px-5 py-3">
      <div class="mb-2 text-xs font-semibold text-[var(--color-ink-muted)]">交付物清单</div>
      <div class="flex flex-wrap gap-2">
        <span v-for="f in session.doneFiles" :key="f.path"
          :class="['inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold',
            f.is_temp ? 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]' : 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]']"
          :title="f.is_temp ? '文件被占用，已保存到临时文件 — 关闭占用程序后重命名替换原文件即可' : f.path">
          <span v-if="f.is_temp">&#9888;</span>
          <span v-else>&#10003;</span>
          {{ f.label }}
          <span class="opacity-60">{{ f.size_kb }} KB</span>
        </span>
      </div>
      <div v-if="session.doneFiles.some(f => f.is_temp)" class="mt-2 text-xs text-[var(--color-warning)]">
        &#9888; 有文件保存到了 <code class="rounded bg-[var(--color-warning-soft)] px-1">_TEMP</code> 临时文件，关闭 Excel/WPS 后重命名替换原文件即可
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="flex flex-col gap-3 px-5 py-3 md:flex-row md:items-center">
    <span class="min-w-0 flex-1 truncate text-sm text-[var(--color-ink-muted)]">
      <template v-if="session.outputDir">交付物目录: {{ session.outputDir }}</template>
    </span>
    <button v-if="session.isRunning" @click="cancelTask"
      class="btn-danger">
      <XCircleIcon class="w-4 h-4" />
      停止
    </button>
    <button v-if="config.workMode === 'local'" @click="openFolder"
      :disabled="!session.sessionId"
      class="btn-secondary">
      <FolderOpenIcon class="w-4 h-4" />
      打开交付物目录
    </button>
    <button v-else @click="downloadZip"
      :disabled="!session.sessionId"
      class="btn-secondary">
      <ArrowDownTrayIcon class="w-4 h-4" />
      下载交付物 .zip
    </button>
    <button @click="showAI"
      :disabled="!session.isDone"
      class="btn-secondary">
      <ChatBubbleLeftEllipsisIcon class="w-4 h-4" />
      AI 交互
    </button>
    <button v-if="session.isDone" @click="resetTask"
      class="btn-quiet">
      新任务
    </button>
    </div>
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

// ── 完成提示音 ──
const lastNotifiedSession = ref('')
const _audio = new Audio('/static/audio/ticktick_pop.wav')

watch(() => session.isDone, (done) => {
  if (!done || !session.sessionId || session.sessionId === lastNotifiedSession.value) return
  lastNotifiedSession.value = session.sessionId
  if (config.workMode === 'local') {
    fetch('/api/play-notify', { method: 'POST' }).catch(() => {})
  } else {
    _audio.play().catch(() => {})
  }
})
</script>
