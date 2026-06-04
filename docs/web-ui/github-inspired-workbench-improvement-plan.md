# Web UI GitHub 工作台化改进方案

日期：2026-06-04

## 背景

本方案综合参考了以下 GitHub 页面形态：

- GitHub Dashboard：左侧全局导航、中间主工作流、右侧轻量信息栏。
- 仓库首页：顶部仓库导航、文件列表、右侧元信息摘要。
- 仓库 Settings：左侧分组设置导航、右侧分段配置表单。
- Actions 新建 workflow：搜索框、分类区块、模板卡片。
- Actions runs 列表：左侧 workflow 过滤、右侧高密度运行记录列表。
- Actions run summary：任务状态、触发信息、耗时、产物、注解、作业摘要。
- Actions job log：左侧 run 内导航、右侧阶段折叠日志、日志搜索、每步耗时。

当前 Web UI 已完成一轮专业化优化：导航降噪、FPA 预览入口前置、移动端卡片、友好错误文案、高级选项分组、操作栏层级整理和响应式验收。本轮不重复这些基础优化，而是把产品进一步升级为“可追踪、可诊断、可复盘”的自动化生成工作台。

## 设计原则

1. **任务优先**
   用户进入系统后，第一视觉焦点应是“当前任务能否启动、运行到哪一步、产物在哪里”，而不是大面积说明或营销式欢迎页。

2. **高密度但可读**
   参考 GitHub Actions 的信息密度：列表行可以紧凑，但状态、标题、触发来源、时间、耗时必须稳定对齐。

3. **摘要先于日志**
   日志是诊断材料，不应长期占据默认主视觉。默认展示阶段和异常摘要，用户需要时再展开原始日志。

4. **侧栏承载导航，主区承载任务**
   左侧用于筛选和局部导航，中间用于主任务内容，右侧只放上下文摘要或详情，不用装饰性卡片。

5. **FPA 术语严格稳定**
   FPA 相关页面继续遵循 `docs/fpa/result-review-terminology.md`，用户可见文案固定使用 `新增/修改功能点`、`类型`、`计算依据归类`、`计算依据说明`、`生成方式`。

## 总体信息架构

推荐将 Web UI 的核心页面理解为四类 GitHub 式工作台：

| 页面 | 借鉴对象 | 目标形态 |
|---|---|---|
| 首页生成任务 | GitHub Dashboard + Actions run summary | 项目工作流状态 + 当前/最近 run 总览 |
| 历史记录 | Actions runs 列表 | 按项目聚合、可搜索、可筛选、可复盘的运行记录 |
| 生成进度与日志 | Actions job log | 阶段折叠日志 + 搜索 + 注解 |
| FPA 预览 | 仓库文件列表 + run annotations | 审阅列表 + 详情抽屉 + 异常定位 |
| 高级配置 | Settings | 分组导航 + 分段配置 |
| 生成/预览方案选择 | Actions workflow templates | 搜索 + 分类 + 方案卡片 |

## Workflow 与 Run 双层状态前置约束

优先级：P0

`gen-all` 可以保留为理想状态下的一键快捷路径，但真实业务通常是分步进行：先 `gen-fpa`，人工审阅和确认送审工作量，隔几天再 `gen-cosmic`，之后再生成需求清单和需求说明书。

因此 Web UI 不应只围绕“一个 session 是否 running”建模。更准确的产品对象是：

```text
项目工作流 / workflow
  ├─ run: gen-basedata
  ├─ run: gen-fpa
  ├─ 人工审阅 / 确认送审工作量
  ├─ run: gen-cosmic
  ├─ 人工确认 CFP / FPA
  ├─ run: gen-list
  └─ run: gen-spec
```

其中：

- **Workflow 状态**描述项目整体停在哪一步，可以长期存在。
- **Run 状态**描述某一次后台执行是否正在跑，不应该跨天“运行中”。

### Workflow 状态

