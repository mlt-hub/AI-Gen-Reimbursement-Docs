<template>
  <div class="mx-auto box-border w-full max-w-6xl space-y-4 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 class="text-lg font-semibold">任务</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">
            查看仍在关注中的 Web 任务；关闭后任务会从这里移除，并保留在运行历史中。
          </p>
        </div>
        <button class="btn-secondary w-fit" :disabled="loading" @click="loadTasks">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div class="mt-4 flex flex-wrap gap-3">
        <select v-model="filters.mode" class="field-control w-auto min-w-32" @change="loadTasks">
          <option value="all">全部模式</option>
          <option value="local">本机</option>
          <option value="remote">远程</option>
        </select>
        <select v-model="filters.state" class="field-control w-auto min-w-32" @change="loadTasks">
          <option value="all">全部状态</option>
          <option value="queued">排队中</option>
          <option value="running">运行中</option>
          <option value="done">完成</option>
          <option value="error">失败</option>
          <option value="cancelled">已取消</option>
        </select>
      </div>

      <p v-if="notice" class="mt-3 text-sm text-[var(--color-success)]">{{ notice }}</p>
      <p v-if="error" class="mt-3 text-sm text-[var(--color-danger)]">{{ error }}</p>
    </section>

    <section class="surface rounded-lg p-0">
      <div v-if="!loading && items.length === 0" class="empty-state m-4">
        <div class="text-sm font-semibold text-[var(--color-ink)]">暂无任务</div>
        <p class="mt-1 text-xs">运行中、完成、失败和已取消的 Web 任务会显示在这里。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[1120px] border-collapse text-left text-sm">
          <thead class="border-b border-[var(--color-rule)] text-xs uppercase text-[var(--color-ink-soft)]">
            <tr>
              <th class="px-4 py-3 font-semibold">状态</th>
              <th class="px-4 py-3 font-semibold">任务模式</th>
              <th class="px-4 py-3 font-semibold">项目名</th>
              <th class="px-4 py-3 font-semibold">来源</th>
              <th class="px-4 py-3 font-semibold">输入文件</th>
              <th class="px-4 py-3 font-semibold">开始时间</th>
              <th class="px-4 py-3 font-semibold">更新时间</th>
              <th class="px-4 py-3 font-semibold">交付物</th>
              <th class="px-4 py-3 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.run_id" class="border-b border-[var(--color-rule)] last:border-b-0">
              <td class="px-4 py-3 align-top">
                <span :class="['status-badge', stateClass(item.run_state)]">{{ stateLabel(item.run_state) }}</span>
                <div v-if="item.run_state === 'queued'" class="mt-1 text-xs text-[var(--color-ink-soft)]">
                  {{ queuePositionText(item) }}
                </div>
              </td>
              <td class="px-4 py-3 align-top">
                <div class="font-semibold">{{ item.task_mode || '-' }}</div>
                <div class="text-xs font-mono text-[var(--color-ink-soft)]">{{ item.run_id }}</div>
              </td>
              <td class="w-56 px-4 py-3 align-top">
                <div class="max-w-56 whitespace-normal break-words leading-5" :title="projectName(item)">{{ projectName(item) }}</div>
              </td>
              <td class="px-4 py-3 align-top">
                <div class="font-semibold">{{ sourceLabel(item) }}</div>
                <div class="text-xs text-[var(--color-ink-soft)]">{{ item.mode === 'remote' ? item.owner_label || '-' : '本机用户' }}</div>
              </td>
              <td class="max-w-[14rem] px-4 py-3 align-top">
                <div class="truncate" :title="item.input_name">{{ item.input_name || '-' }}</div>
              </td>
              <td class="px-4 py-3 align-top text-xs text-[var(--color-ink-muted)]">{{ formatTime(item.started_at || item.created_at) }}</td>
              <td class="px-4 py-3 align-top text-xs text-[var(--color-ink-muted)]">{{ formatTime(item.updated_at) }}</td>
              <td class="px-4 py-3 align-top">
                <div>{{ artifactLabel(item) }}</div>
                <div class="text-xs text-[var(--color-ink-soft)]">{{ item.done_files.length }} 个文件</div>
              </td>
              <td class="px-4 py-3 align-top">
                <div class="flex flex-wrap gap-2">
                  <button
                    v-if="canContinue(item)"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="continueTask(item)"
                  >
                    继续
                  </button>
                  <RouterLink
                    v-if="item.session_id"
                    :to="`/tasks/${item.session_id}`"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  >
                    详情
                  </RouterLink>
                  <span
                    v-else-if="isUnrecoverableRunning(item)"
                    class="status-badge status-badge--neutral"
                  >
                    会话不可恢复
                  </span>
                  <button
                    v-if="isUnrecoverableRunning(item)"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="markUnrecoverable(item)"
                  >
                    标记已取消
                  </button>
                  <button
                    v-if="item.run_state === 'queued'"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="cancelQueued(item)"
                  >
                    取消排队
                  </button>
                  <button
                    v-if="canRerun(item)"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="rerun(item)"
                  >
                    重跑
                  </button>
                  <RouterLink
                    v-if="canOpenCosmicPreview(item)"
                    :to="`/sessions/${item.session_id}/cosmic/preview`"
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  >
                    COSMIC 预览
                  </RouterLink>
                  <button
                    class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                    :disabled="actionId === item.run_id"
                    @click="closeTask(item)"
                  >
                    关闭
                  </button>
                  <RouterLink to="/history" class="btn-secondary min-h-0 px-3 py-1.5 text-xs">
                    历史
                  </RouterLink>
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
import { ApiError, apiFetch, normalizeApiError } from '@/lib/api.ts'

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

