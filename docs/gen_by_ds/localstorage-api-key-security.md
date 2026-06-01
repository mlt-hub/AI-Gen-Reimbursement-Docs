# localStorage 存储 API Key 安全策略

## 现状

前端通过 Pinia store（[`config.ts`](../../web_app/src/stores/config.ts#L10-L28)）保存用户配置。历史实现曾将所有配置统一持久化到 `localStorage`，其中包括 API Key。

| Key | 内容 | 代码位置 |
|---|---|---|
| `apiKey` | API Key 明文，短期实现为 `sessionStorage` 会话级保存 | `config.ts` |
| `model` | 模型名称，继续保存到 `localStorage` | `config.ts` |
| `baseUrl` | API 端点地址，继续保存到 `localStorage` | `config.ts` |
| `maxTokens` | 最大 Token 数，继续保存到 `localStorage` | `config.ts` |
| `projectName` / `fpaProfile` / … | 其他非敏感业务配置，继续保存到 `localStorage` | `config.ts` |

当前短期实现：`apiKey` 单独使用 `sessionStorage`，并在 Pinia store 初始化时清理历史遗留的 `localStorage.apiKey`；其他非敏感配置仍通过 `watch` 写入 `localStorage`。

此外，[`Home.vue`](../../web_app/src/views/Home.vue#L313) 用 `localStorage` 保存最近一次会话 ID，用于页面刷新后恢复任务状态。

---

## 风险评估

### 1. XSS 泄露（主要风险）

```
攻击者注入的 JS → localStorage.getItem('apiKey') → 明文 Key 到手
```

`localStorage` 对页面内所有 JS 完全透明，无任何访问控制。一旦存在 XSS 注入点（即使是非持久型），攻击者可直接读取 Key 并发往外部。

**影响程度**：Key 被窃取后，攻击者可用该 Key 调用 DeepSeek API，消耗账户余额。本项目使用按量计费的 DeepSeek Key，单次损失有限，但攻击者可长期静默使用。

### 2. 永久存储无过期

`localStorage` 无 TTL，浏览器关闭、重启后 Key 仍在。用户可能忘记自己在浏览器中存过 Key，长期暴露。

### 3. 明文落盘

浏览器将 `localStorage` 以明文 SQLite/JSON 文件写入磁盘。本地恶意软件、备份工具、浏览器同步服务都可能意外泄露。

### 4. 同源共享

同源下的所有页面、所有 Tab 共享同一份 `localStorage`。未来新增页面、第三方脚本或被注入的脚本都可读取同源 `localStorage` 中的数据。

### 5. 导出配置扩散

如果导出的用户配置 JSON 包含 API Key，用户可能把 Key 随配置文件一起发送给同事、提交到 issue、上传给 AI 或进入备份系统。即使浏览器本地不再持久化 Key，导出文件仍可能成为泄露源。

### 6. 日志脱敏边界

日志不应记录 API Key 的前几位或后几位。需要排查“是否使用同一个 Key”时，使用不可逆指纹，例如 `sha256:<前 8-12 位 hex>`，并同时记录来源和是否已配置。

已实现的安全日志格式：

```text
API Key [web_task]: configured, source=session_override, fingerprint=sha256:8f3a21c9d4e5
API Key [prompt_debug]: configured, source=user_env_file, fingerprint=sha256:8f3a21c9d4e5
API Key [fpa_preview]: missing, source=missing
```

`source` 枚举：

| source | 含义 |
|---|---|
| `session_override` | 前端本次会话填写并随请求提交的覆盖 Key |
| `user_env_file` | 服务端用户配置目录 `~/.ai-gen-reimbursement-docs/.env` |
| `system_env` | 操作系统环境变量 `ANTHROPIC_API_KEY` |
| `config_json` | 旧版/兜底 `config.json` |
| `missing` | 未解析到可用 Key |

实现位置：`config_utils.resolve_api_key()` 返回 Key 值、来源和不可逆指纹；`log_api_key_resolution()` 负责输出安全日志。

---

## 改进方案

### 推荐方案：服务端统一管理 Key + 前端可选覆盖

**核心思路**：Key 由服务端 `~/.ai-gen-reimbursement-docs/.env` 管理，前端仅提供一个"本次会话覆盖"输入框。

```
┌─────────────────────────────────────────────────────┐
│ 服务端 (已有)                                        │
│ ~/.ai-gen-reimbursement-docs/.env                    │
│   ANTHROPIC_API_KEY=sk-xxx    ← 唯一持久化位置       │
│                                                      │
│ 任务接口 → 服务端读取配置并注入 Key                    │
└─────────────────────────────────────────────────────┘
         ▲
         │  LLM 请求走服务端代理
         │
┌─────────────────────────────────────────────────────┐
│ 前端                                                │
│ - 用户可选输入覆盖 Key → 仅存 sessionStorage / 内存    │
│ - 不持久化 API Key                                  │
│ - 读取配置从服务端 /api/config 获取                    │
└─────────────────────────────────────────────────────┘
```

**优点**：
- Key 从不出现在浏览器持久存储中
- XSS 不能直接读取服务端持久 Key；如果用户填写了会话覆盖 Key，XSS 仍可能读取当前会话值或滥用当前页面发起请求
- 关闭浏览器 Key 自动清除
- 向后兼容：现有的 `~/.ai-gen-reimbursement-docs/.env` 配置机制无需改变

**改动点**：
1. 任务接口默认不再依赖前端传入 `api_key`，服务端优先读取 `~/.ai-gen-reimbursement-docs/.env`
2. 前端 `config.ts` 移除 `localStorage` 中 `apiKey` 的持久化，改为 `sessionStorage` 或内存
3. 前端仅在用户显式填写"本次会话覆盖 Key"时随任务请求传递该 Key
4. 日志、历史记录、错误响应、导出配置均不得包含 API Key 原文片段

### 降级方案：sessionStorage 替代 localStorage

如果暂时不调整服务端任务接口，至少将 API Key 从 `localStorage` 改为 `sessionStorage`：

| 对比 | localStorage | sessionStorage |
|---|---|---|
| 生命周期 | 永久 | 关闭标签页即清除 |
| XSS 可读 | 是 | 是 |
| 浏览器同步 | 可能泄露 | 不同步 |
| 持久化风险 | 高 | 低（不会遗留） |

改动最小：只对 `apiKey` 使用 `sessionStorage`；`model`、`baseUrl`、`fpaProfile` 等非敏感配置继续使用 `localStorage`，避免牺牲用户体验。

**局限性**：XSS 仍可读取，只是减少了持久化泄露面。

已实施的短期动作：

- `apiKey` 初始化时只从 `sessionStorage` 读取
- `apiKey` 变化时只写入 `sessionStorage`
- store 初始化时删除历史遗留的 `localStorage.apiKey`
- 导出的用户设置 JSON 不再包含 `apiKey`
- 导入旧配置时如存在 `apiKey`，只写入当前会话状态，不重新持久化到 `localStorage`
- 后端任务、FPA 预览和 Prompt Debug 入口会记录 Key 来源及不可逆指纹，不记录 Key 原文片段

---

## 决策建议

| 场景 | 推荐方案 |
|---|---|
| 当前阶段（内部工具、未上线） | **已实施短期方案**：`apiKey` 从 `localStorage` 移到 `sessionStorage`，并清理历史遗留 Key |
| 上线前 | **推荐方案**：任务接口默认使用服务端 `.env` Key，前端只允许会话级覆盖 |

两阶段可渐进实施：先切 `sessionStorage` 快速止血，再把任务接口改成默认由服务端注入 Key，前端只保留本次会话覆盖能力。