| 状态 | UI 文案 | 含义 | 主操作 |
|---|---|---|---|
| `not_started` | `待生成 FPA` | 尚未开始正式工作量评估 | `生成 FPA` |
| `fpa_running` | `正在生成 FPA` | 当前 run 正在执行 gen-fpa | `停止` |
| `fpa_review` | `待确认 FPA` | gen-fpa 已完成，等待人工审阅和确认送审工作量 | `确认送审工作量` |
| `cosmic_ready` | `待生成 COSMIC` | FPA 已确认，下一步可运行 gen-cosmic | `生成 COSMIC` |
| `cosmic_running` | `正在生成 COSMIC` | 当前 run 正在执行 gen-cosmic | `停止` |
| `list_ready` | `待生成需求清单` | COSMIC 已完成，等待确认 CFP/FPA 后生成需求清单 | `生成需求清单` |
| `spec_ready` | `待生成需求说明书` | 需求清单或基础数据已具备，可生成 SPEC | `生成需求说明书` |
| `completed` | `已完成` | 当前项目所需交付物已完成 | `打开交付物目录` / `下载交付物` |

### Run 状态

Run 状态只表达某一次后台执行：

| 状态 | 含义 | UI 文案 | 典型场景 |
|---|---|---|---|
| `idle` | 当前没有后台 run | `无运行` | 等待用户启动下一步 |
| `running` | 后台任务正在执行 | `运行中` | 正在执行 gen-fpa、gen-cosmic、gen-list 或 gen-spec |
| `waiting_input` | 短时间等待当前页面确认 | `等待确认` | 弹窗要求输入 FPA 核减后的工作量或确认送审工作量 |
| `done` | 本次 run 完成 | `已完成` | 本次 gen-fpa / gen-cosmic / gen-list / gen-spec 已完成 |
| `error` | 失败终止 | `出错` | 后端异常、文件读取失败、生成失败 |
| `cancelled` | 用户主动停止 | `已停止` | 用户点击停止 |

### 分步业务语义

gen-fpa 后不应视为“旧 session 继续跑”，而应视为“项目 workflow 进入下一阶段”：

```text
run(gen-fpa) 完成 -> workflow: 待确认 FPA / 待生成 COSMIC -> 用户之后启动 run(gen-cosmic)
```

当 workflow 进入 `fpa_review` 或 `cosmic_ready`：

- 后台 run 应结束或释放执行线程。
- 项目工作流、输出目录、中间产物、FPA 结果和 progress snapshot 需要保留。
- 首页主状态显示 workflow 阶段，例如 `待确认 FPA` 或 `待生成 COSMIC`。
- 最近一次 run 显示为 `gen-fpa 已完成`，不计入“运行中”。
- 主按钮根据 workflow 阶段显示 `确认送审工作量` 或 `生成 COSMIC`。
- 历史记录中同一项目下可以看到多次 run，例如 `gen-fpa #12`、`gen-cosmic #13`。

当用户点击下一步：

- 后端从已有 workflow/output checkpoint 恢复。
- 新一段后台任务重新进入 `running`。
- 新 run 记录自己的 `run_state`、耗时、产物和日志。
- 已完成的 workflow 阶段保持完成，后续阶段继续推进。

### 最小兼容方案

如果短期不新增 workflow 存储，也至少应在历史记录和首页派生一个 `workflow_stage`：

- 如果最近 run 是 `from-excel-gen-fpa` 且完成，显示 `待确认 FPA` 或 `待生成 COSMIC`。
- 如果最近 run 是 `from-excel-gen-cosmic` 且完成，显示 `待生成需求清单`。
- 如果当前 run 正在执行，才显示 `运行中`。
- `/api/continue/{session_id}` 仍只用于当前等待输入的 run，不要把它表达成“几天后继续 COSMIC”。

## 阶段 1：首页任务运行体验 Actions 化

优先级：P0

### 目标行为

首页从“表单 + 进度卡片 + 日志面板”升级为“项目工作流入口 + 当前/最近 run 摘要 + 阶段进展”。用户一眼能看到项目停在哪一步、最近一次运行结果、产物和下一步动作。

