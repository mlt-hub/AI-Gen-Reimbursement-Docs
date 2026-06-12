# 生成页控件精简分期实施文档

## 文档定位

本文档用于拆分生成页控件精简、运行详情、多任务查看和并发排队相关工作。它不是单轮实施清单，而是分期实施计划。

当前四期均已达到可实施状态，但必须分期推进、分别验证和提交。第四期涉及后端任务生命周期、队列调度和输出目录隔离，必须作为独立任务、独立提交组或独立 PR 实施，不应和第一到第三期的前端页面调整混做。

除四期主线外，本文档还记录一个独立实施项：`FPA Profile 参数联动与自定义 Profile`。该项属于生成页高级参数能力增强，可单独实施和提交。

## 总目标

- 生成页把主流程收紧到同一视觉区域：`操作模式`、`功能清单 .xlsx 路径（或项目目录）`、`开始生成` 在桌面视口中并排或紧凑展示，窄屏自然换行。
- `高级参数（FPA策略与运行参数）` 位于主操作区第一行下方，并保持本次任务参数快照能力。
- 生成页不再展示单独的 `FPA预览` 按钮，但保留 `预览 -> FPA预览` 入口。
- 生成页启动失败时必须在执行监控主区域展示明确错误原因，不能只显示状态“出错”；例如本机功能清单路径不存在时，应直接展示后端返回的 `路径不存在: ...`，并提示用户检查主操作区中的功能清单路径后重新启动。
- 运行中和失败后的任务详情有明确入口，可查看任务状态、`生成过程`、日志、错误详情、参数快照和交付物。
- 任务列表和运行详情支持按 `session_id` 隔离查看，避免日志、确认弹窗和提交结果串到其他任务。
- 任务达到并发上限时进入排队状态，并允许取消排队任务。
- 任务页和历史页完整展示项目名，长项目名不能只靠截断隐藏关键信息。
- `FPA 策略与运行参数` 以 FPA profile 为主控项：官方 profile 展示其绑定的策略、规则集、核心规则和 prompt 模板但不可改；只有自定义 profile 允许用户手动选择这些细项。

## 已确认决策

### 路由与页面

- 运行详情采用独立路由：`/tasks/:sessionId`。
- 任务列表 `/tasks` 继续负责多任务列表、筛选、刷新和任务级入口。
- 生成页的 `运行详情 / 排错信息` 按钮跳转到当前 `session_id` 对应的 `/tasks/:sessionId`。
- 如果当前没有 `session_id`，生成页展示禁用态 `运行详情 / 排错信息` 按钮，并提示“任务启动后可查看”。
- `预览 -> FPA预览` 继续使用现有 `/preview/fpa` 路径。

### 多详情查看

- 第一阶段的多详情查看使用浏览器多标签页或多窗口承载，即每个 `/tasks/:sessionId` 页面只关注一个任务。
- 页面内多标签页、左右分栏属于后续增强，不进入第一版运行详情页验收。
- 每个详情页必须从路由参数读取 `sessionId`，不能依赖全局当前 session。

### 运行状态模型

- 当前状态继续保留：`idle`、`running`、`done`、`error`、`cancelled`。
- 第四期引入队列能力时新增 `queued` 状态。
- `queued` 状态必须出现在后端 session 状态、任务列表、运行详情页和前端状态类型中。

### 开始生成

- 每次成功提交 `开始生成` 都创建新的后端 session 和新的运行历史记录。
- 提交前清空当前页面的运行态、日志和阶段进展。
- 如果提交前校验或后端创建 session 前失败，生成页必须保留并展示本次启动失败的错误摘要；错误摘要应出现在执行监控主区域，同时仍可写入 toast 和日志。
- 任务运行中时保持禁用或明确提示，不允许静默覆盖当前 session。
- 本机模式使用 `功能清单 .xlsx 路径（或项目目录）` 作为输入；目录模式继续按现有规则自动寻找 `.xlsx`。
- 远程模式使用当前选择的上传文件作为输入。
- 高级参数随新任务一起提交，并固化为本次任务的参数快照。

### 新任务

- `新任务` 不是后端任务创建入口，只把生成页清空到准备下一次填写和生成的页面状态。
- `新任务` 只做前端页面清空：清空当前页面 session 状态、日志展示、阶段进展展示、交付物展示，并移除浏览器中的 `ard:lastSessionId`。
- `新任务` 不取消后端任务，不删除运行历史，不删除交付物文件，不删除后端 session 记录，也不创建新任务。
- `新任务` 只在任务完成、失败或已停止后显示；任务运行中只显示 `停止`。
- `新任务` 后保留用户已填或已选择的生成参数，包括操作模式、路径输入和高级参数。
- 点击 `新任务` 后，用户需要再次点击 `开始生成`，才会创建新的后端 session 和运行历史记录。
- 点击 `新任务` 后应清除上一次启动失败的错误摘要，避免用户误以为新任务已经失败。

### 重新运行

- `重新运行` 属于运行详情页和任务列表的任务级操作。
- `重新运行` 基于原任务参数快照创建新的 session，不复用原 session。
- 重跑成功后自动跳转到新 session 的运行详情页。

### 定位参数

- `定位参数` 只负责回到生成页并定位或高亮相关参数。
- `定位参数` 不自动创建新任务，也不隐式修改历史任务。
- 定位协议使用 query 参数：`/?focus=<field>&fromSession=<sessionId>`。
- 第一版支持的 `focus` 值为：`mode`、`input`、`advanced`、`fpa-profile`、`fpa-strategy`、`fpa-rule-set`、`fpa-confirmation-mode`。
- 生成页收到 `focus` 后滚动到对应控件区域，并给出短暂高亮；无法识别的 `focus` 值忽略。

