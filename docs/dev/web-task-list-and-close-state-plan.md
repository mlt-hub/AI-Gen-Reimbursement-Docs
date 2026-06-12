# Web UI 任务列表与关闭状态方案

## 推进状态

状态：任务列表、关闭状态、继续执行、不可恢复任务标记、重跑配置快照、项目名展示和完成时回写项目名均已落地到 `master`。本轮继续推进关闭任务恢复、重跑前 API Key 前置校验、远程输入文件持久快照和自定义模板持久快照。

相关提交：

- `e191f93 feat: add web task list close state`
- `ccb4f19 merge: web task list close state`
- `7a4773e feat: continue running tasks from list`
- `a208cce feat: backfill project name on finish`
- `9d918b7 merge: backfill project name on finish`

已完成：

- 新增 `/tasks` 任务列表页，默认展示未关闭的 Web 任务。
- 新增 `closed` 状态，任务列表默认排除 `closed`，历史页保留并支持筛选。
- 新增 `/api/tasks`、`/api/tasks/{run_id}/close`、`/api/tasks/{run_id}/rerun`。
- `done`、`error`、`cancelled` 支持重跑；`running`、`closed` 禁止重跑。
- `running` 禁止关闭，需要先取消后再关闭。
- 关闭任务不删除历史记录、交付物信息、错误信息和日志索引。
- 远程模式按 owner 隔离任务列表、关闭和重跑权限。
- 运行中任务支持从任务列表“继续”回到仍可恢复的 session。
- 任务列表能区分 `running` 且 session 可恢复、以及历史仍为 `running` 但 session 不可恢复。
- session 不可恢复的 `running` 任务可由用户显式标记为 `cancelled`，随后按既有规则重跑。
- 运行历史保存任务启动参数快照，重跑优先使用原任务参数。
- 任务列表和历史列表展示项目名，来源为启动参数快照中的 `project_name`。
- 任务完成时如果启动参数快照中的 `project_name` 为空，会从输入 Excel 推断项目名并回写历史快照。
- 关闭任务可从历史页或任务详情页恢复为关闭前状态。
- 远程上传任务会把重跑所需输入文件复制到服务侧 `products/task_assets/{session_id}/input`，历史记录中的 `input_path` 指向该持久快照。
- 使用自定义模板的任务会把模板复制到服务侧 `products/task_assets/{session_id}/custom_templates`，重跑优先复用该持久快照。
- 重跑需要 AI 且当前无可用 API Key 时，接口会在创建新任务前返回明确错误。