### 推荐结构

```text
---------------------------------------------------------------+
| 顶部导航：生成 / 预览 / 历史 / 配置                          |
+----------------------+----------------------------------------+
| 任务启动              | 当前任务摘要                            |
| - 输入来源            | 状态 / 触发方式 / 输入来源 / 耗时 / 产物 |
| - 输出目录            |----------------------------------------|
| - 当前 FPA 方案       | 注解：warning / notice / error          |
| - 开始生成            |----------------------------------------|
|                      | 阶段进展                                |
+----------------------+----------------------------------------+
```

### 修改建议

1. 在 [Home.vue](../../web_app/src/views/Home.vue) 中增加 run summary 区域：
   - 空闲态：显示“尚未启动任务”和下一步提示。
   - 运行中：显示 `运行中`、任务模式、输入来源、已运行时间。
   - 等待确认：显示 `等待确认`，突出当前 run 需要用户确认的字段。
   - 分步待办：显示 workflow 阶段，例如 `待确认 FPA`、`待生成 COSMIC`、`待生成需求清单`。
   - 完成态：显示 `已完成`、总耗时、产物数量、输出目录或下载入口。
   - 失败态：显示失败阶段、错误摘要和下一步操作。

2. 把当前任务元信息稳定化：
   - `触发方式`：本机任务 / 远程上传 / 恢复会话。
   - `输入来源`：文件名或本机路径，长文本截断但可查看完整值。
   - `输出位置`：本机目录或远程下载包。
   - `FPA 方案`、`执行策略`、`规则集`。

3. 增加 annotations 区域：
   - `错误`：任务失败、后端异常、文件读取失败。
   - `警告`：兜底生成、配置缺失、后端部分异常。
   - `提示`：使用默认配置、产物已生成、可继续人工确认。

4. 将 `ActionBar` 与 run summary 联动：
   - 运行中只突出 `停止`。
   - 无后台 run 时，根据 workflow 阶段突出 `生成 FPA`、`确认送审工作量`、`生成 COSMIC`、`生成需求清单` 等下一步动作。
   - 完成后突出 `打开交付物目录` 或 `下载交付物 .zip`。
   - `AI 交互`、`新任务` 作为次级操作。

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/views/Home.vue` | 首页布局与当前任务摘要编排 |
| `web_app/src/components/ActionBar.vue` | 完成态、运行态操作层级 |
| `web_app/src/components/GenerationProgress.vue` | 与 run summary 的阶段状态联动 |
| `web_app/src/stores/session.ts` | 当前 run 状态 |
| `web_app/src/stores/workflow.ts` 或等价模块 | 项目 workflow 阶段和下一步动作 |
| `web_app/src/stores/steps.ts` | 暴露 warning/error/notice 摘要 |

### 验收标准

- 空闲、运行中、完成、失败四种状态下，首页首屏都有明确任务摘要。
- 任务完成后，不打开日志也能知道结果、耗时和产物入口。
- 失败时不只显示原始错误，必须说明失败阶段和下一步。
- 375px 下任务摘要不横向溢出。

## 阶段 2：生成进度与日志改为 job steps

优先级：P0

### 目标行为

将当前阶段卡片网格改成 GitHub Actions job log 风格：每个阶段一行，默认折叠，展示状态、阶段名和耗时。点击阶段后展开日志或产物详情。

### 推荐结构

```text
---------------------------------------------------+
| build / 生成任务                       搜索日志   |
+---------------------------------------------------+
| v 生成基础数据                         18s        |
|   日志片段 / 阶段产物 / 警告                      |
| > 生成 FPA                                  49s   |
| > 生成 SPEC                                 20s   |
| > 生成 COSMIC                               33s   |
| > 写入交付物                                10s   |
+---------------------------------------------------+
```

### 修改建议

1. [GenerationProgress.vue](../../web_app/src/components/GenerationProgress.vue) 从卡片网格改为阶段列表：
   - 左侧：展开箭头 + 状态图标。
   - 中间：阶段名称和当前动作。
   - 右侧：耗时、产物数量、警告数量。

2. 阶段支持折叠：
   - 默认只展开当前运行阶段和失败阶段。
   - 完成阶段默认折叠，只显示摘要。
   - 用户可手动展开查看产物和日志片段。

3. 增加日志搜索：
   - 搜索范围覆盖阶段名、当前动作、错误信息、日志文本。
   - 命中时自动展开对应阶段。

4. `LogViewer` 默认降级为“原始日志详情”：
   - 不再在空闲态占据大面积深色面板。
   - 可作为展开阶段中的原始日志区域。
   - 保留完整日志入口，满足调试需求。

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/components/GenerationProgress.vue` | 阶段列表、折叠、耗时、搜索 |
| `web_app/src/components/LogViewer.vue` | 原始日志展示方式调整 |
| `web_app/src/stores/log.ts` | 支持按阶段或关键字筛选日志 |
| `web_app/src/stores/steps.ts` | 记录阶段开始/结束时间、耗时、日志关联 |

