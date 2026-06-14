# 生成进度体验优化方案

日期：2026-06-14

状态：已实施

实施提交：`3e0e50c39f83654abe4a7f4364a9ffbac47bccff`（`Improve generation progress experience`）

中间文件补充提交：`bb5de5af8ca5dfbdb4738f75a854a5122ef12a34`（`Show intermediate files in generation progress`）

## 实施记录

本轮已完成同一轮“生成进度体验优化”的核心改造：

- 生成页顶部入口改为 `查看任务详情`，通过显式导航进入 `/tasks/:sessionId`，导航失败时给出 toast 反馈。
- 页内折叠区改为 `运行日志 / 排错信息`，与跳转入口职责分离。
- 生成进度顶部状态改为“生命周期状态 + 当前步骤”，并在下方展示当前动作摘要。
- 恢复 session 时已支持回填历史日志；页内日志面板打开时也会按需合并 session 历史日志快照，避免只依赖实时 SSE。
- 日志面板已明确提示 `DEBUG` 是否被隐藏，并默认显示 `DEBUG` 及以上日志，避免排错信息被初始过滤隐藏。
- 从任务列表点击 `继续` 回到生成页时，回填历史任务的输入路径或远程输入名、输出目录、任务模式和 FPA 运行参数快照。
- 阶段卡片已拆成同级的 `输出模板`、`中间文件`、`阶段产物` 三段；中间文件和交付物分别展示，并在本机模式提供 `打开目录`、远程完成后提供 `下载 ZIP`。
- `gen-fpa` 已补充阶段中间文件事件，当前会在 `生成 FPA` 卡片的 `中间文件` 区域列出 FPA 模板 Markdown、FPA 工作量汇总 Markdown、FPA 规划 Markdown、FPA 审计 Trace。
- `gen-spec`、`gen-cosmic`、`gen-list` 的中间文件已补齐到各自阶段卡片：SPEC 展示功能章节 Markdown，COSMIC 展示核减汇总、模板、AI 填充和校验材料，LIST 展示送审参数快照。
- 输出模板 manifest 预检事件按模板类型归属到对应阶段：FPA、需求说明书、COSMIC、需求清单分别展示在自身阶段卡片中。
- 日志终态同步已补强：页内日志面板持续打开时会监听 session 变化和终态变化，任务详情页也会在实时流结束或轮询发现终态后重新合并 session 历史日志，并对重复事件去重、自动滚动到最新日志。

已验证：

- `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_callbacks.py tests/test_session_manager.py`
- `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_callbacks.py`
- `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_callbacks.py tests/test_pipeline.py::TestGenCosmic::test_generates_cosmic_xlsx tests/test_pipeline.py::TestGenSpec::test_generates_docx tests/test_pipeline.py::TestGenList::test_generates_xlsx`
- `.\.venv\Scripts\python.exe -m pytest tests/test_session_manager.py`
- `npm run build`
- `git diff --check`

## 问题

生成页“生成进度”区域中的 `运行详情 / 排错信息` 在 `gen-fpa` 运行完成后点击无明显反应。当前体感是用户已经看到任务结束，但无法顺手进入对应任务详情页继续看日志、交付物和参数快照。

同一区域右上角的任务状态目前只展示 `已完成`、`运行中`、`已停止` 等生命周期状态。这个信息过粗，用户无法从首屏判断当前任务处在“读取基础数据”“生成 FPA”“生成需求说明书”“等待确认”等哪一个具体步骤。

生成页框内和框外都在表达“运行详情 / 排错信息”时会产生重复，容易让用户误以为是同一个动作。需要把“跳转到任务详情”和“留在本页看日志”分开命名。

页内 `运行日志 / 排错信息` 曾经打开后日志有时不全、也不够同步。原面板主要依赖实时事件流，缺少打开时的 session 历史日志回填，默认级别过滤也会把一部分调试信息藏起来；该问题已通过展开时合并历史快照、阶段事件同步追加到日志面板、默认显示 `DEBUG` 级别修正。

