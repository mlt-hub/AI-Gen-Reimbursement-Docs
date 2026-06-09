<template>
  <div>
    <div class="mb-3">
      <p class="text-xs font-semibold text-[var(--color-ink-soft)]">Word 模板导入</p>
      <h3 class="mt-1 text-sm font-semibold">需求说明书模板草稿</h3>
    </div>

    <div class="space-y-3">
      <input
        type="file"
        accept=".docx"
        class="w-full max-w-full text-xs text-[var(--color-ink-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface-raised)] file:px-3 file:py-1 file:text-xs file:text-[var(--color-ink-muted)] hover:file:bg-[var(--color-surface-muted)]"
        :disabled="loading"
        @change="onFileChange"
      />

      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', statusClass]">{{ statusText }}</span>
        <button class="btn-secondary w-fit" :disabled="loading || !selectedFile" @click="importTemplate">
          {{ loading ? '导入中...' : '生成模板草稿' }}
        </button>
      </div>

      <p v-if="message" :class="['text-sm', ok ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ message }}</p>

      <div v-if="result" class="space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
        <div class="grid gap-2 text-xs text-[var(--color-ink-muted)] sm:grid-cols-[5rem_1fr]">
          <span class="text-[var(--color-ink-soft)]">模板</span>
          <span class="break-all font-mono">{{ result.template_path }}</span>
          <span class="text-[var(--color-ink-soft)]">manifest</span>
          <span class="break-all font-mono">{{ result.manifest_path }}</span>
        </div>

        <div v-if="result.detected_placeholders.length">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">已识别字段</p>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <span
              v-for="item in result.detected_placeholders"
              :key="item.key + item.scope"
              class="rounded border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-2 py-1 text-xs text-[var(--color-ink-muted)]"
            >
              {{ item.label }} / {{ scopeLabel(item.scope) }}
            </span>
          </div>
        </div>

        <div v-if="result.inserted_anchors.length">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">功能需求锚点</p>
          <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
            <li v-for="item in result.inserted_anchors" :key="item.key">{{ item.token }} / {{ anchorLocationLabel(item.location) }}</li>
          </ul>
        </div>

        <div v-if="result.pending_confirmations.length">
          <p class="text-xs font-semibold text-[var(--color-warning)]">待确认</p>
          <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-warning)]">
            <li v-for="item in result.pending_confirmations" :key="item">{{ item }}</li>
          </ul>
        </div>

        <div v-if="result.warnings.length">
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">边界</p>
          <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
            <li v-for="item in result.warnings" :key="item">{{ item }}</li>
          </ul>
        </div>

        <button class="btn-primary w-fit" @click="applyMapping">应用到模板映射</button>
      </div>

      <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-xs font-semibold text-[var(--color-ink-soft)]">已导入草稿</p>
            <p class="mt-1 text-xs text-[var(--color-ink-muted)]">选择已生成的 Word 模板草稿应用到模板映射。</p>
          </div>
          <button class="btn-secondary w-fit" :disabled="draftsLoading" @click="loadDrafts">
            {{ draftsLoading ? '加载中...' : '刷新' }}
          </button>
        </div>

        <p v-if="draftsMessage" :class="['mt-2 text-sm', draftsOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ draftsMessage }}</p>

        <div v-if="drafts.length" class="mt-3 space-y-2">
          <div
            v-for="item in drafts"
            :key="item.id"
            class="rounded-md border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3"
          >
            <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-sm font-semibold text-[var(--color-ink)]">{{ item.display_name || item.id }}</span>
                  <span class="font-mono text-xs text-[var(--color-ink-muted)]">{{ item.id }}</span>
                  <span :class="['status-badge', item.ok ? 'status-badge--success' : 'status-badge--warning']">
                    {{ item.ok ? '预检通过' : '需检查' }}
                  </span>
                  <span :class="['status-badge', item.confirmed ? 'status-badge--success' : 'status-badge--neutral']">
                    {{ item.confirmed ? '已确认' : '未确认' }}
                  </span>
                  <span v-if="item.published" class="status-badge status-badge--success">已发布</span>
                  <span class="text-xs text-[var(--color-ink-soft)]">{{ formatBytes(item.size_bytes) }}</span>
                </div>
                <p v-if="item.note" class="mt-1 text-xs text-[var(--color-ink-muted)]">{{ item.note }}</p>
                <p class="mt-1 break-all font-mono text-xs text-[var(--color-ink-soft)]">{{ item.template_path }}</p>
                <p v-if="item.capabilities?.anchor_mode" class="mt-1 text-xs text-[var(--color-ink-muted)]">
                  {{ anchorModeLabel(item.capabilities.anchor_mode) }} / 模块表 {{ moduleColumnCount(item) }} 列
                </p>
                <ul v-if="item.errors.length" class="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--color-danger)]">
                  <li v-for="error in item.errors" :key="error">{{ error }}</li>
                </ul>
                <ul v-if="item.warnings.length" class="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--color-warning)]">
                  <li v-for="warning in item.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>
              <div class="flex flex-wrap gap-2">
                <a class="btn-secondary min-h-0 px-2 py-1 text-xs" :href="draftDownloadUrl(item, item.template_filename)">下载</a>
                <a class="btn-secondary min-h-0 px-2 py-1 text-xs" :href="draftDownloadUrl(item, item.manifest_filename)">manifest</a>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="previewLoadingId === item.id" @click="loadPreview(item)">
                  {{ previewLoadingId === item.id ? '预览中' : '预览' }}
                </button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="layoutLoadingId === item.id" @click="loadLayoutPreview(item)">
                  {{ layoutLoadingId === item.id ? '渲染中' : '版式' }}
                </button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" @click="toggleMetadataEditor(item)">命名</button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="metadataSavingId === item.id" @click="setDraftConfirmed(item, !item.confirmed)">
                  {{ item.confirmed ? '取消确认' : '确认' }}
                </button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="publishingId === item.id || !item.confirmed || !item.ok" @click="publishDraft(item)">
                  {{ publishingId === item.id ? '发布中' : '发布' }}
                </button>
                <button class="btn-primary min-h-0 px-2 py-1 text-xs" @click="applyDraft(item)">应用</button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="deletingId === item.id" @click="deleteDraft(item)">
                  {{ deletingId === item.id ? '删除中' : '删除' }}
                </button>
              </div>
            </div>

            <div v-if="metadataEditorId === item.id" class="mt-3 grid gap-3 border-t border-[var(--color-rule)] pt-3 md:grid-cols-2">
              <div>
                <label class="field-label text-xs">模板名称</label>
                <input v-model.trim="draftEdits[item.id].display_name" type="text" class="field-control" />
              </div>
              <div>
                <label class="field-label text-xs">版本备注</label>
                <input v-model.trim="draftEdits[item.id].note" type="text" class="field-control" />
              </div>
              <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)] md:col-span-2">
                <input
                  v-model="draftEdits[item.id].confirmed"
                  type="checkbox"
                  class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
                />
                确认字段和功能需求锚点位置可用于生成
              </label>
              <div class="flex flex-wrap gap-2 md:col-span-2">
                <button class="btn-primary min-h-0 px-2 py-1 text-xs" :disabled="metadataSavingId === item.id" @click="saveDraftMetadata(item)">
                  {{ metadataSavingId === item.id ? '保存中' : '保存确认信息' }}
                </button>
                <button class="btn-secondary min-h-0 px-2 py-1 text-xs" @click="metadataEditorId = ''">收起</button>
              </div>
            </div>

            <div v-if="activePreviewId === item.id && activePreview" class="mt-3 space-y-3 border-t border-[var(--color-rule)] pt-3">
              <div class="grid gap-2 text-xs text-[var(--color-ink-muted)] sm:grid-cols-3">
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  正文段落：{{ activePreview.summary.body_paragraph_count }}
                </div>
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  占位符：{{ activePreview.summary.placeholder_count }}
                </div>
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  锚点：{{ activePreview.summary.anchor_count }}
                </div>
              </div>

              <div v-if="activePreview.anchors.length">
                <p class="text-xs font-semibold text-[var(--color-ink-soft)]">锚点位置</p>
                <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
                  <li v-for="anchor in activePreview.anchors" :key="anchor.key + anchor.location">
                    {{ anchor.token }} / {{ scopeLabel(anchor.scope) }} / {{ anchor.location }} / {{ anchor.text }}
                  </li>
                </ul>
              </div>

              <div v-if="activePreview.section_candidates.length">
                <p class="text-xs font-semibold text-[var(--color-ink-soft)]">功能需求章节候选</p>
                <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
                  <li v-for="candidate in activePreview.section_candidates" :key="candidate.location + candidate.text">
                    {{ candidate.location }} / {{ candidate.style }} / {{ candidate.text }}
                  </li>
                </ul>
              </div>

              <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                <p class="text-xs font-semibold text-[var(--color-ink-soft)]">在线调整</p>
                <div class="mt-3 grid gap-3 md:grid-cols-2">
                  <div>
                    <label class="field-label text-xs">模块清单锚点</label>
                    <select v-model="adjustmentForm.moduleTableLocation" class="field-control text-xs">
                      <option value="">不调整</option>
                      <option value="document_end">文档末尾</option>
                      <option v-for="candidate in activePreview.section_candidates" :key="'module-table-' + candidate.location" :value="anchorAfterLocation(candidate.location)">
                        {{ candidate.location }} / {{ candidate.text }}
                      </option>
                    </select>
                  </div>
                  <div>
                    <label class="field-label text-xs">功能过程详情锚点</label>
                    <select v-model="adjustmentForm.moduleDetailsLocation" class="field-control text-xs">
                      <option value="">不调整</option>
                      <option value="document_end">文档末尾</option>
                      <option v-for="candidate in activePreview.section_candidates" :key="'module-details-' + candidate.location" :value="anchorAfterLocation(candidate.location)">
                        {{ candidate.location }} / {{ candidate.text }}
                      </option>
                    </select>
                  </div>
                  <div>
                    <label class="field-label text-xs">字段段落</label>
                    <select v-model="adjustmentForm.placeholderLocation" class="field-control text-xs">
                      <option value="">不调整字段</option>
                      <option v-for="option in adjustableParagraphOptions" :key="option.value" :value="option.value">
                        {{ option.label }}
                      </option>
                    </select>
                  </div>
                  <div>
                    <label class="field-label text-xs">替换为占位符</label>
                    <input v-model.trim="adjustmentForm.placeholderToken" type="text" class="field-control font-mono text-xs" placeholder="{{字段名}}" />
                  </div>
                  <div class="md:col-span-2">
                    <label class="field-label text-xs">待替换文本</label>
                    <input v-model.trim="adjustmentForm.placeholderText" type="text" class="field-control text-xs" />
                  </div>
                  <div class="md:col-span-2">
                    <button class="btn-primary min-h-0 px-2 py-1 text-xs" :disabled="adjustmentSavingId === item.id" @click="saveAdjustments(item)">
                      {{ adjustmentSavingId === item.id ? '保存中' : '保存调整' }}
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="activePreview.placeholders.length">
                <p class="text-xs font-semibold text-[var(--color-ink-soft)]">占位符位置</p>
                <div class="mt-2 max-h-48 overflow-auto rounded border border-[var(--color-rule)] bg-[var(--color-surface)]">
                  <div
                    v-for="placeholder in activePreview.placeholders"
                    :key="placeholder.token + placeholder.scope + placeholder.location"
                    class="grid gap-1 border-b border-[var(--color-rule)] px-2 py-1 text-xs text-[var(--color-ink-muted)] last:border-b-0 sm:grid-cols-[8rem_5rem_1fr]"
                  >
                    <span class="font-mono">{{ placeholder.token }}</span>
                    <span>{{ scopeLabel(placeholder.scope) }}</span>
                    <span class="break-all">{{ placeholder.location }} / {{ placeholder.text }}</span>
                  </div>
                </div>
              </div>

              <details>
                <summary class="subtle-link cursor-pointer select-none text-xs">结构摘要</summary>
                <div class="mt-2 space-y-2">
                  <div v-for="scope in activePreview.scopes" :key="scope.scope" class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] p-2">
                    <p class="text-xs font-semibold text-[var(--color-ink-soft)]">{{ scope.label }}</p>
                    <p class="mt-1 text-xs text-[var(--color-ink-muted)]">段落 {{ scope.paragraphs.length }} / 表格 {{ scope.tables.length }}</p>
                    <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
                      <li v-for="paragraph in scope.paragraphs.slice(0, 8)" :key="paragraph.index">
                        {{ paragraph.index }} / {{ paragraph.style }} / {{ paragraph.text }}
                      </li>
                    </ul>
                  </div>
                </div>
              </details>
            </div>

            <div v-if="activeLayoutId === item.id && activeLayout" class="mt-3 space-y-3 border-t border-[var(--color-rule)] pt-3">
              <div class="grid gap-2 text-xs text-[var(--color-ink-muted)] sm:grid-cols-3">
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  页面：{{ activeLayout.page.orientation === 'landscape' ? '横向' : '纵向' }}
                </div>
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  内容块：{{ activeLayout.summary.body_block_count }}
                </div>
                <div class="rounded border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1">
                  占位符：{{ activeLayout.summary.placeholder_count }}
                </div>
              </div>

              <div class="overflow-auto rounded border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
                <div
                  class="mx-auto bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
                  :style="layoutPageStyle(activeLayout)"
                >
                  <div class="border-b border-dashed border-slate-200 pb-2 text-[10px] text-slate-500">
                    <div v-for="block in activeLayout.headers" :key="'h-' + block.kind + block.index" class="truncate">
                      {{ layoutBlockText(block) }}
                    </div>
                  </div>
                  <div class="space-y-2 py-3">
                    <template v-for="block in activeLayout.body" :key="'b-' + block.kind + block.index">
                      <p
                        v-if="block.kind === 'paragraph'"
                        class="text-xs leading-5"
                        :class="block.placeholders.length ? 'font-mono text-emerald-700' : ''"
                        :style="layoutParagraphStyle(block)"
                      >
                        {{ block.text }}
                      </p>
                      <table v-else class="w-full border-collapse text-[10px]">
                        <tbody>
                          <tr v-for="(row, rowIndex) in (block.rows || [])" :key="rowIndex">
                            <td v-for="(cell, cellIndex) in row" :key="cellIndex" class="border border-slate-300 px-1 py-0.5 align-top">
                              {{ cell }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </template>
                  </div>
                  <div class="border-t border-dashed border-slate-200 pt-2 text-[10px] text-slate-500">
                    <div v-for="block in activeLayout.footers" :key="'f-' + block.kind + block.index" class="truncate">
                      {{ layoutBlockText(block) }}
                    </div>
                  </div>
                </div>
              </div>

              <ul class="list-disc space-y-1 pl-5 text-xs text-[var(--color-ink-muted)]">
                <li v-for="item in activeLayout.limitations" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </div>
        <p v-else-if="!draftsLoading" class="mt-3 text-xs text-[var(--color-ink-soft)]">暂无已导入草稿。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, type CSSProperties } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface ImportPlaceholder {
  key: string
  label: string
  token: string
  scope: string
}

