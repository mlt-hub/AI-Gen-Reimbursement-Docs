# 身份与权限安全整改实施文档

## 背景

本次安全审查聚焦 Web 后端的身份认证、权限边界、会话安全和资源归属校验。当前项目已有一套轻量鉴权框架：

- `web_app/dependencies.py` 提供 `require_auth`、`require_admin`、`require_local`。
- `ai_gen_reimbursement_docs/auth.py` 负责用户、角色、邀请码和 cookie token。
- `web_app/services/session_access.py` 通过 `SessionManager.can_access` 做 session 访问隔离。
- 远程任务历史通过 `owner_id` 过滤，任务产物、日志、确认数据大多已接入 session 访问校验。

核心问题不是完全没有鉴权框架，而是部分高风险接口绕过了现有框架；本地模式和 token 生命周期也缺少更严格的安全约束。

## 目标行为

整改后应满足以下目标：

1. 远程模式下，所有非公开 `/api/*` 接口必须先完成登录态校验。
2. 管理类、全局配置类、本地文件路径类接口必须具备明确的管理员或本机访问边界。
3. 所有以 `session_id`、`run_id`、`import_id`、`file_id` 定位资源的接口必须校验当前用户是否可访问该资源。
4. Cookie token 不应长期无条件有效；用户禁用、改密、角色变更后，旧 token 应失效。
5. 使用 cookie 鉴权的写接口应具备 CSRF 或 Origin 校验。

## 风险清单

### P0: 调试 AI 接口未鉴权

涉及位置：

- `web_app/routes/prompt_debug.py`
- `/api/test-prompt`
- `/api/test-ai-reliability-desc`
- `/api/test-ai-metadata`

现状：

- 这些接口没有 `Depends(require_auth)`、`require_admin` 或 `require_local`。
- `/api/test-ai-reliability-desc` 和 `/api/test-ai-metadata` 接收 `xlsx_path`，会读取服务端本地 Excel 内容。
- 接口会触发 LLM 调用，存在未授权资源消耗和本地文件内容外发风险。

整改方案：

- 给所有 prompt debug 接口添加权限依赖。
- 推荐策略：
  - `/api/test-prompt`: 至少 `require_auth`；如只用于本机调试，改为 `require_local`。
  - `/api/test-ai-reliability-desc`: `require_local`，禁止远程用户传服务端路径。
  - `/api/test-ai-metadata`: `require_local`，禁止远程用户传服务端路径。
- 如果未来需要远程用户调试，应改为上传文件模式，不能接收任意服务端路径。

验收标准：

- 未登录远程请求上述接口返回 `401` 或 `403`。
- 非本机请求不能通过 `xlsx_path` 读取服务端文件。
- 有测试覆盖未登录、普通用户、管理员或本机访问三类情况。

## P0: 配置读取接口绕过鉴权

涉及位置：

- `web_app/routes/config.py`
- `/api/config`
- `/api/config-read`

现状：

- `/api/config` 无鉴权，返回全局配置脱敏视图。
- `/api/config-read` 无鉴权；未登录远程请求会落到全局配置读取分支，返回 `system_config.yaml`、`business_rules.yaml` 原文和 masked `.env`。

整改方案：

- `/api/config` 添加 `require_auth`。
- `/api/config-read` 添加 `require_auth`，并显式区分：
  - 本地模式：允许读取本机全局配置。
  - 远程模式：只允许读取当前登录用户目录配置和必要的脱敏全局默认。
- 如果 `/api/config-read` 是旧接口，优先考虑删除或迁移到已有 `/api/web-config`、`/api/user/config`。

验收标准：

- 未登录远程请求 `/api/config`、`/api/config-read` 返回 `401`。
- 远程普通用户不能读取全局 `.env`、全局 `business_rules.yaml` 原文。
- 本机模式下现有配置页功能不回退。

## P1: 本地模式成为全局鉴权旁路

涉及位置：

- `web_app/dependencies.py`
- `require_auth`
- `is_local_mode`

现状：

- `require_auth` 在 `is_local_mode(request)` 为真时直接放行。
- `is_local_mode` 受 `web_work_mode` 配置影响；如果服务绑定到 `0.0.0.0` 且配置为 `local`，远程访问也可能绕过登录。

整改方案：

- 明确两套概念：
  - `require_auth`: 只负责登录态，不应因为配置是 local 就无条件放行所有请求。
  - `require_local`: 只使用纯 IP 判断，控制本机能力。
- 对本机专属能力使用 `require_local`，例如打开文件夹、读取服务端路径、编辑高级配置。
- 启动时增加安全检查：
  - 如果监听地址不是 loopback，禁止 `web_work_mode=local`。
  - 或在远程可访问监听下强制进入 remote 鉴权模式。

验收标准：

- 远程 IP 访问时，即使配置误设为 local，也不能绕过需要登录的接口。
- 本机专属接口仍只允许 loopback 访问。
- 增加至少一个配置误设场景的回归测试。

## P1: Local session 在远程请求下可被直接放行

涉及位置：

- `web_app/services/session_manager.py`
- `SessionManager.can_access`

现状：

- `can_access` 中 `local_mode or state.mode == "local"` 会直接返回 `True`。
- 这意味着只要 session 是 local 类型，即使当前请求不是本机，也可能因为 `state.mode == "local"` 被放行。

