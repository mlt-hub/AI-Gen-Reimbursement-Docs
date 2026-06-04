# Web UI 重构详细设计

> 基于 [web-ui-refactoring-plan.md](./web-ui-refactoring-plan.md) 展开，包含具体的文件结构、接口定义、组件 API 和迁移步骤。

---

## 目录

1. [目标文件结构](#1-目标文件结构)
2. [API 层设计](#2-api-层设计)
3. [数据查询层 —— @tanstack/vue-query](#3-数据查询层--tanstackvue-query)
4. [基础 UI 组件设计](#4-基础-ui-组件设计)
5. [Home.vue 拆分设计](#5-homevue-拆分设计)
6. [Store 拆分设计](#6-store-拆分设计)
7. [路由守卫设计](#7-路由守卫设计)
8. [错误边界设计](#8-错误边界设计)
9. [暗色模式设计](#9-暗色模式设计)
10. [测试体系设计](#10-测试体系设计)

---

## 1. 目标文件结构

```
web_app/src/
├── api/                          # 【新增】API 层
│   ├── client.ts                 #   apiFetch 基础封装（从 lib/api.ts 迁移）
│   ├── types.ts                  #   共享请求/响应类型
│   ├── tasks.ts                  #   任务启动/取消/继续
│   ├── sessions.ts               #   会话状态查询
│   ├── config.ts                 #   模式列表/FPA选项/健康检查
│   ├── ai.ts                     #   AI 交互日志
│   └── artifacts.ts              #   产物下载/打开目录
│
├── composables/
│   ├── useFpaOptions.ts          # 【保留，改用 vue-query 内部实现】
│   ├── useSensitiveInputGuard.ts # 【保留，不变】
│   ├── useTaskRunner.ts          # 【新增】从 Home.vue 抽取
│   ├── useSessionRestore.ts      # 【新增】从 Home.vue 抽取
│   └── useDarkMode.ts            # 【新增】暗色模式
│
├── components/
│   ├── ui/                       # 【新增】基础 UI 组件
│   │   ├── BaseButton.vue
│   │   ├── BaseInput.vue
│   │   ├── BaseSelect.vue
│   │   ├── BaseModal.vue
│   │   ├── BaseToast.vue
│   │   ├── BaseBadge.vue
│   │   └── BaseCard.vue
│   ├── layout/                   # 【新增】布局组件
│   │   ├── AppHeader.vue         #   从 App.vue 抽取顶栏
│   │   └── ErrorBoundary.vue
│   ├── modals/                   # 【新增】业务弹窗
│   │   ├── FpaInputModal.vue     #   从 Home.vue 抽取
│   │   ├── ListConfirmModal.vue  #   从 Home.vue 抽取
│   │   └── AiInteractionModal.vue #  从 Home.vue 抽取
│   ├── ConfigPanel.vue           # 【保留】
│   ├── GenerationProgress.vue    # 【保留】
│   ├── LogViewer.vue             # 【保留】
│   ├── StepsBar.vue              # 【保留】
│   ├── ActionBar.vue             # 【保留】
│   ├── FileInput.vue             # 【保留】
│   ├── AdvancedOptions.vue       # 【保留】
│   ├── FpaPreview.vue            # 【保留】
│   ├── PreviewLayout.vue         # 【保留】
│   ├── TemplateUpload.vue        # 【保留】
│   ├── TemplateDownload.vue      # 【保留】
│   └── Toast.vue                 # 【保留，重构为 BaseToast 驱动】
│
├── stores/
│   ├── auth.ts                   # 【保留】
│   ├── config.ts                 # 【精简，抽取工具函数】
│   ├── session.ts                # 【保留】
│   ├── log.ts                    # 【保留】
│   ├── steps.ts                  # 【保留】
│   └── toast.ts                  # 【保留】
│
├── lib/
│   ├── api.ts                    # 【迁移到 api/client.ts】
│   ├── storage.ts                # 【新增】localStorage/sessionStorage 封装
│   ├── settings-io.ts            # 【新增】导入导出逻辑
│   └── api-key.ts                # 【新增】API Key 安全过滤
│
├── router/
│   ├── index.ts                  # 【精简，仅路由定义】
│   └── guards.ts                 # 【新增】导航守卫
│
├── views/                        # 【全部保留，精简 Home.vue】
│   ├── Home.vue
│   ├── Config.vue
│   ├── History.vue
│   ├── License.vue
│   ├── Login.vue
│   ├── FpaPreviewPage.vue
│   └── PromptDebug.vue
│
├── App.vue                       # 【精简，抽取 AppHeader + ErrorBoundary】
└── main.ts                       # 【不变】
```

---

## 2. API 层设计

### 2.1 基础客户端 `api/client.ts`

```typescript
// 从 lib/api.ts 迁移，行为不变
// 新增：泛型约束、超时支持、可取消请求

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { ... }
}

// 核心方法（现有逻辑不变）
export async function apiFetch<T = unknown>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<T> { ... }

// 新增：带超时的请求
export async function apiFetchWithTimeout<T = unknown>(
  input: RequestInfo | URL,
  timeoutMs: number,
  init?: RequestInit
): Promise<T> { ... }

// 保留
export function normalizeApiError(error: unknown): string { ... }
```

### 2.2 共享类型 `api/types.ts`

```typescript
// ── 任务相关 ──

export interface RunTaskRequest {
  mode: PipelineMode
  api_key?: string
  model?: string
  base_url?: string
  max_tokens?: string
  project_name?: string
  fpa_profile?: string
  fpa_strategy?: string
  fpa_rule_set?: string
  clean?: boolean
  xlsx_path?: string       // 本地模式
  output_dir?: string       // 本地模式
  file?: File               // 远程模式
}

export interface RunTaskResponse {
  session_id: string
  output_dir?: string
}

export interface ContinueRequest {
  field: string
  fpa_reduced: number
  cfp_total?: number
}

// ── 会话相关 ──

export type RunState = 'idle' | 'running' | 'done' | 'error' | 'cancelled'

export interface SessionStatus {
  session_id: string
  mode: 'local' | 'remote'
  run_state: RunState
  output_dir?: string
  done_files?: DoneFile[]
  progress_steps?: Record<string, StepProgress>
}

export interface DoneFile {
  label: string
  path: string
  size_kb: number
  is_temp: boolean
}

// ── 配置相关 ──

export interface PipelineModeInfo {
  label: string
  desc: string
}

export interface FpaOptions { ... }     // 已定义在 useFpaOptions.ts

export interface HealthResponse {
  ok?: boolean
  version?: string
  work_mode?: string
}

// ── AI 交互 ──

export interface AiInteraction {
  name: string
  type: 'prompt' | 'response'
  content: string
}

export interface AiLogResponse {
  content?: string
}

// ── 通用 ──

export interface VersionResponse { version?: string }
export interface WorkModeResponse { work_mode?: string }
```

### 2.3 各领域 API 模块

#### `api/tasks.ts`

```typescript
import { apiFetch } from './client'
import type { RunTaskResponse, ContinueRequest } from './types'

/** 启动本地任务 */
export function runLocalTask(form: FormData): Promise<RunTaskResponse> {
  return apiFetch('/api/run-local', { method: 'POST', body: form })
}

/** 启动远程任务（上传文件） */
export function runUploadTask(form: FormData): Promise<RunTaskResponse> {
  return apiFetch('/api/run-upload', { method: 'POST', body: form })
}

/** 继续任务（响应输入提示） */
export function continueTask(sessionId: string, data: ContinueRequest): Promise<void> {
  return apiFetch(`/api/continue/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

/** 取消任务 */
export function cancelTask(sessionId: string): Promise<void> {
  return apiFetch(`/api/cancel/${sessionId}`, { method: 'POST' })
}
```

#### `api/sessions.ts`

```typescript
import { apiFetch } from './client'
import type { SessionStatus } from './types'

/** 获取会话状态（用于恢复） */
export function getSessionStatus(sessionId: string): Promise<SessionStatus> {
  return apiFetch(`/api/sessions/${sessionId}`)
}
```

#### `api/config.ts`

```typescript
import { apiFetch } from './client'
import type { PipelineModeInfo, FpaOptions, HealthResponse } from './types'

export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/api/health')
}

export function getModes(): Promise<Record<string, PipelineModeInfo>> {
  return apiFetch('/api/modes')
}

export function getFpaOptions(): Promise<FpaOptions> {
  return apiFetch('/api/fpa/options')
}

export function getVersion(): Promise<{ version?: string }> {
  return apiFetch('/api/version')
}
```

#### `api/ai.ts`

```typescript
import { apiFetch } from './client'
import type { AiInteraction, AiLogResponse } from './types'

export function getAiInteractions(sessionId: string): Promise<{ interactions: AiInteraction[] }> {
  return apiFetch(`/api/ai-interactions/${sessionId}`)
}

export function getAiLog(sessionId: string): Promise<AiLogResponse> {
  return apiFetch(`/api/ai-log/${sessionId}`)
}
```

---

## 3. 数据查询层 —— @tanstack/vue-query

### 3.1 安装与配置

```bash
npm add @tanstack/vue-query
```

`main.ts` 中注册：

```typescript
import { VueQueryPlugin } from '@tanstack/vue-query'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 30_000,       // 30 秒内不重新请求
        retry: 1,                // 失败重试 1 次
        refetchOnWindowFocus: true,
      },
    },
  },
})
app.mount('#app')
```

### 3.2 关键查询/变更设计

#### 会话状态轮询

```typescript
// composables/useSessionStatus.ts（或在组件内直接使用）

import { useQuery } from '@tanstack/vue-query'
import { getSessionStatus } from '@/api/sessions'
import { computed } from 'vue'

export function useSessionStatus(sessionId: Ref<string | null>) {
  const enabled = computed(() => !!sessionId.value)

  return useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSessionStatus(sessionId.value!),
    enabled,
    refetchInterval: (query) => {
      // 运行中或等待输入时持续轮询；完成/出错/取消后停止
      const state = query.state.data?.run_state
      if (state === 'running') return 2000
      return false
    },
    staleTime: 1000,
  })
}
```

#### 任务启动

```typescript
// 在 useTaskRunner.ts 中

import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { runLocalTask, runUploadTask } from '@/api/tasks'

export function useStartTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      mode: 'local' | 'remote'
      formData: FormData
    }) => {
      if (params.mode === 'local') return runLocalTask(params.formData)
      return runUploadTask(params.formData)
    },
    onSuccess: (data) => {
      // 启动成功后立即触发会话状态查询
      queryClient.invalidateQueries({ queryKey: ['session', data.session_id] })
    },
  })
}
```

#### 模式列表 / FPA 选项（替代当前 ConfigPanel 和 useFpaOptions 中的手写逻辑）

```typescript
// 全局只需定义 queryOptions，InfiniteQuery 不需要

