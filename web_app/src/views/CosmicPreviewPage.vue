<template>
  <PreviewLayout title="COSMIC 预览">
    <template #controls>
      <div class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3">
        <div class="flex flex-wrap items-center gap-3">
          <label class="btn-secondary cursor-pointer">
            选择 COSMIC JSON
            <input class="sr-only" type="file" accept="application/json,.json" @change="loadJsonFile" />
          </label>
          <button v-if="sessionId" class="btn-secondary" type="button" :disabled="backendLoading" @click="() => loadSessionDraft()">
            {{ backendLoading ? '读取中...' : '读取任务草稿' }}
          </button>
          <button v-if="sessionId" class="btn-secondary" type="button" :disabled="backendLoading" @click="loadSessionConfirmation">
            {{ backendLoading ? '读取中...' : '读取会话确认' }}
          </button>
          <button v-if="sessionId" class="btn-secondary" type="button" :disabled="!report || backendSaving" @click="saveSessionConfirmation">
            {{ backendSaving ? '保存中...' : '保存到会话' }}
          </button>
          <button v-if="sessionId" class="btn-secondary" type="button" :disabled="!canExportConfirmedExcel || backendExporting" @click="exportConfirmedExcel">
            {{ backendExporting ? '导出中...' : '导出确认后 Excel' }}
          </button>
          <button class="btn-secondary" type="button" :disabled="!report" @click="exportReport">导出确认 JSON</button>
          <button class="btn-secondary" type="button" :disabled="!report" @click="clearReport">清空</button>
        </div>
        <p v-if="error" class="text-sm text-[var(--color-danger)]">{{ error }}</p>
        <p v-if="backendSyncError" class="text-sm text-[var(--color-danger)]">{{ backendSyncError }}</p>
        <p v-if="backendSyncStatus" class="text-sm text-[var(--color-success)]">{{ backendSyncStatus }}</p>
      </div>
    </template>

    <div v-if="!report" class="flex h-full min-h-[360px] items-center justify-center p-5">
      <div class="max-w-md text-center">
        <p class="text-sm font-semibold text-[var(--color-ink)]">等待 COSMIC JSON 草稿</p>
        <p class="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">
          新增/修改功能过程、数据移动和审阅项将在这里集中审阅。
        </p>
      </div>
    </div>

    <div v-else class="flex h-full min-h-0 flex-col">
      <section class="grid gap-3 border-b border-[var(--color-rule)] bg-[var(--color-surface)] p-4 md:grid-cols-4">
        <div class="summary-cell">
          <span>项目</span>
          <strong>{{ report.project || '-' }}</strong>
        </div>
        <div class="summary-cell">
          <span>校验状态</span>
          <strong :class="statusClass(report.status)">{{ statusLabel(report.status) }}</strong>
        </div>
        <div class="summary-cell">
          <span>新增/修改功能过程</span>
          <strong>{{ report.summary?.total ?? report.preview_rows.length }}</strong>
        </div>
        <div class="summary-cell">
          <span>审阅项</span>
          <strong>{{ report.review_items.length }}</strong>
        </div>
      </section>

      <section v-if="report.export_policy" class="border-b border-[var(--color-rule)] px-4 py-3 text-sm">
        <div class="grid gap-2 md:grid-cols-3">
          <div>
            <span class="text-[var(--color-ink-muted)]">人工确认</span>
            <span class="ml-2 font-medium text-[var(--color-ink)]">
              {{ confirmationSummaryText }}
            </span>
          </div>
          <div>
            <span class="text-[var(--color-ink-muted)]">正式 Excel</span>
            <span class="ml-2 font-medium text-[var(--color-ink)]">{{ report.export_policy.formal_excel?.reason || '-' }}</span>
          </div>
          <div>
            <span class="text-[var(--color-ink-muted)]">草稿 Excel</span>
            <span class="ml-2 font-medium text-[var(--color-ink)]">{{ report.export_policy.draft_excel?.reason || '-' }}</span>
          </div>
        </div>
      </section>

      <section v-if="globalReviewItems.length" class="border-b border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-3">
        <p class="detail-title">全局审阅项</p>
        <div class="mt-2 grid gap-2 lg:grid-cols-2">
          <ReviewItemCard v-for="item in globalReviewItems" :key="item.review_id" :item="item" />
        </div>
      </section>

      <div class="min-h-0 flex-1 overflow-auto">
        <table class="min-w-full border-collapse text-left text-sm">
          <thead class="sticky top-0 z-10 bg-[var(--color-surface-muted)] text-xs text-[var(--color-ink-muted)]">
            <tr>
              <th class="table-head w-12">#</th>
              <th class="table-head min-w-52">模块路径</th>
              <th class="table-head min-w-56">新增/修改功能过程</th>
              <th class="table-head min-w-48">功能用户</th>
              <th class="table-head min-w-40">触发事件</th>
              <th class="table-head min-w-36">数据移动</th>
              <th class="table-head min-w-36">数据移动类型</th>
              <th class="table-head min-w-28">CFP</th>
              <th class="table-head min-w-28">校验状态</th>
              <th class="table-head min-w-32">审阅项</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in report.preview_rows" :key="row.item_index">
              <tr class="border-b border-[var(--color-rule)] align-top hover:bg-[var(--color-surface-muted)]">
                <td class="table-cell text-[var(--color-ink-muted)]">{{ row.item_index + 1 }}</td>
                <td class="table-cell">{{ row.module_path || '-' }}</td>
                <td class="table-cell font-medium text-[var(--color-ink)]">{{ row.process || '-' }}</td>
                <td class="table-cell">{{ row.user || '-' }}</td>
                <td class="table-cell">{{ row.trigger || '-' }}</td>
                <td class="table-cell">{{ row.movement_count }}</td>
                <td class="table-cell">{{ row.movement_types.join(' / ') || '-' }}</td>
                <td class="table-cell">{{ cfpForRow(row.item_index) }}</td>
                <td class="table-cell">
                  <span :class="['status-pill', statusClass(row.status)]">{{ statusLabel(row.status) }}</span>
                </td>
                <td class="table-cell">{{ row.issue_count }}</td>
              </tr>
              <tr class="border-b border-[var(--color-rule)] bg-[var(--color-surface)]">
                <td></td>
                <td class="px-3 py-3" colspan="9">
                  <div class="grid gap-3 xl:grid-cols-2">
                    <div>
                      <p class="detail-title">数据移动</p>
                      <div class="mt-2 overflow-hidden rounded border border-[var(--color-rule)]">
                        <table class="min-w-full text-xs">
                          <thead class="bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]">
                            <tr>
                              <th class="detail-head">#</th>
                              <th class="detail-head">子过程</th>
                              <th class="detail-head">数据移动类型</th>
                              <th class="detail-head">数据组</th>
                              <th class="detail-head">数据属性</th>
                              <th class="detail-head">复用度</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="movement in itemForRow(row.item_index)?.movements ?? []" :key="movement.order" class="border-t border-[var(--color-rule)]">
                              <td class="detail-cell">{{ movement.order }}</td>
                              <td class="detail-cell">{{ movement.sub_process || '-' }}</td>
                              <td class="detail-cell font-medium">{{ movement.move_type || '-' }}</td>
                              <td class="detail-cell">{{ movement.data_group || '-' }}</td>
                              <td class="detail-cell">{{ movement.data_attrs || '-' }}</td>
                              <td class="detail-cell">{{ movement.reuse || '-' }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div>
                      <p class="detail-title">审阅项</p>
                      <div v-if="reviewItemsForRow(row).length" class="mt-2 space-y-2">
                        <ReviewItemCard v-for="item in reviewItemsForRow(row)" :key="item.review_id" :item="item" />
                      </div>
                      <p v-else class="mt-2 text-xs text-[var(--color-ink-muted)]">无审阅项。</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </PreviewLayout>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import PreviewLayout from '@/components/PreviewLayout.vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'
import { useSessionStore, type DoneFile } from '@/stores/session.ts'

interface CosmicMovement {
  order: number
  sub_process: string
  move_type: string
  data_group: string
  data_attrs: string
  reuse: string
}

interface CosmicItem {
  process: string
  movements: CosmicMovement[]
  basis?: Record<string, unknown>
}

interface CosmicPreviewRow {
  item_index: number
  module_path: string
  process: string
  user: string
  trigger: string
  movement_count: number
  movement_types: string[]
  status: string
  issue_count: number
  review_item_ids: string[]
}

interface CosmicReviewItem {
  review_id: string
  scope: string
  item_index: number | null
  code: string
  severity: string
  field: string
  message: string
  details?: Record<string, unknown>
  confirmation?: {
    status?: string
    decision?: string
    note?: string
    confirmed_by?: string
    confirmed_at?: string
  }
}

interface CosmicReport {
  project: string
  status: string
  summary?: Record<string, number>
  cfp_basis?: Record<string, unknown>
  export_policy?: {
    manual_confirmation_required: boolean
    unconfirmed_review_item_count?: number
    formal_excel?: { status?: string; reason?: string }
    draft_excel?: { status?: string; reason?: string; requires_config?: boolean; config_key?: string }
  }
  confirmation_summary?: {
    total_review_item_count?: number
    unconfirmed_review_item_count?: number
    resolved_review_item_count?: number
    error_review_item_count?: number
    warning_review_item_count?: number
    info_review_item_count?: number
  }
  preview_rows: CosmicPreviewRow[]
  review_items: CosmicReviewItem[]
  items: CosmicItem[]
}

interface CosmicJsonResponse {
  session_id: string
  filename: string
  payload: CosmicReport
}

interface CosmicExportResponse {
  ok: boolean
  filename: string
  path: string
  file?: DoneFile
  files?: DoneFile[]
  cfp_total?: number
  cfp_summary_file?: DoneFile
  export_policy?: CosmicReport['export_policy']
}

const route = useRoute()
const session = useSessionStore()
const report = ref<CosmicReport | null>(null)
const error = ref('')
const confirmationStoreKey = ref('')
const backendSyncStatus = ref('')
const backendSyncError = ref('')
const backendLoading = ref(false)
const backendSaving = ref(false)
const backendExporting = ref(false)

const sessionId = computed(() => {
  const routeSession = route.params.sessionId
  const querySession = route.query.session
  const raw = Array.isArray(routeSession) ? routeSession[0] : routeSession || querySession
  return String(Array.isArray(raw) ? raw[0] : raw || '').trim()
})

const reviewItemsById = computed(() => {
  const map = new Map<string, CosmicReviewItem>()
  for (const item of report.value?.review_items ?? []) {
    map.set(item.review_id, item)
  }
  return map
})

const globalReviewItems = computed(() => {
  return (report.value?.review_items ?? []).filter(item => item.scope === 'global' || item.item_index === null)
})

const confirmationSummaryText = computed(() => {
  const summary = report.value?.confirmation_summary
  const total = summary?.total_review_item_count ?? report.value?.review_items.length ?? 0
  const unconfirmed = summary?.unconfirmed_review_item_count ?? report.value?.export_policy?.unconfirmed_review_item_count ?? total
  if (!total) return '不需要'
  return unconfirmed ? `未确认 ${unconfirmed}/${total}` : `已处理 ${total}/${total}`
})

const canExportConfirmedExcel = computed(() => {
  const status = report.value?.export_policy?.formal_excel?.status || ''
  return status === 'allowed' || status === 'allowed_after_confirmation'
})

onMounted(() => {
  if (sessionId.value) {
    void loadSessionDraft({ silent: true })
  }
})

async function loadJsonFile(event: Event) {
  error.value = ''
  backendSyncError.value = ''
  backendSyncStatus.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  try {
    const parsed = JSON.parse(await file.text())
    const normalized = normalizeReport(parsed)
    confirmationStoreKey.value = buildConfirmationStoreKey(normalized)
    applyStoredConfirmations(normalized)
    applyConfirmationExportPolicy(normalized)
    report.value = normalized
    backendSyncStatus.value = '已读取本地 COSMIC JSON'
  } catch (err) {
    report.value = null
    confirmationStoreKey.value = ''
    error.value = err instanceof Error ? err.message : '无法读取 COSMIC JSON'
  }
}

function clearReport() {
  report.value = null
  error.value = ''
  confirmationStoreKey.value = ''
  backendSyncError.value = ''
  backendSyncStatus.value = ''
}

function exportReport() {
  if (!report.value) return
  const blob = new Blob([`${JSON.stringify(report.value, null, 2)}\n`], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${report.value.project || 'cosmic'}-确认.json`
  link.click()
  URL.revokeObjectURL(url)
}

function normalizeReport(value: unknown): CosmicReport {
  if (!value || typeof value !== 'object') {
    throw new Error('COSMIC JSON 必须是对象')
  }
  const data = value as Partial<CosmicReport>
  if (!Array.isArray(data.preview_rows) || !Array.isArray(data.items) || !Array.isArray(data.review_items)) {
    throw new Error('COSMIC JSON 缺少 preview_rows、items 或 review_items')
  }
  return {
    project: String(data.project ?? ''),
    status: String(data.status ?? ''),
    summary: data.summary,
    cfp_basis: data.cfp_basis,
    export_policy: data.export_policy,
    confirmation_summary: data.confirmation_summary,
    preview_rows: data.preview_rows,
    review_items: data.review_items.map(normalizeReviewItem),
    items: data.items,
  }
}

async function loadSessionConfirmation() {
  if (!sessionId.value) return
  backendLoading.value = true
  backendSyncError.value = ''
  backendSyncStatus.value = ''
  try {
    const response = await fetchSessionConfirmation()
    const normalized = normalizeReport(response.payload)
    confirmationStoreKey.value = buildConfirmationStoreKey(normalized)
    applyStoredConfirmations(normalized)
    applyConfirmationExportPolicy(normalized)
    report.value = normalized
    backendSyncStatus.value = '已读取会话确认'
  } catch (err) {
    backendSyncError.value = normalizeApiError(err)
  } finally {
    backendLoading.value = false
  }
}

async function loadSessionDraft(options: { silent?: boolean } = {}) {
  if (!sessionId.value) return
  backendLoading.value = true
  backendSyncError.value = ''
  backendSyncStatus.value = ''
  try {
    const response = await apiFetch<CosmicJsonResponse>(
      `/api/sessions/${encodeURIComponent(sessionId.value)}/cosmic/draft`,
    )
    const normalized = normalizeReport(response.payload)
    confirmationStoreKey.value = buildConfirmationStoreKey(normalized)
    applyStoredConfirmations(normalized)
    await applySessionConfirmations(normalized)
    applyConfirmationExportPolicy(normalized)
    report.value = normalized
    backendSyncStatus.value = '已读取任务草稿'
  } catch (err) {
    if (!options.silent) {
      backendSyncError.value = normalizeApiError(err)
    }
  } finally {
    backendLoading.value = false
  }
}

async function fetchSessionConfirmation(): Promise<CosmicJsonResponse> {
  return apiFetch<CosmicJsonResponse>(
    `/api/sessions/${encodeURIComponent(sessionId.value)}/cosmic/confirmation`,
  )
}

async function applySessionConfirmations(data: CosmicReport) {
  if (!sessionId.value) return
  try {
    const response = await fetchSessionConfirmation()
    mergeConfirmations(data, response.payload)
  } catch {
    // A missing saved confirmation should not block loading the generated draft.
  }
}

function mergeConfirmations(target: CosmicReport, source: Partial<CosmicReport>) {
  if (!Array.isArray(source.review_items)) return
  const confirmations = new Map<string, CosmicReviewItem['confirmation']>()
  for (const item of source.review_items) {
    if (item?.review_id && item.confirmation) {
      confirmations.set(item.review_id, item.confirmation)
    }
  }
  for (const item of target.review_items) {
    const confirmation = confirmations.get(item.review_id)
    if (confirmation) {
      item.confirmation = {
        ...item.confirmation,
        ...confirmation,
      }
    }
  }
  applyConfirmationExportPolicy(target)
}

async function saveSessionConfirmation() {
  if (!sessionId.value || !report.value) return
  backendSaving.value = true
  backendSyncError.value = ''
  backendSyncStatus.value = ''
  try {
    const response = await apiFetch<CosmicJsonResponse>(
      `/api/sessions/${encodeURIComponent(sessionId.value)}/cosmic/confirmation`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report.value),
      },
    )
    report.value.export_policy = response.payload.export_policy
    report.value.confirmation_summary = response.payload.confirmation_summary
    backendSyncStatus.value = '已保存到会话'
  } catch (err) {
    backendSyncError.value = normalizeApiError(err)
  } finally {
    backendSaving.value = false
  }
}

async function exportConfirmedExcel() {
  if (!sessionId.value || !report.value) return
  backendExporting.value = true
  backendSyncError.value = ''
  backendSyncStatus.value = ''
  try {
    const response = await apiFetch<CosmicExportResponse>(
      `/api/sessions/${encodeURIComponent(sessionId.value)}/cosmic/export-confirmed`,
      { method: 'POST' },
    )
    if (response.export_policy) {
      report.value.export_policy = response.export_policy
    }
    const exportedFiles = response.files ?? (response.file ? [response.file] : [])
    if (session.sessionId === sessionId.value) {
      exportedFiles.forEach(file => session.upsertDoneFile(file))
    }
    backendSyncStatus.value = `已导出 ${response.filename}`
  } catch (err) {
    backendSyncError.value = normalizeApiError(err)
  } finally {
    backendExporting.value = false
  }
}

function normalizeReviewItem(item: CosmicReviewItem): CosmicReviewItem {
  return {
    ...item,
    confirmation: {
      status: String(item.confirmation?.status || 'unconfirmed'),
      decision: String(item.confirmation?.decision || ''),
      note: String(item.confirmation?.note || ''),
      confirmed_by: String(item.confirmation?.confirmed_by || ''),
      confirmed_at: String(item.confirmation?.confirmed_at || ''),
    },
  }
}

function buildConfirmationStoreKey(data: CosmicReport): string {
  const ids = data.review_items.map(item => item.review_id).sort().join('|')
  return `cosmic-preview-confirmations:${data.project || 'unknown'}:${ids}`
}

function applyStoredConfirmations(data: CosmicReport) {
  if (!confirmationStoreKey.value) return
  try {
    const raw = window.localStorage.getItem(confirmationStoreKey.value)
    if (!raw) return
    const stored = JSON.parse(raw)
    if (!stored || typeof stored !== 'object') return
    for (const item of data.review_items) {
      const confirmation = (stored as Record<string, unknown>)[item.review_id]
      if (confirmation && typeof confirmation === 'object') {
        item.confirmation = {
          ...item.confirmation,
          ...(confirmation as Record<string, string>),
        }
      }
    }
  } catch {
    // Ignore corrupt local review state and keep the JSON defaults.
  }
}

function saveConfirmations() {
  if (!report.value || !confirmationStoreKey.value) return
  const state = Object.fromEntries(
    report.value.review_items.map(item => [item.review_id, item.confirmation || {}]),
  )
  window.localStorage.setItem(confirmationStoreKey.value, JSON.stringify(state))
}

function itemForRow(index: number): CosmicItem | undefined {
  return report.value?.items[index]
}

function reviewItemsForRow(row: CosmicPreviewRow): CosmicReviewItem[] {
  return row.review_item_ids
    .map(id => reviewItemsById.value.get(id))
    .filter((item): item is CosmicReviewItem => Boolean(item))
}

function updateConfirmation(reviewId: string, patch: Record<string, string>) {
  const item = report.value?.review_items.find(candidate => candidate.review_id === reviewId)
  if (!item) return
  const previous = item.confirmation || {}
  const nextStatus = patch.status ?? previous.status ?? 'unconfirmed'
  const statusChanged = patch.status !== undefined && patch.status !== previous.status
  item.confirmation = {
    status: nextStatus,
    decision: nextStatus === 'unconfirmed' ? '' : statusChanged ? nextStatus : previous.decision || nextStatus,
    note: patch.note ?? previous.note ?? '',
    confirmed_by: previous.confirmed_by ?? '',
    confirmed_at: nextStatus === 'unconfirmed' ? '' : statusChanged ? new Date().toISOString() : previous.confirmed_at ?? '',
  }
  if (report.value) {
    applyConfirmationExportPolicy(report.value)
  }
  saveConfirmations()
}

function applyConfirmationExportPolicy(data: CosmicReport) {
  const total = data.review_items.length
  const unconfirmed = data.review_items.filter(item => !isResolvedConfirmation(item)).length
  const errorCount = data.review_items.filter(item => item.severity === 'error').length
  const warningCount = data.review_items.filter(item => item.severity === 'warning').length
  const infoCount = data.review_items.filter(item => item.severity === 'info').length
  data.confirmation_summary = {
    total_review_item_count: total,
    unconfirmed_review_item_count: unconfirmed,
    resolved_review_item_count: total - unconfirmed,
    error_review_item_count: errorCount,
    warning_review_item_count: warningCount,
    info_review_item_count: infoCount,
  }
  data.export_policy = buildConfirmationExportPolicy(data.status, total, unconfirmed, errorCount)
}

function isResolvedConfirmation(item: CosmicReviewItem): boolean {
  const status = item.confirmation?.status || 'unconfirmed'
  return status === 'confirmed' || status === 'rejected' || status === 'waived'
}

function buildConfirmationExportPolicy(status: string, total: number, unconfirmed: number, errorCount: number): CosmicReport['export_policy'] {
  if (status === 'passed') {
    return {
      manual_confirmation_required: total > 0,
      unconfirmed_review_item_count: unconfirmed,
      formal_excel: { status: 'allowed', reason: '校验通过，可写正式 Excel' },
      draft_excel: { status: 'not_needed', reason: '校验通过，不需要草稿 Excel', requires_config: false, config_key: 'gen_cosmic.allow_draft_excel_output' },
    }
  }
  if (unconfirmed) {
    return {
      manual_confirmation_required: total > 0,
      unconfirmed_review_item_count: unconfirmed,
      formal_excel: { status: 'blocked', reason: `仍有 ${unconfirmed} 个审阅项未确认，正式 Excel 需人工确认后再导出` },
      draft_excel: {
        status: status === 'review_required' ? 'eligible' : 'blocked',
        reason: status === 'review_required' ? '存在待审问题，可在配置开启后写草稿 Excel' : '存在阻断问题，不能写草稿 Excel',
        requires_config: status === 'review_required',
        config_key: 'gen_cosmic.allow_draft_excel_output',
      },
    }
  }
  if (errorCount) {
    return {
      manual_confirmation_required: total > 0,
      unconfirmed_review_item_count: 0,
      formal_excel: { status: 'blocked', reason: '存在 error 级阻断项，即使已确认也不能写正式 Excel' },
      draft_excel: { status: 'blocked', reason: '存在 error 级阻断项，不能写草稿 Excel', requires_config: false, config_key: 'gen_cosmic.allow_draft_excel_output' },
    }
  }
  return {
    manual_confirmation_required: total > 0,
    unconfirmed_review_item_count: 0,
    formal_excel: { status: 'allowed_after_confirmation', reason: '待审项已人工处理，可写正式 Excel' },
    draft_excel: { status: 'not_needed', reason: '待审项已人工处理，不需要草稿 Excel', requires_config: false, config_key: 'gen_cosmic.allow_draft_excel_output' },
  }
}

function cfpForRow(index: number): string {
  const basis = itemForRow(index)?.basis
  const cfp = basis && typeof basis === 'object' ? (basis as Record<string, unknown>).cfp : undefined
  return cfp === undefined || cfp === null || cfp === '' ? '-' : String(cfp)
}

function statusLabel(status: string): string {
  if (status === 'passed') return '通过'
  if (status === 'review_required') return '待审'
  if (status === 'blocked') return '阻断'
  return status || '-'
}

function statusClass(status: string): string {
  if (status === 'passed') return 'text-[var(--color-success)]'
  if (status === 'review_required') return 'text-[var(--color-warning)]'
  if (status === 'blocked') return 'text-[var(--color-danger)]'
  return 'text-[var(--color-ink)]'
}

function severityLabel(severity: string): string {
  if (severity === 'error') return '错误'
  if (severity === 'warning') return '警告'
  if (severity === 'info') return '提示'
  return severity || '-'
}

function severityClass(severity: string): string {
  if (severity === 'error') return 'text-[var(--color-danger)]'
  if (severity === 'warning') return 'text-[var(--color-warning)]'
  return 'text-[var(--color-ink-muted)]'
}

function confirmationLabel(item: CosmicReviewItem): string {
  const status = item.confirmation?.status || 'unconfirmed'
  if (status === 'confirmed') return '已确认'
  if (status === 'rejected') return '已驳回'
  if (status === 'waived') return '已豁免'
  return '未确认'
}

function confirmationText(item: CosmicReviewItem): string {
  const parts = [
    item.confirmation?.decision,
    item.confirmation?.note,
    item.confirmation?.confirmed_by,
    item.confirmation?.confirmed_at,
  ]
    .map(value => String(value ?? '').trim())
    .filter(Boolean)
  return parts.join(' / ')
}

function detailsText(details: Record<string, unknown> | undefined): string {
  if (!details) return ''
  const parts: string[] = []
  for (const [key, value] of Object.entries(details)) {
    if (value === undefined || value === null || value === '') continue
    const text = Array.isArray(value) ? value.join('、') : String(value)
    if (text) parts.push(`${key}: ${text}`)
  }
  return parts.join('\n')
}

const ReviewItemCard = defineComponent({
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    return () => {
      const item = props.item as CosmicReviewItem
      const details = detailsText(item.details)
      const confirmation = confirmationText(item)
      return h('article', { class: 'rounded border border-[var(--color-rule)] p-3 text-xs' }, [
        h('div', { class: 'flex flex-wrap items-center gap-2' }, [
          h('span', { class: 'font-semibold text-[var(--color-ink)]' }, item.code),
          h(
            'span',
            { class: ['inline-flex items-center whitespace-nowrap rounded bg-[var(--color-surface-muted)] px-2 py-0.5 text-xs font-semibold', severityClass(item.severity)] },
            severityLabel(item.severity),
          ),
          h(
            'span',
            { class: 'inline-flex items-center whitespace-nowrap rounded bg-[var(--color-surface-muted)] px-2 py-0.5 text-xs font-semibold text-[var(--color-ink-muted)]' },
            confirmationLabel(item),
          ),
          h('span', { class: 'text-[var(--color-ink-muted)]' }, `字段位置：${item.field || '-'}`),
        ]),
        h('p', { class: 'mt-2 text-sm text-[var(--color-ink)]' }, item.message),
        confirmation ? h('p', { class: 'mt-2 text-[var(--color-ink-muted)]' }, `人工确认：${confirmation}`) : null,
        h('p', { class: 'mt-2 break-all text-[var(--color-ink-muted)]' }, `审阅项 ID：${item.review_id}`),
        details
          ? h('dl', { class: 'mt-2' }, [
              h('dt', { class: 'font-medium text-[var(--color-ink)]' }, '依据'),
              h('dd', { class: 'mt-1 whitespace-pre-wrap text-[var(--color-ink-muted)]' }, details),
            ])
          : null,
        h('div', { class: 'mt-3 grid gap-2 md:grid-cols-[160px_1fr]' }, [
          h('label', { class: 'confirmation-field' }, [
            h('span', '确认状态'),
            h(
              'select',
              {
                class: 'confirmation-input',
                value: item.confirmation?.status || 'unconfirmed',
                onChange: (event: Event) => {
                  updateConfirmation(item.review_id, { status: (event.target as HTMLSelectElement).value })
                },
              },
              [
                h('option', { value: 'unconfirmed' }, '未确认'),
                h('option', { value: 'confirmed' }, '已确认'),
                h('option', { value: 'rejected' }, '已驳回'),
                h('option', { value: 'waived' }, '已豁免'),
              ],
            ),
          ]),
          h('label', { class: 'confirmation-field' }, [
            h('span', '确认备注'),
            h('input', {
              class: 'confirmation-input',
              type: 'text',
              value: item.confirmation?.note || '',
              onInput: (event: Event) => {
                updateConfirmation(item.review_id, { note: (event.target as HTMLInputElement).value })
              },
            }),
          ]),
        ]),
      ])
    }
  },
})
</script>

<style scoped>
.summary-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.25rem;
  border: 1px solid var(--color-rule);
  border-radius: 0.375rem;
  padding: 0.75rem;
}

.summary-cell span {
  font-size: 0.75rem;
  color: var(--color-ink-muted);
}

.summary-cell strong {
  overflow-wrap: anywhere;
  font-size: 0.95rem;
}

.table-head,
.table-cell {
  border-bottom: 1px solid var(--color-rule);
  padding: 0.75rem;
  vertical-align: top;
}

.detail-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-ink);
}

.detail-head,
.detail-cell {
  padding: 0.5rem;
  vertical-align: top;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  border-radius: 0.25rem;
  background: var(--color-surface-muted);
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.confirmation-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.25rem;
}

.confirmation-field span {
  color: var(--color-ink-muted);
  font-size: 0.75rem;
}

.confirmation-input {
  min-width: 0;
  border: 1px solid var(--color-rule);
  border-radius: 0.25rem;
  background: var(--color-surface);
  padding: 0.375rem 0.5rem;
  color: var(--color-ink);
}
</style>
