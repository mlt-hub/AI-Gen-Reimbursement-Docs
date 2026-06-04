# Web UI 专业度后续整改实施方案

日期：2026-05-29

依据文档：

- [Web UI 专业度审计与整改方案](./web-ui-professionalism-audit.md)
- [Web UI 专业度整改执行总结](./web-ui-professionalism-implementation-summary.md)

## 目标

上一轮整改已经解决了首屏空白、源码树 sidecar 污染、后端离线缺少反馈、主要页面观感不统一等高风险问题。本方案面向下一阶段推进，目标是把 Web UI 从“可打开、状态清楚、观感统一”继续推进到“可诊断、可回归验证、配置结构清晰、适合开源用户长期使用”。

本阶段不追求大改版，不引入重型依赖，不重写业务流程。所有修改应围绕以下原则：

- 保持当前控制台式产品方向。
- 优先补齐可用性、诊断能力和自动化防回归。
- 每个阶段都能独立构建、独立验证、独立提交。
- 避免把视觉润色和业务逻辑改动混在同一批。

## 当前基线

已完成：

- 首屏路由空白已修复。
- `/static/dist/` 能正确渲染首页。
- `web_app/src` 下生成的 `.js` / `.vue.js` sidecar 已清理，并通过 `.gitignore` 与 `tsconfig.json` 防再生。
- 后端未连接时，顶部、任务面板、日志空态均有明确状态。
- 首页、登录页、配置页、提示词调试页已基本统一到 token 化视觉系统。
- 主要英文 UI 文案已中文化。
- 桌面端与移动端已做过截图验证。

仍需推进：

- 缺少专门的后端健康检查接口。
- 缺少环境诊断入口。
- 配置页信息架构仍偏“长表单/配置文件编辑器”。
- 缺少前端自动化 smoke test。
- 缺少“源码目录不得出现构建产物”的自动检查。
- 截图资产仍在仓库根目录，归档策略未定。
- 显式 `.ts` 导入是当前可控修复，但仍需确认是否作为长期规范。

## 推荐推进顺序

建议按以下顺序推进：

1. 增加自动化防回归检查。
2. 增加后端 `/api/health` 与前端健康状态消费。
3. 增加环境诊断入口。
4. 重整配置页信息架构。
5. 完成截图资产和文档资产整理。
6. 复核 TypeScript 导入规范，决定长期策略。

这个顺序的理由是：先建立验证网，再增加诊断能力，然后再做更大范围的信息架构整理。这样每一步都更可控，后续改动也更容易发现回归。

## 阶段 1：建立自动化防回归检查

优先级：P0

目标：防止上一轮已经修好的问题再次出现，尤其是首屏空白、sidecar 文件再生、主要页面无法打开。

### 1.1 新增源码生成物检查脚本

建议新增脚本：

```text
scripts/check_web_source_artifacts.ps1
```

检查内容：

- `web_app/src/**/*.js`
- `web_app/src/**/*.vue.js`
- `web_app/src/**/*.vue.d.ts`

如果发现任何文件，脚本应：

- 输出文件列表。
- 返回非 0 exit code。
- 明确提示这些文件不应出现在源码目录。

建议实现逻辑：

```powershell
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$patterns = @('*.js', '*.vue.js', '*.vue.d.ts')
$found = @()

foreach ($pattern in $patterns) {
    $found += Get-ChildItem -Path (Join-Path $repoRoot 'web_app/src') -Recurse -File -Filter $pattern
}

if ($found.Count -gt 0) {
    Write-Host 'web_app/src 下发现不应提交的生成文件：' -ForegroundColor Red
    $found | ForEach-Object { Write-Host "  $($_.FullName)" }
    exit 1
}

Write-Host 'web_app/src 生成物检查通过。' -ForegroundColor Green
```

验收标准：

- 当前工作树运行该脚本通过。
- 手动放入一个 `web_app/src/tmp.js` 时脚本失败。
- 删除测试文件后脚本恢复通过。

风险控制：

- 脚本只读，不删除文件。
- 不自动修改 `.gitignore`，避免误伤需要人工判断的文件。

### 1.2 新增 Web UI smoke test