import { useQuery } from '@tanstack/vue-query'
import { getModes, getFpaOptions, getHealth } from '@/api/config'

export function useModesQuery() {
  return useQuery({
    queryKey: ['modes'],
    queryFn: getModes,
    staleTime: 5 * 60 * 1000, // 5 分钟内不重新获取
    placeholderData: FALLBACK_MODES,  // 加载时用前端 fallback 占位
  })
}

export function useFpaOptionsQuery() {
  return useQuery({
    queryKey: ['fpa-options'],
    queryFn: getFpaOptions,
    staleTime: 5 * 60 * 1000,
    placeholderData: FALLBACK_FPA_OPTIONS,
  })
}

export function useHealthQuery() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    staleTime: 30_000,
  })
}
```

#### AI 交互日志

```typescript
import { useQuery } from '@tanstack/vue-query'
import { getAiInteractions, getAiLog } from '@/api/ai'

export function useAiInteractions(sessionId: Ref<string | null>) {
  return useQuery({
    queryKey: ['ai-interactions', sessionId],
    queryFn: () => getAiInteractions(sessionId.value!),
    enabled: computed(() => !!sessionId.value),
  })
}

export function useAiCombinedLog(sessionId: Ref<string | null>) {
  return useQuery({
    queryKey: ['ai-log', sessionId],
    queryFn: () => getAiLog(sessionId.value!),
    enabled: computed(() => !!sessionId.value),
  })
}
```

### 3.3 迁移对照

| 当前实现 | 迁移后 |
|----------|--------|
| `ConfigPanel.vue` 内 `onMounted` + `apiFetch('/api/modes')` | `useModesQuery()` |
| `useFpaOptions.ts` 手写 loading/error/pending 状态机 | `useFpaOptionsQuery()` |
| `App.vue` 内 `onMounted` 调 3 个 API + `loadLegacyBackendState()` | `useHealthQuery()` + `onSuccess` 回调 |
| `Home.vue` 内 `loadAIList()` / `loadAICombined()` | `useAiInteractions()` / `useAiCombinedLog()` |
| `Home.vue` 内 `startTask()` 手动组装 FormData | `useStartTask()` mutation |

---

## 4. 基础 UI 组件设计

### 4.1 设计原则

- **零依赖**：基于现有 Tailwind + CSS 变量体系，不引入第三方 UI 库
- **渐进迁移**：新组件先建好，旧页面逐步替换，不强制一次全改
- **单向数据流**：Props 入，Events 出，遵循 Vue 3 `v-model` 惯例
- **无障碍**：每个组件至少保证 `focus-visible`、`role`、`aria-label` 的基本支持

### 4.2 BaseButton

```typescript
// Props
interface BaseButtonProps {
  variant?: 'primary' | 'secondary' | 'danger' | 'quiet'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  block?: boolean         // 是否占满宽度
}

