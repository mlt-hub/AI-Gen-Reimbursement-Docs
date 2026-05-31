# localStorage 存储 API Key 安全策略

## 现状

前端通过 Pinia store（[`config.ts`](../../web_app/src/stores/config.ts#L10-L28)）将用户配置持久化到 `localStorage`，包括：

| Key | 内容 | 代码位置 |
|---|---|---|
| `apiKey` | API Key 明文 | config.ts:70 |
| `model` | 模型名称 | config.ts:71 |
| `baseUrl` | API 端点地址 | config.ts:72 |
| `maxTokens` | 最大 Token 数 | config.ts:73 |
| `projectName` / `fpaProfile` / … | 其他业务配置 | config.ts:74-78 |

持久化机制：`watch` 监听 ref 变化 → 自动 `localStorage.setItem()` 写入（config.ts:82-91）。页面加载时 `loadStr()` 从 `localStorage` 读取恢复。

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

同一 `127.0.0.1:9090` 下的所有页面、所有 Tab 共享同一份 `localStorage`。如果将来运行更多 Web 服务在同一端口，它们也能读取这些数据。

---

## 改进方案

### 推荐方案：服务端统一管理 Key + 前端可选覆盖

**核心思路**：Key 由服务端 `~/.ai-gen-reimbursement-docs/.env` 管理，前端仅提供一个"临时覆盖"输入框。

```
┌─────────────────────────────────────────────────────┐
│ 服务端 (已有)                                        │
│ ~/.ai-gen-reimbursement-docs/.env                    │
│   ANTHROPIC_API_KEY=sk-xxx    ← 唯一持久化位置       │
│                                                      │
│ /api/llm  → 转发请求，注入 Key                        │
└─────────────────────────────────────────────────────┘
         ▲
         │  LLM 请求走服务端代理
         │
┌─────────────────────────────────────────────────────┐
│ 前端                                                │
│ - 用户可选输入覆盖 Key → 仅存 sessionStorage          │
│ - 不持久化 API Key                                  │
│ - 读取配置从服务端 /api/config 获取                    │
└─────────────────────────────────────────────────────┘
```

**优点**：
- Key 从不出现在浏览器持久存储中
- XSS 即使发生，也拿不到 Key（仅在 session 内存中）
- 关闭浏览器 Key 自动清除
- 向后兼容：现有的 `~/.ai-gen-reimbursement-docs/.env` 配置机制无需改变

**改动点**：
1. 新增 `POST /api/llm` 代理端点，服务端读取 Key 后转发 LLM 请求
2. 前端 `config.ts` 移除 `localStorage` 中 `apiKey` 的持久化，改为 `sessionStorage`（仅内存）
3. 前端 LLM 调用改为经 `/api/llm`，不再直接从浏览器发请求

### 降级方案：sessionStorage 替代 localStorage

如果暂时不加服务端代理，至少将 API Key 从 `localStorage` 改为 `sessionStorage`：

| 对比 | localStorage | sessionStorage |
|---|---|---|
| 生命周期 | 永久 | 关闭标签页即清除 |
| XSS 可读 | 是 | 是 |
| 浏览器同步 | 可能泄露 | 不同步 |
| 持久化风险 | 高 | 低（不会遗留） |

改动最小：将 `config.ts` 中 `loadStr`/`saveStr`/`loadBool`/`saveBool` 的 `localStorage` 替换为 `sessionStorage`。

**局限性**：XSS 仍可读取，只是减少了持久化泄露面。

---

## 决策建议

| 场景 | 推荐方案 |
|---|---|
| 当前阶段（内部工具、未上线） | **降级方案**：切到 `sessionStorage`，改动一行，立即减少泄露面 |
| 上线前 | **推荐方案**：服务端代理 LLM 调用，前端不碰 Key |

两阶段可渐进实施：先切 `sessionStorage` 快速止血，再加服务端代理彻底解决。
