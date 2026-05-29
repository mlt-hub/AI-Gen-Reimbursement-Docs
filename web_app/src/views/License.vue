<template>
  <div class="mx-auto box-border w-full max-w-3xl space-y-6 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold">授权状态</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">检查受保护数据包、公钥和本机激活元数据。</p>
        </div>
        <button class="btn-secondary w-fit" :disabled="loadingStatus" @click="loadStatus">
          {{ loadingStatus ? '检查中...' : '刷新' }}
        </button>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div v-for="item in statusItems" :key="item.label" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2">
          <div class="flex min-w-0 items-center justify-between gap-3">
            <span class="min-w-0 text-sm text-[var(--color-ink-muted)]">{{ item.label }}</span>
            <span :class="['shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold', item.className]">{{ item.value }}</span>
          </div>
        </div>
      </div>

      <dl v-if="status" class="mt-4 space-y-2 text-xs text-[var(--color-ink-soft)]">
        <div v-for="item in pathItems" :key="item.label" class="grid gap-1 sm:grid-cols-[8rem_1fr]">
          <dt class="font-semibold text-[var(--color-ink-muted)]">{{ item.label }}</dt>
          <dd class="min-w-0 break-all font-mono">{{ item.value }}</dd>
        </div>
      </dl>

      <p v-if="statusError" class="mt-3 text-sm text-[var(--color-danger)]">{{ statusError }}</p>
    </section>

    <section class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <h2 class="text-lg font-semibold">离线激活</h2>
        <p class="mt-1 text-sm text-[var(--color-ink-muted)]">输入客户 license 文件路径和 license secret。</p>
      </div>

      <form class="space-y-4" @submit.prevent="submitActivation">
        <div
          :class="['rounded-lg border border-dashed p-4 transition-colors', dragActive ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)]' : 'border-[var(--color-rule-strong)] bg-[var(--color-surface)]']"
          @dragenter.prevent="dragActive = true"
          @dragover.prevent="dragActive = true"
          @dragleave.prevent="dragActive = false"
          @drop.prevent="handleDrop"
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <label class="field-label text-xs">选择 license.ard.json</label>
              <p class="text-sm text-[var(--color-ink-muted)]">拖入文件，或从本机选择 license JSON。</p>
            </div>
            <input class="field-control sm:max-w-xs" type="file" accept=".json,application/json" @change="handleLicenseFile" />
          </div>
          <p v-if="selectedFileName" class="mt-2 text-xs text-[var(--color-ink-soft)]">{{ selectedFileName }}</p>
          <p v-if="licenseValidationMessage" :class="['mt-2 text-sm', licenseValidationOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">
            {{ licenseValidationMessage }}
          </p>
        </div>
        <div>
          <label class="field-label text-xs">license 文件路径</label>
          <input v-model.trim="form.license_path" class="field-control font-mono" type="text" />
        </div>
        <div>
          <div class="flex items-center justify-between gap-3">
            <label class="field-label text-xs">license secret</label>
            <button type="button" class="btn-quiet min-h-0 px-2 py-1 text-xs" @click="showSecret = !showSecret">
              {{ showSecret ? '隐藏' : '显示' }}
            </button>
          </div>
          <input v-model.trim="form.license_secret" :type="showSecret ? 'text' : 'password'" class="field-control font-mono" />
        </div>

        <details class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
          <summary class="cursor-pointer text-sm font-semibold text-[var(--color-ink-muted)]">高级路径</summary>
          <div class="mt-3 space-y-3">
            <div>
              <label class="field-label text-xs">data.enc</label>
              <input v-model.trim="form.data_enc" class="field-control font-mono" type="text" :placeholder="status?.paths.data_enc || ''" />
            </div>
            <div>
              <label class="field-label text-xs">data 输出目录</label>
              <input v-model.trim="form.data_output" class="field-control font-mono" type="text" :placeholder="status?.paths.data_output || ''" />
            </div>
            <div>
              <label class="field-label text-xs">public_key.pem</label>
              <input v-model.trim="form.public_key" class="field-control font-mono" type="text" :placeholder="status?.paths.public_key || ''" />
            </div>
            <div>
              <label class="field-label text-xs">激活元数据</label>
              <input v-model.trim="form.activation_path" class="field-control font-mono" type="text" :placeholder="status?.paths.activation_metadata || ''" />
            </div>
          </div>
        </details>

        <div v-if="readinessMessages.length" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
          <p v-for="message in readinessMessages" :key="message" class="text-sm text-[var(--color-warning)]">{{ message }}</p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button class="btn-primary" type="submit" :disabled="activating || !canSubmit">
            {{ activating ? '激活中...' : '激活' }}
          </button>
          <span v-if="activateMessage" :class="['text-sm', activateOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">
            {{ activateMessage }}
          </span>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { apiFetch, normalizeApiError } from '@/lib/api.ts'

interface LicensePaths {
  data_enc: string
  data_output: string
  public_key: string
  activation_metadata: string
}

interface LicenseStatus {
  activated: boolean
  crypto_available: boolean
  data_package_present: boolean
  public_key_present: boolean
  activation_metadata_present: boolean
  paths: LicensePaths
}

interface ActivateResponse {
  ok: boolean
  license_id: string
  customer: string
  activation_path: string
  data_output: string
}