interface TaskItem {
  run_id: string
  session_id: string
  source: 'web'
  mode: 'local' | 'remote'
  owner_label: string
  task_mode: string
  run_state: string
  input_name: string
  artifact_kind: 'local_dir' | 'remote_zip'
  download_available: boolean
  open_folder_available: boolean
  created_at: string
  started_at: string
  updated_at: string
  done_files: DoneFile[]
  run_config?: RunConfig
  session_available?: boolean
  queue_position?: number | null
}

interface TasksResponse {
  items: TaskItem[]
}

const loading = ref(false)
const actionId = ref('')
const error = ref('')
const notice = ref('')
const items = ref<TaskItem[]>([])
const filters = reactive({ mode: 'all', state: 'all' })
const router = useRouter()
const UNRECOVERABLE_SESSION_MESSAGE = '会话已结束或服务已重启，无法继续当前执行'

const query = computed(() => new URLSearchParams({
  mode: filters.mode,
  state: filters.state,
  limit: '50',
}).toString())

async function loadTasks() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch<TasksResponse>(`/api/tasks?${query.value}`)
    items.value = data.items
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    loading.value = false
  }
}

function sourceLabel(item: TaskItem) {
  return item.mode === 'remote' ? 'Web 远程' : 'Web 本机'
}

function projectName(item: TaskItem) {
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
  }
  return map[state] || state
}

function stateClass(state: string) {
  if (state === 'done') return 'status-badge--success'
  if (state === 'queued') return 'status-badge--warning'
  if (state === 'running') return 'status-badge--info'
  if (state === 'error') return 'status-badge--danger'
  if (state === 'cancelled') return 'status-badge--neutral'
  return 'status-badge--warning'
}

function artifactLabel(item: TaskItem) {
  if (item.run_state === 'queued') return '等待运行'
  if (item.run_state === 'running') return '生成中'
  if (item.artifact_kind === 'remote_zip') return item.download_available ? '下载可用' : '下载已过期'
  return item.open_folder_available ? '目录可用' : '目录不存在'
}

function canRerun(item: TaskItem) {
  return ['done', 'error', 'cancelled'].includes(item.run_state)
}

function canOpenCosmicPreview(item: TaskItem) {
  return Boolean(
    item.session_id
    && item.session_available
    && ['from-excel-gen-all', 'from-excel-gen-cosmic'].includes(item.task_mode),
  )
}

function canContinue(item: TaskItem) {
  return item.run_state === 'running' && item.session_available
}

function queuePositionText(item: TaskItem) {
  return item.queue_position ? `队列位置 ${item.queue_position}` : '已进入等待队列'
}

function isUnrecoverableRunning(item: TaskItem) {
  return item.run_state === 'running' && !item.session_available
}

function formatTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

async function continueTask(item: TaskItem) {
  actionId.value = item.run_id
  error.value = ''
  notice.value = ''
  try {
    await apiFetch(`/api/sessions/${item.session_id || item.run_id}`)
    await router.push({ path: '/', query: { session: item.session_id || item.run_id } })
  } catch (err) {
    await loadTasks()
    error.value = err instanceof ApiError && err.status === 404
      ? UNRECOVERABLE_SESSION_MESSAGE
      : normalizeApiError(err)
  } finally {
    actionId.value = ''
  }
}

async function rerun(item: TaskItem) {
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

async function markUnrecoverable(item: TaskItem) {
  if (!window.confirm('确认将该任务标记为已取消？')) return
  actionId.value = item.run_id
  error.value = ''
  notice.value = ''
  try {
    await apiFetch(`/api/tasks/${item.run_id}/mark-unrecoverable`, { method: 'POST' })
    notice.value = '任务已标记为已取消，可以重新执行'
    await loadTasks()
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionId.value = ''
  }
}

async function cancelQueued(item: TaskItem) {
  if (!window.confirm('确认取消该排队任务？')) return
  actionId.value = item.run_id
  error.value = ''
  notice.value = ''
  try {
    await apiFetch(`/api/cancel/${item.session_id || item.run_id}`, { method: 'POST' })
    notice.value = '排队任务已取消'
    await loadTasks()
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionId.value = ''
  }
}

async function closeTask(item: TaskItem) {
  if (!window.confirm('确认关闭该任务？')) return
  actionId.value = item.run_id
  error.value = ''
  notice.value = ''
  try {
    await apiFetch(`/api/tasks/${item.run_id}/close`, { method: 'POST' })
    notice.value = '任务已关闭'
    await loadTasks()
  } catch (err) {
    error.value = normalizeApiError(err)
  } finally {
    actionId.value = ''
  }
}

onMounted(loadTasks)
</script>