interface ImportAnchor {
  key: string
  token: string
  location: string
}

interface ImportResult {
  template_path: string
  manifest_path: string
  template_filename: string
  manifest_filename: string
  detected_placeholders: ImportPlaceholder[]
  inserted_anchors: ImportAnchor[]
  pending_confirmations: string[]
  warnings: string[]
  out_templates_patch: Record<string, string>
}

interface ImportedDraft {
  id: string
  display_name: string
  note: string
  confirmed: boolean
  confirmed_at: string
  published: boolean
  published_at: string
  published_template_path: string
  updated_at: string
  template_path: string
  manifest_path: string
  template_filename: string
  manifest_filename: string
  created_at: number
  size_bytes: number
  ok: boolean
  warnings: string[]
  errors: string[]
  capabilities: Record<string, any>
  out_templates_patch: Record<string, string>
}

interface ImportedDraftsResponse {
  templates?: ImportedDraft[]
}

interface PreviewParagraph {
  index: number
  text: string
  style: string
  placeholders: string[]
}

interface PreviewTable {
  index: number
  row_count: number
  column_count: number
  style: string
  text_preview: string
  placeholders: string[]
}

interface PreviewScope {
  scope: string
  label: string
  paragraphs: PreviewParagraph[]
  tables: PreviewTable[]
}