### 并发与队列

- 并发上限由后端配置提供，默认值为 `1`；前端只展示接口返回状态。
- 达到并发上限时，新任务进入 `queued` 状态，不直接失败。
- 排队任务显示“已进入等待队列”以及可用的排队位置；第一版不展示预计等待时间。
- 用户可取消排队中的任务；取消后不影响已在运行的其他任务。
- 第一版不支持服务重启后恢复排队任务；重启后排队任务统一标记为 `cancelled`。
- 列表页只做轮询刷新，不为每个任务维持实时连接。
- 详情页只为当前页面的 `session_id` 建立实时连接；离开详情页时关闭连接或降级为轮询。

### 输出目录隔离

- 远程模式继续使用独立临时工作目录，目录名必须包含新 session id。
- 本机模式如果用户提供的是输出根目录，则后端应为每个 session 创建独立子目录。
- 本机模式如果用户填写输出目录，新任务统一在该目录下创建独立子目录，不直接写入用户填写的根目录。
- 具体目录命名为：`<project_name_or_input_name>_<session_id>`。

### FPA Profile 参数联动

- `FPA 方案` 是 FPA 运行参数的主控项。
- 官方 profile 包括当前内置 profile，例如 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping`。
- 新增一个自定义 profile，名称固定为 `custom_profile`，不要复用旧语义中的 `custom_rules`。
- 每个 profile 都应能展示其绑定的：
  - `strategy`
  - `rule_set`
  - `core_rules`
  - `system_prompt`
  - `user_prompt`
  - `confirmation_mode`
- 选择官方 profile 时，上述细项控件灰掉不可编辑，但必须显示该 profile 当前绑定的选项。
- 只有选择 `custom_profile` 时，上述细项控件才可编辑。
- 从官方 profile 切换到 `custom_profile` 时，自定义细项默认拷贝切换前 profile 的当前绑定值，方便用户在既有口径基础上微调。
- 从 `custom_profile` 切回官方 profile 时，前端保留上一次自定义选择，但页面展示和提交以官方 profile 绑定值为准。
- 任务提交时，官方 profile 由后端按 profile 绑定解析最终细项；`custom_profile` 使用用户显式选择的细项。

### 测试策略

- 第一期先使用前端构建检查和人工检查验收；第二、三期以前端构建检查和可脚本化的页面 smoke 检查为主。
- 如果需要稳定断言 Vue 组件行为，应先引入前端测试命令，再把相关断言纳入 `package.json`。
- 后端任务创建、重跑、队列、取消、输出隔离必须使用 Python 测试验证，运行命令使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- 前端构建检查使用：

```powershell
cd web_app
npm run build
```

## 第一期：生成页主操作区精简

### 实施状态

- 2026-06-10 已实施：生成页主操作区改为第一行紧凑展示 `操作模式`、`功能清单 .xlsx 路径（或项目目录）`、`开始生成`，并将 `高级参数（FPA策略与运行参数）` 放在同一主操作区第二行。
- 2026-06-10 已实施：生成页移除单独 `FPA预览` 按钮，保留导航和预览布局中的 `/preview/fpa` 入口。
- 2026-06-10 已实施：启动失败会在执行监控主区域展示错误摘要和下一步提示；本机路径问题提示用户检查主操作区中的功能清单路径后重新启动。
- 2026-06-10 已实施：`新任务` 改为完成、失败或已停止后显示，并由生成页统一清空页面运行态、日志、阶段进展和旧错误摘要，保留用户已填参数。
- 2026-06-10 已实施：任务页和历史页项目名改为可换行完整展示，不再只依赖截断。

### 目标行为

- 进入生成页后，用户第一眼能完成模式选择、路径填写和开始生成。
- `操作模式`、`功能清单 .xlsx 路径（或项目目录）`、`开始生成` 位于主操作区第一行；桌面并排，窄屏换行。
- `高级参数（FPA策略与运行参数）` 位于主操作区第一行下方。
- 生成页不展示 `FPA预览` 按钮。
- `预览 -> FPA预览` 入口保留，FPA 预览能力不受影响。
- 任务页和历史页完整显示项目名；长项目名可换行、多行展示、详情展开或悬浮提示，但不能只截断隐藏。

### 修改范围

- `web_app/src/views/Home.vue`
- `web_app/src/components/ConfigPanel.vue`
- `web_app/src/components/FileInput.vue`
- `web_app/src/components/run/FpaRunSettingsSection.vue`
- `web_app/src/views/Tasks.vue`
- `web_app/src/views/History.vue`
- 必要时更新相关 web-ui 文档或截图说明。

### 待办

1. 调整生成页文案，不再提示“先预览 FPA 功能点”作为主流程动作。
2. 定位生成页入口组件和 `FPA预览` 按钮来源。
3. 梳理 `操作模式`、输入路径和 `开始生成` 当前状态绑定关系。
4. 梳理 `高级参数（FPA策略与运行参数）` 当前位置、折叠状态和任务参数绑定关系。
5. 将 `操作模式`、路径输入和 `开始生成` 收敛到主操作区第一行。
6. 将 `高级参数（FPA策略与运行参数）` 移到主操作区第二行，位于第一行下方。
7. 移除生成页 `FPA预览` 按钮及仅供该按钮使用的事件处理。
8. 确认 `预览 -> FPA预览` 入口仍存在，且可以进入原 FPA 预览能力。
9. 确认 `开始生成` 保持现有校验逻辑：路径为空、模式未选、任务运行中等状态仍有明确反馈。
10. 为 `开始生成` 的启动失败增加执行监控主区域错误摘要，不只依赖 toast 或折叠日志。
11. 本机功能清单路径不存在时，展示后端返回的 `路径不存在: ...`，并提示“请检查主操作区中的功能清单路径，然后重新启动生成任务。”
12. 确认 `开始生成` 每次成功提交都会创建新 session，并在提交前清空当前页面运行态、日志、阶段进展和旧错误摘要。
13. 确认 `新任务` 按钮只清空页面视图，并保留操作模式、路径输入和高级参数。
14. 确认 `新任务` 不调用取消、关闭、删除、重跑或创建任务接口。
15. 调整任务页和历史页项目名展示，长项目名不破坏表格布局。

### 验收标准

- 桌面视口中主操作控件紧凑排列，页面不再被单个控件纵向拉长。
- 窄屏视口控件自然换行，不重叠、不横向撑爆。
- `高级参数（FPA策略与运行参数）` 和主生成流程保持同一区域。
- 生成页不存在 `FPA预览` 按钮。
- `/preview/fpa` 仍可从预览导航进入。
- 移除按钮后不影响生成任务创建、运行中状态展示和错误提示。
- 使用不存在的本机 `.xlsx` 路径点击 `开始生成` 后，页面执行监控主区域显示明确错误详情和下一步提示，不只显示“出错”。
- `新任务` 行为仅清空页面视图，不影响后端任务、历史或交付物。
- 任务页和历史页项目名完整可见，长项目名不只依赖截断。

### 验证方式

- `cd web_app && npm run build`
- 人工检查桌面和移动端布局。
- 人工检查 `/preview/fpa` 入口仍可进入。
- 人工检查本机模式不存在路径启动失败：执行监控主区域应展示 `路径不存在: ...` 和检查功能清单路径的下一步提示。
- 如已有 smoke 脚本覆盖移动端布局，可补充或运行对应脚本。

### 风险

- 高级参数移入主操作区后，需要确认折叠、默认值和任务提交参数不发生隐式变化。
- 移除生成页按钮时要避免删除 `预览 -> FPA预览` 入口和仍被其他页面复用的预览组件。
- 启动失败错误摘要属于本次页面启动尝试，不应在恢复历史 session、成功启动新 session 或点击 `新任务` 后继续残留。
- 项目名不能简单移除截断，需要稳定的换行、列宽或详情展示策略，避免表格布局被撑坏。

## 独立实施项：FPA Profile 参数联动与自定义 Profile

### 独立实施边界

本项可独立于第二到第四期实施。它属于生成页高级参数能力增强，建议任务标题为：`实现 FPA Profile 参数联动与自定义 Profile`。

本项不改变 FPA 结果审阅术语，不新增 FPA 审阅页字段；用户可见文案仍需遵循 `docs/fpa/result-review-terminology.md`。

### 目标行为

- `FPA 策略与运行参数` 增加可选择项：`strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode`。
- `FPA 方案` 作为主控项，切换 profile 时联动显示对应细项。
- 官方 profile 的细项只读：显示该 profile 对应选项，但控件灰掉不可选。
- 新增 `custom_profile`，只有选择该 profile 时，细项控件才可编辑。
- 切换到 `custom_profile` 时，默认拷贝上一个 profile 的细项值，用户可以在此基础上调整。
- 切回官方 profile 时，保留用户上次自定义选择，但当前显示和任务提交以官方 profile 绑定值为准。
- `开始生成` 提交时，高级参数随新任务固化为本次任务参数快照。
- FPA 审核副本 `*-FPA工作量评估-check.xlsx` 必须写入本次任务最终解析后的 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode`，用于排查 profile 口径、规则集和 prompt 模板选择。
- check Excel 中的 `system_prompt`、`user_prompt` 记录配置 key，不写入 prompt 正文；`core_rules` 同样记录配置 key，不写入规则正文。

