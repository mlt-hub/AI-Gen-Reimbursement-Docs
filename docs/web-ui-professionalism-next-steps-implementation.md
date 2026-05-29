# Web UI 后续整改执行记录

日期：2026-05-29

关联方案：[Web UI 专业度后续整改实施方案](./web-ui-professionalism-next-steps-plan.md)

## 概要

本记录汇总 2026-05-29 连续两轮后续整改的实际落地内容。

第一轮聚焦“可控和防回归”：

- 建立 Web UI 自动化检查脚本。
- 增加前端 smoke test。
- 新增后端 `/api/health`。
- 让前端优先消费 `/api/health`，并保留旧接口 fallback。
- 在配置页增加环境诊断入口。

第二轮聚焦“配置页专业化和资产归档”：

- 整理配置页信息架构。
- 增加分区导航。
- 完善远程个人配置的保存状态。
- 增加 API Key 显示/隐藏控制。
- 建立 Web UI 验证截图归档目录，并归档本次配置页截图。

这两轮修改延续上一阶段原则：不做大改版，不引入大型依赖，不改变核心业务流程，优先建立可靠性、可诊断性和可维护性。

## 第一轮：自动化防回归与健康检查

### 1. 新增源码生成物检查

新增文件：

```text
scripts/check_web_source_artifacts.ps1
```

目的：

- 防止 `web_app/src` 下再次出现构建或编辑器生成物。
- 保护上一轮已修复的 sidecar 问题不回归。

检查范围：

```text
web_app/src/**/*.js
web_app/src/**/*.vue.js
web_app/src/**/*.vue.d.ts
```

行为：

- 如果发现任何匹配文件，输出文件列表并返回非 0 exit code。
- 如果没有发现，输出 `web_app/src 生成物检查通过。`
- 脚本只读，不自动删除文件。

验证：

```powershell
.\scripts\check_web_source_artifacts.ps1
```

结果：

```text
web_app/src 生成物检查通过。
```

### 2. 新增 Web UI smoke test

新增文件：

```text
scripts/web_smoke.ps1
```

目的：

- 用无头 Edge 检查核心页面能否渲染。
- 防止路由基路径、首屏空白、主要页面空白等问题回归。
- 不新增 Playwright 等依赖，避免网络安装和依赖膨胀。

默认检查地址：

```text
http://127.0.0.1:5173/static/dist/
```

检查页面：

- 首页 `/static/dist/`
- 配置页 `/static/dist/config`
- 提示词调试页 `/static/dist/prompt-debug`

核心断言：

- 首页包含 `AI 生成项目报账文档`。
- 首页包含 `任务设置`。
- 首页包含 `执行监控`。
- 首页包含 `后端未连接`、`后端已连接` 或 `检查服务中` 之一。
- 配置页包含 `环境变量`、`个人配置` 或 `系统配置` 之一。
- 提示词调试页包含 `通用提示词调试` 和 `AI 返回结果`。

风险控制：

- 只做 smoke test，不测试复杂任务运行链路。
- 使用 DOM 文本断言，而不是脆弱的截图像素断言。
- 保留 `-EdgePath` 参数，便于不同机器指定 Edge 路径。

### 3. 新增统一 Web UI 检查脚本

新增文件：

```text
scripts/check_web_ui.ps1
```

目的：

把 Web UI 的本地检查流程标准化，避免每次人工手动拼命令。

执行步骤：

1. 运行 `scripts/check_web_source_artifacts.ps1`。
2. 在 `web_app` 下执行 `npm run build`。
3. 启动 Vite dev server。
4. 等待 `/static/dist/` 可访问。
5. 执行 `scripts/web_smoke.ps1`。
6. 结束时关闭 dev server。

实现细节：

- 默认端口为 `5173`。
- 如果 `5173` 被占用，会在后续端口范围内寻找空闲端口。
- 结束时不仅停止 `npm.cmd` 进程，还会按监听端口查找 Vite 子进程并清理，避免残留 `node.exe` 继续占用端口。

验证：