// Slots: default（按钮文字）
// Emits: click

// 使用示例
<BaseButton variant="primary" :loading="isPending" @click="handleSubmit">
  开始生成
</BaseButton>
```

映射关系（现有多 CSS class → 组件 prop）：

| 当前写法 | 迁移后 |
|----------|--------|
| `class="btn-primary w-full text-base"` | `<BaseButton variant="primary" block size="lg">` |
| `class="btn-quiet min-h-0 px-2 py-1 text-xs"` | `<BaseButton variant="quiet" size="sm">` |
| `class="btn-secondary min-h-0 shrink-0 px-2 py-1 text-xs"` | `<BaseButton variant="secondary" size="sm">` |

### 4.3 BaseInput

```typescript
// Props
interface BaseInputProps {
  modelValue: string | number
  label?: string
  type?: 'text' | 'number' | 'password' | 'email'
  placeholder?: string
  error?: string          // 错误提示文案
  disabled?: boolean
  readonly?: boolean
  name?: string
  autocomplete?: string   // 敏感输入场景需要
  step?: string           // type="number" 时
  min?: number
}

// Slots: hint（label 旁的提示文字）
// Emits: update:modelValue, blur, focus, keyup

// 使用示例
<BaseInput
  v-model="fpaInputValue"
  label="FPA核减后的工作量（人/天）"
  type="number"
  step="0.1"
  min="0"
  @keyup.enter="submitFpaInput"
