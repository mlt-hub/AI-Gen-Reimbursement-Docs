# Web UI 任务列表与关闭状态实现说明

## 状态

本方案已收口并落地到 `master`。任务列表、关闭状态、继续执行、不可恢复任务标记、重跑配置快照、项目名展示与回写、关闭任务恢复、重跑前 API Key 校验、远程输入/模板快照、`task_assets` 生命周期策略、本机输入可选快照、旧关闭记录迁移和前端回归契约均已实现。

相关提交：

- `e191f93 feat: add web task list close state`
- `ccb4f19 merge: web task list close state`
- `7a4773e feat: continue running tasks from list`
- `a208cce feat: backfill project name on finish`
- `9d918b7 merge: backfill project name on finish`
- `518d161 feat: finish web task close followups`
- `f28af33 merge: web task close followups`
- `a26bdca docs: update web task close followups status`
- `5f82f63 feat: add web task asset lifecycle`
- `1f063cc merge: web task asset lifecycle`

## 用户行为

- `/tasks` 是日常任务列表，默认展示未关闭的 Web 任务。
- `/history` 是审计视角，展示全部历史状态，包括 `closed`。
- `done`、`error`、`cancelled` 任务可以重跑。
- `running`、`queued`、`closed` 任务不能重跑。
- `running` 任务不能关闭，需要先取消或标记为不可恢复。
- `closed` 任务不会出现在任务列表，但可在历史页或详情页恢复。
- 关闭不是删除，历史记录、交付物信息、错误信息、日志索引和启动参数快照会保留。

状态语义：

| 状态 | 用户文案 | 含义 | 任务列表展示 | 是否可重跑 |
| --- | --- | --- | --- | --- |
| `queued` | 排队中 | 任务已创建，等待后台执行 | 是 | 否 |
| `running` | 运行中 | 任务正在执行 | 是 | 否 |
| `done` | 完成 | 本次运行成功结束 | 是 | 是 |
| `error` | 失败 | 本次运行失败 | 是 | 是 |
| `cancelled` | 已取消 | 用户停止或系统标记取消 | 是 | 是 |
| `closed` | 关闭 | 用户不再关注，进入历史归档 | 否 | 否 |

## 接口

- `GET /api/tasks`：返回当前用户可访问的未关闭 Web 任务。
- `POST /api/tasks/{run_id}/close`：关闭非运行中任务。
- `POST /api/tasks/{run_id}/restore`：恢复关闭任务到关闭前状态。
- `POST /api/tasks/{run_id}/rerun`：基于历史快照创建新的运行记录。
- `POST /api/tasks/{run_id}/mark-unrecoverable`：将不可恢复的 `running` 历史标记为 `cancelled`。
- `GET /api/history`：返回运行历史，支持按 `closed` 等状态筛选。
- `GET /api/sessions/{session_id}`：查询当前进程内仍可恢复的 session。

远程模式继续按 owner 隔离任务列表、关闭、恢复、重跑、历史详情和下载权限。

## 重跑与快照

运行历史通过 `run_config_json` 保存任务启动参数快照，包括模型、Base URL、最大 Token、项目名、FPA 方案、FPA 策略、FPA 规则集、FPA 生成模式、清理输出目录选项和自定义模板信息。

安全约束：

- 不保存 API Key 明文。
- 重跑需要 AI 且当前用户或系统配置无可用 API Key 时，接口在创建新任务前返回 400。
- 重跑不覆盖原历史记录，而是创建新的 `session_id` 和新的运行历史。

输入与模板快照：

- 远程上传任务会把输入文件复制到 `products/task_assets/{session_id}/input`。
- 使用自定义模板的任务会把模板复制到 `products/task_assets/{session_id}/custom_templates`。
- 历史记录中的远程 `input_path` 和 `custom_templates_dir` 指向服务侧持久快照，而不是远程临时 workdir。
- 本机任务默认仍引用原始 `input_path`；如需更强可重跑性，可开启 `local_task_input_snapshot_enabled`。

## 运维配置

`system_config.yaml` 支持以下配置：

```yaml
task_assets_retention_days: 30
local_task_input_snapshot_enabled: false
remote_session_retention_days: 1
```

- `task_assets_retention_days`：重跑输入和模板快照保留天数，默认 30 天；小于等于 0 表示不自动清理。
- `local_task_input_snapshot_enabled`：是否为本机 Web 任务保存输入文件快照，默认关闭。
- `remote_session_retention_days`：远程交付物 ZIP 下载保留天数，和 `task_assets` 生命周期相互独立。

清理行为：

- 服务启动会清理过期 `products/task_assets`。
- 新任务启动和重跑前也会触发过期 `task_assets` 清理。
- 清理记录写入 `products/task_assets_cleanup.jsonl`。
- 如果 `task_assets` 已过期或被外部删除，重跑会返回明确的输入文件或模板缺失错误。

## 旧数据兼容

- 旧表通过既有 `run_config_json` 补列逻辑兼容。
- 服务启动会扫描旧的 `closed` Web 任务。
- 缺少 `run_config.closed_from_state` 的旧关闭记录会被回填恢复目标状态。
- 回填规则：`error == "cancelled"` 恢复为 `cancelled`；存在其他错误信息恢复为 `error`；否则恢复为 `done`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_run_history.py tests\test_web_history.py tests\test_web_tasks.py tests\test_web_config_service.py tests\test_task_assets_service.py tests\test_web_frontend_contracts.py
```

结果：`159 passed`。

```powershell
npm run build
```

结果：前端类型检查和生产构建通过。

## 残余边界

- “继续执行”依赖服务进程内存中的 `SessionManager`，服务重启后无法恢复实时后台线程。
- 历史记录中的 `running` 不等价于当前仍有可继续执行的 session；UI 需要区分“运行中且可继续”和“会话不可恢复”。
- `task_assets` 过期或被外部清理后，依赖该快照的远程重跑无法保证复现。
- 本机任务默认仍依赖原始输入路径；只有开启 `local_task_input_snapshot_enabled` 后才会保存本机输入快照。
- 远程交付物 ZIP 过期不影响历史记录，但下载不可用；重跑依赖 `task_assets`，不依赖旧交付物。
- API Key 不随历史保存；重跑始终使用当前可用配置。

## 后续

当前没有必须继续推进的主线任务。后续如引入 Vitest 或组件测试框架，可将现有前端静态契约测试升级为交互级组件测试。