最新复现显示：交付物已经出现，但日志面板仍可能停在 `basedata` 早期片段。这说明上一轮只解决了“打开时补拉”和“默认过滤”的问题，还缺少日志面板持续打开时的 session 变化监听、任务进入终态后的最终历史补拉，以及任务详情页独立日志区的同口径回填、去重和滚动行为。

从任务列表点击 `继续` 回到生成页时，当前只恢复 session 运行状态和进度，不会回填主操作区的 `功能清单 .xlsx 路径（或项目目录）`。用户无法确认当前继续的是哪份输入，也不方便基于原参数再次启动或定位问题。

生成进度中的阶段产物和模板契约也需要统一归属。中间文件曾经只打标签但缺少操作入口，部分阶段生成的中间文件没有出现在对应阶段卡片中；该问题已通过同级 `中间文件` 区块和各生成过程的中间文件事件补充修正。输出模板 manifest 信息也应归属到对应生成阶段，而不是只作为泛化进度信息展示。

## 目标行为

- 点击后应进入当前 `sessionId` 对应的任务详情页。
- 完成态、运行态、排队态都应保持可点击，只要当前存在有效 `sessionId`。
- 当前没有 `sessionId` 时，入口保持禁用态，并明确提示任务启动后可查看。
- 如果导航失败，应给出可见错误反馈，不能表现为静默无响应。
- 页面内外两个入口的文案应区分清楚：一个负责跳详情，一个负责看当前页日志。
- 生成进度框中的任务状态应带上当前步骤，而不是只展示生命周期状态。
- 用户在不展开日志、不进入详情页的情况下，也能看出任务当前在做什么。
- 每个生成阶段都应展示本阶段产生或使用的关键材料，包括中间文件、最终交付物和输出模板契约。
- 中间文件也应可操作：本机模式可打开目录，远程模式可下载或进入下载包。
- 修改后不影响生成页的启动、停止、进度展示和日志能力。

## 相关文件范围

- `web_app/src/views/Home.vue`
  - 生成页顶部“生成进度”区域。
  - 当前入口文案和框内折叠区文案所在位置。
  - 当前状态徽标 `runStateText` 的展示逻辑。
  - 从 `session` 或 `fromSession` 参数恢复任务时的表单回填逻辑。
- `web_app/src/stores/steps.ts`
  - 生成过程步骤状态、步骤名称和 `current_action` 来源。
- `web_app/src/components/GenerationProgress.vue`
  - 生成过程卡片中步骤状态和当前动作的既有展示。
  - 需要保持与生成进度框顶部摘要口径一致。
  - 阶段产物、中间文件、输出模板 manifest 的归属和操作入口。
- `web_app/src/views/TaskDetail.vue`
  - 任务详情页。
  - 需要确认从主页跳转后能正常展示运行详情、生成过程、日志和交付物。
- `web_app/src/router/index.ts`
  - `/tasks/:sessionId` 路由定义。
- `web_app/src/stores/session.ts`
  - 结束态是否保留 `sessionId`。
- `web_app/src/stores/log.ts`
  - 任务完成后日志连接和状态收束逻辑。
- `web_app/src/components/LogViewer.vue`
  - 页内日志面板的级别过滤和滚动行为。
- `web_app/src/stores/config.ts`
  - 主操作区表单状态，包括 `xlsxPath`、`outputDir`、`pipelineMode` 和 FPA 运行参数。
- `web_app/src/views/Tasks.vue`
  - 任务列表 `继续` 操作入口。
- `scripts/web_smoke.ps1`
- `scripts/web_mobile_smoke.mjs`
  - 首页文案断言和可视可点击状态的回归检查。

## 现状观察

