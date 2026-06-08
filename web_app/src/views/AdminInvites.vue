<template>
  <div class="mx-auto box-border w-full max-w-5xl space-y-6 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold">邀请注册</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">生成和停用远程注册邀请码。</p>
        </div>
        <button class="btn-secondary w-fit" :disabled="loading" @click="loadInvites()">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <form class="grid gap-3 sm:grid-cols-[minmax(0,10rem)_minmax(0,10rem)_auto]" @submit.prevent="createInvite">
        <div>
          <label for="invite-days" class="field-label">有效期（天）</label>
          <input id="invite-days" v-model.number="form.expires_in_days" class="field-control" type="number" min="1" />
        </div>
        <div>
          <label for="invite-uses" class="field-label">最大使用次数</label>
          <input id="invite-uses" v-model.number="form.max_uses" class="field-control" type="number" min="1" />
        </div>
        <div class="flex items-end">
          <button class="btn-primary w-full sm:w-auto" type="submit" :disabled="creating">
            {{ creating ? '生成中...' : '生成邀请码' }}
          </button>
        </div>
      </form>

      <div v-if="createdInvite" class="mt-4 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <div class="text-xs font-semibold text-[var(--color-ink-muted)]">本次生成的邀请码</div>
            <div class="mt-1 break-all font-mono text-base font-semibold text-[var(--color-ink)]">{{ createdInvite.code }}</div>
          </div>
          <button class="btn-secondary w-fit" type="button" @click="copyCode(createdInvite.code)">
            复制
          </button>
        </div>
        <p class="mt-2 text-xs text-[var(--color-ink-soft)]">明文邀请码只在本次生成后展示。</p>
      </div>

      <p v-if="message" :class="['mt-3 text-sm', messageOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">
        {{ message }}
      </p>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <h2 class="text-lg font-semibold">邀请码列表</h2>
        <p class="mt-1 text-sm text-[var(--color-ink-muted)]">列表不展示明文邀请码。</p>
      </div>

      <div v-if="!invites.length && !loading" class="empty-state">
        暂无邀请码
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[48rem] border-separate border-spacing-0 text-left text-sm">
          <thead class="text-xs text-[var(--color-ink-muted)]">
            <tr>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 font-semibold">状态</th>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 font-semibold">创建人</th>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 font-semibold">创建时间</th>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 font-semibold">过期时间</th>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 font-semibold">使用次数</th>
              <th class="border-b border-[var(--color-rule)] px-3 py-2 text-right font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="invite in invites" :key="invite.id">
              <td class="border-b border-[var(--color-rule)] px-3 py-2">
                <span :class="['status-badge', statusClass(invite.status)]">{{ statusLabel(invite.status) }}</span>
              </td>
              <td class="border-b border-[var(--color-rule)] px-3 py-2">{{ invite.created_by }}</td>
              <td class="border-b border-[var(--color-rule)] px-3 py-2 text-[var(--color-ink-muted)]">{{ formatTime(invite.created_at) }}</td>
              <td class="border-b border-[var(--color-rule)] px-3 py-2 text-[var(--color-ink-muted)]">{{ formatTime(invite.expires_at) }}</td>
              <td class="border-b border-[var(--color-rule)] px-3 py-2">{{ invite.used_count }} / {{ invite.max_uses }}</td>
              <td class="border-b border-[var(--color-rule)] px-3 py-2 text-right">
                <button
                  class="btn-secondary min-h-0 px-2.5 py-1.5 text-xs"
                  type="button"
                  :disabled="invite.status === 'disabled'"
                  @click="disableInvite(invite)"
                >
                  停用
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface Invite {
  id: number
  code?: string
  created_by: string
  created_at: string
  expires_at: string
  max_uses: number
  used_count: number
  disabled: boolean
  status: 'active' | 'disabled' | 'expired' | 'exhausted'
}

interface InviteListResponse {
  invites: Invite[]
}

const invites = ref<Invite[]>([])
const loading = ref(false)
const creating = ref(false)
const message = ref('')
const messageOk = ref(false)
const createdInvite = ref<Invite | null>(null)

const form = reactive({
  expires_in_days: 7,
  max_uses: 1,
})

async function loadInvites(clearMessage = true) {
  loading.value = true
  if (clearMessage) message.value = ''
  try {
    const data = await apiFetch<InviteListResponse>('/api/admin/invites')
    invites.value = data.invites
  } catch (error) {
    messageOk.value = false
    message.value = normalizeApiError(error)
  } finally {
    loading.value = false
  }
}

async function createInvite() {
  creating.value = true
  message.value = ''
  createdInvite.value = null
  try {
    const invite = await apiFetch<Invite>('/api/admin/invites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expires_in_days: form.expires_in_days,
        max_uses: form.max_uses,
      }),
    })
    createdInvite.value = invite
    messageOk.value = true
    message.value = '邀请码已生成'
    await loadInvites(false)
  } catch (error) {
    messageOk.value = false
    message.value = normalizeApiError(error)
  } finally {
    creating.value = false
  }
}

async function disableInvite(invite: Invite) {
  message.value = ''
  try {
    await apiFetch(`/api/admin/invites/${invite.id}/disable`, { method: 'POST' })
    messageOk.value = true
    message.value = '邀请码已停用'
    await loadInvites(false)
  } catch (error) {
    messageOk.value = false
    message.value = normalizeApiError(error)
  }
}

async function copyCode(code?: string) {
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    messageOk.value = true
    message.value = '邀请码已复制'
  } catch {
    messageOk.value = false
    message.value = '复制失败，请手动选择邀请码'
  }
}

function statusLabel(status: Invite['status']) {
  const labels = {
    active: '可用',
    disabled: '已停用',
    expired: '已过期',
    exhausted: '已用尽',
  }
  return labels[status]
}

function statusClass(status: Invite['status']) {
  const classes = {
    active: 'status-badge--success',
    disabled: 'status-badge--neutral',
    expired: 'status-badge--warning',
    exhausted: 'status-badge--danger',
  }
  return classes[status]
}

function formatTime(value: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(loadInvites)
</script>