/>
```

映射关系：

| 当前写法 | 迁移后 |
|----------|--------|
| `<label class="field-label">` + `<input class="field-control">` | `<BaseInput>` 内含 label + input |
| `<input v-model.number="..." class="field-control">` | `<BaseInput v-model="..." type="number">` |

### 4.4 BaseSelect

```typescript
// Props
interface BaseSelectProps {
  modelValue: string
  label?: string
  options: Record<string, { label: string; desc?: string }>
  disabled?: boolean
  showDesc?: boolean       // 选中后是否显示 desc 提示
}

// Slots: hint
// Emits: update:modelValue

// 使用示例
<BaseSelect
  v-model="config.pipelineMode"
  label="操作模式"
  :options="modes"
  showDesc
/>
```

### 4.5 BaseModal

```typescript
// Props
interface BaseModalProps {
  open: boolean
  title: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  closable?: boolean        // 是否允许点击遮罩关闭
  persistent?: boolean      // 是否阻止 ESC 关闭
}

// Slots: default（主体内容），footer（底部按钮区）
// Emits: close

// 使用示例
<BaseModal
  :open="aiModalOpen"
  title="AI 交互记录"
  size="xl"
  @close="aiModalOpen = false"
>
  <template #default>
    <!-- 内容 -->
  </template>
</BaseModal>
```

### 4.6 BaseBadge

```typescript
// Props
interface BaseBadgeProps {
  variant: 'neutral' | 'accent' | 'success' | 'danger' | 'warning'
  size?: 'sm' | 'md'
  dot?: boolean             // 是否显示圆点
}

// Slots: default
```

映射关系（消除组件内大量重复的状态样式函数）：

| 当前写法 | 迁移后 |
|----------|--------|
| `statusClass()` / `badgeClass()` / `cardClass()` 等函数 | `<BaseBadge variant="success">` |
| `runStateClass` / `runDotClass` computed | `<BaseBadge variant="accent" dot>运行中</BaseBadge>` |

### 4.7 BaseCard

```typescript
// Props
interface BaseCardProps {
  border?: 'neutral' | 'accent' | 'success' | 'danger' | 'warning'
  padding?: 'sm' | 'md' | 'lg'
}

// Slots: default, header, footer
```

---

## 5. Home.vue 拆分设计

### 5.1 拆分前后对比

```
拆分前: Home.vue (424 行)
  ├── 模板: 左右布局 + 3 个 Teleport 弹窗 + AI 交互弹窗（含 Tab/展开）
  ├── 脚本: 4 个接口定义 + startTask + restoreLastSession
  │         + submitFpaInput + submitListInput + cancelTask
  │         + openAIModal + loadAIList + loadAICombined + resetTask
  │         + 5 个 computed (runTitle/runStateText/runStateClass/runDotClass)
  └── 总计: 约 15 个函数/方法

拆分后:

Home.vue (~120 行)                  ← 纯编排
  ├── 模板: 左右布局，引用子组件
  ├── 脚本: 仅子组件引用 + Composable 调用
  └── Props/Emits: 无（路由页面）

modals/FpaInputModal.vue (~60 行)   ← 从 Home.vue 抽取
modals/ListConfirmModal.vue (~60 行)
modals/AiInteractionModal.vue (~120 行)

composables/useTaskRunner.ts (~80 行)     ← 从 Home.vue 抽取
composables/useSessionRestore.ts (~50 行)
```

### 5.2 各抽取模块签名

#### `composables/useTaskRunner.ts`

```typescript
export function useTaskRunner() {
  const { mutate: startTask, isPending: isStarting } = useStartTask()

  async function run() {
    // 组装 FormData（原 startTask 逻辑）
    // 校验必填字段
    // 调用 mutate
    // 成功后: session.start(), localStorage.setItem(LAST_SESSION_KEY), log.connect()
  }

  async function cancel() {
    // 原 cancelTask 逻辑
  }

  return { run, cancel, isStarting }
}
```

#### `composables/useSessionRestore.ts`

```typescript
export function useSessionRestore() {
  const { data: status } = useQuery({
    queryKey: ['session', lastSessionId],
    queryFn: () => getSessionStatus(lastSessionId.value!),
    enabled: computed(() => !!lastSessionId.value),
  })

  // watch status → session.restore() / steps.applySnapshot() / log.append()
  // 原 restoreLastSession 逻辑

  return { isRestoring }
}
```

#### `components/modals/FpaInputModal.vue`

```typescript
// Props
interface FpaInputModalProps {
  open: boolean
  sessionId: string
  prompt: InputPrompt | null
}

