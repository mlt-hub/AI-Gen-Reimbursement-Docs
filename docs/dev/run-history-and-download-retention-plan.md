# 运行历史与交付物保留方案

日期：2026-05-29

## 背景

项目存在三种运行入口：

```text
CLI
Web UI 本机模式
Web UI 远程服务模式
```

它们都需要留下“曾经运行过什么”的历史记录，但交付物生命周期不同：

- CLI 和 Web 本机模式的产物在用户本机输出目录中。
- Web 远程服务模式的产物在服务端临时目录中，需要短期保留并自动清理。
- 运行历史不应因为交付物被清理而消失。

因此需要把两个概念拆开：

```text
运行历史：长期记录，不等同于文件下载。
交付物：可能是本地目录，也可能是远程 zip，有各自保留策略。
```

## 目标

1. 三种入口都写入运行历史。
2. Web UI 提供历史列表，能展示 CLI、本机 Web、远程 Web 的运行记录。
3. 明确告诉用户远程下载保留多久。
4. 明确告诉用户本机/CLI 产物不由 Web UI 自动删除。
5. 即使交付物已过期、目录被用户删除，历史记录仍保留。
6. 远程多用户场景下，历史记录按用户隔离。
7. 历史数据库属于运行期数据，不进入发布包。

## 三种模式定义

### CLI

CLI 是用户在本机命令行直接运行。

特点：

- 无 Web session。
- 无远程 zip 下载生命周期。
- 产物输出到本机目录。
- 历史应跟随当前操作系统用户，而不是跟随某个工作目录。

推荐历史存储：

```text
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

交付物策略：

```text
artifact_kind = local_dir
Web UI/CLI 不自动删除输出目录
```

### Web UI 本机模式

Web UI 本机模式由本机浏览器访问本机服务。

特点：

- 有 Web session。
- 产物输出到本机目录。
- 可通过 Web UI 打开目录。
- 不参与远程下载过期清理。

推荐历史存储：

```text
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

交付物策略：

```text
artifact_kind = local_dir
Web UI 不自动删除输出目录
```

### Web UI 远程服务模式

远程服务模式由多用户访问同一个服务端。

特点：

- 有 Web session。
- 有稳定用户标识隔离。
- 产物位于服务端临时目录。
- 通过 zip 下载交付物。
- zip 和临时目录需要按天清理。

推荐历史存储：

```text
products/run_history.sqlite3
```

交付物策略：

```text
artifact_kind = remote_zip
按 remote_session_retention_days 清理 zip 和临时目录
历史记录不随交付物删除
```

## 保留策略

### 远程下载保留

配置项：

```yaml
remote_session_retention_days: 1
```

含义：

- 远程任务交付物下载默认保留 1 天。
- 到期后清理 zip 和远程临时工作目录。
- 历史记录不随下载文件删除。

用户文案：

```text
远程任务交付物下载默认保留 1 天；过期后运行记录仍保留。
```

### 本机/CLI 文件保留

规则：

- CLI 和 Web 本机模式的输出目录不由 Web UI 自动删除。
- 历史记录保存输出目录路径和文件清单。
- 查询历史时动态检查输出目录是否仍存在。
- 目录存在时提供“打开目录”“复制路径”等操作。
- 目录不存在时历史仍显示，标记为“目录不存在”。

用户文案：

```text
本机与 CLI 任务交付物保存在本机输出目录，系统不会自动删除。
```

### 历史记录保留

第一阶段建议不自动删除历史记录。

后续如果需要清理，可新增：

```yaml
run_history_retention_days: 0
```

语义：

```text
0：永久保留历史记录。
大于 0：保留指定天数。
```

第一阶段建议默认永久保留，避免用户误以为运行记录也会随下载文件过期。

## 存储位置决策

### 用户级历史

适用：

```text
CLI
Web UI 本机模式
```

路径：