```powershell
.\scripts\check_web_ui.ps1
```

结果：

```text
Step 1/4: 检查 web_app/src 生成物
web_app/src 生成物检查通过。
Step 2/4: 执行前端生产构建
...
Step 3/4: 启动 Vite dev server
Step 4/4: 执行 Web UI smoke test
Web UI smoke test 通过。
Web UI 检查全部通过。
```

额外确认：

- 检查结束后，`127.0.0.1:5173` 没有残留 LISTENING 进程。

### 4. 新增 `/api/health`

修改文件：

```text
web_app/routes/system.py
```

新增接口：

```text
GET /api/health
```

返回示例：

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
    "output_writable": null
  },
  "features": {
    "prompt_debug": true,
    "ai_interactions": true
  }
}
```

实现原则：

- 健康检查保持轻量，不执行昂贵业务逻辑。
- 版本读取复用 `pyproject.toml`。
- 工作模式根据配置和请求来源解析。
- 模板目录检查只判断输入模板目录和输出模板目录是否存在且可读。
- 当前无法可靠判断的 `output_writable` 返回 `null`，不伪造状态。

新增测试：

```text
tests/test_web_system.py
```

覆盖内容：

- `/api/health` 返回 HTTP 200。
- 返回体包含 `ok`、`version`、`work_mode`。
- `work_mode` 在 `local` / `remote` 范围内。
- `api`、`paths`、`features` 结构符合预期。

### 5. 前端优先消费 `/api/health`

修改文件：

```text
web_app/src/App.vue
web_app/src/stores/config.ts
```

修改内容：

- `BackendStatus` 扩展为：

  ```ts
  type BackendStatus = 'checking' | 'connected' | 'degraded' | 'offline'
  ```

- 应用启动时优先请求：

  ```text
  /api/health
  ```

- 请求成功时：
  - `ok !== false` 显示 `后端已连接`。
  - `ok === false` 显示 `后端部分异常`。
  - 使用 `health.version` 设置顶部版本号。
  - 使用 `health.work_mode` 设置工作模式。

- 请求失败时：
  - 回退到旧接口组合：

    ```text
    /api/version
    /api/default-work-mode
    /api/is-local
    ```

兼容性：

- 新后端优先使用 `/api/health`。
- 老后端没有 `/api/health` 时仍能使用旧接口 fallback。
- 后端完全不可达时仍显示 `后端未连接`。

### 6. 配置页新增环境诊断入口

修改文件：

```text
web_app/src/views/Config.vue
```

新增内容：

- 页面顶部新增 `环境诊断` 面板。
- 展示关键状态：
  - 后端连接。
  - 后端版本。
  - 工作模式。
  - 模板目录。
  - 配置接口。
  - 提示词调试。
- 提供 `重新检查` 按钮。
- 展示最近检查时间。
- 后端不可达时显示明确错误：

  ```text
  后端服务未连接：...
  ```

设计策略：

- 使用现有 `surface`、`btn-secondary`、token 颜色。
- 使用紧凑状态徽标，不做大面积告警卡。
- 面板在配置页顶部出现，作为配置前的环境状态入口。

## 第二轮：配置页信息架构、保存状态、截图归档

### 1. 配置页信息架构整理

修改文件：

```text
web_app/src/views/Config.vue
```

原状态：

- 配置页内容线性堆叠。
- 本机模式下环境变量、系统配置、业务规则全部纵向展示。
- 远程模式下个人配置、服务端全局默认、业务规则全部纵向展示。
- 页面更像“长表单/配置文件查看器”，扫描效率不高。

新结构：

- 保留顶部 `环境诊断` 面板。
- 新增配置分区导航。

本机模式分区：

```text
环境变量
系统配置
业务规则
```

远程模式分区：

```text
个人配置
全局默认
业务规则
```

实现方式：

- 新增 `activeTab` 控制当前分区。
- 新增 `configTabs` 根据本机/远程模式动态生成分区。
- 各分区使用 `v-if` 渲染对应内容。

收益：

- 配置页更像管理控制台。
- 用户可以快速在配置类别间切换。
- 避免长页面一次性堆叠过多信息。

### 2. 保存状态完善

修改文件：

```text
web_app/src/views/Config.vue
```

新增状态：

- `savedSnapshot`
- `lastSavedAt`
- `hasUnsavedChanges`
- `saveStatusText`
- `saveStatusClass`

显示状态：

```text
已保存
有未保存修改
保存中
保存失败
```

行为：

- 远程个人配置加载完成后记录初始快照。
- 用户修改 `.env`、布尔字段、普通字段或嵌套配置后，状态变为 `有未保存修改`。
- 保存按钮在没有未保存修改时禁用。
- 保存中显示 `保存中`。
- 保存成功后：
  - 状态回到 `已保存`。
  - 更新快照。
  - 记录 `上次保存` 时间。
- 保存失败后：
  - 状态显示 `保存失败`。
  - 保留用户输入。
  - 显示具体错误信息。

收益：

- 用户不再需要猜测配置是否已经保存。
- 避免重复点击保存。
- 保存失败不会丢失当前输入。

### 3. API Key 显示/隐藏控制

修改文件：

```text
web_app/src/views/Config.vue
```

新增行为：

- `ANTHROPIC_API_KEY` 默认以 password 类型显示。
- 用户可以点击：

  ```text
  显示密钥
  隐藏密钥
  ```

- 切换输入框类型：

  ```ts
  :type="showApiKey ? 'text' : 'password'"
  ```

收益：

- 默认保护敏感值。
- 用户需要检查时仍可主动显示。
- 行为符合配置工具常见预期。

### 4. 配置页响应式宽度修正

修改文件：

```text
web_app/src/views/Config.vue
```

问题：

- 截取 375px 移动端图时，配置页诊断面板右侧看起来有裁切。
- 此前 DevTools 测量显示页面没有真实横向滚动，但截图存在 Windows + Edge headless DPI 换算差异。

修正：

- 配置页根容器改为：

  ```html
  class="mx-auto box-border w-full max-w-3xl space-y-8 overflow-x-hidden px-4 py-6 sm:px-6"
  ```

- 诊断列表和诊断项增加：
  - `min-w-0`
  - `overflow-x-hidden`
  - 更明确的窄屏宽度约束。

验证：

- `npm run build` 通过。
- `scripts/check_web_ui.ps1` 通过。
- 使用 Edge headless 截取了桌面和窄屏配置页截图。

注意：

- 375px 截图在当前 Windows + Edge headless 环境中仍可能出现物理裁切感。
- 为避免误导，最终保留了无裁切的 `narrow` 截图作为归档证据。

### 5. 截图资产归档

新增目录：

```text
docs/assets/web-ui/
```

新增文件：

```text
docs/assets/web-ui/README.md
```

归档约定：

- 不再将 `ui-*.png` 放在仓库根目录。
- 临时截图如果只用于当次人工检查，可以在验证结束后删除。
- 需要长期保留的截图放到 `docs/assets/web-ui/`。
- 命名使用日期、页面、阶段和视口。

本次归档截图：

```text
docs/assets/web-ui/2026-05-29-config-after-desktop.png
docs/assets/web-ui/2026-05-29-config-after-narrow.png
```

已删除/未保留：

```text
docs/assets/web-ui/2026-05-29-config-after-mobile.png
```

原因：

- 该截图受当前 Edge headless DPI 换算影响，存在物理裁切感，容易误导后续审阅。

同时更新：

```text
docs/web-ui-professionalism-next-steps-plan.md
```

补充截图归档执行状态。

## 修改文件清单

### 新增

```text
scripts/check_web_source_artifacts.ps1
scripts/web_smoke.ps1
scripts/check_web_ui.ps1
tests/test_web_system.py
docs/assets/web-ui/README.md
docs/assets/web-ui/2026-05-29-config-after-desktop.png
docs/assets/web-ui/2026-05-29-config-after-narrow.png
docs/web-ui-professionalism-next-steps-implementation.md
```

### 修改

```text
web_app/routes/system.py
web_app/src/App.vue
web_app/src/stores/config.ts
web_app/src/views/Config.vue
docs/web-ui-professionalism-next-steps-plan.md
```

## 验证记录

### 后端 Web 相关测试

命令：

```powershell
.\scripts\test.ps1 tests/test_web_system.py tests/test_web_tasks.py tests/test_web_session_auth.py tests/test_web_logging_bootstrap.py tests/test_web_config_service.py
```

结果：

```text
18 passed
```

### 健康检查和配置服务测试

命令：

```powershell
.\scripts\test.ps1 tests/test_web_system.py tests/test_web_config_service.py
```

结果：

```text
3 passed
```

### 前端构建

命令：

```powershell
cd web_app
npm run build
```

结果：

```text
vue-tsc -b 通过
vite build 通过
```

### 完整 Web UI 检查

命令：

```powershell
.\scripts\check_web_ui.ps1
```

结果：

```text
web_app/src 生成物检查通过。
npm run build 通过。
首页 smoke test 通过。
配置页 smoke test 通过。
提示词调试页 smoke test 通过。
Web UI 检查全部通过。
```

### 残留进程检查

检查项：

```powershell
netstat -ano | Select-String -Pattern "127.0.0.1:5173.*LISTENING"
```

结果：

- 无输出。
- 表示检查脚本和截图验证后没有留下 Vite dev server。

### 源码生成物检查

命令：

```powershell
rg --files web_app/src -g "*.js" -g "*.vue.js" -g "*.vue.d.ts"
```

结果：

- 无输出。

## 当前完成度

已完成：

- 自动化防回归脚本。
- Web UI smoke test。
- 统一 Web UI 检查脚本。
- 后端 `/api/health`。
- 前端 health 优先消费与旧接口 fallback。
- `degraded` 后端状态。
- 配置页环境诊断入口。
- 配置页分区导航。
- 远程个人配置保存状态。
- API Key 显示/隐藏。
- 截图资产归档目录和归档说明。
- 配置页桌面/窄屏截图归档。

仍可继续推进：

- 配置页更深层的信息架构，例如把业务规则从只读文本升级为结构化表单。
- 保存失败场景的前端交互测试。
- 将 `scripts/check_web_ui.ps1` 接入 CI。
- 明确 TypeScript 显式 `.ts` 导入是否作为长期团队规范。
- 增加真实浏览器/Playwright 设备模拟，替代 Edge headless DPI 不稳定截图。

## 风险与注意事项

### 1. `/api/health` 当前仍是轻量健康检查

它不会深度检查所有文件系统权限，也不会执行真实生成链路。当前重点是给前端提供稳定、快速、可扩展的状态入口。

后续可以逐步增强：

- 输出目录可写性。
- 模板文件完整性。
- AI 配置是否存在。
- 后端任务执行依赖是否齐备。

### 2. 配置页分区当前只改变呈现结构

这次没有改变后端配置保存格式，也没有改动业务字段语义。远程个人配置仍然通过 `/api/user/config` 保存。

### 3. 截图验证受当前无头 Edge 环境影响

在 Windows + Edge headless 下，375px 截图可能出现物理裁切。当前使用 `narrow` 截图作为可读归档证据，自动化回归仍以 DOM smoke test 和构建为准。

### 4. `docs/` 当前在 git 状态中可能整体显示为未跟踪

如果提交，需要确认以下文档和资产都纳入：

- `docs/web-ui-professionalism-next-steps-plan.md`
- `docs/web-ui-professionalism-next-steps-implementation.md`
- `docs/assets/web-ui/README.md`
- `docs/assets/web-ui/*.png`

## 建议下一步

最值得继续做的是：

1. 将 `scripts/check_web_ui.ps1` 接入 CI 或项目统一测试入口。
2. 把配置页保存失败场景补成可自动验证的测试。
3. 决定 TypeScript 显式 `.ts` 导入是否写入前端开发规范。

到目前为止，Web UI 的后续整改已经具备了“可打开、可诊断、可检查、可归档”的基础闭环。
