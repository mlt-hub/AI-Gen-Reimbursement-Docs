# Web UI 重构方案

## 当前现状

| 维度 | 详情 |
|------|------|
| 技术栈 | Vue 3.5 + TypeScript 5.7 + Vite 6 + Pinia 2 + Vue Router 4 |
| 样式 | Tailwind CSS 3 + 自研 CSS 变量主题系统 |
| 组件库 | Headless UI + Heroicons（无封装，直接手写 Tailwind） |
| 页面 | 7 个路由页面（Home / Config / History / License / Login / FpaPreview / PromptDebug） |
| 组件 | 12 个（ConfigPanel、GenerationProgress、LogViewer、StepsBar 等） |
| 状态管理 | 6 个 Pinia Store（auth / config / session / log / steps / toast） |
| Composable | 2 个（useFpaOptions / useSensitiveInputGuard） |
| 后端 | FastAPI，Vite proxy 转发 `/api`，SSE 推送日志 |
| 测试 | 无（package.json 有 Playwright 但未编写用例） |

---

## 一、组件拆分 —— 解决 `Home.vue` 巨型组件

### 问题

[Home.vue](../web_app/src/views/Home.vue) **424 行**，包含 3 个模态弹窗、任务启动、会话恢复、AI 日志加载等全部混在一个文件里。是重构的头号目标。

### 方案

| 抽取内容 | 目标文件 | 说明 |
|----------|----------|------|
| FPA 核减工作量弹窗 | `components/FpaInputModal.vue` | Teleport 弹窗，输入 + 提交逻辑 |
| 送审确认弹窗 | `components/ListConfirmModal.vue` | Teleport 弹窗，两个字段 + 提交逻辑 |
| AI 交互记录弹窗 | `components/AiInteractionModal.vue` | Tab 切换（列表/合并日志），展开/收起 |
| 任务启动逻辑 | `composables/useTaskRunner.ts` | `startTask()` + FormData 组装 |
| 会话恢复逻辑 | `composables/useSessionRestore.ts` | `restoreLastSession()` + localStorage |

### 目标

`Home.vue` 控制在 **150 行以内**，只做布局编排和子组件/Composable 的调度。

---

## 二、引入 `@tanstack/vue-query` 管理服务端状态

### 问题

API 调用全在组件内手写 `apiFetch` + `try/catch`，无缓存、无去重、无后台刷新。

### 方案

```typescript
// 示例：会话状态轮询
const { data: status } = useQuery({
  queryKey: ['session', sessionId],
  queryFn: () => apiFetch(`/api/sessions/${sessionId}`),
  refetchInterval: 2000,           // 自动轮询
  enabled: computed(() => !!sessionId.value),
})

// 示例：启动任务
const { mutate: startTask, isPending } = useMutation({
  mutationFn: (form: FormData) => apiFetch('/api/run-local', { method: 'POST', body: form }),
  onSuccess: (data) => { session.start(data.session_id) },
  onError: (e) => toast.show('error', normalizeApiError(e)),
})
```

### 收益

- 自动获得 `loading / error / data` 三态，减少样板代码
- 相同 key 的请求自动去重
- 窗口聚焦自动刷新
- 轮询逻辑声明式管理

---

## 三、建立统一的 API 层

### 问题

`apiFetch` 只有基础封装，接口定义散落在各组件里，无类型安全的请求/响应定义。

### 方案

```
web_app/src/api/
├── client.ts        # apiFetch 基础封装（已有 lib/api.ts，迁移至此）
├── tasks.ts         # 任务相关：启动、取消、继续
├── sessions.ts      # 会话相关：状态查询、历史、交付物
├── config.ts        # 配置相关：导入导出、健康检查
├── ai.ts            # AI 交互日志
└── types.ts         # 共享的请求/响应 interface
```

每个 API 函数明确定义入参出参类型，统一错误码 → Toast 文案映射。

---

## 四、Store 职责拆分

### 问题

[config.ts](../web_app/src/stores/config.ts) Store 做了太多事：业务配置 + localStorage 持久化 + 导入导出 + API Key 安全过滤。

### 方案

| 抽取内容 | 目标文件 | 说明 |
|----------|----------|------|
| localStorage 封装 | `lib/storage.ts` | `loadStr/saveStr/loadBool/saveBool/removeStr` |
| 导入导出逻辑 | `lib/settings-io.ts` | `exportSettings/importSettings` + JSON 校验 |
| API Key 安全过滤 | `lib/api-key.ts` | `normalizeApiKeyInput` + 占位符黑名单 |

Store 只保留响应式状态 + 业务动作（如 `reset()`、`start()` 等），不再包含工具函数。

---

## 五、封装基础 UI 组件

### 问题

Button、Input、Modal、Toast 没有统一组件，每个页面重复手写 `btn-primary`/`btn-quiet`/`field-control` 等 Tailwind 类组合。

### 方案

优先封装 4 个基础组件（不引入第三方库，保持轻量）：