1. 主页入口当前使用 `RouterLink` 跳转到 `/tasks/${session.sessionId}`。
2. 路由层已经存在 `/tasks/:sessionId`，并且服务端也为 `/tasks/{path:path}` 提供 SPA fallback。
3. `session.finish()` 不会清空 `sessionId`，所以“完成后入口消失”不是当前主因。
4. 任务详情页会同时拉取历史、session 状态和日志；如果任一接口异常，页面会落到错误态或空态，用户可能把它理解成“没反应”。
5. 步骤 store 已经维护 `读取基础数据`、`生成 FPA`、`生成需求说明书`、`生成 COSMIC`、`生成需求清单` 等步骤，以及每个步骤的 `status` 和 `current_action`。
6. 生成进度框顶部当前只展示生命周期状态，没有消费步骤 store 中的当前步骤信息。
7. 当前页内折叠区与跳转入口使用了相近的“运行详情 / 排错信息”语义，存在命名重叠。
8. 页内日志面板打开时会调用 `/api/sessions/{sessionId}/logs` 合并历史快照；实时 `EventSource` 仍负责后续增量追加。
9. `LogViewer` 默认显示级别为 `DEBUG`，用户手动调整的过滤级别会保存在浏览器本地。
10. 当前页内日志只在 details toggle 打开时主动回填；如果面板已经打开，session 后续变化或任务进入完成态，不会自动再次补拉完整历史。
11. `TaskDetail.vue` 使用独立日志数组，不复用 `LogViewer` store 的历史合并和去重逻辑；实时流结束时也需要再拉一次 `/api/sessions/{sessionId}/logs`。
12. `Tasks.vue` 的 `继续` 操作只检查 `/api/sessions/{sessionId}` 后跳回 `/?session={sessionId}`。
13. `Home.vue` 的 `restoreSessionById` 只读取 session 状态，不读取 `/api/history/{sessionId}`，因此拿不到历史记录中的 `input_path`、`output_dir` 和 `run_config`。
14. 本机目录输入在后端会被解析为具体 `.xlsx`。当前历史记录稳定保存的是解析后的 `input_path`，不一定保存用户最初输入的目录文本。
15. `GenerationProgress.vue` 已按 `artifact.is_temp` 将材料拆成同级 `中间文件` 和 `阶段产物` 区块，不再把中间文件混在阶段产物中只靠标签区分。
16. `gen-fpa` 已在后端补发中间文件 artifact：`1.1.gen-fpa-FPA-模板.md`、`1.2.gen-fpa-FPA工作量-总和.md`、`1.3.gen-fpa-AI填充-FPA.md`、`1.5.gen-fpa-audit-trace.json`；`rules_only` 场景会按路径去重，避免同一 MD 重复展示。
17. `gen-cosmic` 已展示 `3.1.gen-cosmic-FPA核减后的工作量-总和.md`、`3.2.gen-cosmic-COSMIC-模板.md`、`3.3.gen-cosmic-AI填充-COSMIC.md`、`COSMIC JSON 草稿` 和 `COSMIC 校验报告`。
18. `gen-spec` 已展示 `2.1.gen-spec-SPEC-功能需求章节-模板.md` 和 `2.2.gen-spec-AI填充-SPEC-功能需求章节.md`。
19. `gen-list` 已新增送审参数快照 Markdown，记录本次 `cfp_total`、`fpa_reduced`、模板路径和任务模式，并作为中间文件展示。
20. 输出模板 manifest 目前作为步骤卡片中的“输出模板”摘要展示，并已按阶段归属：FPA manifest 属于 `生成 FPA`，spec manifest 属于 `生成需求说明书`，cosmic manifest 属于 `生成 COSMIC`，list manifest 属于 `生成需求清单`。

## 诊断假设