### API 与数据契约

- `/api/fpa/options` 返回值需要扩展 profile 绑定信息。
- 每个 profile 选项至少包含：
  - `value`
  - `label`
  - `editable`
  - `strategy`
  - `rule_set`
  - `core_rules`
  - `system_prompt`
  - `user_prompt`
  - `confirmation_mode`
- options 顶层需要返回可选列表：
  - `strategies`
  - `rule_sets`
  - `core_rules`
  - `system_prompt_sets`
  - `user_prompt_sets`
  - `confirmation_modes`
- 官方 profile 的 `editable` 为 `false`。
- `custom_profile` 的 `editable` 为 `true`。
- `custom_profile` 不需要在默认配置中真实定义为业务 profile；后端可以把它作为 Web/API 运行时 profile alias 处理，并用显式细项解析实际 FPA 运行配置。

### 后端解析规则

- 官方 profile：后端忽略前端传入的细项覆盖值，只按 profile 配置中的绑定解析 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`。
- `custom_profile`：后端使用前端显式提交的 `fpa_strategy`、`fpa_rule_set`、`fpa_core_rules`、`fpa_system_prompt`、`fpa_user_prompt`、`fpa_confirmation_mode`。
- `custom_profile` 同时提交内部继承字段 `fpa_base_profile`，用于决定自定义运行时复用哪个官方 profile 的行为 kind、审阅口径和兜底逻辑；该字段不是用户直接编辑项。
- `custom_profile` 缺少任一必填细项时，后端返回明确 400 错误，不静默回退官方 profile。
- `fpa_core_rules`、`fpa_system_prompt`、`fpa_user_prompt` 必须引用已存在的配置 key，不能直接传大段 prompt 文本。
- 运行历史 `run_config` 需要保存 profile 和最终细项 key，方便重跑和排错。
- FPA audit trace 和 check Excel 需要保存同一组最终细项 key：`strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode`。
- 生成 check Excel 时必须以 audit trace 或任务最终解析配置为准，不能只回显前端原始提交值；官方 profile 被前端篡改细项时，check Excel 仍展示后端解析后的官方绑定值。

### 实施记录

2026-06-12 已完成第一版闭环：

- `/api/fpa/options` 已返回 profile 绑定值、`editable`、`core_rules/system_prompt_sets/user_prompt_sets` 可选 key 列表，并追加运行时 `custom_profile`。
- 生成页 `FPA 策略与运行参数` 已新增 `core_rules`、`system_prompt`、`user_prompt` 选择控件；官方 profile 显示绑定值但禁用，`custom_profile` 可编辑。
- 前端任务启动、FPA 预览、运行默认值和任务详情已纳入 `fpa_core_rules`、`fpa_system_prompt`、`fpa_user_prompt`、`fpa_base_profile`。
- 后端任务快照会对官方 profile 重新解析绑定值并忽略前端细项覆盖；`custom_profile` 会校验显式 key 并使用 `fpa_base_profile` 继承行为 kind。
- FPA audit trace 和 `FPA工作量评估-check.xlsx` 默认列已写入最终解析后的 `core_rules`、`system_prompt`、`user_prompt` key。

### 修改范围

- `web_app/src/components/run/FpaRunSettingsSection.vue`
- `web_app/src/composables/useFpaOptions.ts`
- `web_app/src/stores/config.ts`
- `web_app/src/views/Home.vue`
- `web_app/routes/tasks.py`
- `/api/fpa/options` 对应路由或 service
- FPA 配置读取和任务配置快照相关代码
- `config/fpa_config.yaml.example`
- 相关 FPA 配置和 Web 任务测试

### 待办

1. 扩展 `/api/fpa/options`，返回 profile 绑定值、`editable` 和新增 options 列表。
2. 在 options 中新增 `custom_profile` 选项。
3. 前端 config store 增加 `fpaCoreRules`、`fpaSystemPrompt`、`fpaUserPrompt`。
4. `FpaRunSettingsSection` 增加 `core_rules`、`system_prompt`、`user_prompt` 三个选择控件。
5. 实现 profile 切换联动：官方 profile 覆盖显示细项并禁用控件，`custom_profile` 启用控件。
6. 切换到 `custom_profile` 时，初始化为上一个 profile 的细项值；用户修改后保留自定义值。
7. `Home.vue` 任务提交 FormData 增加 `fpa_core_rules`、`fpa_system_prompt`、`fpa_user_prompt`。
8. 后端任务配置快照保存最终 profile 和细项 key。
9. 后端执行配置解析区分官方 profile 和 `custom_profile`。
10. 重跑任务时恢复原任务快照中的 profile 和细项 key。
11. 将最终解析后的 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode` 写入 FPA audit trace 和 `*-FPA工作量评估-check.xlsx`。
12. 更新配置示例，说明 `custom_profile` 是 Web/API 运行时自定义入口，不复用旧 `custom_rules` 语义。
13. 更新测试，覆盖官方 profile 灰掉、自定义 profile 可选、任务提交、重跑快照和 check Excel 审计字段。

