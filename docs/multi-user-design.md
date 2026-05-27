# Web UI 远程模式 — 多用户系统设计

## 1. 背景

### 1.1 三种运行模式

| 模式 | 用户 | 配置文件 | 用户系统 |
|---|---|---|---|
| CLI | 单人 | 本机 `~/.ai-gen-reimbursement-docs/` | 无 |
| Web 本机 | 单人（localhost） | 本机 `~/.ai-gen-reimbursement-docs/` | 无 |
| Web 远程 | 多人（非 localhost） | 服务端 `users/<username>/` | **本次新增** |

CLI 和 Web 本机模式不变。多用户系统仅在 Web 远程模式下启用。

### 1.2 当前问题

远程模式缺少用户隔离：
- 所有用户共享一套配置和 API Key
- 配置页只读，用户无法个性化设置
- 刷新页面后填写的配置全部丢失

---

## 2. 服务端设计

### 2.1 目录结构

```
~/.ai-gen-reimbursement-docs/
├── system_config.yaml          # 全局默认配置（部署者维护）
├── .env                        # 全局默认环境变量（可选）
├── users.db                    # SQLite，用户表
├── users/
│   └── <username>/
│       ├── .env                # 用户个性化环境变量
│       ├── system_config.yaml  # 用户完整配置（注册时从 example 拷贝）
│       ├── templates/          # 用户上传的自定义模板
│       └── tasks/              # 用户任务历史和输出
└── business_rules.yaml         # 全局业务规则（只读，不按用户分）
```

### 2.2 用户配置初始化

新用户注册时，从**项目内置模板**拷贝，而非从管理员的配置文件：

```
注册 → 拷贝 <项目根>/config/system_config.yaml.example
     → users/<username>/system_config.yaml
```

理由：
- example 是"出厂默认"，带完整注释，适合新人
- 避免泄露管理员的 API Key 等私密信息
- 管理员改自己的配置不影响新用户的起点

### 2.3 数据库

`users.db`（SQLite），一张表：

```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,          -- bcrypt 哈希
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

不设角色字段，所有人平等。

### 2.4 认证

- **登录**：POST username + password → 返回 session token（JWT 或随机字符串，服务端内存 + cookie）
- **退出**：清除 cookie
- **注册**：POST username + password → 自动创建用户目录、拷贝配置模板
- **注册开关**：`system_config.yaml` 中新增 `allow_register: true`，管理员可设为 `false` 关闭注册

### 2.5 API 变更

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/auth/register` | POST | 注册（可开关） |
| `/api/auth/login` | POST | 登录，返回 token |
| `/api/auth/logout` | POST | 退出 |
| `/api/auth/me` | GET | 返回当前登录用户信息 |
| `/api/user/config` | GET | 读取**用户的** system_config.yaml + .env |
| `/api/user/config` | POST | 保存**用户的** system_config.yaml + .env |
| `/api/user/templates` | GET | 列出用户已上传的模板 |
| `/api/user/templates/{name}` | GET | 下载用户模板 |
| `/api/user/templates/{name}` | DELETE | 删除用户模板 |
| `/api/templates/input` | GET | 下载录入模板（公开，不需登录） |
| `/api/templates/output` | GET | 列出输出模板（公开） |
| `/api/templates/output/{name}` | GET | 下载输出模板（公开） |

**重要**：已登录用户的 pipeline 启动时，API Key/Model 优先用用户自己的 `.env`，未配置则 fallback 到全局默认。

---

## 3. 前端设计

### 3.1 页面结构

```
┌──────────────────────────────────────────┐
│  AI 生成项目报账文档   用户名 ▼ [退出]     │
├──────────────────────────────────────────┤
│  /  → 生成页（首页）                      │
│  /config → 配置页（可编辑）                │
│  /prompt-debug → 提示词调试               │
└──────────────────────────────────────────┘
```

### 3.2 登录页