```text
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

原因：

- CLI 可能从不同项目目录运行。
- 本机用户希望跨工作目录查看自己的历史。
- 不应把个人运行历史写入项目仓库或发布目录。

### 服务端实例级历史

适用：

```text
Web UI 远程服务模式
```

路径：

```text
products/run_history.sqlite3
```

原因：

- 远程服务是一个部署实例。
- 多用户历史需要服务端统一管理。
- `owner_id` 隔离在服务端历史中处理。
- 数据库属于运行期数据，不应进入发布包、安装包或源码仓库。

## 存储实现

历史记录主存储采用 SQLite：

```text
CLI + Web 本机：~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
Web 远程：products/run_history.sqlite3
```

不采用 JSONL 作为主存储的原因：

- 远程多用户同时完成任务时，单文件追加存在记录交错或丢失风险。
- 如果采用“读全量 -> 修改 -> 写回”，并发写会互相覆盖。
- Windows 与 Linux 的文件锁语义不一致，不能依赖裸文件 append 的原子性。
- 后续如果服务用多进程部署，进程内锁无法保护同一个 JSONL 文件。

SQLite 优点：

- Python 标准库内置 `sqlite3`，不增加依赖。
- 事务保证写入完整性。
- 多连接并发写会由 SQLite 排队处理。
- 便于按 `owner_id`、source、mode、state、created_at 分页查询。
- 后续可以自然扩展搜索、筛选、导出。

建议初始化连接时启用：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

说明：

- `WAL` 提升读写并发能力。
- `busy_timeout` 让并发写等待锁释放，减少瞬时 `database is locked`。
- 每次 upsert 使用事务，失败时回滚。
- 远程部署时，SQLite 数据库应放在服务端本机磁盘；不建议放在网络共享盘、同步盘或对象存储挂载目录。

JSONL 仅保留为后续可选导出格式，不作为运行历史主存储。

### 发布包边界

以下文件是运行期数据，不能进入发布产物：

```text
products/run_history.sqlite3
products/run_history.sqlite3-wal
products/run_history.sqlite3-shm
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

发布包检查应确保：

```text
dist/ard/products/run_history.sqlite3 不存在
dist/ard/products/run_history.sqlite3-wal 不存在
dist/ard/products/run_history.sqlite3-shm 不存在
```

说明：

- 发布包只包含程序、公开资源、`data.enc` 和公钥。
- 历史数据库只在用户运行后生成。
- 不允许把开发机或服务端历史记录打进公开包。

## 数据模型

建议新增共享历史模块：

```text
ai_gen_reimbursement_docs/run_history.py
```

Web 可在服务层封装：

```text
web_app/services/run_history_service.py
```

### SQLite 表结构

```sql
CREATE TABLE IF NOT EXISTS run_history (
  run_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL DEFAULT 1,
  source TEXT NOT NULL,
  session_id TEXT NOT NULL DEFAULT '',
  mode TEXT NOT NULL,
  owner_id TEXT NOT NULL DEFAULT '',
  owner_label TEXT NOT NULL DEFAULT '',
  task_mode TEXT NOT NULL DEFAULT '',
  run_state TEXT NOT NULL,
  input_name TEXT NOT NULL DEFAULT '',
  input_path TEXT NOT NULL DEFAULT '',
  output_dir TEXT NOT NULL DEFAULT '',
  artifact_kind TEXT NOT NULL,
  zip_path TEXT NOT NULL DEFAULT '',
  download_expires_at TEXT NOT NULL DEFAULT '',
  done_files_json TEXT NOT NULL DEFAULT '[]',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT '',
  finished_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_history_created
ON run_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_run_history_owner_created
ON run_history(owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_run_history_source_mode_state
ON run_history(source, mode, run_state, created_at DESC);
```

迁移表：

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

实现要求：

- 模块初始化时自动创建表。
- schema 后续变更通过 `schema_migrations` 管理。
- `done_files` 存为 JSON 字符串，字段名为 `done_files_json`。
- 查询返回给 API/CLI 时再反序列化为数组。

### 统一字段

```json
{
  "schema_version": 1,
  "source": "web",
  "run_id": "20260529_100000_xxx",
  "session_id": "20260529_100000_xxx",
  "created_at": "2026-05-29T10:00:00+08:00",
  "started_at": "2026-05-29T10:00:01+08:00",
  "finished_at": "2026-05-29T10:03:20+08:00",
  "updated_at": "2026-05-29T10:03:20+08:00",
  "mode": "local",
  "owner_id": "",
  "owner_label": "",
  "task_mode": "gen-all",
  "run_state": "done",
  "input_name": "功能清单.xlsx",
  "input_path": "D:/work/功能清单.xlsx",
  "output_dir": "D:/work/products/xxx",
  "artifact_kind": "local_dir",
  "zip_path": "",
  "download_expires_at": "",
  "download_available": false,
  "open_folder_available": true,
  "done_files": [
    {
      "name": "项目需求说明书.docx",
      "path": "D:/work/products/xxx/项目需求说明书.docx",
      "is_temp": false
    }
  ],
  "error": ""
}
```