建议优先采用现有前端生态中最小可行方案。如果项目已经有 Playwright，则直接使用 Playwright；如果没有，可以先使用无头 Edge/Chrome 命令加 DOM dump 做轻量检查。

推荐路径：

```text
web_app/tests/smoke/
```

或：

```text
scripts/web_smoke.ps1
```

最小断言：

- 打开 `/static/dist/` 或 Vite dev server 根路径后，页面包含 `AI 生成项目报账文档`。
- 首页包含 `任务设置`。
- 首页包含 `执行监控`。
- 后端不可用时包含 `后端未连接`。
- 打开 `/static/dist/config` 时，配置页可以渲染。
- 打开 `/static/dist/prompt-debug` 时，提示词调试页可以渲染。

如果使用 Playwright，建议断言：

```ts
await expect(page.getByText('任务设置')).toBeVisible()
await expect(page.getByText('执行监控')).toBeVisible()
await expect(page.getByText('后端未连接')).toBeVisible()
```

如果先用 PowerShell + Edge headless，建议断言 DOM：

```powershell
& $edge --headless=new --dump-dom http://127.0.0.1:5173/static/dist/ |
  Select-String -Pattern '任务设置|执行监控|后端未连接'
```

验收标准：

- smoke test 能在后端未启动时通过。
- 如果路由再次空白，测试失败。
- 如果顶部标题缺失，测试失败。
- 如果构建产物路径 `/static/dist/` 再次失配，测试失败。

风险控制：

- 不在第一阶段引入过多 E2E 测试。
- 先覆盖“能打开”和“核心空状态可见”，不要测试复杂任务运行流程。

### 1.3 串联本地验证命令

建议新增一个统一检查脚本：

```text
scripts/check_web_ui.ps1
```

职责：

1. 运行源码生成物检查。
2. 运行 `npm run build`。
3. 启动 Vite dev server。
4. 运行 smoke test。
5. 关闭 dev server。

注意事项：

- dev server 启动后需要等待端口可用。
- 如果端口 `5173` 已占用，应提示用户，或者改用临时端口。
- 脚本退出时必须清理启动的进程。

验收标准：

- 正常情况下脚本一次通过。
- 中途失败也会关闭自己启动的 dev server。
- 输出清晰区分构建失败、路由失败、页面断言失败。

## 阶段 2：增加后端 `/api/health`

优先级：P1

目标：把当前“任一元信息接口成功即认为 connected”的宽松判断，升级为明确、可扩展的健康检查。

### 2.1 后端新增健康检查接口

建议接口：

```text
GET /api/health
```

建议返回：

```json
{
  "ok": true,
  "version": "1.0.0",
  "work_mode": "local",
  "api": {
    "version": true,
    "modes": true,
    "config": true
  },
  "paths": {
    "templates_readable": true,
    "output_writable": true
  },
  "features": {
    "prompt_debug": true,
    "ai_interactions": true
  }
}
```

字段说明：

- `ok`：整体可用性。
- `version`：后端版本。
- `work_mode`：`local` 或 `remote`。
- `api`：关键接口是否可用。
- `paths`：本地文件系统相关状态。
- `features`：前端可展示的能力开关。

如果某些字段当前无法可靠判断，可以先返回 `null`，不要伪造状态：

```json
{
  "paths": {
    "templates_readable": null,
    "output_writable": null
  }
}
```

验收标准：

- 后端启动时，`GET /api/health` 返回 HTTP 200。
- 返回体至少包含 `ok`、`version`、`work_mode`。
- 后端异常状态能通过 `ok: false` 或 5xx 表达。

风险控制：

- 不让 `/api/health` 执行昂贵操作。
- 文件系统检查应设置短路径、短超时，不阻塞页面加载。
- 健康检查失败不应导致后端进程崩溃。

### 2.2 前端改用 `/api/health`

当前 `App.vue` 通过以下接口推断状态：

- `/api/version`
- `/api/default-work-mode`
- `/api/is-local`

建议改为：

1. 首先请求 `/api/health`。
2. 如果成功，用返回体设置：
   - `backendStatus`
   - `version`
   - `workMode`
   - 诊断信息
3. 如果 `/api/health` 不存在或失败，再 fallback 到旧接口组合。

这样可以兼容后端尚未升级的场景。

建议新增类型：

