# Web UI 前端重构方案

> 2026-05-23，通过 `/grill-me` 逐项决策确定。

## 1. 技术栈

| 决策点 | 选择 |
|---|---|
| 框架 | Vue 3 + Vite |
| CSS 方案 | Tailwind CSS |
| 组件库 | Headless UI（弹窗/下拉）+ 手写 Steps/Toast |
| 图标 | Heroicons（SVG 内嵌） |
| 状态管理 | Pinia |
| 路由 | Vue Router |

## 2. 页面路由

| 路由 | 组件 | 说明 |
|---|---|---|
| `/` | `Home.vue` | 核心：配置 + 生成 + 日志 |
| `/config` | `Config.vue` | 系统配置管理 |
| `/prompt-debug` | `PromptDebug.vue` | 提示词调试 |

## 3. 组件树

```
Home.vue
├── StepsBar          (管道进度步骤条，解析日志关键事件驱动)
├── ConfigPanel       (模式切换 + 文件输入 + 高级选项 + 自定义模板)
│   ├── ModeSelector  (本机/远程 切换)
│   ├── FileInput     (本机路径 或 远程上传)
│   ├── AdvancedOptions (API Key、模型、端点、MaxTokens、项目名、clean)
│   └── TemplateUpload  (FPA/COSMIC/需求清单/需求说明书 自定义模板)
├── LogViewer         (SSE 实时日志流)
├── ActionBar         (打开交付物目录 / 下载 zip / AI 交互 / 新任务)
└── Toast             (通知提示)

Config.vue
├── ConfigForm        (.env 编辑)
└── ConfigForm        (system_config.yaml 编辑)

PromptDebug.vue
├── ReliabilityTest   (可靠性描述 AI 生成测试)
└── MetadataTest      (元数据 #AI生成# 测试)
```

## 4. Pinia Store 设计

| Store | 职责 |
|---|---|
| `useSessionStore` | sessionId、运行状态（idle/running/done/error）、交付物目录 |
| `useLogStore` | 日志数组、追加日志、清空日志、SSE 连接管理 |
| `useConfigStore` | 表单参数（mode、xlsxPath、outputDir、apiKey 等） |
| `useAIStore` | AI 交互记录、合并日志 |

## 5. 进度反馈（StepsBar）

管道阶段：
```
基础数据 → FPA工作量评估 → COSMIC功能点拆分 → 需求清单 → 需求说明书
```

- 通过解析日志中 `===` 分节标题推进步骤
- 当前步骤高亮 + 脉冲动画
- 已完成步骤打勾
- 错误步骤标红

## 6. 开发模式

```
开发:  npm run dev (Vite :5173) + python -m web_app.server (uvicorn :8000)
       Vite proxy: /api/* → http://127.0.0.1:8000

生产:  npm run build → web_app/static/dist/
       FastAPI StaticFiles 挂载 dist/
       PyInstaller --onedir 打包时 Copy-Item web_app → dist/ard/web_app/
```

`vite.config.ts` 配置：
```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000'
  }
}
```

## 7. 目录结构

```
web_app/
├── server.py              (FastAPI 后端，不变)
├── static/
│   ├── dist/              (Vite 构建产物，gitignore)
│   │   ├── index.html
│   │   ├── assets/
│   │   └── ...
│   └── index.html         (删除，由 Vue Router 生成)
├── src/                   (Vue 源码)
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   ├── session.ts
│   │   ├── log.ts
│   │   ├── config.ts
│   │   └── ai.ts
│   ├── components/
│   │   ├── StepsBar.vue
│   │   ├── ConfigPanel.vue
│   │   ├── ModeSelector.vue
│   │   ├── FileInput.vue
│   │   ├── AdvancedOptions.vue
│   │   ├── TemplateUpload.vue
│   │   ├── LogViewer.vue
│   │   ├── ActionBar.vue
│   │   └── Toast.vue
│   ├── views/
│   │   ├── Home.vue
│   │   ├── Config.vue
│   │   └── PromptDebug.vue
│   └── assets/
│       └── main.css
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

## 8. 后端适配

| 改动 | 说明 |
|---|---|
| `StaticFiles` 挂载路径 | 生产环境指向 `static/dist/`，开发环境回退 `static/` |
| `index.html` 入口 | 路由到 `static/dist/index.html`（Vue SPA 入口） |
| SPA fallback | 非 `/api/*` 路径返回 `index.html`（Vue Router history mode） |

## 9. 实施阶段

| 阶段 | 内容 |
|---|---|
| 1. 脚手架 | `npm create vue`，配置 Tailwind + Router + Pinia |
| 2. 核心页面 | Home.vue + 所有子组件 + Stores + SSE 集成 |
| 3. 配置/调试页 | Config.vue + PromptDebug.vue |
| 4. 后端适配 | FastAPI 静态文件路由调整 |
| 5. 打包集成 | 更新 build_exe.ps1 / CI / PyInstaller |