| 组件 | Props | 说明 |
|------|-------|------|
| `BaseButton.vue` | `variant: 'primary' \| 'quiet' \| 'danger'`, `size`, `loading`, `disabled` | 统一按钮样式和行为 |
| `BaseInput.vue` | `label`, `type`, `modelValue`, `error`, `placeholder` | 统一输入框 + label + 错误提示 |
| `BaseModal.vue` | `open`, `title`, `size` | Teleport 弹窗壳子，插槽 `default` + `footer` |
| `BaseToast.vue` | 由 Toast Store 驱动，全局挂载 | 统一通知样式 |

如果后续需求增长，再评估引入 **shadcn-vue**（源码级复制，完全可控，适合已有 Tailwind 项目）或 **PrimeVue**（组件丰富，适合企业后台）。

---

## 六、路由守卫规范化

### 问题

认证守卫写在 [App.vue](../web_app/src/App.vue) 的 `watch(route.path)` 里，逻辑脆弱，且与组件生命周期耦合。

### 方案

```typescript
// router/guards.ts
import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function registerGuards(router: Router) {
  router.beforeEach((to, from) => {
    const auth = useAuthStore()

    // 远程模式未登录 → 跳转登录页
    if (to.path !== '/login' && auth.isRemote && !auth.isLoggedIn) {
      return '/login'
    }
  })
}
```

在 `router/index.ts` 中调用 `registerGuards(router)`。

---

## 七、错误边界

### 问题

Vue 3 提供了 `onErrorCaptured`，但项目中未使用。未捕获的异常会导致白屏。

### 方案

```vue
<!-- components/ErrorBoundary.vue -->
<template>
  <div v-if="error" class="error-fallback">
    <h2>页面出错了</h2>
    <p>{{ error.message }}</p>
    <button @click="reset">重试</button>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)

onErrorCaptured((err) => {
  error.value = err as Error
  return false // 阻止向上传播
})

function reset() { error.value = null }
</script>
```

在路由视图外包裹：

```vue
<ErrorBoundary>
  <router-view />
</ErrorBoundary>
```

---

## 八、暗色模式支持

### 问题

已有 CSS 变量体系（`--color-ink`、`--color-surface` 等），但未提供切换能力。

### 方案

```typescript
// composables/useDarkMode.ts
import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'ard:darkMode'
const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'true')

watchEffect(() => {
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem(STORAGE_KEY, String(isDark.value))
})

export function useDarkMode() {
  return { isDark, toggle: () => (isDark.value = !isDark.value) }
}
```

配合 Tailwind `darkMode: 'class'`，在 CSS 中按需覆盖变量值即可。

---

## 九、补充测试体系

### 现状

`package.json` 有 Playwright 依赖，但无测试文件。

### 方案

| 层级 | 工具 | 覆盖范围 |
|------|------|----------|
| 单元测试 | Vitest | Store（状态转换）、Composable（逻辑）、工具函数 |
| 组件测试 | Vitest + @vue/test-utils | 关键组件交互（ConfigPanel、GenerationProgress） |
| E2E | Playwright | 核心流程：登录 → 配置 → 生成任务 → 查看结果 → 下载 |

### 优先编写

1. `configStore` 的状态转换单测（`start/reset/finish/setError`）
2. `useFpaOptions` 的边界值测试
3. `Home.vue` 的 E2E 冒烟测试（本地模式提交 → 轮询状态 → 完成）

---

## 十、附加建议

### 10.1 TypeScript 严格模式

当前 `tsconfig` 未确认是否开启 `strict: true`。建议开启并修复类型问题，提升代码健壮性。

### 10.2 构建产物优化

- 路由已部分使用懒加载（`() => import(...)`），建议全部路由统一懒加载
- Vite 6 支持 `manualChunks`，可将 `pinia` + `vue-router` + `headlessui` 合并为 vendor chunk
- 开启 `vite-plugin-compression` 压缩静态资源

### 10.3 开发体验

- 建议添加 ESLint + Prettier 配置（当前项目未发现）
- `vue-tsc` 已用于 build 前类型检查，建议添加 `lint-staged` + `simple-git-hooks` 做提交前检查

---

## 重构路径

```
第一阶段（低风险，不改变行为）
├── 建立 API 层（api/ 目录 + 类型定义）
├── 抽取持久化工具（lib/storage.ts）
├── 路由守卫规范化（router/guards.ts）
└── 错误边界组件

第二阶段（中风险，调整结构）
├── 拆分 Home.vue（弹窗组件 + Composable）
├── 引入 vue-query（替换 API 调用模式）
├── Store 职责拆分
└── 封装基础 UI 组件（BaseButton / BaseInput / BaseModal / BaseToast）

第三阶段（需设计评审）
├── 暗色模式
├── 评估引入 shadcn-vue / PrimeVue
└── 补充测试体系
```

每个阶段内部各任务可并行推进，阶段之间建议顺序执行以控制风险。