整改方案：

- 将 local session 的访问条件改为请求本身必须是本机。
- 建议规则：
  - `local_mode=True`: 允许访问存在的 session。
  - `state.mode == "remote"`: 必须 `state.owner == user`。
  - `state.mode == "local"` 且 `local_mode=False`: 拒绝。

验收标准：

- 远程用户不能访问 local session 的下载、日志、确认草稿或继续/取消接口。
- 本机请求仍可访问 local session。
- 更新 `tests/test_session_manager.py` 和 `tests/test_web_session_auth.py` 中对应预期。

## P1: Token 生命周期和撤销机制不足

涉及位置：

- `ai_gen_reimbursement_docs/auth.py`
- `create_token`
- `get_username_by_token`
- `change_password`

现状：

- 普通 `_tokens` 内存 token 没有过期时间。
- remember-me token 可持久化 30 天，但每次解析只查 token 是否存在和是否过期。
- `get_username_by_token` 不复核用户是否仍启用、是否已改密、角色是否变化。
- 改密、禁用用户、角色变更时没有统一撤销已有 token。

整改方案：

- 为 token 增加会话元数据：`expires_at`、`created_at`、`last_seen_at`、`session_version`。
- 用户表增加或复用类似 `session_version` / `password_changed_at` 字段。
- `get_username_by_token` 每次解析后复核：
  - 用户存在且未禁用。
  - token 的 session version 与用户当前 session version 一致。
  - token 未过期。
- `change_password` 成功后撤销该用户所有历史 token，或提升 session version。
- 未来如果增加禁用用户/角色管理，同步撤销该用户 token。

验收标准：

- 改密后旧 token 不能继续访问 `/api/auth/me` 或业务接口。
- disabled 用户 token 不能继续访问接口。
- remember-me token 仍可在服务重启后恢复，但必须遵守用户状态和版本校验。

## P2: Cookie 写接口缺少 CSRF 或 Origin 校验

涉及位置：

- 所有使用 cookie 鉴权的写接口。
- 重点包括配置保存、任务取消/继续、确认 JSON 保存、邀请码管理。

现状：

- 登录 cookie 设置了 `HttpOnly`、`SameSite=Lax`，HTTPS 下设置 `Secure`。
- 但后端没有统一 CSRF token 或 Origin/Referer 校验。

整改方案：

- 短期：对所有非 GET API 增加 Origin/Referer 校验，允许同源和本机来源。
- 中期：增加 CSRF token。
  - 登录或 `/api/auth/me` 返回 CSRF token。
  - 前端 `apiFetch` 对写请求自动带 `X-CSRF-Token`。
  - 后端依赖校验 cookie session 与 CSRF token 绑定。

验收标准：

- 跨站 POST 写接口被拒绝。
- 同源前端请求不受影响。
- 覆盖至少一个配置保存接口和一个任务操作接口。

## P2: 公开模板和系统信息接口需要明确白名单

涉及位置：

- `web_app/routes/templates.py`
- `web_app/routes/system.py`
- `web_app/routes/logging.py`

现状：

- 录入模板、输出模板列表、输出模板下载是公开接口。
- `/api/modes`、`/api/version`、`/api/health`、`/api/license/status`、`/api/log-level` 也是公开或弱限制接口。

整改方案：

- 建立公开接口白名单文档或常量。
- 对公开模板确认内容不含内部敏感业务规则、密钥、客户数据。
- 如果输出模板包含专有格式或内部规则，改为 `require_auth`。
- `/api/health` 中避免返回过细路径状态或配置存在性。

验收标准：

- 所有公开接口都有明确理由。
- 新增 API 时默认需要鉴权，只有进入白名单才能公开。

## 建议实施顺序

1. 修复 `prompt_debug.py` 未鉴权接口。
2. 修复 `/api/config`、`/api/config-read` 未鉴权问题。
3. 收紧 `SessionManager.can_access` 对 local session 的放行规则。
4. 拆分并强化 `require_auth` 与 `require_local` 的职责。
5. 增加 token 撤销和用户状态复核。
6. 增加 CSRF 或 Origin 校验。
7. 建立公开 API 白名单和回归测试清单。

## 回归测试建议

新增或更新以下测试：

- `tests/test_web_prompt_debug_auth.py`
  - 未登录不能调用 prompt debug 接口。
  - 远程请求不能通过 `xlsx_path` 读取服务端文件。
- `tests/test_web_config_auth.py`
  - 未登录不能访问 `/api/config`、`/api/config-read`。
  - 远程用户只能读取个人配置作用域。
- `tests/test_web_session_auth.py`
  - 远程用户不能访问 local session。
  - 远程用户不能访问其他用户 remote session。
- `tests/test_auth_config.py`
  - 改密后旧 token 失效。
  - disabled 用户 token 失效。
- `tests/test_web_csrf.py`
  - 跨站 Origin 的 POST 被拒绝。
  - 同源 POST 正常通过。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_session_auth.py tests/test_web_admin_invites.py tests/test_auth_config.py
```

在完成对应修复后，再补充运行新增测试文件。

## 备注

本次文档只整理审查结果和可实施整改方案，不修改业务代码。后续实施时应按 P0、P1、P2 分批提交，避免把鉴权策略、会话模型和前端调用改动混在一个不可回滚的大变更中。
