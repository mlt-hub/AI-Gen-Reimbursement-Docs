# 密码保存、自动登录与管理员邀请注册实施记录

## 状态

- 状态：已实施并合并到 `master`
- 功能提交：`ebd205f988b1bd20f151001c757c973681d31916` (`feat: add admin invite auth flow`)
- 合并提交：`eb768707ab08a410e4e2dc2e156e08c1a7dbcfca` (`Merge branch 'feature/auth-account'`)
- 风险收敛提交：`2afea257bba32efa5c1f7071c8d3d7fd9d677a79` (`fix: harden auth account flow`)
- 实施分支：`feature/auth-account`
- 实施 worktree：`F:\tmp\ai_gen_reimbursement_docs-auth-account`

## 风险收敛更新

`2afea257bba32efa5c1f7071c8d3d7fd9d677a79` 已将合入后复核发现的剩余风险收敛到当前 `master`：

- 内置管理员首次登录后必须修改初始密码；未改密前禁止访问管理员接口。
- `/api/auth/change-password` 支持当前登录用户修改密码，管理员不能继续使用内置初始密码。
- 邀请码注册流程改为同一 SQLite 事务内完成用户写入和邀请码次数扣减，避免注册失败消耗邀请码。
- HTTPS 请求下设置 `ard_token` cookie 的 `Secure` 属性，本地 HTTP 开发模式保持可用。
- 开发期旧 `users` 表会轻量补齐 `role`、`disabled`、`must_change_password` 字段。

## 背景

当前 Web 远程模式已有简易多用户认证：

- 用户数据存储在 `~/.ai-gen-reimbursement-docs/users.db`。
- 登录 token 仅保存在服务端内存字典，服务重启后登录态失效。
- 浏览器通过 `ard_token` cookie 携带登录 token。
- 注册开关由 `system_config.yaml` 中的 `allow_register` 控制。

本次实现扩展现有认证体系，不新增并行认证系统。

## 目标行为

### 密码保存功能

登录页提供“记住我”选项。

- 勾选后，只在浏览器本地保存上次登录用户名。
- 不在前端、后端或配置文件中保存明文密码。
- 密码保存交给浏览器自身密码管理器处理。

### 自动登录功能

登录时勾选“记住我”后，系统创建可持久化的会话 token。

- `ard_token` cookie 设置有效期。
- 自动登录有效期固定为 30 天。
- 服务端将 token 哈希、用户名、过期时间写入 SQLite。
- 服务重启后，`/api/auth/me` 可根据 cookie 恢复登录态。
- 登出时立即删除服务端会话记录，并清除 cookie。
- 每次登录、登出、`/api/auth/me` 校验时顺手清理已过期会话。
- 未勾选“记住我”时保持当前会话级登录体验。

### 管理员内置账户功能

认证库初始化时确保存在管理员账号。

- 用户表增加 `role` 字段，支持 `admin` 与 `user`。
- 内置管理员账号固定为 `admin / mlt123`。
- 系统启动或认证库初始化时，如果管理员账号不存在，则创建 `admin` 用户并写入 PBKDF2 密码哈希。
- 内置管理员首次登录后必须修改初始密码；未修改前不能访问管理员接口。
- 系统尚未上线，不需要兼容旧版本用户库或旧账号结构。
- 管理员账号创建后应复用现有用户目录初始化流程。

### 管理员邀请注册功能

关闭公开注册，改为管理员邀请注册。

- 远程模式下普通用户注册必须填写有效邀请码。
- 普通用户注册密码至少 6 位。
- 管理员内置账号不走邀请码注册流程。
- 邀请码由管理员生成。
- 邀请码生成 16 位随机码，只在生成成功响应中展示一次。
- 数据库只保存邀请码哈希，不保存明文邀请码。
- 邀请码支持过期时间、最大使用次数、停用状态。
- 管理 UI 生成邀请码时，默认有效期 7 天、最大使用次数 1 次。
- 普通用户不能创建、查看或停用邀请码。
- 邀请码使用成功后扣减次数；一次性邀请码使用后失效。
- 邀请码校验、用户创建和邀请码使用次数更新在同一 SQLite 事务中完成，避免注册失败但邀请码被消耗。
- 邀请码管理页放在“系统管理”下，提供完整管理 UI。