1. 最可能原因：入口跳转本身成功，但任务详情页初次加载失败或空态不够明确，用户把结果理解成无响应。
2. 次可能原因：当前入口是声明式 `RouterLink`，在某些运行态或布局条件下没有形成足够明显的交互反馈。
3. 较低可能原因：完成态后日志连接、session 恢复或本地存储逻辑把页面状态重置，造成用户以为点击没有生效。
4. 状态信息过粗会放大“无响应”体感：用户只看到 `已完成`，但不知道交付物是否生成、最后完成的是哪个步骤、是否还有可查看的详情。
5. 任务列表 `继续` 后输入框不回填的直接原因是：恢复 session 时没有读取历史记录并写回 `config` store。

## 拟实施方案

### 1. 把入口改成显式导航动作

- 在 `Home.vue` 中保留同样的视觉样式，但把入口从纯 `RouterLink` 改为显式点击处理。
- 点击时调用 `router.push({ name: 'task-detail', params: { sessionId } })`。
- 若导航失败，统一通过 toast 提示错误。
- 无 `sessionId` 时仍显示禁用态按钮，不改当前视觉语义。
- 顶部跳转入口建议命名为 `查看任务详情`，让用户知道它会离开当前页。

### 2. 补强任务详情页的到达反馈

- 确认进入 `/tasks/:sessionId` 后有清晰首屏状态。
- 若 `history` 或 `session` 数据不存在，页面应显示明确说明，而不是只剩空白区域。
- 保持“返回任务列表”“返回生成设置”“重新运行”等既有动作不变。

### 2.1 区分页内日志入口

- 生成页框内折叠区继续保留当前页内日志查看能力，但文案不要再和跳转入口重名。
- 折叠区建议改名为 `运行日志 / 排错信息`，或更短的 `运行日志`。
- 框内折叠区只负责展开当前页日志，不承担跳转任务详情的职责。

### 3. 加回归检查

- 首页 smoke 要覆盖“存在任务时入口文案仍可见”。
- 增加一个可执行的跳转断言，确认点击后 URL 进入 `/tasks/:sessionId`。
- 若现有 smoke 不够直接，补一个更小的前端 e2e 检查脚本。

### 3.1 补日志回填与同步

- 在生成页打开页内日志面板时，先请求 `/api/sessions/{sessionId}/logs` 做历史回填，再继续监听实时 `EventSource`。
- 当 session 已完成、重新恢复、或页面首次进入时，都应确保已有日志能先展示出来。
- 当日志面板已经打开且 session 进入 `done`、`error`、`cancelled` 等终态时，应再次请求 `/api/sessions/{sessionId}/logs`，把实时流可能漏掉的尾部日志补齐。
- 当日志面板已经打开且 sessionId 变化时，应自动合并新 session 的历史日志，不依赖用户再次折叠/展开。
- `TaskDetail.vue` 的日志区需要和首页保持同样口径：初次加载、实时流结束、轮询发现终态时都要补拉历史日志，并避免重复展示同一事件。
- 需要把 `step_started`、`activity`、`artifact`、`step_done` 等阶段事件同步追加到日志面板，避免进度区和日志区出现内容断层。
- 保持实时流增量追加不变，但不要只依赖流。
- 如果默认级别仍是 `INFO`，需要在面板中明确告诉用户 `DEBUG` 被隐藏，或者把默认级别调整为更适合排错的值。
- 面板打开、历史批量合并和终态补拉后应自动滚动到末尾，避免用户只看到旧日志开头。

### 3.2 继续任务时回填主操作区表单

- 在 `Home.vue` 的 session 恢复流程中，额外读取 `/api/history/{sessionId}`。
- 使用历史记录回填主操作区表单：
  - 本机模式：`config.xlsxPath = history.input_path`。
  - 本机模式：`config.outputDir = history.output_dir`。
  - `config.pipelineMode = history.task_mode`。
  - `run_config.project_name` 回填到 `config.projectName`。
  - `run_config.fpa_profile`、`fpa_strategy`、`fpa_rule_set`、`fpa_core_rules`、`fpa_system_prompt`、`fpa_user_prompt`、`fpa_base_profile`、`fpa_confirmation_mode` 回填到对应 FPA 参数。
  - `run_config.clean` 回填到清理输出目录选项。