interface PreviewOccurrence {
  token: string
  scope: string
  location: string
  text: string
}

interface PreviewAnchor extends PreviewOccurrence {
  key: string
}

interface PreviewCandidate {
  scope: string
  location: string
  text: string
  style: string
}

interface ImportedDraftPreview {
  id: string
  metadata: {
    display_name: string
    note: string
    confirmed: boolean
    confirmed_at: string
    updated_at: string
  }
  ok: boolean
  summary: {
    body_paragraph_count: number
    body_table_count: number
    section_count: number
    placeholder_count: number
    anchor_count: number
    section_candidate_count: number
  }
  placeholders: PreviewOccurrence[]
  anchors: PreviewAnchor[]
  section_candidates: PreviewCandidate[]
  scopes: PreviewScope[]
}

interface LayoutBlock {
  kind: 'paragraph' | 'table'
  scope: string
  index: number
  text?: string
  style?: string
  alignment?: string
  left_indent_pt?: number
  row_count?: number
  column_count?: number
  rows?: string[][]
  placeholders: string[]
}

interface ImportedLayoutPreview {
  id: string
  render_mode: string
  ok: boolean
  page: {
    width_pt: number
    height_pt: number
    margin_top_pt: number
    margin_right_pt: number
    margin_bottom_pt: number
    margin_left_pt: number
    orientation: string
  }
  summary: {
    body_block_count: number
    header_block_count: number
    footer_block_count: number
    placeholder_count: number
    truncated: boolean
  }
  headers: LayoutBlock[]
  body: LayoutBlock[]
  footers: LayoutBlock[]
  limitations: string[]
}

