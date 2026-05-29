<template>
  <div class="mx-auto box-border w-full max-w-6xl space-y-4 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 class="text-lg font-semibold">运行历史</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">
            远程任务交付物下载默认保留 {{ retentionDays }} 天；过期后运行记录仍保留。本机与 CLI 任务交付物保存在本机输出目录，系统不会自动删除。
          </p>
        </div>
        <button class="btn-secondary w-fit" :disabled="loading" @click="loadHistory">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div class="mt-4 flex flex-wrap gap-3">
        <select v-model="filters.source" class="field-control w-auto min-w-32" @change="loadHistory">
          <option value="all">全部来源</option>
          <option value="web">Web</option>
          <option value="cli">CLI</option>
        </select>
        <select v-model="filters.mode" class="field-control w-auto min-w-32" @change="loadHistory">
          <option value="all">全部模式</option>
          <option value="local">本机</option>
          <option value="remote">远程</option>
        </select>
        <select v-model="filters.state" class="field-control w-auto min-w-32" @change="loadHistory">
          <option value="all">全部状态</option>
          <option value="running">运行中</option>
          <option value="done">完成</option>
          <option value="error">失败</option>
          <option value="cancelled">已取消</option>
        </select>
      </div>

      <p v-if="error" class="mt-3 text-sm text-[var(--color-danger)]">{{ error }}</p>
    </section>

    <section class="surface rounded-lg p-0">
      <div v-if="!loading && items.length === 0" class="p-8 text-center text-sm text-[var(--color-ink-muted)]">
        暂无运行历史
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[920px] border-collapse text-left text-sm">
          <thead class="border-b border-[var(--color-rule)] text-xs uppercase text-[var(--color-ink-soft)]">
            <tr>
              <th class="px-4 py-3 font-semibold">时间</th>
              <th class="px-4 py-3 font-semibold">来源</th>
              <th class="px-4 py-3 font-semibold">任务</th>
              <th class="px-4 py-3 font-semibold">状态</th>
              <th class="px-4 py-3 font-semibold">输入</th>
              <th class="px-4 py-3 font-semibold">交付物</th>
              <th class="px-4 py-3 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.run_id" class="border-b border-[var(--color-rule)] last:border-b-0">
              <td class="px-4 py-3 align-top text-xs text-[var(--color-ink-muted)]">{{ formatTime(item.created_at) }}</td>
              <td class="px-4 py-3 align-top">
                <div class="font-semibold">{{ sourceLabel(item) }}</div>
                <div class="text-xs text-[var(--color-ink-soft)]">{{ item.mode === 'remote' ? item.owner_label || '-' : '本机用户' }}</div>
              </td>
              <td class="px-4 py-3 align-top">
                <div class="font-semibold">{{ item.task_mode || '-' }}</div>
                <div class="text-xs font-mono text-[var(--color-ink-soft)]">{{ item.run_id }}</div>
              </td>
              <td class="px-4 py-3 align-top">
                <span :class="['rounded-md px-2 py-0.5 text-xs font-semibold', stateClass(item.run_state)]">{{ stateLabel(item.run_state) }}</span>
              </td>
              <td class="max-w-[15rem] px-4 py-3 align-top">
                <div class="truncate" :title="item.input_name">{{ item.input_name || '-' }}</div>
              </td>
              <td class="px-4 py-3 align-top">
                <div>{{ artifactLabel(item) }}</div>
                <div class="text-xs text-[var(--color-ink-soft)]">{{ item.done_files.length }} 个文件</div>
              </td>
              <td class="px-4 py-3 align-top">
                <div class="flex flex-wrap gap-2">
                  <button v-if="item.download_available" class="btn-secondary min-h-0 px-3 py-1.5 text-xs" @click="download(item)">
                    下载 .zip
                  </button>
                  <button v-else-if="item.open_folder_available" class="btn-secondary min-h-0 px-3 py-1.5 text-xs" @click="openFolder(item)">
                    打开目录
                  </button>
                  <span v-else class="rounded-md bg-[var(--color-surface-muted)] px-2 py-1 text-xs text-[var(--color-ink-muted)]">
                    {{ unavailableLabel(item) }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface DoneFile {
  name?: string
  label?: string
  path?: string
  relative_path?: string
  size_kb?: number
  is_temp?: boolean
}

interface HistoryItem {
  run_id: string
  session_id: string
  source: 'cli' | 'web'
  mode: 'local' | 'remote'
  owner_label: string
  task_mode: string
  run_state: string
  input_name: string
  output_dir: string
  artifact_kind: 'local_dir' | 'remote_zip'
  download_available: boolean
  open_folder_available: boolean
  created_at: string
  done_files: DoneFile[]
}

interface HistoryResponse {
  retention: {
    remote_download_retention_days: number
    local_retention_label: string
  }
  items: HistoryItem[]
}

const loading = ref(false)
const error = ref('')
const items = ref<HistoryItem[]>([])
const retentionDays = ref(1)
const filters = reactive({ source: 'all', mode: 'all', state: 'all' })

const query = computed(() => new URLSearchParams({
  source: filters.source,
  mode: filters.mode,
  state: filters.state,
  limit: '50',
}).toString())

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch<HistoryResponse>(`/api/history?${query.value}`)
    items.value = data.items
    retentionDays.value = data.retention.remote_download_retention_days
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    loading.value = false
  }
}

function sourceLabel(item: HistoryItem) {
  if (item.source === 'cli') return 'CLI'
  return item.mode === 'remote' ? 'Web 远程' : 'Web 本机'
}

function stateLabel(state: string) {
  const map: Record<string, string> = {
    running: '运行中',
    done: '完成',
    error: '失败',
    cancelled: '已取消',
  }
  return map[state] || state
}

function stateClass(state: string) {
  if (state === 'done') return 'bg-[var(--color-success-soft)] text-[var(--color-success)]'
  if (state === 'running') return 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
  return 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]'
}

function artifactLabel(item: HistoryItem) {
  if (item.artifact_kind === 'remote_zip') return item.download_available ? '下载可用' : '下载已过期'
  return item.open_folder_available ? '目录可用' : '目录不存在'
}

function unavailableLabel(item: HistoryItem) {
  return item.artifact_kind === 'remote_zip' ? '已过期' : '目录不存在'
}

function formatTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function download(item: HistoryItem) {
  window.location.href = `/api/history/${item.run_id}/download`
}

async function openFolder(item: HistoryItem) {
  try {
    await apiFetch(`/api/history/${item.run_id}/open-folder`, { method: 'POST' })
  } catch (err) {
    error.value = normalizeApiError(err)
  }
}

onMounted(loadHistory)
</script>