```ts
interface HealthResponse {
  ok?: boolean
  version?: string
  work_mode?: 'local' | 'remote'
  api?: Record<string, boolean | null>
  paths?: Record<string, boolean | null>
  features?: Record<string, boolean | null>
}
```

验收标准：

- 新后端存在 `/api/health` 时，前端优先使用该接口。
- 老后端没有 `/api/health` 时，前端仍能通过旧接口显示状态。
- 后端完全未启动时，前端仍显示 `后端未连接`。

风险控制：

- 不删除旧接口 fallback。
- 不把 `ok: false` 简单等同于网络断开，应在 UI 中区分：
  - `后端未连接`
  - `后端异常`

### 2.3 增加更细的后端状态

当前状态：

```ts
type BackendStatus = 'checking' | 'connected' | 'offline'
```

建议扩展为：

```ts
type BackendStatus = 'checking' | 'connected' | 'degraded' | 'offline'
```

含义：

- `checking`：正在探测。
- `connected`：健康检查通过。
- `degraded`：后端可达，但健康检查有部分失败。
- `offline`：后端不可达。

UI 文案：

- `检查服务中`
- `后端已连接`
- `后端部分异常`
- `后端未连接`

验收标准：

- `ok: true` 显示 `后端已连接`。
- `ok: false` 但接口可达，显示 `后端部分异常`。
- 网络失败显示 `后端未连接`。

## 阶段 3：增加环境诊断入口

优先级：P1

目标：让开源用户不用翻终端日志，就能知道当前环境为什么不能运行任务。

### 3.1 新增诊断页面或诊断面板

推荐方案：在配置页增加一个“环境诊断”分区，而不是新建独立路由。

原因：

- 当前导航已有 `生成`、`配置`、`提示词调试`。
- 诊断属于配置/环境问题，放在配置页更自然。
- 避免顶部导航过多。

建议分区标题：

```text
环境诊断
```

展示项：

- 后端连接状态。
- 后端版本。
- 当前工作模式。
- 生成模式接口是否可用。
- 配置接口是否可用。
- 模板目录是否可读。
- 输出目录是否可写。
- 最近一次检查时间。

状态展示建议：

- 正常：绿色或成功色小标记，文案 `正常`。
- 异常：警告/危险色小标记，文案 `异常`。
- 未知：中性色，文案 `未检测`。

不要使用大面积彩色卡片。诊断项应紧凑、可扫描。

### 3.2 增加“重新检查”操作

配置页诊断区应提供一个按钮：

```text
重新检查
```

行为：

- 调用 `/api/health`。
- 刷新诊断结果。
- 显示检查中状态。
- 失败时保留上一次结果，并显示错误提示。

验收标准：

- 后端在线时点击后刷新状态。
- 后端离线时点击后显示明确失败。
- 按钮不会导致整页闪烁。

### 3.3 增加排障提示

诊断区底部可以提供一段简短操作型提示：

```text
如果后端未连接，请先启动后端服务；如果模板目录异常，请检查模板文件是否存在并具有读取权限。
```

注意：

- 不要写营销式说明。
- 不要写过长教程。
- 如果已有 README/文档，可提供文档入口。

验收标准：

- 新用户看到诊断区后，能判断下一步该启动服务、改配置还是检查路径。

## 阶段 4：重整配置页信息架构

优先级：P2

目标：把配置页从“长表单堆叠”整理成可扫描、可维护的管理界面。

### 4.1 建议分组

配置页建议拆成以下分区：

1. 后端状态
2. 环境变量
3. 业务规则
4. 个人配置
5. 环境诊断

如果页面过长，建议使用左侧分区导航或顶部 tabs：

- `环境`
- `规则`
- `个人`
- `诊断`

当前项目是工具型应用，不建议做大幅营销式页面，也不建议用超大 hero。

### 4.2 环境变量分区