- 第一期接受回填为解析后的 `.xlsx` 路径。若用户最初输入的是项目目录，先不强行恢复目录文本。
- 远程上传模式不能恢复浏览器 `File` 对象，应只展示上传文件名或输入摘要，避免让用户误以为文件仍可直接重新提交。
- 如果 `/api/history/{sessionId}` 不存在或无权限，仍允许恢复 session 状态，但表单回填失败要有轻量提示。

### 3.3 阶段产物与模板归属统一规则

实施进度：已完成阶段卡片同级拆分，并补齐 `gen-fpa`、`gen-spec`、`gen-cosmic`、`gen-list` 的阶段中间文件。

- 每个阶段卡片都展示本阶段产生或使用的关键材料，不只展示最终交付物。
- 阶段材料分三类展示：
  - `输出模板`：本阶段使用的 manifest 或模板契约。
  - `中间文件`：用于排错、复核和审计的阶段过程文件。
  - `交付物`：用户最终需要交付或下载的结果文件。
- 所有阶段都采用同一操作规则：
  - 本机模式：中间文件和交付物都可 `打开目录`。
  - 远程模式：中间文件和交付物都可 `下载`，或至少进入同一个结果 ZIP。
  - 中间文件必须保留 `中间文件` 标签，避免和最终交付物混淆。
- 模板契约按阶段归属：
  - FPA manifest 放入 `生成 FPA`。
  - Word/spec manifest 放入 `生成需求说明书`。
  - COSMIC manifest 放入 `生成 COSMIC`。
  - list manifest 放入 `生成需求清单`。
  - 基础数据阶段如果后续有输入解析或基础数据模板契约，也放入 `读取基础数据`。
- 阶段示例：
  - `读取基础数据`：模块树 md、输入检查结果、解析后的基础数据。
  - `生成 FPA`：FPA manifest、FPA 中间 md、FPA 校验报告、FPA 工作量评估表。
  - `生成需求说明书`：Word manifest、章节解析/锚点匹配结果、需求说明书 docx。
  - `生成 COSMIC`：COSMIC manifest、COSMIC 中间报告、COSMIC 估算表。
  - `生成需求清单`：list manifest、清单中间数据、项目需求清单 xlsx。
- 如果后端事件当前没有把某个中间文件挂到正确 step，应优先补事件归属，而不是在前端按文件名硬猜。

### 3.4 补齐其他生成过程的中间文件

- `gen-spec`：
  - 将 `2.1.gen-spec-SPEC-功能需求章节-模板.md` 作为 `生成需求说明书` 阶段的中间文件。
  - 将 `2.2.gen-spec-AI填充-SPEC-功能需求章节.md` 作为 `生成需求说明书` 阶段的中间文件。
  - 需求说明书 Word 继续作为 `阶段产物`。
- `gen-cosmic`：
  - 将 `3.1.gen-cosmic-FPA核减后的工作量-总和.md` 作为 `生成 COSMIC` 阶段的中间文件。
  - 将 `3.2.gen-cosmic-COSMIC-模板.md` 作为 `生成 COSMIC` 阶段的中间文件。
  - 将 `3.3.gen-cosmic-AI填充-COSMIC.md` 作为 `生成 COSMIC` 阶段的中间文件。
  - 保留已有 `COSMIC JSON 草稿` 和 `COSMIC 校验报告` 中间文件。
  - 正式项目功能点拆分表继续作为 `阶段产物`，草稿 Excel 如果仍用于人工补齐，应继续标识清楚，避免和正式交付物混淆。
- `gen-list`：
  - 新增轻量中间文件 `4.1.gen-list-送审参数-快照.md`，记录本次 `cfp_total`、`fpa_reduced`、模板路径和任务模式。
  - 将该快照作为 `生成需求清单` 阶段的中间文件。
  - 项目需求清单 Excel 继续作为 `阶段产物`。