// Emits: confirm(value: number), cancel
```

#### `components/modals/ListConfirmModal.vue`

```typescript
// Props
interface ListConfirmModalProps {
  open: boolean
  sessionId: string
  prompt: ListPrompt | null
}

// Emits: confirm(fpaReduced: number, cfpTotal: number), cancel
```

#### `components/modals/AiInteractionModal.vue`

```typescript
// Props
interface AiInteractionModalProps {
  open: boolean
  sessionId: string | null
}

// Emits: close
// 内部使用 useAiInteractions / useAiCombinedLog
```

### 5.3 拆分后 Home.vue 示意

```vue
<template>
  <div class="box-border flex h-full max-w-full flex-col gap-4 ...">
    <aside class="surface ...">
      <ConfigPanel @start="taskRunner.run()" />
    </aside>

    <div class="surface flex min-h-[420px] ...">
      <ExecutionHeader />          <!-- runTitle/runState badge -->
      <GenerationProgress />
      <LogViewerSection />
      <ActionBar @ai="aiModalOpen = true" @reset="resetTask" />
    </div>

    <FpaInputModal
      :open="!!session.inputPrompt"
      :session-id="session.sessionId"
      :prompt="session.inputPrompt"
      @confirm="taskRunner.confirmFpa"
      @cancel="taskRunner.cancel"
    />

    <ListConfirmModal
      :open="!!session.listPrompt"
      :session-id="session.sessionId"
      :prompt="session.listPrompt"
      @confirm="taskRunner.confirmList"
      @cancel="taskRunner.cancel"
    />

    <AiInteractionModal
      :open="aiModalOpen"
      :session-id="session.sessionId"
      @close="aiModalOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useTaskRunner } from '@/composables/useTaskRunner'
import { useSessionRestore } from '@/composables/useSessionRestore'
import ConfigPanel from '@/components/ConfigPanel.vue'
import GenerationProgress from '@/components/GenerationProgress.vue'
import LogViewer from '@/components/LogViewer.vue'
import ActionBar from '@/components/ActionBar.vue'
import FpaInputModal from '@/components/modals/FpaInputModal.vue'
import ListConfirmModal from '@/components/modals/ListConfirmModal.vue'
import AiInteractionModal from '@/components/modals/AiInteractionModal.vue'

const session = useSessionStore()
const config = useConfigStore()
const taskRunner = useTaskRunner()
const { isRestoring } = useSessionRestore()

const aiModalOpen = ref(false)

function resetTask() {
  session.reset()
  // log.clear() / steps.reset() — 由 taskRunner 内部处理
}

onMounted(() => {
  // 会话恢复由 useSessionRestore 自动处理
})
</script>
```

---

## 6. Store 拆分设计

### 6.1 `config.ts` → 精简约 30%

| 当前 | 迁移到 | 说明 |
|------|--------|------|
| `loadStr / saveStr / loadBool / saveBool / removeLocalStr / removeSessionStr` | `lib/storage.ts` | 通用 localStorage 封装 |
| `normalizeApiKeyInput` | `lib/api-key.ts` | API Key 安全过滤 |
| `exportSettings / importSettings` | `lib/settings-io.ts` | 导入导出逻辑 |
| `API_KEY_PLACEHOLDERS` | `lib/api-key.ts` | 常量 |
| 10 个 `watch(... saveStr)` | Store 内保留，但改用 `lib/storage.ts` 的 `createPersistedRef` 工具 |

#### `lib/storage.ts` 设计

```typescript
// 类型安全的 localStorage 封装
export function loadStr(key: string, fallback: string): string
export function saveStr(key: string, val: string): void
export function loadBool(key: string, fallback: boolean): boolean
export function saveBool(key: string, val: boolean): void
export function loadJson<T>(key: string, fallback: T): T
export function saveJson<T>(key: string, val: T): void
export function remove(key: string): void

// 便捷方法：创建自动持久化的 ref（减少 Store 中的 watch 样板）
export function createPersistedRef<T>(
  key: string,
  fallback: T,
  options?: {
    serialize?: (v: T) => string
    deserialize?: (s: string) => T
    storage?: Storage  // 默认 localStorage
  }
): Ref<T>
```

#### `lib/api-key.ts` 设计

```typescript
export const API_KEY_PLACEHOLDERS: ReadonlySet<string>