展示字段：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_MODEL`
- `MAX_TOKENS`

设计要求：

- 配置键名保持原样。
- 字段标签可以中文化，但键名要可见。
- API Key 默认遮蔽显示。
- 提供“显示/隐藏”按钮。
- 保存前做最小校验。

验收标准：

- 用户能清楚区分“字段用途”和“真实配置键名”。
- API Key 不以明文长期暴露。

### 4.3 业务规则分区

建议展示：

- 工作量计算规则。
- 模板选择规则。
- 默认生成模式。
- 与报账文档相关的领域配置。

设计要求：

- 避免把长 JSON 直接暴露给普通用户。
- 如果必须编辑结构化配置，提供代码编辑区，并明确“高级配置”。

验收标准：

- 常用业务规则可以通过表单修改。
- 高级结构化内容有明确边界。

### 4.4 个人配置分区

建议展示：

- 默认输入目录。
- 默认输出目录。
- 最近使用路径。
- 用户偏好。

注意：

- 如果这些配置当前后端不支持，不要在 UI 上伪造保存。
- 可以先做只读展示或暂不实现。

验收标准：

- 页面不出现保存后实际不生效的控件。

### 4.5 保存状态与错误反馈

配置页所有保存动作应有明确状态：

- 未修改。
- 已修改未保存。
- 保存中。
- 已保存。
- 保存失败。

建议：

- 保存失败展示具体错误。
- 离开页面前如有未保存修改，可以提示。

验收标准：

- 用户不会误以为配置已经保存。
- API 保存失败时，页面保留用户输入。

## 阶段 5：完善任务页的运行前校验

优先级：P2

目标：减少用户点击“开始生成”后才发现环境或输入错误的情况。

### 5.1 运行前校验项

开始生成前建议检查：

- 后端状态必须不是 `offline`。
- 必填输入路径存在或格式合理。
- 输出目录字段格式合理。
- 当前生成模式有效。
- 必需模板状态正常。
- 如果远程模式需要登录，应确认已登录。

验收标准：

- 缺少输入路径时，不发起 `/api/run`。
- 后端离线时，不发起 `/api/run`。
- 模板缺失时，提示用户下载或上传模板。

### 5.2 错误提示应给出下一步

错误提示不只写“失败”，而是给出可执行建议。

示例：

```text
无法启动任务：后端未连接。请先启动后端服务后重试。
```

```text
无法读取输入文件。请确认路径存在，且当前用户具有读取权限。
```

验收标准：

- 常见错误不需要用户打开开发者工具才能理解。

## 阶段 6：截图与文档资产整理

优先级：P2

目标：避免仓库根目录长期堆积验证截图，同时保留必要的审计证据。

### 6.1 决策截图是否纳入仓库

当前截图：

- `ui-desktop.png`
- `ui-desktop-after.png`
- `ui-mobile-after.png`

建议二选一：

方案 A：不纳入仓库

- 删除根目录截图。
- 在文档中只保留验证命令和观察结论。

方案 B：纳入文档资产

- 移动到：

  ```text
  docs/assets/web-ui/
  ```

- 重命名：

  ```text
  2026-05-28-home-before-desktop.png
  2026-05-28-home-after-desktop.png
  2026-05-28-home-after-mobile.png
  ```

- 在审计/总结文档中引用。

推荐：如果这个项目希望保留设计审计过程，采用方案 B；否则采用方案 A。

执行状态：

- 已新增截图归档目录说明：`docs/assets/web-ui/README.md`。
- 当前仓库根目录未发现 `ui-*.png` 截图残留。
- 后续需要保留的验证截图应直接归档到 `docs/assets/web-ui/`，不再放在仓库根目录。

### 6.2 更新文档索引

如果 `docs/` 下已有 README 或索引页，建议加入：

- Web UI 专业度审计。
- Web UI 整改执行总结。
- Web UI 后续整改实施方案。

验收标准：

- 新加入项目的人能从 `docs/` 找到这三份文档。

## 阶段 7：确认 TypeScript 导入长期策略

优先级：P3

目标：决定显式 `.ts` 导入是长期规范，还是过渡性修复。

### 7.1 当前情况

上一轮为了规避 sidecar 清理后的解析问题，采用了显式 `.ts` 导入，并启用：

```json
{
  "allowImportingTsExtensions": true,
  "noEmit": true
}
```

这让当前构建稳定，但与部分 Vue/Vite 项目常见的 extensionless import 习惯不同。

### 7.2 可选策略

方案 A：保持显式 `.ts` 导入

优点：

- 当前已验证可行。
- 解析路径明确。
- 与 `allowImportingTsExtensions` 匹配。

缺点：

- 与部分团队习惯不同。
- 后续迁移到其他构建工具时可能需要复核。

方案 B：恢复 extensionless import

前置条件：

- 找到此前 extensionless import 被转为 `.js` 请求的根因。
- 确认 Vite resolve、TypeScript moduleResolution、Vue 插件配置都稳定。
- 有 smoke test 能防止空白页回归。

推荐：

- 短期保持方案 A。
- 在自动化 smoke test 建立后，再评估是否切换到方案 B。

验收标准：

- 选定策略后写入 `docs/dev/` 或前端开发说明。
- lint 或 review checklist 中明确导入风格。

## 阶段 8：真实浏览器响应式复核

优先级：P3

目标：用真实浏览器确认移动端体验，避免仅依赖 Edge headless 截图。

### 8.1 复核宽度

建议宽度：

- 320px
- 375px
- 414px
- 768px
- 1440px

检查页面：

- 首页 `/static/dist/`
- 配置页 `/static/dist/config`
- 提示词调试页 `/static/dist/prompt-debug`
- 登录页 `/static/dist/login`

检查重点：

- 无横向滚动。
- 顶部导航换行自然。
- 文件路径、session id、错误信息不会把布局撑破。
- 按钮文字不溢出。
- 弹窗内容不超出视口。
- 日志区域在窄屏下仍可读。

验收标准：

- 每个宽度至少保留一张关键截图，或在验证记录中写明通过。
- 如果发现破版，优先修容器约束和文本换行，不引入新的大布局。

## 推荐提交批次

为了确保可控，建议拆成以下提交：

### 提交 1：自动化防回归

内容：

- 生成物检查脚本。
- Web UI smoke test。
- 统一检查脚本。

验收：

- `npm run build` 通过。
- 新增检查脚本通过。

### 提交 2：后端健康检查

内容：

- `/api/health`。
- 后端测试。
- 文档说明。

验收：

- 后端启动时健康检查返回正确状态。
- 后端异常时不崩溃。

### 提交 3：前端健康状态消费

内容：

- 前端优先请求 `/api/health`。
- 增加 `degraded` 状态。
- 保留旧接口 fallback。

验收：

- 新旧后端均可显示状态。
- 后端离线仍显示完整 UI。

### 提交 4：环境诊断面板

内容：

- 配置页诊断区。
- 重新检查操作。
- 诊断状态展示。

验收：

- 后端在线、离线、部分异常三种状态均有明确 UI。

### 提交 5：配置页信息架构整理

内容：

- 配置页分区或 tabs。
- 保存状态改进。
- API Key 遮蔽。

验收：

- 配置页更易扫描。
- 保存失败不丢输入。

### 提交 6：文档与截图资产整理

内容：

- 截图移动或删除。
- docs 索引更新。
- 导入风格说明。

验收：

- 仓库根目录不再散落临时截图。
- 新成员能找到 Web UI 整改相关文档。

## 总体验收清单

完成后应满足：

- `npm run build` 通过。
- Web UI smoke test 通过。
- `web_app/src` 下没有 `.js` / `.vue.js` / `.vue.d.ts` 生成文件。
- `/api/health` 可用，并被前端优先消费。
- 后端在线、离线、部分异常状态均有可理解 UI。
- 配置页结构清晰，不再像单一长表单。
- 首页、配置页、登录页、提示词调试页在 375px 与 1440px 下无明显破版。
- 截图资产有明确归档策略。
- TypeScript 导入规范有明确结论。

## 不建议本阶段做的事

- 不建议重做整套 UI。
- 不建议引入大型组件库。
- 不建议把 Web UI 改成营销式首页。
- 不建议在没有 smoke test 前重构路由和入口。
- 不建议删除旧元信息接口 fallback。
- 不建议伪造后端不支持的配置保存能力。

## 下一步建议

最小可执行下一步：

1. 新增 `scripts/check_web_source_artifacts.ps1`。
2. 新增一个能断言首页内容的 smoke test。
3. 把这两个检查串进 `scripts/check_web_ui.ps1`。

完成这三项后，再推进 `/api/health` 会更稳，因为前端状态逻辑的后续改动已经有基础回归保护。