已验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_run_history.py tests\test_web_history.py tests\test_web_tasks.py
```

结果：`59 passed`。

```powershell
npm run build
```

结果：前端类型检查和生产构建通过。

后续关注：

- 出于安全考虑，任务启动参数快照不保存 API Key 明文；重跑前会校验当前用户或系统配置中存在可用 API Key。
- 远程重跑依赖服务侧 `products/task_assets` 中的输入和模板快照；如果该目录被外部清理，接口会返回明确错误。
- 关闭任务支持恢复；旧关闭记录如缺少关闭前状态，会按错误信息回退推断为 `error` / `cancelled`，否则恢复为 `done`。

## 背景

当前 Web UI 已有运行历史页和运行历史接口，但任务生命周期语义还不够清晰：

- 完成状态代表一次运行结束，但不代表任务不再需要展示或操作。
- 用户需要一个任务列表页，集中查看所有仍在关注中的任务。
- 用户需要把不再关注的任务从任务列表移除，但仍保留历史记录。

因此新增 `closed`（关闭）状态，用于表达任务已归档或终止关注。

## 目标行为

- Web UI 提供任务列表页，列出所有未关闭任务。
- 任务状态增加 `closed`。
- 只有 `closed` 状态的任务不在任务列表页展示。
- `done` 状态任务仍保留在任务列表页，并允许重跑。
- `closed` 状态任务不能重跑。
- `closed` 状态任务可恢复为关闭前状态，恢复后重新进入任务列表。
- 关闭状态任务只在任务历史页展示。
- 关闭不是删除，历史记录、交付物信息、错误信息和日志索引应继续保留。

## 状态语义

| 状态 | 用户文案 | 含义 | 任务列表展示 | 是否可重跑 |
| --- | --- | --- | --- | --- |
| `running` | 运行中 | 任务正在执行 | 是 | 否 |
| `done` | 完成 | 本次运行成功结束 | 是 | 是 |
| `error` | 失败 | 本次运行失败 | 是 | 是 |
| `cancelled` | 已取消 | 用户停止了本次运行 | 是 | 是 |
| `closed` | 关闭 | 用户不再关注该任务，任务进入历史归档 | 否 | 否 |

## 页面设计

### 任务列表页

任务列表页用于日常工作台视角，默认展示所有未关闭任务：

- 筛选条件默认排除 `closed`。
- 展示状态、任务模式、项目名、来源、输入文件、开始时间、更新时间、交付物状态。
- 项目名优先读取启动参数快照；若启动时未填写，任务完成后读取输入 Excel 推断并回写历史。
- `running` 状态展示“继续”入口，用于回到当前运行 session 的执行监控。
- `done`、`error`、`cancelled` 状态展示“重跑”入口。
- 非 `closed` 状态展示“关闭”入口。
- `running` 状态不展示“重跑”入口。
- 点击关闭前需要二次确认。

建议路由：

- `/tasks`：任务列表页。
- `/history`：任务历史页。

### 任务历史页

任务历史页保留审计视角：

- 可查看所有状态，包括 `closed`。
- 支持按状态筛选 `closed`。
- 展示项目名；旧历史记录或未填写项目名时显示 `-`。
- 对启动时未填写项目名但输入 Excel 可识别项目名的任务，完成后展示回写后的项目名。
- `closed` 状态不展示重跑入口。
- 可继续提供下载、打开目录、查看调试记录等历史能力。

### 继续执行语义

任务列表中的“继续”与“重跑”语义不同：

- “继续”只针对当前仍在运行的 `running` 任务。
- “继续”应回到原 `session_id` 对应的生成页执行监控，而不是创建新任务。
- “重跑”会创建新的 `session_id` 和新的运行历史记录。

服务未重启时：

- `SessionManager` 内存中仍保存运行中的 session。
- `/api/sessions/{session_id}` 可以返回实时状态。
- 前端可以继续查看进度、监听日志流、响应人工输入、取消任务，并在任务完成后下载或打开交付物。

服务已重启或 session 已被清理时：

- `run_history` 中的历史记录仍保留，但 `SessionManager` 中不再有实时 session。
- `/api/sessions/{session_id}` 会返回 404。
- 此时不能真正继续当前执行，应提示“会话已结束或服务已重启，无法继续当前执行”。
- UI 应保留历史入口，并根据任务状态提供重跑能力；不得假装仍可继续执行。

任务列表建议展示规则：

- `running` 且 session 存在：展示“继续”。
- `running` 但 session 不存在：展示“会话不可恢复”提示和“标记已取消”入口，不展示“继续”。
- `done`、`error`、`cancelled`：展示“重跑”。
- `closed`：不在任务列表展示，历史页也不展示“继续”或“重跑”。

## 后端接口设计

### 查询任务列表

建议新增任务列表接口，或在现有历史接口上增加视图参数。

推荐新增：

```http
GET /api/tasks
```

默认返回：

- 当前用户可访问的 Web 任务。
- `run_state != "closed"`。
- 按 `updated_at` 或 `created_at` 倒序。

### 查询历史

现有接口继续保留：

```http
GET /api/history
```

行为：

- 默认可返回所有历史状态。
- `state=closed` 时返回关闭任务。
- 不因为关闭状态删除任何历史记录。

### 关闭任务

新增接口：

```http
POST /api/tasks/{run_id}/close
```

行为：

- 校验当前用户是否有权访问该任务。
- 将 `run_state` 更新为 `closed`。
- 更新 `updated_at`。
- 不删除交付物和历史记录。

运行中任务关闭策略建议先采用保守规则：

- `running` 状态不允许关闭。
- 用户需要先取消任务，任务变为 `cancelled` 后再关闭。

这样可以避免 UI 已关闭但后台仍在执行的状态不一致。

### 重跑任务

新增接口：

```http
POST /api/tasks/{run_id}/rerun
```

行为：

- `closed` 状态返回 400。
- `running` 状态返回 400。
- `done`、`error`、`cancelled` 可重跑。
- 重跑应创建新的 `session_id` 和新的运行历史记录，不覆盖原历史。
- 原任务保留原状态。
- 重跑优先使用原任务的启动参数快照，而不是当前页面配置。
- 快照不保存 API Key；重跑时 API Key 仍按当前配置解析。
- 原任务使用过自定义模板时，重跑会复用历史快照中的模板目录；模板目录或模板文件缺失时返回 400。
- 重跑前如任务模式需要 AI 且当前用户或系统配置无可用 API Key，返回 400 且不创建新任务。

### 查询运行 session

现有接口继续用于“继续执行”入口：

```http
GET /api/sessions/{session_id}
```

行为：

- session 存在且当前用户有权访问时，返回实时运行状态。
- session 不存在时返回 404。
- 远程模式下继续按 owner 校验访问权限。

前端点击“继续”时应先调用该接口确认 session 可恢复，再进入生成页执行监控。

### 标记不可恢复任务

新增接口：

```http
POST /api/tasks/{run_id}/mark-unrecoverable
```

行为：

- 仅允许历史状态为 `running` 的 Web 任务调用。
- 如果 `SessionManager` 中仍存在对应 session，返回 400，提示任务仍可继续执行。
- 如果 session 不存在，说明服务已重启、session 已过期或已被清理，可将历史状态标记为 `cancelled`。
- 写入 `finished_at`、`updated_at` 和错误说明“服务已重启或会话已结束，无法继续当前执行”。
- 标记后任务仍留在任务列表中，状态变为 `cancelled`，可按既有规则重跑。

### 恢复关闭任务

新增接口：

```http
POST /api/tasks/{run_id}/restore
```

行为：

- 仅允许历史状态为 `closed` 的 Web 任务调用。
- 校验当前用户是否有权访问该任务。
- 将任务恢复为关闭前状态；关闭前状态写入 `run_config.closed_from_state`。
- 如果旧记录缺少 `closed_from_state`，按错误信息推断为 `error` / `cancelled`，否则恢复为 `done`。
- 恢复后任务重新出现在任务列表；是否可重跑由恢复后的状态决定。

## 数据模型

现有运行历史表已有 `run_state` 字段，因此可以直接扩展状态值为 `closed`。

新增 `run_config_json` 字段用于保存任务启动参数快照：

- `model`
- `base_url`
- `max_tokens`
- `project_name`
- `fpa_profile`
- `fpa_strategy`
- `fpa_rule_set`
- `fpa_confirmation_mode`
- `clean`
- `custom_templates_dir`
- `custom_templates`

安全约束：

- 不保存 API Key 明文。
- 本机任务只保存输入文件路径；远程上传任务会保存一份服务端输入文件快照用于重跑。
- 重跑时如果输入文件或自定义模板文件不存在，应返回明确错误。
- 远程上传任务和远程重跑任务的 `input_path` 指向服务侧持久输入快照，而不是临时 workdir。
- 使用自定义模板时，`custom_templates_dir` 指向服务侧持久模板快照，而不是临时 workdir。

项目名回写约束：

- 启动时保存用户提交的 `project_name`，允许为空。
- 完成时仅当历史快照中的 `project_name` 为空，才从 `input_path` 指向的 Excel 推断项目名并回写 `run_config_json`。
- 完成时回写不得覆盖用户显式填写的项目名。
- 完成时回写应保留原有启动参数快照字段，并继续过滤 API Key。
- 如果输入文件不存在、不可读或无法识别项目名，历史仍保留空项目名，列表页显示 `-`。

建议补充一个更新状态的服务函数，例如：

```python
close_history_item(base_dir, run_id, local_mode, owner_id)
```

该函数负责：

- 查找历史记录。
- 校验权限。
- 拒绝关闭 `running`。
- 写回 `run_state = "closed"`。
- 更新 `updated_at`。

## 前端改动范围

- `web_app/src/router/index.ts`
  - 新增 `/tasks` 路由。
- `web_app/src/components/layout/SideNav.vue`
  - 新增“任务”导航项。
  - 保留“历史”导航项。
- `web_app/src/views/Tasks.vue`
  - 新增任务列表页。
  - 默认调用 `/api/tasks`。
  - 展示项目名列，读取 `run_config.project_name`。
  - 提供刷新、继续、重跑、关闭、进入历史等操作。
  - `running` 任务点击“继续”时携带 `session_id` 回到生成页。
  - `running` 但 session 不可恢复时展示“标记已取消”。
- `web_app/src/views/Home.vue`
  - 支持从路由参数或 query 中读取 `session_id`。
  - 调用 `/api/sessions/{session_id}` 恢复执行监控状态。
  - session 不存在时展示“会话已结束或服务已重启，无法继续当前执行”。
- `web_app/src/stores/session.ts`
  - 如现有 store 无恢复入口，补充从 session 状态 payload 恢复当前执行监控的方法。
- `web_app/src/views/History.vue`
  - 状态筛选增加 `closed`。
  - 状态文案增加“关闭”。
  - 展示项目名列，读取 `run_config.project_name`。
  - 关闭状态隐藏重跑动作。
  - 关闭状态展示恢复入口。

## 后端改动范围

- `ai_gen_reimbursement_docs/run_history.py`
  - 增加按排除状态查询的能力，或为任务列表新增专用查询。
  - 增加更新历史状态的函数。
  - 增加 `run_config_json` 字段和旧表补列逻辑。
- `web_app/services/run_history_service.py`
  - 增加任务列表服务。
  - 增加关闭任务服务。
  - 增加恢复关闭任务服务。
  - 增加重跑前状态校验服务。
  - 写入任务启动参数快照。
- `web_app/routes/history.py`
  - 历史查询支持 `closed` 筛选。
- `web_app/routes/tasks.py`
  - 增加 `/api/tasks`。
  - 增加 `/api/tasks/{run_id}/close`。
  - 增加 `/api/tasks/{run_id}/restore`。
  - 增加 `/api/tasks/{run_id}/rerun`。
  - 增加 `/api/tasks/{run_id}/mark-unrecoverable`。

## 验收标准

- 创建运行中任务后，任务列表页可以看到该任务。
- 任务列表展示项目名；没有项目名的旧记录显示 `-`。
- 历史列表展示项目名；没有项目名的旧记录显示 `-`。
- 服务未重启且 session 仍存在时，运行中任务可以从任务列表点击“继续”回到执行监控。
- 点击“继续”后能查看当前进度、继续监听日志流，并可响应后续人工输入。
- 服务已重启或 session 已清理时，运行中历史记录不能继续执行，页面应明确提示会话不可恢复。
- 会话不可恢复的 `running` 任务可标记为 `cancelled`，标记后可重跑。
- 仍可继续执行的 `running` 任务不能标记为不可恢复。
- 任务完成后，任务列表页仍可以看到该任务。
- 完成任务可以重跑，重跑后生成新的运行记录。
- 重跑使用原任务保存的模型、base_url、max_tokens、项目名和 FPA 口径参数。
- 重跑需要 AI 且当前无可用 API Key 时，不创建新任务并返回明确错误。
- 启动时未填写项目名但输入 Excel 可识别项目名时，任务完成后历史列表和任务列表展示推断出的项目名。
- 启动时已填写项目名时，任务完成后不得被 Excel 推断值覆盖。
- 重跑不复用原任务 API Key 明文，而是使用当前可用 API Key。
- 原任务自定义模板缺失时，重跑返回明确错误。
- 远程临时 workdir 被清理后，只要持久输入和模板快照仍存在，任务仍可重跑。
- 关闭任务后，任务列表页不再展示该任务。
- 关闭任务在历史页仍可查询。
- 关闭任务不可重跑，接口返回明确错误。
- 关闭任务可恢复到关闭前状态，恢复后重新出现在任务列表。
- 运行中任务不可重跑。
- 运行中任务不可关闭，需要先取消。
- 历史页按状态筛选 `closed` 能返回关闭任务。

## 测试建议

后端测试：

- `/api/tasks` 默认排除 `closed`。
- `/api/sessions/{session_id}` 对存在且可访问的 session 返回实时状态。
- `/api/sessions/{session_id}` 对不存在或无权访问的 session 返回 404。
- `/api/history?state=closed` 返回关闭任务。
- `POST /api/tasks/{run_id}/close` 能关闭 `done` 任务。
- 关闭 `running` 任务返回 400。
- 重跑 `done` 任务成功创建新任务。
- 重跑 `closed` 任务返回 400。
- 标记不可恢复的 `running` 任务成功后状态变为 `cancelled`。
- 仍可恢复的 `running` 任务调用标记接口返回 400。
- 标记不可恢复后的任务可以重跑。
- 运行历史保存 `run_config_json`，且不保存 API Key。
- 启动时 `project_name` 为空，完成后回写输入 Excel 推断出的项目名。
- 完成时回写项目名保留原 `run_config_json` 中的其他启动参数。
- 启动时已填写 `project_name`，完成时不覆盖。
- 原任务配置与当前配置不同时，重跑使用原任务启动参数快照。
- 重跑 AI 任务时当前无可用 API Key 返回 400，且不创建新任务。
- 远程上传任务历史记录保存持久输入文件快照路径。
- 自定义模板上传后历史记录保存持久模板快照路径。
- 关闭任务可恢复到关闭前状态。
- 远程模式下，用户不能关闭或重跑其他用户任务。

前端测试：

- 任务列表页不展示关闭任务。
- 任务列表页展示项目名列。
- 历史列表页展示项目名列。
- 运行中任务展示“继续”按钮，不展示“重跑”按钮。
- 点击“继续”能回到生成页并恢复对应 session 的执行监控。
- session 不存在时展示“会话已结束或服务已重启，无法继续当前执行”，并可标记为已取消。
- 完成任务展示重跑按钮。
- 关闭任务在历史页展示，且无重跑按钮。
- 关闭任务在历史页和详情页展示恢复按钮。
- 点击关闭有二次确认。

## 风险与待确认

- “继续执行”依赖服务进程内存中的 `SessionManager`，服务重启后无法恢复实时后台线程。
- 历史记录中的 `running` 不等价于当前还有可继续执行的 session；UI 需要区分“运行中且可继续”和“运行记录显示运行中但会话不可恢复”。
- 重跑需要复用原始输入与启动参数；远程任务已改为保存服务侧输入快照，若 `products/task_assets` 被外部清理仍可能无法重跑。
- 重跑不保存也不复用原任务 API Key；如果当前配置没有可用 API Key，需要 AI 的重跑任务会在创建前返回配置错误。
- 项目名优先来自启动参数快照；启动时未填写的任务会在完成时尝试从输入 Excel 回写，旧历史记录或无法读取 Excel 时仍显示 `-`。
- 本机任务仍依赖原始 `input_path` 重跑；远程任务依赖服务侧 `task_assets` 输入快照。
- 自定义模板已保存服务侧快照；若 `task_assets` 被外部清理，重跑无法保证复现。
- 如果远程交付物过期，重跑不应依赖旧交付物。
- 关闭状态已允许恢复；恢复目标状态来自关闭时写入的 `closed_from_state`。