### 验收标准

- 选择官方 profile 时，`strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode` 均显示对应绑定值但不可修改。
- 选择 `custom_profile` 时，上述细项均可修改。
- 从官方 profile 切到 `custom_profile` 时，初始细项等于切换前官方 profile 绑定值。
- 从 `custom_profile` 切回官方 profile 后，官方 profile 细项恢复只读绑定值；再次切回 `custom_profile` 时仍保留用户上次自定义选择。
- 官方 profile 提交任务时，后端按官方 profile 绑定解析，不接受前端细项篡改。
- `custom_profile` 提交任务时，后端使用用户显式选择的细项 key。
- `custom_profile` 缺少必填细项时，后端返回明确错误。
- 运行历史和重跑能保留并复用本次任务的 profile 与最终细项 key。
- `*-FPA工作量评估-check.xlsx` 能查看本次任务最终解析后的 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode`。
- 官方 profile 提交时，即使请求里携带被篡改的细项，check Excel 也记录后端按官方 profile 解析出的绑定值。
- check Excel 中 `core_rules`、`system_prompt`、`user_prompt` 只记录配置 key，不写入规则或 prompt 正文。
- AI cache 命中时，check Excel 仍能展示本行或本模块对应的最终 profile 细项 key，并能区分 `ai` 与 `ai_cache` 来源。

### 验证方式

- `cd web_app && npm run build`
- `.\.venv\Scripts\python.exe -m pytest tests/test_web_tasks.py`
- 视实际落点补充并运行 FPA options、FPA config 或任务配置快照相关测试。
- 使用 `openpyxl` 断言生成的 `*-FPA工作量评估-check.xlsx` 包含 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode`，且值为后端最终解析 key。
- 补充或保留 AI cache 测试，确认 cache key 覆盖 `profile`、`strategy`、`rule_set`、`rule_set_config`、`core_rules`、`system_prompt`、`user_prompt`、`domain_context`、`judgement_rules`、模块 group 和 model；任一口径变化都不能命中旧 cache。
- 人工检查生成页高级参数：官方 profile 灰掉、自定义 profile 可编辑、切换后显示值符合预期。

### 风险