interface AdjustmentResponse {
  changed_fields: string[]
  preview: ImportedDraftPreview
}

const emit = defineEmits<{
  apply: [patch: Record<string, string>]
}>()

const selectedFile = ref<File | null>(null)
const loading = ref(false)
const result = ref<ImportResult | null>(null)
const message = ref('')
const ok = ref(true)
const drafts = ref<ImportedDraft[]>([])
const draftsLoading = ref(false)
const draftsMessage = ref('')
const draftsOk = ref(true)
const deletingId = ref('')
const previewLoadingId = ref('')
const layoutLoadingId = ref('')
const activePreviewId = ref('')
const activePreview = ref<ImportedDraftPreview | null>(null)
const activeLayoutId = ref('')
const activeLayout = ref<ImportedLayoutPreview | null>(null)
const metadataEditorId = ref('')
const metadataSavingId = ref('')
const publishingId = ref('')
const adjustmentSavingId = ref('')
const draftEdits = ref<Record<string, { display_name: string; note: string; confirmed: boolean }>>({})
const adjustmentForm = ref({
  moduleTableLocation: '',
  moduleDetailsLocation: '',
  placeholderLocation: '',
  placeholderText: '',
  placeholderToken: '',
})

const statusText = computed(() => {
  if (loading.value) return '导入中'
  if (message.value && !ok.value) return '导入失败'
  if (result.value) return '草稿已生成'
  return '未导入'
})