### 验收标准

- 1440px 下阶段列表比卡片网格更紧凑，首屏可看到更多阶段。
- 运行中阶段醒目，已完成阶段不抢主视觉。
- 搜索日志能定位到阶段。
- 失败阶段默认展开并展示错误摘要。

## 阶段 3：历史记录 Actions runs 列表化

优先级：P0

### 目标行为

历史记录页从“产物/记录集合”升级为“运行记录列表”。用户可以像看 GitHub Actions runs 一样筛选、搜索、进入详情。

### 推荐结构

```text
+----------------------+----------------------------------------+
| 全部任务              | 搜索运行记录                            |
| 本机任务              | 42 次运行                               |
| 远程任务              |----------------------------------------|
| FPA                   | ✓ 项目 A  本机任务 master  5m 14s       |
| COSMIC                | ✕ 项目 B  远程任务 失败于 FPA  1m 03s   |
| SPEC                  | ...                                    |
+----------------------+----------------------------------------+
```

### 修改建议

1. [History.vue](../../web_app/src/views/History.vue) 增加左侧筛选：
   - `全部任务`
   - `本机任务`
   - `远程任务`
   - `已完成`
   - `失败`
   - `已停止`

2. 右侧运行记录列表每行展示：
   - 状态图标。
   - 项目名或输出目录。
   - 触发方式。
   - 时间。
   - 总耗时。
   - 产物入口。
   - 更多操作。

3. 顶部增加搜索与过滤：
   - 搜索项目名、输出目录、session id。
   - 按状态、模式、日期范围过滤。

4. 点击记录进入详情：
   - 如果已有详情页，可跳转详情页。
   - 如果暂不新增路由，可在当前页打开右侧详情抽屉。

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/views/History.vue` | Actions runs 风格布局 |
| `web_app/src/stores/session.ts` | 当前会话与历史会话字段对齐 |
| `web_app/routes/history.py` | 如后端历史接口缺字段，补充耗时、状态、产物数量 |
| `web_app/services/run_history_service.py` | 历史记录数据结构补齐 |

### 验收标准

- 历史页 1440px 下能快速扫读多条运行记录。
- 支持按状态和关键字过滤。
- 每条记录都能找到产物或失败原因。
- 375px 下列表改为卡片，但字段顺序仍稳定：状态、标题、时间、耗时、操作。

## 阶段 4：FPA 预览 Repo list + Annotations 化

优先级：P1

### 目标行为

FPA 预览页继续保持专业审阅工具定位，但从“表格预览”进一步升级为“审阅列表 + 详情 + 异常定位”。它借鉴仓库文件列表的扫读效率和 Actions annotations 的异常聚合。

### 推荐结构

```text
+----------------------+----------------------------------------+------------------+
| 输入设置              | 工具条：搜索 / 类型 / 生成方式 / 异常项 | 当前结果详情       |
| 预览设置              |----------------------------------------| 新增/修改功能点    |
| 生成基础数据          | ✓ 新增/修改功能点 A  EI  AI  正常       | 类型 / 生成方式    |
| 生成预览              | ! 新增/修改功能点 B  ILF  兜底 需审阅   | 计算依据归类       |
|                      | ...                                    | 计算依据说明       |
+----------------------+----------------------------------------+------------------+
```

### 修改建议

1. 在 [FpaPreview.vue](../../web_app/src/components/FpaPreview.vue) 顶部增加审阅工具条：
   - 搜索 `新增/修改功能点`。
   - 按 `类型` 筛选。
   - 按 `生成方式` 筛选。
   - 只看异常项。
   - 全部展开 / 全部收起。

2. 增加 annotations 摘要：
   - 缺失功能过程。
   - 兜底生成。
   - AI 失败后兜底。
   - 规则集未命中。
   - 计算依据说明为空或过短。

3. 桌面端增加详情抽屉：
   - 点击一行后右侧显示详情。
   - 主列表只保留高密度字段：`#`、`新增/修改功能点`、`类型`、`生成方式`、`计算依据归类`。
   - `计算依据说明` 放在详情抽屉，不挤压主列表。

