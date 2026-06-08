# 密码保存、自动登录与管理员邀请注册方案

## 背景

当前 Web 远程模式已有简易多用户认证：

- 用户数据存储在 `~/.ai-gen-reimbursement-docs/users.db`。
- 登录 token 仅保存在服务端内存字典，服务重启后登录态失效。
- 浏览器通过 `ard_token` cookie 携带登录 token。
- 注册开关由 `system_config.yaml` 中的 `allow_register` 控制。

本方案扩展现有认证体系，不新增并行认证系统。

## 目标行为

### 密码保存功能

登录页提供“记住我”选项。

- 勾选后，只在浏览器本地保存上次登录用户名。
- 不在前端、后端或配置文件中保存明文密码。
- 密码保存交给浏览器自身密码管理器处理。

### 自动登录功能

登录时勾选“记住我”后，系统创建可持久化的会话 token。

- `ard_token` cookie 设置有效期。
- 服务端将 token 哈希、用户名、过期时间写入 SQLite。
- 服务重启后，`/api/auth/me` 可根据 cookie 恢复登录态。
- 登出时立即删除服务端会话记录，并清除 cookie。
- 未勾选“记住我”时保持当前会话级登录体验。

### 管理员内置账户功能

认证库初始化时确保存在管理员账号。

- 用户表增加 `role` 字段，支持 `admin` 与 `user`。
- 内置管理员账号固定为 `admin / mlt123`。
- 系统启动或认证库初始化时，如果管理员账号不存在，则创建 `admin` 用户并写入 PBKDF2 密码哈希。
- 系统尚未上线，不需要兼容旧版本用户库或旧账号结构。
- 管理员账号创建后应复用现有用户目录初始化流程。

### 管理员邀请注册功能

关闭公开注册，改为管理员邀请注册。

- 注册接口要求邀请码。
- 邀请码由管理员生成。
- 邀请码支持过期时间、最大使用次数、停用状态。
- 普通用户不能创建、查看或停用邀请码。
- 邀请码使用成功后扣减次数；一次性邀请码使用后失效。
- 邀请码管理页放在“系统管理”下，提供完整管理 UI。

### 管理员邀请码管理 UI

系统管理下新增“邀请注册”页面，仅管理员可见。

- 管理员可生成邀请码。
- 管理员可设置邀请码有效期和最大使用次数。
- 生成成功后仅本次展示明文邀请码，并提供复制按钮。
- 管理员可查看邀请码列表，包括状态、创建人、创建时间、过期时间、最大使用次数、已使用次数。
- 管理员可停用未停用的邀请码。
- 非管理员不显示入口；即使直接访问接口，后端也必须拒绝。

## 拟修改文件

- `ai_gen_reimbursement_docs/auth.py`
  - 扩展用户表结构。
  - 新增角色、管理员初始化、持久会话、邀请码相关函数。
  - 将 token 校验从纯内存字典扩展为“内存优先、数据库兜底”。

- `web_app/dependencies.py`
  - 新增 `require_admin` 依赖。
  - 保留现有 `require_auth` 行为。

- `web_app/server.py`
  - 扩展 `/api/auth/login`，支持 `remember_me`。
  - 扩展 `/api/auth/register`，支持邀请码校验。
  - 扩展 `/api/auth/me`，返回用户角色。
  - 新增管理员邀请码管理接口。

- `web_app/src/stores/auth.ts`
  - 登录请求增加 `remember_me`。
  - 当前用户状态增加 `role`。
  - 支持保存和恢复上次登录用户名。

- `web_app/src/views/Login.vue`
  - 增加“记住我”控件。
  - 注册模式增加邀请码输入。
  - 登录页初始化时填充上次保存的用户名。

- 系统管理相关前端文件
  - 在系统管理下新增邀请注册管理页面。
  - 仅 `role === 'admin'` 时展示入口。
  - 支持生成、复制、列表查看、停用邀请码。

- `config/system_config.yaml.example`
  - 补充管理员初始账号、自动登录有效期、公开注册策略配置说明。

- 测试文件
  - `tests/test_auth_config.py`
  - `tests/test_web_session_auth.py`
  - 必要时新增 `tests/test_web_admin_invites.py`

## 建议数据模型

系统尚未上线，不需要对旧版 `users.db` 做迁移兼容。实施时可以直接按以下结构初始化新库；如本地存在开发期旧库，可由开发者手动删除后重建。

### users

用户表结构：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `username TEXT UNIQUE NOT NULL`
- `password TEXT NOT NULL`
- `salt TEXT NOT NULL`
- `role TEXT NOT NULL DEFAULT 'user'`
- `disabled INTEGER NOT NULL DEFAULT 0`
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
  "role": "admin"
}
```

### POST /api/auth/register

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
  "is_local": false,
  "allow_register": false
}
```

### POST /api/admin/invites

仅管理员可访问。

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

## 验证方式

后端认证测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth_config.py tests/test_web_session_auth.py
```

新增邀请注册测试后：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_admin_invites.py
```

管理员邀请注册 UI 完成后：

```powershell
npm run build
```

## 风险与约束

- 不实现明文密码落盘。
- 自动登录 token 必须有过期时间，登出后必须立即失效。
- 当前阶段管理员初始密码固定为 `mlt123`；上线前应增加修改密码或首次登录强制改密能力。
- `allow_register` 建议重新定义为“是否允许公开注册”；管理员邀请注册不受公开注册开关影响。
- 系统尚未上线，不做旧版数据库迁移兼容。