const statusClass = computed(() => {
  if (loading.value) return 'status-badge--neutral'
  if (message.value && !ok.value) return 'status-badge--warning'
  if (result.value) return 'status-badge--success'
  return 'status-badge--neutral'
})

const adjustableParagraphOptions = computed(() => {
  const preview = activePreview.value
  if (!preview) return []
  const options: Array<{ value: string; label: string }> = []
  for (const scope of preview.scopes) {
    for (const paragraph of scope.paragraphs) {
      options.push({
        value: `${scope.scope}|paragraph:${paragraph.index}`,
        label: `${scopeLabel(scope.scope)} paragraph:${paragraph.index} / ${paragraph.text}`,
      })
    }
  }
  return options
})

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
  result.value = null
  message.value = ''
}

async function importTemplate() {
  if (!selectedFile.value) return
  loading.value = true
  message.value = ''
  result.value = null
  try {
    const form = new FormData()
    form.append('file', selectedFile.value)
    result.value = await apiFetch<ImportResult>('/api/templates/spec/import', {
      method: 'POST',
      body: form,
    })
    ok.value = true
    message.value = '模板草稿已生成'
    await loadDrafts()
  } catch (error) {
    ok.value = false
    message.value = normalizeApiError(error)
  } finally {
    loading.value = false
  }
}

function applyMapping() {
  if (!result.value) return
  emit('apply', result.value.out_templates_patch || {})
}

async function loadDrafts() {
  draftsLoading.value = true
  draftsMessage.value = ''
  try {
    const data = await apiFetch<ImportedDraftsResponse>('/api/templates/spec/imported')
    drafts.value = data.templates || []
    syncDraftEdits()
    draftsOk.value = true
  } catch (error) {
    drafts.value = []
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    draftsLoading.value = false
  }
}