4. 移动端保留卡片形态：
   - 默认展示 `新增/修改功能点`、`类型`、`生成方式`、`计算依据归类`。
   - `计算依据说明` 默认折叠。
   - 异常项在卡片顶部用小型状态提示。

5. 可选增加审阅状态：
   - `待审阅`
   - `已确认`
   - `有疑问`
   - `需重算`

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/components/FpaPreview.vue` | 工具条、筛选、详情、异常摘要 |
| `web_app/src/views/FpaPreviewPage.vue` | 页面区域编排 |
| `web_app/src/components/PreviewLayout.vue` | 桌面三栏或右侧详情抽屉支持 |
| `docs/fpa/result-review-terminology.md` | 若新增审阅状态术语，需要补充确认 |

### 验收标准

- FPA 页面用户可见术语完全符合规范。
- 1440px 下主列表不被长说明撑开。
- 375px 下无需横向滚动即可审阅单条结果。
- 异常项可从摘要定位到具体行。

## 阶段 5：高级配置 Settings 化

优先级：P1

### 目标行为

高级配置从折叠长表单升级为 Settings 风格的分组配置页或分组面板。普通用户路径保持轻，高级用户能稳定找到完整配置。

### 推荐分组

| 分组 | 字段 |
|---|---|
| 输入与输出 | 功能清单输入、输出目录、上传文件 |
| AI 配置 | API Key、模型、Base URL、最大 Token 数 |
| FPA 策略 | FPA 方案、执行策略、规则集 |
| 运行与调试 | 清理输出、提示词调试、模板下载 |
| 安全与授权 | 授权状态、远程登录状态、敏感配置提示 |

### 修改建议

1. [AdvancedOptions.vue](../../web_app/src/components/AdvancedOptions.vue) 内部改为分组列表：
   - 每组有标题、说明、字段区。
   - 字段说明短而具体，不重复解释常识。

2. 如果配置项继续增多，新增 `ConfigSectionNav`：
   - 桌面端左侧分组导航。
   - 移动端顶部 select 或折叠组。

3. [Config.vue](../../web_app/src/views/Config.vue) 与首页高级选项共用同一组配置分区，避免两套文案。

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/components/AdvancedOptions.vue` | 高级选项分组 |
| `web_app/src/views/Config.vue` | Settings 风格配置页 |
| `web_app/src/components/ConfigPanel.vue` | 首页普通路径降噪 |

### 验收标准

- 普通生成路径不被 API Key、模型、规则集淹没。
- 高级配置可通过分组快速定位。
- 移动端展开高级设置后不出现长而无结构的字段堆叠。

## 阶段 6：方案选择 Actions template 化

优先级：P2

### 目标行为

将“生成模式 / FPA 方案 / 规则集 / 预览类型”从普通 select 升级为可搜索、可解释的方案选择器，借鉴 Actions 新建 workflow 页面。