- 当前配置已有 `profiles -> core_rules/system_prompt/user_prompt` 绑定，实施时必须以后端解析为准，不能只做前端假联动。
- `custom_profile` 需要避开旧 `custom_rules` 语义，避免恢复已移除的旧配置路径。
- 如果官方 profile 的灰掉控件仍随 FormData 提交，后端必须忽略这些覆盖值，防止用户绕过 UI 篡改 profile 口径。
- Prompt 选择项只允许 key 选择，不允许运行页直接编辑大段 prompt 文本；大段 prompt 文本仍应在配置页或配置文件维护。
- 当前 FPA AI cache key 已包含 profile、strategy、rule_set、rule_set_config、core_rules 正文、system_prompt 正文、user_prompt 正文、domain_context、judgement_rules、模块 group 和 model，正常不应跨 profile 或跨 prompt 复用；实施 check Excel 字段时仍需保留该隔离测试。
- 如果后续引入或扩大预览缓存、FPA MD 结果缓存、跨任务复用等能力，缓存键也必须纳入最终 profile 细项 key；不能只按输入 Excel 或模块名称复用结果。

## 第二期：单任务运行详情页

### 实施状态

- 2026-06-10 已实施：新增 `/tasks/:sessionId` 运行详情页，按路由 `sessionId` 独立读取历史记录、session 状态、进度快照、错误详情和交付物。
- 2026-06-10 已实施：详情页支持复制当前 session 日志快照；运行中任务会为当前详情页建立日志流，离开页面关闭连接。
- 2026-06-10 已实施：详情页支持 `重新运行`，重跑成功后跳转到新 session 的 `/tasks/:sessionId`。
- 2026-06-10 已实施：详情页支持 `定位参数`，通过 `/?focus=<field>&fromSession=<sessionId>` 返回生成页并高亮对应控件。
- 2026-06-10 已实施：生成页和任务/历史列表增加运行详情入口。

### 目标行为

- 新增 `/tasks/:sessionId` 运行详情页。
- 详情页展示任务状态、来源、模式、输入、参数快照、`生成过程`、日志、错误详情和交付物。
- 详情页支持 `复制日志`、`重新运行`、`定位参数`；重跑成功后自动跳转到新 session 的运行详情页。
- 生成页出现 `运行详情 / 排错信息` 次级入口，运行中、完成、失败、已停止时均可进入。
- 对于创建 session 前的启动失败，第二期运行详情页通常没有可跳转的 `session_id`；这类错误必须由生成页自身展示清楚。

### 修改范围

- `web_app/src/router/index.ts`
- `web_app/src/views/Tasks.vue`
- 新增 `web_app/src/views/TaskDetail.vue` 或等价详情页组件。
- `web_app/src/views/Home.vue`
- `web_app/src/components/GenerationProgress.vue`
- `web_app/src/components/LogViewer.vue`
- `web_app/src/lib/api.ts`
- 必要时补充后端详情接口字段。

### 待办

1. 新增 `/tasks/:sessionId` 路由。
2. 设计运行详情页面结构。
3. 详情页按路由 `sessionId` 拉取任务状态和参数快照。
4. 详情页复用或抽取 `生成过程` 展示，保持阶段进展与产物展示，不使用下拉进度条。
5. 详情页加载指定 session 的日志，并支持复制日志。
6. 详情页提供 `重新运行` 操作，重跑基于历史参数快照创建新 session。
7. 详情页提供 `定位参数` 操作，按 `/?focus=<field>&fromSession=<sessionId>` 返回生成页。
8. 生成页新增 `运行详情 / 排错信息` 次级按钮，跳转当前 session 详情。
9. 处理任务无日志、任务已清理、无访问权限等空状态和错误态。

### 验收标准

- `/tasks/:sessionId` 可查看指定任务详情。
- 详情页不依赖生成页当前 session，也不污染生成页当前填写参数。
- 运行中和失败后的任务都能进入详情页。
- `生成过程` 展示阶段进展与产物，不出现下拉进度条。
- `复制日志` 可复制当前 session 日志。
- `重新运行` 创建新 session，不复用原 session。
- `定位参数` 只回到生成页并定位或高亮参数，不自动启动任务。

### 验证方式

- `cd web_app && npm run build`
- 后端详情接口如有变更，运行相关 Python 测试。
- 人工验证运行中、完成、失败、已停止四类状态。

### 风险

- 运行详情页需要明确失败后与运行中的展示边界，避免用户在任务未产生日志时看到空白页。
- `重新运行` 和 `定位参数` 需要约束作用域，避免误改历史任务或当前页面状态。

## 第三期：多任务前端状态隔离

### 实施状态

- 2026-06-10 已实施：生成页实时日志连接在建立时绑定当前 `session_id`，后续迟到事件若不属于当前 session 会被忽略，避免切换或恢复任务后污染页面运行态。
- 2026-06-10 已实施：送审工作量输入、送审功能点确认和 FPA 计量口径确认弹窗均记录所属 `session_id`，提交时显式提交到弹窗所属 session，而不是读取可能已变化的全局当前 session。
- 2026-06-10 已实施：运行详情页继续使用路由 `sessionId` 自有日志流和进度快照；生成页全局 store 仅承载当前生成页任务，不影响并行打开的 `/tasks/:sessionId` 详情页。
- 2026-06-10 已实施：后端 `/api/log-stream` 改为每个连接独立订阅同一 session 的日志事件，后台任务会向所有订阅者广播，避免生成页和详情页同时打开时竞争同一个队列导致日志丢失或串扰。

### 目标行为