- 所有新增中间文件 artifact 必须设置 `is_temp=True`，并通过后端 `_artifact` / `_artifacts` 事件挂到正确 step。
- 如果某个中间文件在无 AI、跳过、失败或配置关闭场景中不存在，应跳过展示，不制造空占位。

### 4. 生成进度框顶部状态带当前步骤

- 在 `Home.vue` 中新增“当前步骤摘要”计算逻辑。
- 优先取 `steps.steps` 中状态为 `running` 或 `waiting_input` 的步骤。
- 如果没有运行中步骤，则取最后一个 `failed`、`cancelled` 或 `done` 的步骤，用于失败、停止、完成后的摘要。
- 状态徽标展示格式建议为：
  - `运行中 · 生成 FPA`
  - `等待确认 · 生成 FPA`
  - `出错 · 生成 FPA`
  - `已停止 · 生成 FPA`
  - `已完成 · 交付物已生成`
- 在状态徽标下方或标题区域增加一行轻量说明，优先使用当前步骤的 `current_action`。
- 当前没有步骤进展时，保持原来的 `就绪` 或 `等待任务启动` 语义，不强行展示步骤。

### 5. 状态文案口径

- 生命周期状态继续保留，用于颜色和主状态判断。
- 步骤名称用于解释任务当前卡在哪一步。
- 当前动作只作为二级说明，避免把很长的日志文本塞进徽标。
- 任务完成后不要只显示 `已完成`，应显示 `已完成 · 交付物已生成` 或 `已完成 · 生成 FPA`，具体取决于后续是否能稳定识别最后产物步骤。

## 验证方式

1. 启动 Web 前端和后端。
2. 在生成页发起一次 `gen-fpa` 任务。
3. 任务完成后点击顶部入口 `查看任务详情`。
4. 检查浏览器地址是否进入 `/tasks/<sessionId>`。
5. 检查任务详情页是否能看到：
   - 运行详情标题
   - 当前状态
   - 生成过程
   - 日志与错误详情
   - 交付物区域
6. 检查主页顶部跳转入口和页内日志入口：
   - 顶部入口应显示 `查看任务详情`。
   - 页内折叠区应显示 `运行日志 / 排错信息` 或 `运行日志`。
   - 两者不应再同名。
   - 打开页内日志后，应先看到历史日志回填，再随着任务进度继续追加新日志。
   - `DEBUG` 日志如果仍被隐藏，页面应明确说明当前过滤级别。
7. 从任务列表点击运行中任务的 `继续`：
   - 回到生成页后，`功能清单 .xlsx 路径（或项目目录）` 应回填为历史记录中的 `input_path`。
   - 本机任务的输出目录应回填为历史记录中的 `output_dir`。
   - 任务模式和 FPA 运行参数应回填为本次任务提交参数快照。
   - 如果原始输入是目录，第一期可回填解析后的 `.xlsx` 路径。
8. 检查各生成阶段的材料归属和操作：
   - `输出模板`、`中间文件`、`阶段产物` 在阶段卡片中作为同级区块展示。
   - `gen-fpa` 中间文件出现在 `生成 FPA` 阶段卡片中，不只显示在最终结果区或本机目录里。
   - `gen-fpa` 至少应列出 FPA 模板 Markdown、FPA 工作量汇总 Markdown、FPA 规划 Markdown、FPA 审计 Trace。
   - `gen-spec` 应列出 SPEC 功能需求章节模板 Markdown 和 AI 填充 Markdown。
   - `gen-cosmic` 应列出 FPA 核减汇总 Markdown、COSMIC 模板 Markdown、COSMIC AI 填充 Markdown、COSMIC JSON 草稿和 COSMIC 校验报告。
   - `gen-list` 应列出送审参数快照 Markdown。
   - 中间文件保留 `中间文件` 标签，同时提供打开目录或下载操作。
   - FPA、spec、COSMIC、list 的 manifest 展示在对应生成阶段内。
   - 最终交付物和中间文件有清晰标签区分。