### 适用场景

- FPA 方案选择。
- 执行策略选择。
- 规则集选择。
- 未来 COSMIC / SPEC 预览生成器入口。

### 推荐结构

```text
搜索方案

推荐方案
[严格 FPA] [默认 FPA] [快速预览]

高级方案
[仅规则] [AI 补充] [兜底诊断]
```

### 修改建议

1. 先不替换所有 select，只在 FPA 预览页试点。
2. 每个方案卡片展示：
   - 名称。
   - 适用场景。
   - 风险提示。
   - 是否推荐。
3. 保留原 select 作为低成本 fallback，避免一次性改动过大。

### 涉及文件

| 文件 | 关注点 |
|---|---|
| `web_app/src/composables/useFpaOptions.ts` | 方案数据结构 |
| `web_app/src/components/AdvancedOptions.vue` | 方案选择入口 |
| `web_app/src/components/FpaPreview.vue` | 预览页方案选择试点 |

### 验收标准

- 用户能理解不同方案差异，而不是只看到内部 id。
- 推荐方案和高级方案层级清楚。
- 不影响键盘操作和移动端布局。

## 组件抽取建议

为了支持以上阶段，建议按真实重复度逐步新增基础组件，不做一次性组件库重写。

| 组件 | 用途 |
|---|---|
| `RunSummary.vue` | 首页当前任务摘要 |
| `AnnotationsPanel.vue` | warning / notice / error 聚合 |
| `JobStepList.vue` | 阶段折叠列表 |
| `JobStepRow.vue` | 单个阶段行 |
| `LogSearchInput.vue` | 日志搜索 |
| `RunList.vue` | 历史运行记录列表 |
| `RunListRow.vue` | 单条运行记录 |
| `FpaReviewToolbar.vue` | FPA 搜索筛选工具条 |
| `FpaReviewDrawer.vue` | FPA 详情抽屉 |
| `BaseBadge.vue` | 状态、类型、生成方式 badge |
| `BaseButton.vue` | 主次按钮统一 |

抽取原则：

- 先在业务组件内完成一版，再抽公共组件。
- 只有跨两个以上页面复用时才抽基础组件。
- 不为单纯转移模板而抽组件。

## 数据与接口补充建议

如果后端历史和会话数据缺少以下字段，建议补齐：

| 字段 | 用途 |
|---|---|
| `started_at` / `finished_at` | 计算任务耗时 |
| `trigger_source` | 区分本机、远程上传、恢复会话 |
| `input_label` | 历史列表和 run summary 展示输入来源 |
| `output_label` | 展示输出目录或下载包 |
| `artifact_count` | 完成态摘要 |
| `warning_count` / `error_count` / `notice_count` | annotations 摘要 |
| `failed_step_key` | 失败定位 |
| `step_started_at` / `step_finished_at` | 阶段耗时 |
| `step_log_excerpt` | 阶段折叠预览 |
| `workflow_id` | 同一项目多次 run 的聚合键 |
| `workflow_stage` | 项目整体阶段，如 `fpa_review`、`cosmic_ready` |
| `last_run_id` | 首页恢复时定位最近一次 run |
| `last_run_mode` | 最近一次执行的是 gen-fpa、gen-cosmic、gen-list 等 |
| `next_action` | 前端主按钮文案和下一步接口依据 |

如果暂时不改后端，可先在前端按已有事件和日志推导部分字段，但需要在代码中明确标注为派生值。

## 推荐实施顺序

### 提交 1：Workflow 与 Run 双层状态

内容：

- 引入或派生 `workflow_stage`，区分项目整体阶段与当前 run 状态。
- gen-fpa 完成后 workflow 显示 `待确认 FPA` 或 `待生成 COSMIC`，最近 run 显示 `已完成`。
- 历史记录按 workflow 聚合同一项目的 gen-fpa、gen-cosmic、gen-list 等多次 run。
- `/api/continue/{session_id}` 仅表达当前 run 的短等待确认，不作为长期继续接口。