/** 识别占位符/假值，返回空字符串；否则返回去空白的值 */
export function normalizeApiKeyInput(value: string): string
```

#### `lib/settings-io.ts` 设计

```typescript
import type { UserSettings } from '@/stores/config'

/** 导出用户设置为 JSON 字符串 */
export function exportSettings(settings: UserSettings): string

/** 从 JSON 字符串解析用户设置（含 API Key），返回 null 表示解析失败 */
export function parseSettings(json: string): (UserSettings & { apiKey?: string }) | null

/** 应用导入的设置到 Store */
export function applySettings(store: ReturnType<typeof useConfigStore>, settings: Partial<UserSettings> & { apiKey?: string }): void
```

### 6.2 其他 Store —— 保持不动

`session.ts`、`steps.ts`、`log.ts`、`toast.ts`、`auth.ts` 结构清晰、职责单一，暂不需要拆分。

---

## 7. 路由守卫设计

### 7.1 `router/guards.ts`

```typescript
import type { Router, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function registerGuards(router: Router): void {
  // ── 认证守卫 ──
  router.beforeEach((to: RouteLocationNormalized) => {
    const auth = useAuthStore()

    // 远程模式且未登录 → 重定向到登录页
    if (to.path !== '/login' && auth.isRemote && !auth.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    // 已登录用户访问登录页 → 重定向到首页
    if (to.path === '/login' && auth.isLoggedIn) {
      return '/'
    }
  })

  // ── 页面标题 ──（可选）
  router.afterEach((to: RouteLocationNormalized) => {
    const baseTitle = 'AI 生成项目报账文档'
    const titles: Record<string, string> = {
      '/': '生成任务',
      '/preview/fpa': 'FPA 预览',
      '/history': '历史记录',
      '/config': '配置',
      '/license': '授权',
      '/prompt-debug': '提示词调试',
    }
    document.title = titles[to.path]
      ? `${titles[to.path]} — ${baseTitle}`
      : baseTitle
  })
}
```

### 7.2 `router/index.ts` 调整

```typescript
import { registerGuards } from './guards'

const router = createRouter({ ... })
registerGuards(router)

export default router
```

### 7.3 `App.vue` 移除的代码

移除以下内容（迁移到 guards 或 vue-query）：

- `onMounted` 中的 `loadLegacyBackendState()` → 改用 `useHealthQuery()`
- `watch(route.path)` 认证检查 → 迁移到 `router.beforeEach`
- 版本号/模式标签 → 抽取到 `AppHeader.vue`

---

## 8. 错误边界设计

### 8.1 `components/layout/ErrorBoundary.vue`

```vue
<template>
  <div v-if="error" class="flex h-full flex-col items-center justify-center gap-4 p-8">
    <div class="text-center">
      <h2 class="text-lg font-bold text-[var(--color-ink)]">页面发生错误</h2>
      <p class="mt-2 text-sm text-[var(--color-ink-muted)]">
        {{ error.message || '未知错误，请刷新页面重试' }}
      </p>
    </div>
    <div class="flex gap-3">
      <button class="btn-primary" @click="resetError">重试</button>
      <button class="btn-secondary" @click="reloadPage">刷新页面</button>
    </div>
    <!-- 开发环境显示错误堆栈 -->
    <details v-if="isDev" class="mt-4 max-w-2xl">
      <summary class="cursor-pointer text-xs text-[var(--color-ink-soft)]">错误详情</summary>
      <pre class="mt-2 max-h-64 overflow-auto rounded bg-[var(--color-console)] p-3 text-xs text-slate-300">{{ error.stack }}</pre>
    </details>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)
const isDev = import.meta.env.DEV

onErrorCaptured((err: unknown) => {
  error.value = err instanceof Error ? err : new Error(String(err))
  console.error('[ErrorBoundary]', err)
  return false  // 阻止向上传播
})

function resetError() { error.value = null }
function reloadPage() { window.location.reload() }
</script>
```

### 8.2 挂载位置

```vue
<!-- App.vue -->
<template>
  <div class="app-chrome ...">
    <AppHeader />
    <main class="...">
      <ErrorBoundary>
        <router-view />
      </ErrorBoundary>
    </main>
  </div>
  <BaseToast />  <!-- 全局 Toast，挂载在 Teleport -->
</template>
```

### 8.3 全局未捕获异常兜底

```typescript
// main.ts 中
import { createApp, errorHandler } from 'vue'

const app = createApp(App)

app.config.errorHandler = (err, instance, info) => {
  console.error('[Global Error]', err, info)
  // 生产环境可上报到监控系统
}

// 未捕获的 Promise rejection
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
  event.preventDefault()
})
```

---

## 9. 暗色模式设计

### 9.1 策略

- **Tailwind `darkMode: 'class'`** — 在 `<html>` 上切换 `.dark` class
- **CSS 变量切换** — 在 `tokens.css` 中定义 `:root`（亮色）和 `.dark`（暗色）两套变量值
- **状态持久化** — 存入 localStorage，初始化时恢复

### 9.2 `composables/useDarkMode.ts`

```typescript
import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'ard:darkMode'

