# Web UI 任务列表与关闭状态方案

## 推进状态

状态：已落地到 `master`。

相关提交：

- `e191f93 feat: add web task list close state`
- `ccb4f19 merge: web task list close state`
- `7a4773e feat: continue running tasks from list`

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

已验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_run_history.py tests\test_web_history.py tests\test_web_tasks.py
```

结果：`55 passed`。

```powershell
npm run build
```

结果：前端类型检查和生产构建通过。

后续关注：

- 远程重跑依赖历史记录中的原始输入文件路径；如果远程临时目录已被清理，接口会返回“原始输入文件不存在，无法重跑”。
- 当前方案暂不支持关闭后恢复。

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
- 展示状态、任务模式、来源、输入文件、开始时间、更新时间、交付物状态。
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

## 数据模型

现有运行历史表已有 `run_state` 字段，因此可以直接扩展状态值为 `closed`。

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
  - 关闭状态隐藏重跑动作。

## 后端改动范围

- `ai_gen_reimbursement_docs/run_history.py`
  - 增加按排除状态查询的能力，或为任务列表新增专用查询。
  - 增加更新历史状态的函数。
- `web_app/services/run_history_service.py`
  - 增加任务列表服务。
  - 增加关闭任务服务。
  - 增加重跑前状态校验服务。
- `web_app/routes/history.py`
  - 历史查询支持 `closed` 筛选。
- `web_app/routes/tasks.py`
  - 增加 `/api/tasks`。
  - 增加 `/api/tasks/{run_id}/close`。
  - 增加 `/api/tasks/{run_id}/rerun`。
  - 增加 `/api/tasks/{run_id}/mark-unrecoverable`。

## 验收标准

- 创建运行中任务后，任务列表页可以看到该任务。
- 服务未重启且 session 仍存在时，运行中任务可以从任务列表点击“继续”回到执行监控。
- 点击“继续”后能查看当前进度、继续监听日志流，并可响应后续人工输入。
- 服务已重启或 session 已清理时，运行中历史记录不能继续执行，页面应明确提示会话不可恢复。
- 会话不可恢复的 `running` 任务可标记为 `cancelled`，标记后可重跑。
- 仍可继续执行的 `running` 任务不能标记为不可恢复。
- 任务完成后，任务列表页仍可以看到该任务。
- 完成任务可以重跑，重跑后生成新的运行记录。
- 关闭任务后，任务列表页不再展示该任务。
- 关闭任务在历史页仍可查询。
- 关闭任务不可重跑，接口返回明确错误。
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
- 远程模式下，用户不能关闭或重跑其他用户任务。

前端测试：

- 任务列表页不展示关闭任务。
- 运行中任务展示“继续”按钮，不展示“重跑”按钮。
- 点击“继续”能回到生成页并恢复对应 session 的执行监控。
- session 不存在时展示“会话已结束或服务已重启，无法继续当前执行”，并可标记为已取消。
- 完成任务展示重跑按钮。
- 关闭任务在历史页展示，且无重跑按钮。
- 点击关闭有二次确认。

## 风险与待确认

- “继续执行”依赖服务进程内存中的 `SessionManager`，服务重启后无法恢复实时后台线程。
- 历史记录中的 `running` 不等价于当前还有可继续执行的 session；UI 需要区分“运行中且可继续”和“运行记录显示运行中但会话不可恢复”。
- 重跑需要复用原始输入与启动参数；远程上传文件如果已被清理，可能无法重跑。
- 本机任务可以依赖 `input_path` 重跑；远程任务需要确认是否长期保存输入文件。
- 如果远程交付物过期，重跑不应依赖旧交付物。
- 关闭状态是否允许恢复需要另行确认；本方案暂不支持恢复。
