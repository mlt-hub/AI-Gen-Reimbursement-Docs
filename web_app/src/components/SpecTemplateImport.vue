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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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

const emit = defineEmits<{
  apply: [patch: Record<string, string>]
}>()

const selectedFile = ref<File | null>(null)
const loading = ref(false)
const result = ref<ImportResult | null>(null)
const message = ref('')
const ok = ref(true)

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
</script>