### 字段说明

```text
schema_version
  历史记录结构版本。

source
  cli 或 web。

run_id
  运行唯一 ID。CLI 没有 session 时也必须有 run_id。

session_id
  Web session ID。CLI 可为空。

created_at / started_at / finished_at / updated_at
  生命周期时间，用 ISO 8601 字符串。

mode
  local 或 remote。

owner_id
  远程服务稳定用户 ID，用于权限隔离。CLI 和 Web 本机模式可为空。

owner_label
  用户显示名，仅用于展示。用户改名不应影响 owner_id。

task_mode
  gen-all、gen-fpa、gen-spec 等业务模式。

run_state
  running、waiting_input、done、error、cancelled。

input_name / input_path
  输入文件名和路径。远程上传场景 input_path 可为空或使用临时路径摘要。

output_dir
  CLI/Web 本机模式保存真实输出目录。远程模式可为空。

artifact_kind
  local_dir 或 remote_zip。

zip_path
  远程模式 zip 路径。本机/CLI 通常为空。

download_expires_at
  远程 zip 下载过期时间。本机/CLI 为空。

download_available
  查询时动态计算，不只依赖落盘值。

open_folder_available
  查询时动态检查 output_dir 是否存在。

done_files
  任务完成时生成的文件清单。
  CLI/Web 本机模式可以保存绝对路径。
  Web 远程模式只允许保存文件名、相对路径、大小等展示信息，不保存服务端临时目录绝对路径。

error
  失败或取消原因。
```

## 记录示例

### CLI

```json
{
  "schema_version": 1,
  "source": "cli",
  "run_id": "20260529_103012_cli",
  "session_id": "",
  "mode": "local",
  "owner_id": "",
  "owner_label": "",
  "task_mode": "gen-all",
  "run_state": "done",
  "input_name": "功能清单.xlsx",
  "input_path": "D:/work/功能清单.xlsx",
  "output_dir": "D:/work/products/xxx",
  "artifact_kind": "local_dir",
  "zip_path": "",
  "download_expires_at": "",
  "done_files": [],
  "error": ""
}
```

### Web UI 本机模式

```json
{
  "schema_version": 1,
  "source": "web",
  "run_id": "20260529_103012_local",
  "session_id": "20260529_103012_local",
  "mode": "local",
  "owner_id": "",
  "owner_label": "",
  "task_mode": "gen-spec",
  "run_state": "done",
  "input_name": "功能清单.xlsx",
  "output_dir": "D:/work/products/xxx",
  "artifact_kind": "local_dir",
  "done_files": [],
  "error": ""
}
```

### Web UI 远程服务模式

```json
{
  "schema_version": 1,
  "source": "web",
  "run_id": "20260529_103012_remote",
  "session_id": "20260529_103012_remote",
  "mode": "remote",
  "owner_id": "user_123",
  "owner_label": "alice",
  "task_mode": "gen-all",
  "run_state": "done",
  "input_name": "功能清单.xlsx",
  "output_dir": "",
  "artifact_kind": "remote_zip",
  "zip_path": "products/sessions/20260529_103012_remote/result.zip",
  "download_expires_at": "2026-05-30T10:03:20+08:00",
  "done_files": [
    {
      "name": "项目需求说明书.docx",
      "relative_path": "项目需求说明书.docx",
      "size": 123456
    }
  ],
  "error": ""
}
```

## API 设计

新增路由：

```text
web_app/routes/history.py
```

### 查询历史列表

```http
GET /api/history
```

查询参数：

```text
limit: 默认 50
offset: 默认 0
source: cli | web | all
mode: local | remote | all
state: done | error | cancelled | running | all
```

返回：

```json
{
  "retention": {
    "remote_download_retention_days": 1,
    "local_retention_label": "本机与 CLI 文件不由 Web UI 自动清理"
  },
  "items": []
}
```

读取范围：

- 本机模式：读取用户级历史。
- 远程服务模式：读取服务端实例级历史，并按 `owner_id` 过滤。

### 查询单条历史

```http
GET /api/history/{run_id}
```

用途：

- 查看详细文件清单。
- 查看错误信息。
- 从历史页跳转详情。

### 下载历史交付物

复用现有接口：

