<template>
  <PreviewLayout title="COSMIC 预览">
    <template #controls>
      <div class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3">
        <div class="flex flex-wrap items-center gap-3">
          <label class="btn-secondary cursor-pointer">
            选择 COSMIC JSON
            <input class="sr-only" type="file" accept="application/json,.json" @change="loadJsonFile" />
          </label>
          <button class="btn-secondary" type="button" :disabled="!report" @click="clearReport">清空</button>
        </div>
        <p v-if="error" class="text-sm text-[var(--color-danger)]">{{ error }}</p>
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
              {{ report.export_policy.manual_confirmation_required ? '需要' : '不需要' }}
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
                        <article v-for="item in reviewItemsForRow(row)" :key="item.review_id" class="rounded border border-[var(--color-rule)] p-3 text-xs">
                          <div class="flex flex-wrap items-center gap-2">
                            <span class="font-semibold text-[var(--color-ink)]">{{ item.code }}</span>
                            <span :class="['status-pill', severityClass(item.severity)]">{{ severityLabel(item.severity) }}</span>
                            <span class="text-[var(--color-ink-muted)]">字段位置：{{ item.field || '-' }}</span>
                          </div>
                          <p class="mt-2 text-sm text-[var(--color-ink)]">{{ item.message }}</p>
                          <p class="mt-2 text-[var(--color-ink-muted)]">审阅项 ID：{{ item.review_id }}</p>
                          <dl v-if="detailsText(item.details)" class="mt-2">
                            <dt class="font-medium text-[var(--color-ink)]">依据</dt>
                            <dd class="mt-1 whitespace-pre-wrap text-[var(--color-ink-muted)]">{{ detailsText(item.details) }}</dd>
                          </dl>
                        </article>
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
import { computed, ref } from 'vue'
import PreviewLayout from '@/components/PreviewLayout.vue'

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
}

interface CosmicReport {
  project: string
  status: string
  summary?: Record<string, number>
  cfp_basis?: Record<string, unknown>
  export_policy?: {
    manual_confirmation_required: boolean
    formal_excel?: { reason?: string }
    draft_excel?: { reason?: string }
  }
  preview_rows: CosmicPreviewRow[]
  review_items: CosmicReviewItem[]
  items: CosmicItem[]
}

const report = ref<CosmicReport | null>(null)
const error = ref('')

const reviewItemsById = computed(() => {
  const map = new Map<string, CosmicReviewItem>()
  for (const item of report.value?.review_items ?? []) {
    map.set(item.review_id, item)
  }
  return map
})

async function loadJsonFile(event: Event) {
  error.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  try {
    const parsed = JSON.parse(await file.text())
    report.value = normalizeReport(parsed)
  } catch (err) {
    report.value = null
    error.value = err instanceof Error ? err.message : '无法读取 COSMIC JSON'
  }
}

function clearReport() {
  report.value = null
  error.value = ''
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
    preview_rows: data.preview_rows,
    review_items: data.review_items,
    items: data.items,
  }
}

function itemForRow(index: number): CosmicItem | undefined {
  return report.value?.items[index]
}

function reviewItemsForRow(row: CosmicPreviewRow): CosmicReviewItem[] {
  return row.review_item_ids
    .map(id => reviewItemsById.value.get(id))
    .filter((item): item is CosmicReviewItem => Boolean(item))
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
</style>