function syncDraftEdits() {
  const next: Record<string, { display_name: string; note: string; confirmed: boolean }> = {}
  for (const item of drafts.value) {
    next[item.id] = draftEdits.value[item.id] || {
      display_name: item.display_name || item.id,
      note: item.note || '',
      confirmed: Boolean(item.confirmed),
    }
  }
  draftEdits.value = next
}

function applyDraft(item: ImportedDraft) {
  emit('apply', item.out_templates_patch || {})
  draftsOk.value = true
  draftsMessage.value = '已应用到模板映射，请保存'
}

async function publishDraft(item: ImportedDraft) {
  publishingId.value = item.id
  draftsMessage.value = ''
  try {
    const published = await apiFetch<{ out_templates_patch: Record<string, string> }>(
      `/api/templates/spec/imported/${encodeURIComponent(item.id)}/publish`,
      { method: 'POST' },
    )
    emit('apply', published.out_templates_patch || {})
    draftsOk.value = true
    draftsMessage.value = '正式模板已发布并应用到模板映射，请保存'
    await loadDrafts()
  } catch (error) {
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    publishingId.value = ''
  }
}

async function deleteDraft(item: ImportedDraft) {
  const confirmed = window.confirm(`确认删除模板草稿 ${item.id}？`)
  if (!confirmed) return
  deletingId.value = item.id
  draftsMessage.value = ''
  try {
    await apiFetch(`/api/templates/spec/imported/${encodeURIComponent(item.id)}`, {
      method: 'DELETE',
    })
    draftsOk.value = true
    draftsMessage.value = '模板草稿已删除'
    await loadDrafts()
  } catch (error) {
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    deletingId.value = ''
  }
}

function toggleMetadataEditor(item: ImportedDraft) {
  if (!draftEdits.value[item.id]) {
    draftEdits.value[item.id] = {
      display_name: item.display_name || item.id,
      note: item.note || '',
      confirmed: Boolean(item.confirmed),
    }
  }
  metadataEditorId.value = metadataEditorId.value === item.id ? '' : item.id
}

async function setDraftConfirmed(item: ImportedDraft, confirmed: boolean) {
  if (!draftEdits.value[item.id]) {
    toggleMetadataEditor(item)
    metadataEditorId.value = ''
  }
  draftEdits.value[item.id].confirmed = confirmed
  await saveDraftMetadata(item)
}

async function saveDraftMetadata(item: ImportedDraft) {
  const edit = draftEdits.value[item.id]
  if (!edit) return
  metadataSavingId.value = item.id
  draftsMessage.value = ''
  try {
    await apiFetch(`/api/templates/spec/imported/${encodeURIComponent(item.id)}/metadata`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(edit),
    })
    draftsOk.value = true
    draftsMessage.value = '模板确认信息已保存'
    await loadDrafts()
  } catch (error) {
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    metadataSavingId.value = ''
  }
}

async function loadPreview(item: ImportedDraft) {
  if (activePreviewId.value === item.id && activePreview.value) {
    activePreviewId.value = ''
    activePreview.value = null
    return
  }
  previewLoadingId.value = item.id
  draftsMessage.value = ''
  try {
    activePreview.value = await apiFetch<ImportedDraftPreview>(
      `/api/templates/spec/imported/${encodeURIComponent(item.id)}/preview`,
    )
    activePreviewId.value = item.id
    resetAdjustmentForm()
    draftsOk.value = true
  } catch (error) {
    activePreview.value = null
    activePreviewId.value = ''
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    previewLoadingId.value = ''
  }
}

async function loadLayoutPreview(item: ImportedDraft) {
  if (activeLayoutId.value === item.id && activeLayout.value) {
    activeLayoutId.value = ''
    activeLayout.value = null
    return
  }
  layoutLoadingId.value = item.id
  draftsMessage.value = ''
  try {
    activeLayout.value = await apiFetch<ImportedLayoutPreview>(
      `/api/templates/spec/imported/${encodeURIComponent(item.id)}/layout-preview`,
    )
    activeLayoutId.value = item.id
    draftsOk.value = true
  } catch (error) {
    activeLayout.value = null
    activeLayoutId.value = ''
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    layoutLoadingId.value = ''
  }
}