9. 在任务运行中检查生成进度框右上角状态：
   - 不只显示 `运行中`。
   - 应展示类似 `运行中 · 生成 FPA` 的当前步骤。
10. 在等待确认时检查状态：
   - 应展示 `等待确认 · 生成 FPA` 或对应步骤。
   - 当前动作应说明正在等待用户确认。
11. 在任务完成后检查状态：
   - 不只显示 `已完成`。
   - 应展示完成状态和最后步骤或交付物摘要。
12. 再回头检查一次无 session 的首页，确认入口仍是禁用态。

## 风险

- 如果把 `RouterLink` 改成显式跳转，可能需要补一点点击失败反馈。
- 若详情页本身有接口 404 或权限问题，用户会先看到详情页错误态，这需要文案清楚。
- 增加测试时要避免把“点击后有路由变化”和“页面内容完全加载成功”混为一谈。
- 如果当前步骤选择规则过于复杂，可能让顶部状态和下方步骤卡片显示不一致。
- 如果 `current_action` 太长，需要在顶部做截断或单独放到二级说明，避免撑乱标题区域。
- 如果日志面板只做增量追加而不做回填，任务完成后再打开会天然缺块。
- 如果默认级别仍是 `INFO`，排错时容易误判为“日志不全”，其实只是被过滤。
- 如果直接把历史 `input_path` 回填到输入框，用户最初输入目录的场景会显示解析后的 `.xlsx`，不是原始目录文本。
- 远程上传任务不能恢复 `File` 对象，只能恢复输入摘要，重新提交仍需要用户重新选择文件。
- 如果历史记录缺失但 session 仍在内存中，表单回填会降级失败，需要避免影响继续查看进度。
- 如果后续新增中间文件但后端没有提供所属 step，前端按名称归类可能不稳定；应继续优先让事件 payload 明确携带 step。
- 中间文件可下载后，远程模式需要确认 ZIP 或下载接口是否包含这些文件，避免 UI 给出不可用操作。
- 模板 manifest 归属到阶段后，不能让同一份 manifest 在多个位置重复出现。

## 验收标准

- `gen-fpa` 结束后，点击顶部入口 `查看任务详情` 能稳定进入对应任务详情页。
- 顶部跳转入口和页内日志入口不再重名。
- 顶部入口负责跳转，页内入口负责本页查看日志。
- 完成态、运行态、排队态都可点击，只要存在有效 `sessionId`。
- 无 `sessionId` 时入口保持禁用。
- 生成进度框顶部状态能展示生命周期状态和当前步骤。
- 运行中、等待确认、失败、停止、完成五类状态都有明确可读的摘要。
- 页内日志面板打开后能看到历史回填，并且后续实时更新同步追加。
- 日志过滤级别不会让用户误以为面板缺日志。
- 从任务列表点击 `继续` 后，主操作区能回填本次任务的输入路径、输出目录、任务模式和 FPA 参数快照。
- 本机目录输入第一期回填为解析后的 `.xlsx` 路径，行为清晰可验收。
- 每个 gen 阶段都能展示自身相关的中间文件、交付物和输出模板契约。
- `gen-fpa` 的 FPA 模板 Markdown、FPA 工作量汇总 Markdown、FPA 规划 Markdown、FPA 审计 Trace 能在 `中间文件` 区块展示。
- `gen-spec`、`gen-cosmic`、`gen-list` 的阶段中间文件能在各自 `中间文件` 区块展示。
- 中间文件可以打开目录或下载，并与最终交付物明确区分。
- manifest 信息按阶段归属展示，不出现泛化重复展示。
- 回归测试能捕捉到这条跳转链路。
