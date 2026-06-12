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
          <option value="queued">排队中</option>
          <option value="running">运行中</option>
          <option value="done">完成</option>
          <option value="error">失败</option>
          <option value="cancelled">已取消</option>
          <option value="closed">关闭</option>
        </select>
      </div>

      <p v-if="notice" class="mt-3 text-sm text-[var(--color-success)]">{{ notice }}</p>
      <p v-if="error" class="mt-3 text-sm text-[var(--color-danger)]">{{ error }}</p>
    </section>

    <section class="surface rounded-lg p-0">
      <div v-if="!loading && items.length === 0" class="empty-state m-4">
        <div class="text-sm font-semibold text-[var(--color-ink)]">暂无运行历史</div>
        <p class="mt-1 text-xs">生成任务完成后，会在这里显示交付物、状态和后续操作。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[1040px] border-collapse text-left text-sm">
          <thead class="border-b border-[var(--color-rule)] text-xs uppercase text-[var(--color-ink-soft)]">
            <tr>
              <th class="px-4 py-3 font-semibold">时间</th>
              <th class="px-4 py-3 font-semibold">来源</th>
              <th class="px-4 py-3 font-semibold">任务</th>
              <th class="px-4 py-3 font-semibold">项目名</th>
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
              <td class="w-56 px-4 py-3 align-top">
                <div class="max-w-56 whitespace-normal break-words leading-5" :title="projectName(item)">{{ projectName(item) }}</div>
              </td>
              <td class="px-4 py-3 align-top">
                <span :class="['status-badge', stateClass(item.run_state)]">{{ stateLabel(item.run_state) }}</span>
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
                  <RouterLink
                    v-if="item.source === 'web' && item.session_id"
                    :to="`/tasks/${item.session_id}`"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  >
                    详情
                  </RouterLink>
                  <RouterLink
                    v-if="canOpenFpaDebug(item)"
                    :to="`/sessions/${item.session_id}/fpa/debug`"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  >
                    AI 调试
                  </RouterLink>
                  <RouterLink
                    v-if="canOpenCosmicPreview(item)"
                    :to="`/sessions/${item.session_id}/cosmic/preview`"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  >
                    COSMIC 预览
                  </RouterLink>
                  <button
                    v-if="canRerun(item)"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="rerun(item)"
                  >
                    重跑
                  </button>
                  <span
                    v-if="!item.download_available && !item.open_folder_available && !canOpenFpaDebug(item) && !canOpenCosmicPreview(item) && !canRerun(item)"
                    class="status-badge status-badge--neutral"
                  >
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
import { RouterLink, useRouter } from 'vue-router'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface DoneFile {
  name?: string
  label?: string
  path?: string
  relative_path?: string
  size_kb?: number
  is_temp?: boolean
}

interface RunConfig {
  project_name?: string
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
  run_config?: RunConfig
}

interface HistoryResponse {
  retention: {
    remote_download_retention_days: number
    local_retention_label: string
  }
  items: HistoryItem[]
}

const loading = ref(false)
const actionId = ref('')
const error = ref('')
const notice = ref('')
const items = ref<HistoryItem[]>([])
const retentionDays = ref(1)
const filters = reactive({ source: 'all', mode: 'all', state: 'all' })
const router = useRouter()

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
    notice.value = ''
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

function projectName(item: HistoryItem) {
  const name = item.run_config?.project_name?.trim()
  return name || '-'
}

function stateLabel(state: string) {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    done: '完成',
    error: '失败',
    cancelled: '已取消',
    closed: '关闭',
  }
  return map[state] || state
}

function stateClass(state: string) {
  if (state === 'done') return 'status-badge--success'
  if (state === 'queued') return 'status-badge--warning'
  if (state === 'running') return 'status-badge--info'
  if (state === 'error') return 'status-badge--danger'
  if (state === 'cancelled') return 'status-badge--neutral'
  if (state === 'closed') return 'status-badge--neutral'
  return 'status-badge--warning'
}

function artifactLabel(item: HistoryItem) {
  if (item.run_state === 'queued') return '等待运行'
  if (item.run_state === 'running') return '生成中'
  if (item.artifact_kind === 'remote_zip') return item.download_available ? '下载可用' : '下载已过期'
  return item.open_folder_available ? '目录可用' : '目录不存在'
}

function unavailableLabel(item: HistoryItem) {
  if (item.run_state === 'queued') return '等待运行'
  if (item.run_state === 'running') return '生成中'
  return item.artifact_kind === 'remote_zip' ? '已过期' : '目录不存在'
}

function canOpenFpaDebug(item: HistoryItem) {
  return item.source === 'web' && item.session_id && item.task_mode === 'from-excel-gen-fpa'
}

function canOpenCosmicPreview(item: HistoryItem) {
  return Boolean(
    item.source === 'web'
    && item.session_id
    && ['from-excel-gen-all', 'from-excel-gen-cosmic'].includes(item.task_mode),
  )
}

function canRerun(item: HistoryItem) {
  return item.source === 'web' && ['done', 'error', 'cancelled'].includes(item.run_state)
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

async function rerun(item: HistoryItem) {
  actionId.value = item.run_id
  error.value = ''
  notice.value = ''
  try {
    const data = await apiFetch<{ session_id: string }>(`/api/tasks/${item.run_id}/rerun`, { method: 'POST' })
    notice.value = `已创建重跑任务 ${data.session_id}`
    await router.push(`/tasks/${data.session_id}`)
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionId.value = ''
  }
}

onMounted(loadHistory)
</script>