const status = ref<LicenseStatus | null>(null)
const loadingStatus = ref(false)
const statusError = ref('')
const activating = ref(false)
const activateMessage = ref('')
const activateOk = ref(false)
const showSecret = ref(false)
const selectedFileName = ref('')
const dragActive = ref(false)
const licenseValidationMessage = ref('')
const licenseValidationOk = ref(false)

const form = reactive({
  license_path: '',
  license_text: '',
  license_secret: '',
  data_enc: '',
  data_output: '',
  public_key: '',
  activation_path: '',
})

const canSubmit = computed(() => (form.license_path.length > 0 || form.license_text.length > 0) && form.license_secret.length > 0)

const readinessMessages = computed(() => {
  const current = status.value
  if (!current) return []
  const messages: string[] = []
  if (!current.crypto_available) messages.push('当前运行环境缺少 cryptography，无法执行离线激活。')
  if (!current.data_package_present && !form.data_enc) messages.push('未发现 data.enc，请确认发布包包含受保护数据包，或在高级路径中指定。')
  if (!current.public_key_present && !form.public_key) messages.push('未发现 public_key.pem，请确认发布包包含公钥，或在高级路径中指定。')
  return messages
})

const statusItems = computed(() => {
  const current = status.value
  return [
    statusItem('激活状态', current?.activated === true),
    statusItem('加密依赖', current?.crypto_available === true),
    statusItem('数据包', current?.data_package_present === true),
    statusItem('公钥', current?.public_key_present === true),
    statusItem('激活元数据', current?.activation_metadata_present === true),
  ]
})

const pathItems = computed(() => {
  if (!status.value) return []
  return [
    { label: 'data.enc', value: status.value.paths.data_enc },
    { label: 'data 目录', value: status.value.paths.data_output },
    { label: '公钥', value: status.value.paths.public_key },
    { label: '激活元数据', value: status.value.paths.activation_metadata },
  ]
})

function statusItem(label: string, ok: boolean) {
  return {
    label,
    value: ok ? '正常' : '未就绪',
    className: ok
      ? 'bg-[var(--color-success-soft)] text-[var(--color-success)]'
      : 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  }
}

async function loadStatus() {
  loadingStatus.value = true
  statusError.value = ''
  try {
    status.value = await apiFetch<LicenseStatus>('/api/license/status')
  } catch (error) {
    statusError.value = normalizeApiError(error)
  } finally {
    loadingStatus.value = false
  }
}

async function submitActivation() {
  if (!canSubmit.value) return
  if (form.license_text && !validateLicenseText(form.license_text)) return
  activating.value = true
  activateMessage.value = ''
  activateOk.value = false

  try {
    const result = await apiFetch<ActivateResponse>('/api/license/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    activateOk.value = true
    activateMessage.value = `激活成功：${result.license_id} / ${result.customer}`
    await loadStatus()
  } catch (error) {
    activateMessage.value = friendlyActivationError(normalizeApiError(error))
  } finally {
    activating.value = false
  }
}

async function applyLicenseFile(file: File) {
  selectedFileName.value = file.name
  form.license_text = await file.text()
  form.license_path = ''
  validateLicenseText(form.license_text)
}

function validateLicenseText(text: string) {
  licenseValidationMessage.value = ''
  licenseValidationOk.value = false
  try {
    const doc = JSON.parse(text)
    const payload = doc?.payload
    const signature = doc?.signature
    const missing = []
    if (payload?.format !== 'ard-license-v1') missing.push('payload.format')
    if (!payload?.license_id) missing.push('payload.license_id')
    if (!payload?.customer) missing.push('payload.customer')
    if (!payload?.data_hash) missing.push('payload.data_hash')
    if (!payload?.wrapped_key) missing.push('payload.wrapped_key')
    if (signature?.alg !== 'Ed25519') missing.push('signature.alg')
    if (!signature?.value) missing.push('signature.value')
    if (missing.length) {
      licenseValidationMessage.value = `license 结构不完整：${missing.join('、')}`
      return false
    }
    licenseValidationOk.value = true
    licenseValidationMessage.value = `license 已读取：${payload.license_id} / ${payload.customer}`
    return true
  } catch {
    licenseValidationMessage.value = 'license 文件不是有效 JSON'
    return false
  }
}

function friendlyActivationError(message: string) {
  if (message.includes('expired')) return '授权已过期，请联系发行方重新签发 license。'
  if (message.includes('does not match data package')) return '授权文件与当前 data.enc 不匹配，请确认版本一致。'
  if (message.includes('failed to unwrap CEK')) return 'license secret 不正确，无法解开数据密钥。'
  if (message.includes('invalid license signature')) return '授权文件签名无效，文件可能被修改或公钥不匹配。'
  if (message.includes('data.enc 不存在')) return message
  if (message.includes('公钥文件不存在')) return message
  if (message.includes('cryptography')) return message
  return message
}

async function handleLicenseFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    selectedFileName.value = ''
    form.license_text = ''
    licenseValidationMessage.value = ''
    licenseValidationOk.value = false
    return
  }
  await applyLicenseFile(file)
}

async function handleDrop(event: DragEvent) {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  await applyLicenseFile(file)
}

onMounted(loadStatus)
</script>