// 初始化：读取持久化值 或 跟随系统偏好
function getInitial(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored !== null) return stored === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const isDark = ref(getInitial())

watchEffect(() => {
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem(STORAGE_KEY, String(isDark.value))
})

export function useDarkMode() {
  return {
    isDark,
    toggle: () => (isDark.value = !isDark.value),
    enable: () => (isDark.value = true),
    disable: () => (isDark.value = false),
  }
}
```

### 9.3 CSS 变量体系改造

当前 `tokens.css` 结构（推测）：

```css
:root {
  --color-page: oklch(97% 0 0);
  --color-surface: oklch(100% 0 0);
  --color-surface-muted: oklch(95% 0 0);
  --color-surface-raised: oklch(100% 0 0);
  --color-ink: oklch(20% 0 0);
  --color-ink-muted: oklch(45% 0 0);
  --color-ink-soft: oklch(65% 0 0);
  --color-rule: oklch(90% 0 0);
  --color-rule-strong: oklch(80% 0 0);
  /* ... */
}
```

改造为：

```css
:root {
  --color-page: oklch(97% 0.004 260);
  --color-surface: oklch(100% 0 0);
  --color-surface-muted: oklch(95% 0.006 260);
  --color-surface-raised: oklch(100% 0 0);
  --color-ink: oklch(22% 0.01 260);
  --color-ink-muted: oklch(45% 0.01 260);
  --color-ink-soft: oklch(65% 0.01 260);
  --color-rule: oklch(90% 0.006 260);
  --color-rule-strong: oklch(80% 0.01 260);
  --color-console: oklch(18% 0 0);
  /* accent / success / danger / warning 保持不变或微调对比度 */
}

.dark {
  --color-page: oklch(16% 0.004 260);
  --color-surface: oklch(20% 0.004 260);
  --color-surface-muted: oklch(24% 0.006 260);
  --color-surface-raised: oklch(21% 0.006 260);
  --color-ink: oklch(90% 0.004 260);
  --color-ink-muted: oklch(70% 0.008 260);
  --color-ink-soft: oklch(50% 0.008 260);
  --color-rule: oklch(28% 0.006 260);
  --color-rule-strong: oklch(38% 0.01 260);
  --color-console: oklch(12% 0 0);
  /* accent / success / danger / warning 调高明度 */
}
```

### 9.4 切换入口

在 `AppHeader.vue` 中添加切换按钮：

```vue
<button
  class="nav-link"
  @click="darkMode.toggle()"
  :aria-label="darkMode.isDark.value ? '切换到亮色模式' : '切换到暗色模式'"
>
  <!-- 亮色 → 月亮图标；暗色 → 太阳图标 -->
  <SunIcon v-if="darkMode.isDark.value" class="h-4 w-4" />
  <MoonIcon v-else class="h-4 w-4" />
</button>
```

### 9.5 Tailwind 配置调整

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 可选：将 CSS 变量映射为 Tailwind color tokens
        // 这样 bg-[var(--color-page)] 可以简化为 bg-page
        page: 'var(--color-page)',
        surface: 'var(--color-surface)',
        'surface-muted': 'var(--color-surface-muted)',
        'surface-raised': 'var(--color-surface-raised)',
        ink: 'var(--color-ink)',
        'ink-muted': 'var(--color-ink-muted)',
        'ink-soft': 'var(--color-ink-soft)',
        rule: 'var(--color-rule)',
        'rule-strong': 'var(--color-rule-strong)',
        accent: 'var(--color-accent)',
        'accent-strong': 'var(--color-accent-strong)',
        'accent-soft': 'var(--color-accent-soft)',
        // ...
      },
    },
  },
}
```

这样就可以用 `bg-page` / `text-ink-muted` / `border-rule` 替代冗长的 `bg-[var(--color-page)]` 写法，代码更简洁。

> **注意**：这次颜色 Token 别名改为可选的渐进升级项，不强制一次性全改。新组件优先使用短名，旧组件可保持原写法。

---

## 10. 测试体系设计

### 10.1 工具选型

| 层级 | 工具 | 安装 |
|------|------|------|
| 单元测试 | vitest | `npm add -D vitest` |
| 组件测试 | @vue/test-utils + jsdom | `npm add -D @vue/test-utils jsdom` |
| E2E | playwright | 已安装 |
| Store 测试 | pinia + vitest | 无需额外依赖（createTestingPinia） |