- 任务列表可同时展示多个任务状态、来源、模式、输入、交付物和操作入口。
- 多个详情页可在浏览器多标签页中并行打开，每个详情页绑定独立 `session_id`。
- 日志、阶段进展、生成过程、排错信息按任务隔离。
- FPA 人工确认弹窗和确认提交绑定具体 `session_id`，不会提交到错误任务。
- 多任务同时查看时，只有当前激活详情保持实时日志流。

### 修改范围

- `web_app/src/stores/session.ts`
- `web_app/src/stores/log.ts`
- `web_app/src/stores/steps.ts`
- `web_app/src/views/Home.vue`
- `web_app/src/views/TaskDetail.vue`
- `web_app/src/components/LogViewer.vue`
- `web_app/src/components/GenerationProgress.vue`
- FPA 人工确认相关前后端接口和调用点。

### 待办

1. 将当前单 session 前端状态抽象为可按 `session_id` 索引的状态结构，或为详情页建立独立 store 实例策略。
2. 梳理所有依赖全局 `session.sessionId` 的提交、继续、取消、日志连接和阶段进展逻辑。
3. 详情页只订阅路由 `sessionId` 对应的日志和进展。
4. FPA 人工确认弹窗打开时记录所属 `session_id`。
5. FPA 人工确认提交时显式提交到所属 `session_id`。
6. 切换或关闭详情页时关闭当前实时日志连接。
7. 列表页保留轮询刷新，不为每个任务建立长连接。

### 验收标准

- 两个任务详情页同时打开时，日志、阶段进展和操作互不串扰。
- FPA 人工确认弹窗显示和提交都绑定正确 `session_id`。
- 详情页只对当前任务保持实时连接。
- 列表页仅轮询刷新任务摘要。

### 验证方式

- `cd web_app && npm run build`
- 新增或更新前端行为测试后运行对应命令。
- 后端 `continue`、`cancel`、FPA 确认接口运行相关 Python 测试。

### 风险

- 当前前端 store 以单一当前 session 为中心，直接扩展多任务容易造成隐式串状态。
- FPA 人工确认若仍依赖单一全局 session，多任务后会有提交到错误任务的风险，必须优先隔离。

## 第四期：后端并发队列与输出隔离

### 实施状态

- 2026-06-12 已实施：新增 Web 任务队列服务，后端按 `web.max_concurrent_tasks` 控制并发；达到上限的新任务进入 `queued`，记录排队位置，并在运行任务结束后自动调度下一条任务。
- 2026-06-12 已实施：`/api/run-local`、`/api/run-upload` 和重跑入口均先创建 session 与运行历史，再交由队列决定立即运行或排队；接口返回 `run_state` 和 `queue_position`。
- 2026-06-12 已实施：`/api/cancel/{session_id}` 支持取消排队任务，取消后 session 和运行历史均标记为 `cancelled`，不会启动 pipeline。
- 2026-06-12 已实施：远程任务继续使用包含 session id 的临时工作目录；本机任务输出统一写入 `<project_name_or_input_name>_<session_id>` 子目录，目标子目录已存在时直接报错。
- 2026-06-12 已实施：服务启动时会将历史中遗留的 `queued` Web 任务统一标记为 `cancelled`，并记录“服务重启，排队任务已取消”。
- 2026-06-12 已实施：任务列表、历史页、生成页和运行详情页已支持 `queued` 状态展示；任务列表提供“取消排队”，运行详情页在 queued 状态下轮询摘要，进入 running 后再建立日志流。

### 独立实施边界

第四期必须独立实施，建议任务标题为：`实现 Web 任务并发队列与输出目录隔离`。

本期不包含生成页主操作区布局、运行详情页基础 UI 或多 session 前端 store 重构。它可以在第二期详情页完成后展示完整 queued 详情；如果第二期尚未实施，本期仍可先完成后端队列、任务列表 queued 展示、历史记录和基础接口契约。

本期提交应聚焦后端任务生命周期：并发上限、`queued` 状态、队列服务、取消语义、run history、输出目录隔离和相关接口返回。

### 目标行为

- 达到并发上限时，新任务进入 `queued` 状态。
- 排队任务在任务列表和详情页中明确提示等待状态和排队位置。
- 用户可以取消排队任务。
- 每个任务使用独立输出目录和临时工作目录。
- 详情页实时连接与列表页轮询职责分离。

### 工程设计决策

#### 配置来源

- 新增后端配置项 `web.max_concurrent_tasks`，默认值为 `1`。
- 配置项名称固定使用 `web.max_concurrent_tasks`。
- 配置项由后端任务启动逻辑读取，前端不自行判断并发额度。
- 若配置值为空、非法或小于 `1`，后端按 `1` 处理。
- 前端可以从任务状态接口或后续配置摘要接口展示当前并发上限，但不能依赖前端判断来保证队列行为。

#### 状态契约

- 后端 session 和运行历史新增 `queued` 状态。
- 状态流转：
  - `queued -> running`：调度器取得运行名额并启动 pipeline。
  - `queued -> cancelled`：用户取消排队任务，或服务重启后取消遗留排队任务。
  - `running -> done | error | cancelled`：沿用现有任务生命周期。
- `queued` 状态下必须有 session 和运行历史记录，因此任务列表、运行详情和刷新接口都能看到该任务。
- `queued` 状态下不应创建实时日志长连接；详情页展示等待状态并轮询摘要，进入 `running` 后再建立日志流。

#### 队列服务边界

- 新增轻量队列调度模块，建议文件名为 `web_app/services/task_queue.py`。
- 队列服务负责：
  - 维护排队顺序。
  - 基于内存中的 session 状态统计 `running` 任务数量。
  - 判断新任务立即运行还是进入排队。
  - 取消排队任务。
  - 运行任务结束后启动下一个排队任务。