```http
GET /api/download/{session_id}
```

规则：

- 仅远程 zip 存在且未过期时允许下载。
- 远程 zip 不存在或已过期时返回“下载已过期”。
- CLI/Web 本机记录默认不提供 zip 下载。

### 打开本机目录

复用或扩展现有接口：

```http
POST /api/open-folder?session={session_id}
POST /api/history/{run_id}/open-folder
```

规则：

- 仅本机模式允许。
- CLI/Web 本机记录的 `output_dir` 存在时允许打开。
- 目录不存在时返回明确错误。
- 远程模式永远不允许打开服务端目录。

## CLI 设计

### 写入历史

CLI 每次执行生成任务都写用户级历史：

```text
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

写入时机：

- 启动任务：写 `running`。
- 成功完成：更新为 `done`。
- 失败：更新为 `error` 并写入错误摘要。
- 用户取消：更新为 `cancelled`。

### 查询历史命令

建议新增：

```powershell
ard --history
ard --history --limit 20
ard --history --json
ard --history-open <run_id>
```

第一阶段可只实现写入历史，查询命令放到第二阶段。

## 后端实现步骤

### 1. 新增共享历史模块

文件：

```text
ai_gen_reimbursement_docs/run_history.py
```

职责：

- `user_history_path()`
- `service_history_path(base_dir)`
- `connect(history_path)`
- `init_db(history_path)`
- `upsert_run(record, history_path)`
- `list_runs(history_path, filters, limit, offset)`
- `get_run(run_id, history_path)`
- `compute_artifact_status(record)`
- `sanitize_done_files(record)`

写入策略：

- 每次写入使用 SQLite 事务。
- `run_id` 使用 `INSERT ... ON CONFLICT(run_id) DO UPDATE`。
- 连接设置 `busy_timeout`，处理多用户同时写入。
- 远程服务不要使用进程内列表作为历史真相源。
- 写入远程历史前必须对 `done_files` 做路径脱敏，只保留相对信息。

### 2. Web 封装历史服务

文件：

```text
web_app/services/run_history_service.py
```

职责：

- 判断当前请求读取用户级历史还是服务端历史。
- 处理 `owner_id` 权限过滤。
- 处理本机目录可打开状态。
- 处理远程 zip 下载可用状态。

### 3. CLI 接入

在 CLI 主流程中：

- 为每次运行创建 `run_id`。
- 任务开始写 `running`。
- 管道成功后写 `done`。
- 异常捕获后写 `error`。
- 记录 `input_path`、`output_dir`、`task_mode`、`done_files`。

### 4. Web 任务接入

任务创建时写：

```text
source = web
run_state = running
mode
owner_id
owner_label
task_mode
input_name
artifact_kind
```

其中：

```text
远程模式必须写 owner_id 和 owner_label。
本机模式 owner_id 和 owner_label 留空。
```

任务结束时更新：

```text
run_state
finished_at
done_files
output_dir
zip_path
download_expires_at
error
```

远程任务：

```text
download_expires_at = finished_at + remote_session_retention_days
artifact_kind = remote_zip
```

本机任务：

```text
download_expires_at = ""
artifact_kind = local_dir
```

### 5. 清理逻辑只清交付物

远程清理继续处理：

```text
zip 文件
远程临时工作目录
session 内存状态
```

不要删除：

```text
products/run_history.sqlite3
~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
```

查询时动态计算：

```text
download_available
open_folder_available
```

状态枚举应与现有前端 `RunState` 对齐，避免维护两套状态名称。

## 前端实现步骤

### 1. 新增历史页面

文件：

```text
web_app/src/views/History.vue
```

路由：

```text
/history
```

导航：

```text
历史
```

### 2. 页面提示

顶部说明：

```text
远程任务交付物下载默认保留 1 天；过期后运行记录仍保留。
本机与 CLI 任务交付物保存在本机输出目录，系统不会自动删除。
```

### 3. 列表字段

```text
运行时间
入口来源
模式
任务类型
状态
输入文件
产物数量
交付物状态
操作
```

默认视图：

```text
默认展示全部来源，但提供 CLI / Web 筛选。
每条记录必须清晰标注入口来源，避免 CLI 调试记录和 Web 记录混淆。
```

### 4. 操作按钮

远程 Web：

```text
download_available=true  -> 下载 .zip
download_available=false -> 已过期
```

Web 本机/CLI：

```text
open_folder_available=true  -> 打开目录
open_folder_available=false -> 目录不存在
```

限制：

```text
open_folder_available 只对 source=cli/web 且 mode=local 有意义。
remote 记录永远不显示“打开服务端目录”。
```

通用：

```text
查看详情
复制路径
```

## 测试计划

### 共享历史模块测试

新增：

```text
tests/test_run_history.py
```

覆盖：

1. 初始化 SQLite 表。
2. 追加新记录。
3. 更新已有记录。
3. 按 run_id 查询。
4. 按 source/mode/state 过滤。
5. 本机目录存在时 `open_folder_available=true`。
6. 本机目录删除后历史仍存在。
7. 远程 zip 存在且未过期时 `download_available=true`。
8. 远程 zip 删除或过期后 `download_available=false`。
9. 并发写入多条记录后不丢记录。
10. 同一 `run_id` 并发更新后数据库不损坏。
11. 远程 `done_files` 不包含服务端绝对路径。

### CLI 测试

覆盖：

1. CLI 成功运行写入 `source=cli` 历史。
2. CLI 失败写入 `run_state=error`。
3. CLI 历史写入用户级路径。

### Web 测试

新增：

```text
tests/test_web_history.py
```

覆盖：

1. Web 本机任务完成后写用户级历史。
2. Web 远程任务完成后写服务端历史。
3. 远程用户只能看到自己的历史。
4. 本机模式可查看用户级历史。
5. 清理过期远程 session 不删除历史记录。
6. `/api/history` 返回保留策略说明。
7. 远程历史不会暴露其他用户 owner_id 下的记录。
8. 远程历史不返回服务端临时目录绝对路径。

### 发布检查测试

覆盖：

1. 发布包中不存在 `products/run_history.sqlite3`。
2. 发布包中不存在 `products/run_history.sqlite3-wal`。
3. 发布包中不存在 `products/run_history.sqlite3-shm`。

### 前端验证

```powershell
npm run build
```

检查：

- 无历史记录空状态。
- CLI 历史显示为“CLI”来源。
- Web 本机历史可打开目录。
- Web 远程历史可下载。
- 远程下载过期时按钮禁用并显示“已过期”。
- 页面文案明确说明下载保留时间和本机文件不自动删除。

### 回归测试

```powershell
.\scripts\test.ps1 tests/test_session_manager.py tests/test_web_tasks.py tests/test_web_session_auth.py tests/test_web_config_service.py tests/test_run_history.py tests/test_web_history.py
npm run build
```

## 分阶段实施建议

### 第一阶段：三入口写入历史

- 新增共享历史模块。
- CLI 写用户级历史。
- Web 本机写用户级历史。
- Web 远程写服务端历史。
- 清理远程下载不删除历史。
- 发布检查排除运行期历史数据库。

### 第二阶段：Web 历史列表

- 新增 `/api/history`。
- 新增 `/history` 页面。
- 展示 CLI、Web 本机、Web 远程三类记录。
- 支持远程下载状态和本机目录状态。

### 第三阶段：详情与操作完善

- 新增 `/api/history/{run_id}`。
- 历史详情展示文件清单和错误。
- 本机/CLI 历史支持打开目录。
- CLI 增加 `ard --history` 和 `ard --history-open`。
- 状态枚举与前端 `RunState` 做一次集中校验。

### 第四阶段：体验增强

- 搜索、筛选、分页。
- 历史记录导出。
- 可配置历史记录保留天数。
- 对过期远程记录提供“重新运行”入口。

## 决策结论

采用统一历史模型：

```text
source: cli | web
mode: local | remote
artifact_kind: local_dir | remote_zip
owner_id / owner_label 用于远程用户隔离和展示
```

存储策略：

```text
CLI：~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
Web 本机：~/.ai-gen-reimbursement-docs/history/run_history.sqlite3
Web 远程：products/run_history.sqlite3
```

发布边界：

```text
run_history.sqlite3 是运行期数据，不进入发布包。
远程历史数据库应位于服务端本机磁盘。
```

保留策略：

```text
远程下载：按 remote_session_retention_days 清理，默认 1 天。
CLI/本机文件：系统不自动删除。
运行历史：第一阶段不自动删除。
```

用户可见承诺：

```text
远程任务交付物下载默认保留 1 天；过期后运行记录仍保留。
本机与 CLI 任务交付物保存在本机输出目录，系统不会自动删除。
```