### 管理员邀请码管理 UI

系统管理下新增“邀请注册”页面，仅管理员可见。

- 导航菜单仅管理员显示“邀请注册”入口。
- 管理员可生成邀请码。
- 管理员可设置邀请码有效期和最大使用次数。
- 生成成功后仅本次展示明文邀请码，并提供复制按钮。
- 管理员可查看邀请码列表，包括状态、创建人、创建时间、过期时间、最大使用次数、已使用次数。
- 管理员可停用未停用的邀请码。
- 非管理员不显示入口；即使直接访问接口，后端也必须拒绝。

## 实际修改文件

- `ai_gen_reimbursement_docs/auth.py`
  - 扩展用户表结构。
  - 新增角色、管理员初始化、持久会话、邀请码相关函数。
  - 将 token 校验从纯内存字典扩展为“内存优先、数据库兜底”。
  - 补齐开发期旧 `users` 表缺失的 `role`、`disabled`、`must_change_password` 字段。
  - 新增改密函数，管理员默认密码会标记为必须修改。

- `web_app/dependencies.py`
  - 新增 `require_admin` 依赖。
  - 管理员默认密码未修改时拒绝访问管理员接口。
  - 保留现有 `require_auth` 行为。

- `web_app/server.py`
  - 增加 `/admin/invites` 和 `/static/dist/admin/invites` SPA 入口。

- `web_app/routes/auth.py`
  - 扩展 `/api/auth/login`，支持 `remember_me`。
  - 扩展 `/api/auth/register`，支持事务化邀请码注册。
  - 扩展 `/api/auth/me`，返回用户角色和是否必须改密。
  - 新增 `/api/auth/change-password`。
  - HTTPS 请求下为 `ard_token` cookie 设置 `Secure`。
  - 新增管理员邀请码管理接口。

- `web_app/src/stores/auth.ts`
  - 登录请求增加 `remember_me`。
  - 当前用户状态增加 `role`。
  - 当前用户状态增加 `must_change_password`。
  - 支持保存和恢复上次登录用户名。
  - 支持调用改密接口。

- `web_app/src/views/Login.vue`
  - 增加“记住我”控件。
  - 注册模式增加邀请码输入。
  - 登录页初始化时填充上次保存的用户名。
  - 管理员初始密码未修改时停留在登录页完成改密。

- 系统管理相关前端文件
  - 在系统管理下新增邀请注册管理页面。
  - 仅 `role === 'admin'` 时展示入口。
  - 支持生成、复制、列表查看、停用邀请码。

- `config/system_config.yaml.example`
  - 补充管理员初始账号、自动登录有效期、公开注册策略配置说明。

- 测试文件
  - `tests/test_auth_config.py`
  - `tests/test_web_session_auth.py`
  - `tests/test_web_admin_invites.py`

## 数据模型

系统尚未上线，不需要对旧版 `users.db` 做迁移兼容。当前实现直接按以下结构初始化新库；如本地存在开发期旧库，可由开发者手动删除后重建。

### users

用户表结构：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `username TEXT UNIQUE NOT NULL`
- `password TEXT NOT NULL`
- `salt TEXT NOT NULL`
- `role TEXT NOT NULL DEFAULT 'user'`
- `disabled INTEGER NOT NULL DEFAULT 0`
- `must_change_password INTEGER NOT NULL DEFAULT 0`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

### auth_sessions

新增会话表：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `token_hash TEXT UNIQUE NOT NULL`
- `username TEXT NOT NULL`
- `expires_at TIMESTAMP NOT NULL`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `last_seen_at TIMESTAMP`

### registration_invites

新增邀请码表：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `code_hash TEXT UNIQUE NOT NULL`
- `created_by TEXT NOT NULL`
- `expires_at TIMESTAMP`
- `max_uses INTEGER NOT NULL DEFAULT 1`
- `used_count INTEGER NOT NULL DEFAULT 0`
- `disabled INTEGER NOT NULL DEFAULT 0`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

## 接口设计