- 排队位置按“当前用户可见的排队任务”计算和展示，不暴露其他用户不可见任务的全局队列长度。
- `task_runner.start_background_task` 继续只负责启动单个后台任务和记录生命周期，不直接承载排队策略。
- `routes/tasks.py` 负责构造任务上下文、创建 session 和运行历史，再把可运行的 target 交给队列服务。

#### 任务上下文

- 队列中保存的是可启动任务上下文，而不是已经运行的线程或协程。
- 任务上下文至少包含：
  - `session_id`
  - `mode`：`local` 或 `remote`
  - `owner`
  - `run_id`
  - `target`：真正运行 pipeline 的 callable
  - `created_at`
  - `queue_position`
- 本机和远程任务都必须先完成输入解析、参数快照、输出目录/临时目录准备、session 创建和历史记录创建，再进入队列判断。
- 进入 `queued` 的任务不能提前调用 `mark_task_started`，也不能提前执行 pipeline。

#### 取消接口

- 排队取消复用现有 `/api/cancel/{session_id}`。
- 后端收到取消请求时：
  - 如果任务是 `queued`，从队列移除，session 标记为 cancelled，运行历史标记为 `cancelled`，不启动 pipeline。
  - 如果任务是 `running`，沿用现有取消逻辑。
  - 如果任务已完成、失败或已取消，接口保持幂等，返回当前状态。

#### 调度触发

- 所有后台任务结束后都必须触发一次 `schedule_next()`。
- 触发点建议放在队列服务包装的任务完成回调中，而不是散落在各个 route 的 target 内部。
- 如果任务启动失败，必须释放运行名额、标记当前任务失败，并继续调度下一个排队任务。
- 调度器需要加锁，避免两个任务几乎同时结束时重复启动同一个排队任务。

#### 输出目录命名

- 远程模式继续使用 `tempfile.mkdtemp(prefix=f"ard_web_{session_id}_")`，并在临时目录内使用独立 `input`、`output` 和 `custom_templates` 子目录。
- 本机模式用户填写输出目录时，实际输出目录为：

```text
<用户填写输出目录>/<project_name_or_input_name>_<session_id>
```

- `project_name_or_input_name` 取值优先级：
  1. 本次参数快照中的 `project_name`
  2. 输入 Excel 文件名去扩展名
  3. `task`
- 目录名需要做文件系统安全化处理：去掉路径分隔符、控制字符和首尾空白；空值回退为 `task`。
- 如果目标子目录已存在，后端直接报错并提示用户目录已存在，不自动追加后缀，不覆盖已有交付物。

#### 历史记录

- 创建任务时立即写入运行历史，`run_state` 为 `queued` 或 `running`。
- 进入排队的任务也必须保存完整 `run_config`、输入名称、来源、模式、输出目录和 artifact 类型。
- `queued -> running` 时更新历史状态和开始时间。
- `queued -> cancelled` 时更新历史状态和更新时间。
- 服务启动时扫描历史记录：仍为 `queued` 的 Web 任务统一标记为 `cancelled`，并记录或展示“服务重启，排队任务已取消”；第一版不恢复队列。

#### 接口返回

- `/api/run-local` 和 `/api/run-upload` 返回中增加：
  - `session_id`
  - `run_state`
  - `queue_position`
  - `output_dir` 或 `has_download`
- `/api/sessions/{session_id}` 返回中增加：
  - `run_state: queued`
  - `queue_position`
  - `progress_steps`
  - `done_files`
- `/api/tasks` 和 `/api/history` 支持展示 `queued` 状态。
- `/api/log-stream?session=<session_id>` 对 `queued` 状态不建立长期等待流；如果调用，返回一条明确 SSE 事件后关闭，例如 `INFO: 任务正在排队，请在详情页等待启动`。
- 任务列表中的“关闭”只移除关注，不取消排队；取消排队必须使用明确的“取消排队”操作。

### 修改范围

- `web_app/services/session_manager.py`
- 新增 `web_app/services/task_queue.py`
- `web_app/services/task_runner.py`
- `web_app/services/run_history_service.py`
- `web_app/services/config_service.py`
- `web_app/routes/tasks.py`
- `web_app/routes/artifacts.py`
- `web_app/src/stores/session.ts`
- `web_app/src/views/Tasks.vue`
- `web_app/src/views/TaskDetail.vue`
- 后端任务和运行历史相关测试。

### 待办

1. 增加后端并发上限配置。
2. 增加 `queued` 状态和队列位置字段。
3. 新增队列服务，封装排队、启动、取消和完成后调度。
4. 修改任务提交逻辑：先创建 session 和历史记录，再由队列服务决定立即运行或进入排队。
5. 修改 `start_background_task` 调用边界：由队列服务启动实际 target，并在任务结束后调度下一个任务。
6. 复用 `/api/cancel/{session_id}` 实现排队取消，不影响运行中任务。
7. 确保远程模式工作目录包含 session id。
8. 确保本机模式输出目录始终写入 `<project_name_or_input_name>_<session_id>` 子目录。
9. 服务启动时把历史中遗留的 `queued` Web 任务标记为 `cancelled`。
10. 任务列表轮询展示 `queued`、排队位置和取消入口。
11. 详情页展示 `queued` 状态，并等待任务启动后建立或恢复实时连接。
12. 更新历史页和重跑入口，确保 `queued` 不可重跑，取消后才可重跑。
13. 任务列表关闭 `queued` 任务时只移除关注，不取消排队。

### 验收标准