验证：

- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_session_manager.py tests/test_web_tasks.py`
- `cd web_app && npm run build`
- gen-fpa 后首页不显示长期 `运行中`；下一步操作显示 `确认送审工作量` 或 `生成 COSMIC`。

### 提交 2：Run summary 与任务完成态

内容：

- 新增 `RunSummary.vue`。
- 首页接入当前任务摘要。
- `ActionBar` 与完成态摘要联动。

验证：

- `cd web_app && npm run build`
- 375px / 1440px 首页检查空闲、运行中、完成、失败状态。

### 提交 3：Job steps 阶段列表

内容：

- `GenerationProgress.vue` 改为阶段列表。
- 增加阶段折叠、耗时、失败默认展开。
- `LogViewer` 降级为原始日志详情。

验证：

- `cd web_app && npm run build`
- 运行任务时检查阶段状态更新。
- 失败场景检查错误阶段展开。

### 提交 4：历史记录 runs 列表

内容：

- `History.vue` 改为左侧筛选 + 右侧 runs 列表。
- 增加搜索和状态过滤。
- 每条记录展示状态、时间、耗时、产物入口。

验证：

- `cd web_app && npm run build`
- 历史记录为空、有成功记录、有失败记录三种状态检查。

### 提交 5：FPA 审阅工具条与详情

内容：

- `FpaReviewToolbar.vue`。
- FPA 搜索、类型筛选、生成方式筛选、异常项筛选。
- 桌面详情抽屉，移动端折叠详情。

验证：

- `cd web_app && npm run build`
- 检查 FPA 术语。
- 375px 无横向滚动。

### 提交 6：Settings 化高级配置

内容：

- 高级配置分组统一。
- `Config.vue` 与 `AdvancedOptions.vue` 文案和结构对齐。

验证：

- `cd web_app && npm run build`
- 首页普通路径不被高级字段干扰。
- 配置页分组可扫描。

## 响应式验收矩阵

| 宽度 | 页面 | 检查点 |
|---:|---|---|
| 320px | 首页 | run summary 不溢出，主操作可点击 |
| 375px | 首页 | 阶段列表可读，日志不压过任务摘要 |
| 414px | 历史记录 | runs 卡片字段顺序稳定 |
| 768px | FPA 预览 | 筛选工具条换行合理，详情不遮挡主内容 |
| 1024px | 高级配置 | 分组导航和内容区不挤压 |
| 1440px | 首页 | 左任务区、主摘要区比例自然 |
| 1440px | 历史记录 | 左筛选 + 右列表信息密度接近 Actions |
| 1440px | FPA 预览 | 列表 + 详情抽屉效率高 |

必查事项：

- 无全局横向滚动。
- 文件路径、错误信息、规则集名称不会撑破布局。
- 按钮文字不溢出。
- 长日志和长 `计算依据说明` 不影响主列表宽度。
- 失败和 warning 不只靠颜色表达。

## 不建议本轮做的事

- 不建议把首页改成营销式 Dashboard。
- 不建议引入重型 UI 组件库。
- 不建议一次性重写全部路由和状态管理。
- 不建议为了 GitHub 风格复制 GitHub 的视觉细节，应借鉴信息架构和交互密度。
- 不建议把所有日志默认做成深色控制台；默认应展示阶段摘要。
- 不建议在 FPA 页面引入未确认的新业务术语。

## 最小可执行下一步

如果只做一批，建议优先完成：

1. 拆分 workflow 阶段与 run 状态。
2. gen-fpa 后 workflow 显示 `待确认 FPA` / `待生成 COSMIC`，最近 run 显示 `已完成`，不再长期显示 `运行中`。
3. 首页新增 run summary。
4. `GenerationProgress` 改成 Actions job steps 风格。
5. 日志增加搜索并按阶段折叠。

这些调整能先修正任务语义，再提升“自动化流水线工作台”的专业感，也最贴合当前产品核心路径。