### POST /api/auth/login

请求：

```json
{
  "username": "admin",
  "password": "password",
  "remember_me": true
}
```

响应：

```json
{
  "username": "admin",
  "role": "admin",
  "must_change_password": true
}
```

### POST /api/auth/register

远程模式下必须提供有效邀请码。邀请码无效、已过期、已停用或使用次数已耗尽时，接口应返回明确错误。
普通用户注册密码至少 6 位。

请求：

```json
{
  "username": "alice",
  "password": "password",
  "invite_code": "example-code"
}
```

### GET /api/auth/me

远程模式响应：

```json
{
  "username": "admin",
  "role": "admin",
  "must_change_password": true,
  "is_local": false,
  "allow_register": false
}
```

### POST /api/auth/change-password

当前登录用户修改密码。管理员不能把新密码继续设为内置初始密码。

请求：

```json
{
  "current_password": "mlt123",
  "new_password": "changed-secret"
}
```

响应：

```json
{
  "ok": true,
  "username": "admin",
  "role": "admin",
  "must_change_password": false
}
```

### POST /api/admin/invites

仅管理员可访问。
未传 `expires_in_days` 或 `max_uses` 时，默认有效期 7 天、最大使用次数 1 次。

请求：

```json
{
  "expires_in_days": 7,
  "max_uses": 1
}
```

响应只返回一次明文邀请码，数据库只保存哈希。

### GET /api/admin/invites

仅管理员可访问。返回邀请码列表，不返回明文邀请码。

### POST /api/admin/invites/{invite_id}/disable

仅管理员可访问。停用指定邀请码。

## 错误提示

注册接口应区分以下邀请码错误：

- 邀请码无效。
- 邀请码已过期。
- 邀请码已停用。
- 邀请码使用次数已耗尽。

管理员接口权限错误保持现有认证语义：

- 未登录返回 `401`。
- 非管理员返回 `403`。

## 验证结果

后端认证测试已通过：

```powershell
F:\mlt\mlt-projects\ai_gen_reimbursement_docs\.venv\Scripts\python.exe -m pytest tests/test_auth_config.py tests/test_web_admin_invites.py tests/test_web_session_auth.py
```

前端构建已通过：

```powershell
npm run build
```

## 验收用例

- 首次初始化认证库后，自动存在 `admin / mlt123` 管理员账号。
- `admin` 登录后 `GET /api/auth/me` 返回 `role: "admin"`。
- `admin` 首次登录后 `must_change_password: true`，修改初始密码前不能访问管理员接口。
- 修改密码后 `must_change_password: false`，管理员接口恢复可用。
- 普通用户或未登录用户无法访问管理员邀请码接口。
- 管理员可以生成邀请码，响应中返回一次明文邀请码。
- 邀请码列表不返回明文邀请码。
- 普通用户使用有效邀请码可注册成功。
- 邀请码无效、已过期、已停用、使用次数已耗尽时注册失败，并返回明确提示。
- 一次性邀请码注册成功后不可再次使用。
- 管理 UI 生成邀请码时，默认有效期为 7 天、最大使用次数为 1 次。
- 普通用户注册密码少于 6 位时注册失败。
- 勾选“记住我”登录后，服务重启仍可通过 cookie 恢复登录态。
- HTTPS 登录响应中的 `ard_token` cookie 包含 `Secure`。
- 登出后，原自动登录 token 立即失效。
- 登录、登出、`/api/auth/me` 校验会清理已过期会话。
- 登录页勾选“记住我”后，下次打开自动填充上次用户名，但不填充密码。
- 系统管理菜单仅管理员显示“邀请注册”入口。

## 风险与约束

- 不实现明文密码落盘。
- 自动登录 token 必须有过期时间，登出后必须立即失效。
- 当前阶段管理员初始密码固定为 `mlt123`，但首次登录后必须修改；后续仍建议增加完整账号管理能力。
- `allow_register` 建议重新定义为“是否允许公开注册”；管理员邀请注册不受公开注册开关影响。
- 系统尚未上线，不做完整旧版数据库迁移兼容；当前仅补齐开发期旧 `users` 表所需轻量字段。