- 并发默认上限为 `1`；达到上限时，新任务进入排队，不直接失败。
- 排队任务可取消，取消后不会启动 pipeline。
- 服务重启后不恢复排队任务；排队任务统一标记为 `cancelled`。
- 运行任务结束后，队列中的下一个任务自动开始。
- 每个任务都有独立输出目录和临时工作目录；本机模式用户填写输出目录时，实际输出写入 `<project_name_or_input_name>_<session_id>` 子目录。
- 任务列表只轮询摘要；详情页负责当前任务实时连接。
- 运行历史能看到排队、运行、取消和完成状态的完整流转。
- `/api/cancel/{session_id}` 对 queued、running 和终态任务保持可预测且幂等。
- 目标输出子目录已存在时启动失败并提示，不覆盖、不自动改名。
- 任务列表关闭 queued 任务不会取消排队。

### 验证方式

- `.\.venv\Scripts\python.exe -m pytest tests/test_web_tasks.py`
- `.\.venv\Scripts\python.exe -m pytest tests/test_session_manager.py`
- 新增队列服务测试后运行对应测试文件。
- 视影响范围运行更多后端测试。
- `cd web_app && npm run build`
- 人工验证两个以上任务的排队、取消和自动启动。

### 推荐测试切片

- `max_concurrent_tasks=1` 时提交两个任务，第一个进入 `running`，第二个进入 `queued`。
- 第一个任务结束后，第二个任务自动进入 `running`。
- 取消 `queued` 任务后，pipeline target 不会被调用，历史状态为 `cancelled`。
- 取消 `running` 任务仍沿用现有取消逻辑。
- 服务启动清理时，历史中遗留的 `queued` 任务被标记为 `cancelled`。
- 本机模式用户填写输出目录时，两个任务写入不同 session 子目录。
- 本机模式目标输出子目录已存在时，接口返回明确错误。
- 远程模式两个任务使用不同 `work_dir` 和不同 zip。
- `queued` 任务在 `/api/tasks`、`/api/history`、`/api/sessions/{session_id}` 中展示一致。
- `/api/log-stream` 对 queued 任务发送一条排队提示 SSE 后关闭。
- 任务列表关闭 queued 任务后，任务仍保持 queued；点击取消排队后才变为 cancelled。

### 风险

- 队列调度涉及线程、取消和历史记录一致性，需要覆盖异常退出和取消场景。
- 本机输出目录兼容用户显式路径时要谨慎，必须始终写入 session 子目录，不能悄悄覆盖已有交付物。
- 如果后续需要恢复队列，需要单独设计持久化恢复策略；本期明确不支持队列跨进程恢复。
- 队列服务需要避免和现有 session 日志队列概念混淆；`SessionState.queue` 当前用于日志事件，不应直接复用为任务等待队列。

## 对话覆盖检查

- 生成页主操作区：`操作模式`、`功能清单 .xlsx 路径（或项目目录）`、`开始生成` 并排展示。属于第一期。
- 高级参数：`高级参数（FPA策略与运行参数）` 放到主操作区第一行下方。属于第一期。
- FPA 预览：生成页不展示 `FPA预览` 按钮，保留 `预览 -> FPA预览` 入口。属于第一期。
- 运行详情：新增 `运行详情 / 排错信息` 次级入口，运行中和失败后均可查看。属于第二期。
- 运行详情页能力：查看任务状态、`生成过程`、日志、错误详情、参数快照，支持复制日志、重新运行、定位参数。属于第二期。
- 生成过程：展示阶段进展与产物，不使用下拉进度条。第一期保持现状，第二期在详情页复用。
- `开始生成`：创建新的后端 session 和运行历史记录，不复用旧 session。第一期确认，第四期扩展排队状态。
- `新任务`：只清空页面视图，不取消后端任务，不删除历史、交付物或后端 session，不创建新任务。属于第一期确认。
- `重新运行`：基于历史参数快照创建新 session。第二期确认详情页入口，现有任务列表能力继续保留。
- `定位参数`：只回到生成页定位或高亮参数，不自动启动任务。属于第二期。
- 多任务查看：任务列表可同时展示多个任务，运行详情可并行打开多个任务详情。列表已有基础能力，详情并行属于第二期和第三期。
- 多任务隔离：每个详情绑定独立 `session_id`，日志、阶段进展、生成过程、排错信息按任务隔离。属于第三期。
- FPA 人工确认：弹窗和提交结果必须绑定具体 `session_id`，不能依赖全局单一当前 session。属于第三期。
- FPA Profile check Excel：`strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`confirmation_mode` 都必须写入 FPA 审核副本 `*-FPA工作量评估-check.xlsx`；写入值为后端最终解析后的配置 key，不写入 prompt 或规则正文。属于独立实施项 `FPA Profile 参数联动与自定义 Profile`。
- 并发控制：超限时新任务进入排队并提示用户，排队任务可取消。属于第四期。
- 输出隔离：每个任务必须使用独立输出目录和临时工作目录。属于第四期。
- 刷新策略：详情页使用实时连接，列表页使用轮询刷新。第二期建立详情页职责，第三期和第四期完善多任务与队列场景。
- 生成页启动失败错误：创建 session 前失败时，生成页执行监控主区域要展示后端错误详情和下一步提示，不能只显示“出错”。属于第一期。
- 项目名展示：任务页、历史页的项目名必须完整显示，不能因截断隐藏关键信息。属于第一期。

## 通用注意事项

- FPA 相关用户可见文案需继续遵循 `docs/fpa/result-review-terminology.md`，不要引入禁用同义词。
- 实施每一期时都应更新相关文档、测试和验收说明。
- 每一期结束后单独提交，避免把布局调整、前端状态重构和后端队列调度混入同一个提交。