async function saveAdjustments(item: ImportedDraft) {
  adjustmentSavingId.value = item.id
  draftsMessage.value = ''
  try {
    const anchors: Record<string, string> = {}
    if (adjustmentForm.value.moduleTableLocation) anchors.module_table = adjustmentForm.value.moduleTableLocation
    if (adjustmentForm.value.moduleDetailsLocation) anchors.module_details = adjustmentForm.value.moduleDetailsLocation
    const placeholders = []
    if (adjustmentForm.value.placeholderLocation && adjustmentForm.value.placeholderToken) {
      const [scope, location] = adjustmentForm.value.placeholderLocation.split('|')
      placeholders.push({
        scope,
        location,
        text: adjustmentForm.value.placeholderText,
        token: adjustmentForm.value.placeholderToken,
      })
    }
    const data = await apiFetch<AdjustmentResponse>(
      `/api/templates/spec/imported/${encodeURIComponent(item.id)}/adjustments`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anchors, placeholders }),
      },
    )
    activePreview.value = data.preview
    activePreviewId.value = item.id
    draftsOk.value = true
    draftsMessage.value = data.changed_fields.length ? '模板草稿调整已保存，确认状态已重置' : '没有可保存的调整'
    resetAdjustmentForm()
    await loadDrafts()
  } catch (error) {
    draftsOk.value = false
    draftsMessage.value = normalizeApiError(error)
  } finally {
    adjustmentSavingId.value = ''
  }
}

function resetAdjustmentForm() {
  adjustmentForm.value = {
    moduleTableLocation: '',
    moduleDetailsLocation: '',
    placeholderLocation: '',
    placeholderText: '',
    placeholderToken: '',
  }
}

function scopeLabel(scope: string) {
  return {
    body: '正文',
    tables: '表格',
    headers: '页眉',
    footers: '页脚',
  }[scope] || scope
}

function anchorLocationLabel(location: string) {
  if (location === 'existing') return '模板已有'
  if (location === 'document_end') return '文档末尾'
  if (location.startsWith('after:')) return `位于 ${location.slice(6)} 之后`
  return location
}

function anchorAfterLocation(location: string) {
  return location.startsWith('paragraph:') ? `after:${location}` : ''
}

function draftDownloadUrl(item: ImportedDraft, filename: string) {
  return `/api/templates/spec/imported/${encodeURIComponent(item.id)}/${encodeURIComponent(filename)}`
}

function anchorModeLabel(mode: unknown) {
  return {
    split: '拆分锚点',
    full: '完整章节锚点',
    legacy_full: '历史完整锚点',
    optional: '可选锚点',
  }[String(mode)] || '锚点已配置'
}

function moduleColumnCount(item: ImportedDraft) {
  const moduleTable = item.capabilities?.module_table
  return Number(moduleTable?.column_count || 0)
}

function formatBytes(value: number) {
  if (!Number.isFinite(value)) return '-'
  if (value < 1024) return `${value} B`
  return `${(value / 1024).toFixed(1)} KB`
}

function layoutPageStyle(layout: ImportedLayoutPreview) {
  const maxWidth = 520
  const width = Math.min(maxWidth, Math.max(280, layout.page.width_pt * 0.62))
  const ratio = layout.page.height_pt > 0 ? layout.page.height_pt / layout.page.width_pt : 1.414
  return {
    width: `${width}px`,
    minHeight: `${Math.min(760, Math.max(360, width * ratio))}px`,
    padding: `${Math.max(18, layout.page.margin_top_pt * 0.22)}px ${Math.max(18, layout.page.margin_right_pt * 0.22)}px ${Math.max(18, layout.page.margin_bottom_pt * 0.22)}px ${Math.max(18, layout.page.margin_left_pt * 0.22)}px`,
  }
}

function layoutParagraphStyle(block: LayoutBlock): CSSProperties {
  return {
    textAlign: (block.alignment || 'left') as CSSProperties['textAlign'],
    marginLeft: `${Math.min(block.left_indent_pt || 0, 36)}px`,
  }
}

function layoutBlockText(block: LayoutBlock) {
  if (block.kind === 'table') return `表格 ${block.row_count || 0} x ${block.column_count || 0}`
  return block.text || ''
}

loadDrafts()
</script>