```
┌──────────────────────────┐
│   AI 生成项目报账文档      │
│                          │
│   用户名 [________]       │
│   密码   [________]       │
│                          │
│   [登录]   [注册]         │
└──────────────────────────┘
```

- 注册按钮受 `allow_register` 开关控制
- 未登录时所有页面重定向到登录页

### 3.3 配置页改造

```
配置页
├── 个人配置（可编辑）
│   ├── API Key, Model, Base URL, Max Tokens...
│   ├── AI 限制、开关、偏好...
│   ├── [保存]  [导出]  [导入]
│   └── 编辑即调用 /api/user/config 自动保存
│
├── 自定义模板（可上传/下载/删除）
│
└── 服务端全局默认（只读）
    ├── .env 内容
    └── system_config.yaml 内容
```

### 3.4 导出/导入

| 操作 | 行为 |
|---|---|
| **导出** | 用户个人配置 → 下载为 JSON 文件 |
| **导入** | 选择 JSON 文件 → 回填到个人配置并保存 |

导出的 JSON 仅含用户可配置的字段，不含路径等机器相关值：

```json
{
  "apiKey": "sk-xxx",
  "model": "deepseek-v4-flash[1m]",
  "baseUrl": "https://api.deepseek.com/anthropic",
  "maxTokens": "6000",
  "projectName": "",
  "pipelineMode": "from-excel-gen-all",
  "clean": false,
  "fpaReducedUseWorkload": false,
  "specAutoUpdateToc": true,
  "specRemindUpdateToc": true,
  "cosmicWarnMarker": false,
  "cosmicWarnLog": true
}
```

### 3.5 路由守卫

```
未登录 → 任何页面 → 重定向到 /login
已登录 → /login → 重定向到 /
```

---

## 4. 本机模式区分

### 4.1 判断逻辑

```python
# server.py — 现有代码
@app.get("/api/is-local")
async def is_local(request: Request):
    host = request.client.host if request.client else ""
    return {"local": host in ("127.0.0.1", "::1", "localhost")}
```

```typescript
// App.vue — 已改好
// 1. 配置优先：web_work_mode: local/remote → 强制
// 2. IP 兜底：localhost → local，其他 → remote
```

### 4.2 本机模式行为

- `workMode === 'local'` 时
- 不显示登录页，不需要认证
- 所有 `/api/user/*` 端点在 local 模式下操作**本机**的 `~/.ai-gen-reimbursement-docs/`
- 保持现有逻辑不变

### 4.3 远程模式行为

- `workMode === 'remote'` 时
- 显示登录页，需要认证
- 所有 `/api/user/*` 端点操作 `users/<username>/` 下的个人配置
- 未登录用户只能访问公开端点（模板下载）

---

## 5. 不改动的部分

- CLI 模式全部逻辑
- Web 本机模式全部逻辑
- `business_rules.yaml` — 始终保持全局只读
- 现有的 pipeline 执行流程
- 输出模板（`/api/templates/output`）保持公开访问

---

## 6. 改动清单

| 文件 | 改动 | 预计行数 |
|---|---|---|
| `web_app/server.py` | 新增 auth 端点、用户端点改造、中间件注入用户 | +120 |
| `ai_gen_reimbursement_docs/auth.py` | 新文件：密码哈希、token 生成/验证、用户目录初始化 | +80 |
| `web_app/src/stores/auth.ts` | 新文件：登录状态、用户信息 | +40 |
| `web_app/src/views/Login.vue` | 新文件：登录/注册页 | +60 |
| `web_app/src/views/Config.vue` | 改造：支持编辑保存、导出/导入 | +80 |
| `web_app/src/App.vue` | 加用户标识、路由守卫 | +30 |
| `web_app/src/router.ts` | 加 /login 路由、路由守卫 | +15 |
| `web_app/src/stores/config.ts` | 加 localStorage 持久化、导出导入方法 | +40 |
| `config/system_config.yaml.example` | 加 `allow_register: true` | +2 |

总计约 **470 行**（含前端），改动集中在 Web 层，不影响核心 pipeline 逻辑。