### 10.2 Vitest 配置

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
```

### 10.3 测试清单（优先级排序）

#### P0 —— Store 状态转换

```typescript
// src/stores/__tests__/session.test.ts

describe('sessionStore', () => {
  it('初始状态为 idle')
  it('start() 设置 sessionId、outputDir、runState=running')
  it('finish() 设置 runState=done 并保存 doneFiles')
  it('setError() 设置 runState=error')
  it('setCancelled() 设置 runState=cancelled')
  it('reset() 恢复全部初始值')
  it('showInputPrompt / showListPrompt 设置对应 prompt')
})
```

```typescript
// src/stores/__tests__/steps.test.ts

describe('stepsStore', () => {
  it('初始所有 step 状态为 pending')
  it('handlePipelineEvent step_started → running')
  it('handlePipelineEvent step_done → done')
  it('handlePipelineEvent step_failed → failed + error 信息')
  it('handlePipelineEvent artifact → 追加产物（不去重）')
  it('handlePipelineEvent input_required → waiting_input')
  it('finishAll() 将 running/waiting_input 全部置为 done')
  it('applySnapshot() 正确恢复快照')
})
```

#### P1 —— Composable 逻辑

```typescript
// src/composables/__tests__/useFpaOptions.test.ts

describe('useFpaOptions', () => {
  it('API 失败时返回 fallbackOptions')
  it('API 成功时返回服务端数据')
  it('重复调用 loadFpaOptions 不重复请求')
})
```

```typescript
// src/lib/__tests__/api-key.test.ts

describe('normalizeApiKeyInput', () => {
  it('空字符串返回空')
  it('占位符 "sk-..." 返回空')
  it('有效 key 返回去空白值')
})
```

#### P2 —— 组件交互

```typescript
// src/components/__tests__/BaseButton.test.ts

describe('BaseButton', () => {
  it('渲染按钮文字')
  it('disabled 时不可点击')
  it('loading 时显示加载状态')
  it('点击触发 emit')
})
```

#### P3 —— E2E 冒烟测试

```typescript
// e2e/smoke.spec.ts

test('本地模式生成流程', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('text=AI 生成项目报账文档')).toBeVisible()

  // 选择操作模式
  await page.selectOption('select', 'from-excel-gen-all')

  // 输入 xlsx 路径
  // ...

  // 点击开始生成
  await page.click('text=开始生成')

  // 状态变为运行中
  await expect(page.locator('text=运行中')).toBeVisible({ timeout: 5000 })
})
```

### 10.4 package.json scripts 补充

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

---

## 附录 A：迁移顺序与影响范围

```
第一轮（零风险，纯新增）
  API 层           → 新增 api/ 目录，不动现有代码
  lib/storage.ts   → 新增工具，config Store 逐步引用
  lib/api-key.ts   → 新增工具，config Store 逐步引用
  router/guards.ts → 新增 guards，router/index.ts 加一行调用
  Base 组件        → 新增 ui/ 目录，不修改现有组件

第二轮（低风险，行为等价替换）
  ErrorBoundary    → App.vue 包裹 router-view，不改变业务逻辑
  AppHeader.vue    → 从 App.vue 抽取顶栏，模板完全相同
  Home.vue 弹窗抽取 → 3 个 Modal 组件，模板复制粘贴，不改逻辑
  useTaskRunner    → 从 Home.vue 抽取，startTask 逻辑不改变

第三轮（中风险，引入新依赖）
  vue-query 安装   → npm add
  useModesQuery    → 替代 ConfigPanel 内 onMounted apiFetch
  useFpaOptionsQuery → 替代 useFpaOptions.ts 手写状态机
  useHealthQuery   → 替代 App.vue 内 loadLegacyBackendState

第四轮（需设计评审）
  组件库替换       → 逐步用 Base* 组件替换旧的 CSS class 写法
  暗色模式         → 新增 tokens.css dark 变量 + useDarkMode
  测试用例         → 贯穿全过程，从 P0 开始
```

## 附录 B：不做的部分

1. **不升级 Vue 版本**（当前 3.5.13 稳定够用）
2. **不更换构建工具**（Vite 6 已是当前最新）
3. **不改变后端 API 接口**（除非发现明显设计问题）
4. **不强制全量替换 CSS class 为 Tailwind 短名**（渐进式，新组件优先）
5. **不引入全局状态管理库**（Pinia 已足够，vue-query 承担服务端状态）
6. **不一致性问题**：当前每个组件/页面都手写 `statusLabel()` / `badgeClass()` / `cardClass()` 等状态→样式的映射函数（如 [GenerationProgress.vue:74-103](../web_app/src/components/GenerationProgress.vue#L74-L103)），在封装 `BaseBadge` 后统一消除
