# Web UI 导航与配置重构方案

日期：2026-06-07

## 背景

当前 Web UI 的生成页同时承载了任务启动、任务状态、执行监控、高级选项、AI 配置、自定义输出模板、下载模板和 FPA 预览入口。页面职责偏重，用户在开始一次生成任务时容易被低频配置项打断。

本方案聚焦信息架构调整，不改变后端接口协议。目标是把高频任务路径、低频全局配置、审阅预览和诊断调试拆到更清晰的位置。

## 目标行为

- `生成`、`预览`、`历史`、`配置` 等主入口移到左侧栏。
- 自定义输出模板、下载模板移到 `配置` 页。
- 高级选项中的 `AI 配置` 移到 `配置` 页。
- 任务设置、FPA 策略等影响本次运行的字段，移动到 `执行监控` 下方。
- FPA 预览页使用同一套左侧栏布局。
- FPA 预览中的 `AI 调试信息` 改为跳转到独立页面查看。

## 目标信息架构

```text
Web UI
|
+-- 生成
|   |
|   +-- 输入与模式
|   |   +-- 上传 Excel / 本地 Excel 路径
|   |   +-- 操作模式
|   |
|   +-- 启动与状态
|   |   +-- 开始生成
|   |   +-- 当前任务状态
|   |
|   +-- 执行监控
|   |   +-- 阶段进展与产物
|   |   +-- 日志
|   |   +-- 完成后操作
|   |
|   +-- 低频任务设置
|       +-- 项目名称
|       +-- 输出目录
|       +-- FPA 方案
|       +-- FPA 执行策略
|       +-- FPA 规则集
|       +-- FPA 确认模式
|
+-- 预览
|   |
|   +-- FPA 预览
|       +-- 输入来源
|       +-- 结果审阅
|       +-- 查看 AI 调试信息 -> /sessions/:sessionId/fpa/debug
|
+-- 历史
|   |
|   +-- 历史任务列表
|   +-- 产物下载 / 打开目录
|
+-- 配置
    |
    +-- AI 配置
    |   +-- API Key
    |   +-- 接口地址
    |   +-- 模型
    |   +-- 最大 Token 数
    |
    +-- 模板配置
        +-- 自定义输出模板
        +-- 下载模板
```

## 左侧栏示意

```text
+----------------------+-----------------------------------------------+
| AI 报账文档生成      |  当前页面内容                                  |
|----------------------|                                               |
| > 生成               |  生成页 / 预览页 / 历史页 / 配置页             |
|   预览               |                                               |
|   历史               |                                               |
|   配置               |                                               |
|----------------------|                                               |
| 后端: 已连接         |                                               |
| 用户 / 退出          |                                               |
+----------------------+-----------------------------------------------+
```

移动端建议使用顶部栏加抽屉，不强行保留常驻左侧栏：

```text
+------------------------------------------------+
| [菜单] AI 报账文档生成                  状态    |
+------------------------------------------------+
|                                                |
| 当前页面内容                                    |
|                                                |
+------------------------------------------------+

点击 [菜单]

+----------------------+
| > 生成               |
|   预览               |
|   历史               |
|   配置               |
+----------------------+
```

移动端导航形态固定为顶部栏 + 抽屉菜单。

## 生成页布局示意

```text
+----------------------+-----------------------------------------------+
| 左侧导航             | 生成                                          |
|                      |-----------------------------------------------|
| > 生成               | 输入与模式                                    |
|   预览               | +-------------------------------------------+ |
|   历史               | | Excel 输入 / 操作模式                       | |
|   配置               | +-------------------------------------------+ |
|                      |                                               |
|                      | 启动与状态                                    |
|                      | +-------------------------------------------+ |
|                      | | [开始生成]    任务状态: 就绪               | |
|                      | +-------------------------------------------+ |
|                      |                                               |
|                      | 执行监控                                      |
|                      | +-------------------------------------------+ |
|                      | | 阶段进展与产物                              | |
|                      | | 日志 / 完成后操作                           | |
|                      | +-------------------------------------------+ |
|                      |                                               |
|                      | 低频任务设置                                  |
|                      | +-------------------------------------------+ |
|                      | | 项目名称 / 输出目录 / FPA 方案 / 策略       | |
|                      | +-------------------------------------------+ |
+----------------------+-----------------------------------------------+
```

说明：

- 生成页设置分为两层：启动前必要设置和低频任务设置。
- 启动前必要设置包含操作模式、输入文件或本地路径等启动任务必须确认的字段。
- 低频任务设置放在 `执行监控` 下方，包含项目名称、输出目录、FPA 方案、FPA 执行策略、FPA 规则集、FPA 确认模式等字段，避免用户刚进入页面就被策略类字段压住。
- 输出目录位于低频任务设置中的项目名称后面。
- `AI 配置` 不出现在生成页，减少普通任务路径上的干扰。
- `模板配置` 不出现在生成页，因为它属于全局低频配置。

## 配置页布局示意

```text
+----------------------+-----------------------------------------------+
| 左侧导航             | 配置                                          |
|                      |-----------------------------------------------|
|   生成               | AI 配置                                      |
|   预览               | +-------------------------------------------+ |
|   历史               | | API Key                                    | |
| > 配置               | | 接口地址                                   | |
|                      | | 模型                                       | |
|                      | | 最大 Token 数                              | |
|                      | +-------------------------------------------+ |
|                      |                                               |
|                      | 模板配置                                      |
|                      | +-------------------------------------------+ |
|                      | | 自定义输出模板                              | |
|                      | | 下载模板                                    | |
|                      | +-------------------------------------------+ |
+----------------------+-----------------------------------------------+
```

说明：

- `配置` 页只放跨任务复用或低频维护的设置。
- AI 配置保留“留空使用系统配置”的说明。
- API Key 输入仍应继续使用现有敏感输入保护逻辑。
- 配置页字段保存后写入配置文件，并同步更新前端 `config` store；除已启动的后台任务外，对后续生成、预览和新打开页面即时生效。
- 正在运行中的任务使用启动时提交的参数快照，不受配置页后续修改影响，避免中途换模型、接口或模板导致结果不可复盘。

## 配置持久化与即时生效

配置页不应只修改前端状态。后端需要提供正式的 Web UI 配置保存能力，保证用户保存后可以跨页面、跨刷新、跨重启复用。

推荐新增面向 Web UI 的配置接口：

```text
GET  /api/web-config
PUT  /api/web-config
```

接口命名固定使用 `/api/web-config`，不复用现有 `/api/config` 的内部结构接口。`/api/config` 可继续服务原有 `_env` / `_system` / `_biz` 配置编辑能力，`/api/web-config` 面向新配置页提供稳定、脱敏、业务化的配置视图。

配置保存权限：

- 本机模式保存全局默认配置，写入 `~/.ai-gen-reimbursement-docs/` 下的配置文件。
- 远程登录用户保存个人覆盖配置，写入该用户自己的配置目录。
- 本机全局配置不会直接覆盖已有个人配置；全局配置只作为未设置个人覆盖项时的默认值来源。
- `/api/web-config` 权限固定为：本机模式可读写全局配置；远程登录用户可读合并视图、写个人覆盖配置；未登录不可读写。
- 远程用户读取配置时看到的是合并后的有效值，并标记来源：个人 / 全局 / 默认。
- 共享系统 API Key 开关只允许本机管理员查看和编辑；远程用户只看到系统是否允许共享凭据，不可修改。

`GET /api/web-config` 返回脱敏后的配置视图：

```json
{
  "ai": {
    "api_key_configured": true,
    "shared_api_key_enabled": false,
    "base_url": "https://api.example.test",
    "model": "deepseek-v4-flash",
    "max_tokens": "384K"
  },
  "templates": {
    "custom_output_template_dir": "C:/templates/out"
  },
  "run_defaults": {
    "fpa_profile": "default",
    "fpa_strategy": "rule-first",
    "fpa_rule_set": "standard",
    "fpa_confirmation_mode": "auto"
  }
}
```

`PUT /api/web-config` 接收同结构或等价的可编辑字段，保存成功后返回最新的脱敏配置视图，前端用返回值同步 `config` store。

已确认决策：

| 决策项 | 结论 |
|---|---|
| 配置中心实施范围 | 按三期推进：第一期基础配置和模板配置；第二期 FPA/业务规则；第三期 Prompt/领域上下文。 |
| 高级配置编辑 | 允许 Web UI 直接编辑完整 YAML/JSON，但保存前必须校验和备份。 |
| API Key 加密密钥 | 第一版优先使用系统凭据库；系统凭据库不可用时退到本机密钥文件。 |
| 共享系统 API Key | 允许管理员通过 `allow_shared_ai_credentials: true` 显式开启，默认关闭。 |
| 远程用户无 API Key | 阻止 AI 任务启动，并提示配置个人 API Key 或联系管理员开启共享凭据。 |
| 模板配置模型 | 使用 `out_templates` 映射，按文档类型分别绑定模板，不做单一模板目录。 |
| 配置备份保留 | 每次保存前自动备份，保留最近 5 个版本。 |
| 配置变更审计 | 记录谁在什么时候改了哪个配置文件，但不记录敏感值。 |
| 保存失败策略 | 所有高级配置采用“校验全通过才保存”的强规则。 |
| AI 调试数据源 | 第一阶段复用现有 AI 日志/交互接口，后续再做结构化 FPA 调试接口。 |
| 预览中心扩展 | 第一期只做 FPA，COSMIC、需求清单、需求说明书先保留导航和架构余量。 |
| 运行中任务配置 | 运行中任务继续使用启动时参数快照，不受新配置影响。 |

实施细节决策：

| 决策项 | 结论 |
|---|---|
| 第一期实施状态 | 现在开始实施第一期，只做 10 个第一期工作包，不碰第二/三期复杂配置。 |
| 第一提交粒度 | 按第一期 10 个工作包分多次 commit，不做一次性大提交。 |
| Windows 凭据方案 | 优先使用 DPAPI；DPAPI 不可用时退到本机密钥文件。 |
| 本机密钥文件位置 | `~/.ai-gen-reimbursement-docs/secrets/master.key`。 |
| 配置审计日志位置 | `~/.ai-gen-reimbursement-docs/audit/config_changes.jsonl`。 |
| 配置备份位置 | `~/.ai-gen-reimbursement-docs/backups/config/`。 |
| 配置备份粒度 | 按文件备份，例如 `system_config.yaml.20260607_153000.bak`。 |
| `/api/web-config` 权限 | 本机模式可读写全局配置；远程登录用户可读合并视图、写个人覆盖配置；未登录不可读写。 |
| 远程用户配置可见性 | 远程用户可看到合并后的有效值，并标记来源：个人 / 全局 / 默认。 |
| 共享凭据开关可见性 | 只本机管理员可见和可编辑；远程用户只看到系统是否允许共享凭据，不可修改。 |
| FPA AI 调试无 session | 显示空态，提示“请先从 FPA 预览或历史任务进入”，不自动跳转。 |
| 移动端导航形态 | 顶部栏 + 抽屉菜单。 |

配置文件映射建议：

| Web 配置区 | 配置文件 | 建议字段 |
|---|---|---|
| AI 配置 | `~/.ai-gen-reimbursement-docs/.env` | `ANTHROPIC_API_KEY_ENC` 或等价密文字段、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL` |
| AI 配置 | `~/.ai-gen-reimbursement-docs/system_config.yaml` | `max_tokens`、`allow_shared_ai_credentials` |
| 模板配置 | `~/.ai-gen-reimbursement-docs/system_config.yaml` | `out_templates` |
| 运行默认值 | `~/.ai-gen-reimbursement-docs/system_config.yaml` | FPA 方案、策略、规则集、确认模式等 Web 默认值 |

敏感字段规则：

- API Key 不得明文保存。后端只能保存加密后的密文，例如 `ANTHROPIC_API_KEY_ENC`；`.env`、YAML、备份文件、导出文件中都不得出现 API Key 原文。
- `GET` 不返回 API Key 原文，只返回 `api_key_configured: true/false`。
- `PUT` 中省略 `api_key` 或传入遮罩值时，保留已有加密 API Key。
- `PUT` 中传入新的 `api_key` 时，后端加密后覆盖密文字段。
- 如需清空 API Key，使用显式字段，例如 `clear_api_key: true`，不要把空字符串解释成删除。
- API Key 不参与普通全局默认继承。远程用户只有在配置了个人 API Key，或管理员显式开启 `allow_shared_ai_credentials: true` 时，才可使用服务端共享 API Key。
- `allow_shared_ai_credentials` 默认值为 `false`，避免远程用户未配置个人 Key 时静默消耗管理员或本机全局 Key。
- 日志、错误信息、AI 调试页、配置预览、配置备份和配置导出都必须脱敏，不得输出 API Key 原文或可还原片段。
- Windows 第一版优先使用 DPAPI；DPAPI 不可用时退到本机密钥文件 `~/.ai-gen-reimbursement-docs/secrets/master.key`。加密密钥不得和配置密文放在同一份可导出的配置包中，并应在部署文档中说明恢复和迁移方式。

配置合并优先级：

```text
普通配置：本次请求显式值 > 用户个人配置 > 全局配置 > 系统默认值
敏感凭据：本次请求显式值 > 用户个人配置 > 共享凭据策略 > 系统默认值
```

普通配置包括 `base_url`、`model`、`max_tokens`、模板映射、运行默认值等。敏感凭据当前主要指 API Key。

远程用户未配置个人 API Key 时：

- `allow_shared_ai_credentials: false`：后端返回未配置凭据错误，提示用户配置个人 API Key，或联系管理员开启共享凭据。
- `allow_shared_ai_credentials: true`：允许使用服务端共享 API Key。

在 `allow_shared_ai_credentials: false` 且远程用户没有个人 API Key 时，后端应阻止 AI 任务启动，不自动降级、不继续运行。

模板配置模型采用 `out_templates` 映射，支持不同文档类型绑定不同模板；不降级为单一 `custom_output_template_dir`。如果前端需要简化显示，可在 UI 层把常用模板映射整理成更易理解的表单。

保存流程：

```text
PUT /api/web-config
  -> 校验 payload
  -> 合并现有配置，保留未提交的敏感值
  -> 加密新的 API Key，仅写入密文
  -> 在 ~/.ai-gen-reimbursement-docs/backups/config/ 生成文件级备份，保留最近 5 个版本
  -> 原子写入 .env / system_config.yaml
  -> 写入 ~/.ai-gen-reimbursement-docs/audit/config_changes.jsonl 审计记录，不记录敏感值
  -> 清理当前进程的配置读取缓存
  -> 返回脱敏后的最新 web-config
  -> 前端同步 config store
```

即时生效边界：

- 新打开页面立即读到新配置。
- 下一次生成立即使用新配置。
- 下一次 FPA 预览立即使用新配置。
- 已经运行中的 session 不重新读取配置，继续使用任务启动时的参数快照。
- 运行中任务始终使用启动时参数快照，不受后续配置修改影响。

API Key 安全边界：

- 系统必须保证管理员无法通过配置文件、读取接口、日志、调试信息、备份或导出文件直接取得 API Key 原文。
- 在后端代调用 AI 服务的架构下，后端进程在调用模型时需要使用可用凭据，因此不能承诺拥有服务器最高权限的管理员绝对无法通过修改代码、读取进程内存或拦截请求取得运行时凭据。
- 如需达到“系统管理员也无法取得用户 API Key”的强隔离目标，应改用浏览器端直连 AI 服务、用户本地代理，或外部 KMS/HSM 托管等方案；该能力属于后续架构升级，不纳入当前默认实现。
- 当前默认实现采用加密落盘、读取脱敏、日志脱敏、备份脱敏、不默认共享全局 Key、显式清空的安全模型。

后端实现落点：

| 文件 | 目的 |
|---|---|
| `web_app/routes/config.py` | 新增或扩展 Web 配置读写路由。 |
| `web_app/services/config_service.py` | 增加 Web 配置视图转换、校验、合并保存、脱敏返回和缓存刷新。 |
| `ai_gen_reimbursement_docs/config_utils.py` | 如存在缓存读取函数，提供统一的缓存清理入口。 |
| `web_app/routes/tasks.py` | 任务启动时按“请求参数优先，配置文件默认值兜底”的规则形成参数快照。 |
| `web_app/services/task_runner.py` | 保持运行中任务只使用启动参数，不动态读取配置。 |

任务启动参数优先级：

```text
前端请求显式值 > 用户个人配置 > 全局配置 > 系统默认值
```

这样配置页可以作为默认值来源，但生成页仍允许用户在本次任务中临时覆盖低频任务设置。

## 配置中心扩展范围

长期目标是让所有用户可维护的配置文件都能在 Web UI 中查看、编辑、校验和保存。配置页应升级为“配置中心”，但不建议把所有 YAML/JSON 一次性做成普通表单；应按风险和编辑体验分层实现。

推荐配置中心结构：

```text
配置中心
|
+-- AI 配置
+-- Web 与运行配置
+-- 模板配置
+-- FPA 策略与规则
+-- Prompt 配置
+-- 领域上下文
+-- 高级配置文件
```

配置文件分层：

| 层级 | 配置文件 / 资源 | Web UI 形态 | 实施建议 |
|---|---|---|---|
| 基础配置 | `.env` | 表单 + 脱敏凭据输入 | 第一阶段实现。 |
| 基础配置 | `system_config.yaml` | 表单、开关、数字输入、下拉框 | 第一阶段实现常用项；低频内部字段可放高级区。 |
| 模板配置 | `data/out_templates/*`、`out_templates` | 文件管理 + 模板映射表 | 第一阶段实现。 |
| 业务规则 | `business_rules.yaml` | 结构化表单 + 高级 YAML 编辑器 | 第二阶段实现，保存前必须校验。 |
| FPA 配置 | `fpa_config.yaml` | 常用项表单 + 高级 YAML 编辑器 | 第二阶段实现，必须复用 FPA 配置校验。 |
| FPA 判定规则 | `fpa_judgement_rules.yaml` | 规则列表编辑器 + 高级 YAML 编辑器 | 第二阶段实现，建议提供预览和校验。 |
| Prompt 配置 | `ai_system_prompts_config.yaml` | 多行文本编辑器 + 场景列表 | 第三阶段实现，保存前做 YAML 和必填字段校验。 |
| 领域上下文 | `domain_context.json` | JSON 表单/编辑器 | 第三阶段实现，保存前做 JSON schema 校验。 |

第一阶段优先实现：

- AI 配置。
- Web 与运行配置中的常用项。
- 模板配置和 `out_templates` 映射。
- 配置文件保存、脱敏、备份、缓存刷新、即时生效。
- 第一期预览只做 FPA；COSMIC、需求清单、需求说明书先保留导航和架构余量。

第二阶段实现：

- FPA 策略与规则。
- `business_rules.yaml`。
- `fpa_config.yaml`。
- `fpa_judgement_rules.yaml`。
- 常用字段表单化，完整文件保留高级 YAML 编辑器。

第三阶段实现：

- Prompt 配置。
- 领域上下文。
- 配置历史版本、差异对比、恢复默认、导入导出。

高级配置文件编辑规则：

- 高级 YAML/JSON 编辑器只面向复杂配置，不替代常用项表单。
- 允许 Web UI 直接编辑完整 YAML/JSON，但保存前必须先做语法校验，再做业务校验。
- 所有高级配置采用“校验全通过才保存”的强规则；校验失败不得写入目标文件。
- 保存成功前必须生成备份版本，保留最近 5 个版本，支持回滚。
- 保存成功后清理配置缓存，保证后续生成和预览即时使用新配置。
- 配置变更审计记录操作者、时间、配置文件、变更类型和校验结果，不记录敏感值。
- 对 FPA 页面和规则中出现的用户可见术语，仍必须遵循 `docs/fpa/result-review-terminology.md`。

## FPA 预览页布局示意

`预览` 第一期只实现 FPA 预览；后续可扩展为预览中心，承载 FPA、COSMIC、需求清单、需求说明书等预览入口。当前阶段不需要一次性实现所有预览类型，但路由和导航命名应避免把 `预览` 固化成只能承载 FPA。

```text
+----------------------+-----------------------------------------------+
| 左侧导航             | FPA 预览                                      |
|                      |-----------------------------------------------|
|   生成               | 输入来源                                      |
| > 预览               | +-------------------------------------------+ |
|   历史               | | 当前文件 / 会话 / 预览参数                  | |
|   配置               | +-------------------------------------------+ |
|                      |                                               |
|                      | 结果审阅                                      |
|                      | +----+------------------+------+------------+ |
|                      | | #  | 新增/修改功能点  | 类型 | 生成方式   | |
|                      | +----+------------------+------+------------+ |
|                      | |    | 计算依据归类                         | |
|                      | |    | 计算依据说明                         | |
|                      | +-------------------------------------------+ |
|                      |                                               |
|                      | [查看 AI 调试信息] -> /sessions/:sessionId/fpa/debug |
+----------------------+-----------------------------------------------+
```

FPA 用户可见术语必须遵循 `docs/fpa/result-review-terminology.md`：

- `新增/修改功能点`
- `类型`
- `生成方式`
- `计算依据归类`
- `计算依据说明`

不得替换为 `功能点类型`、`类型判定依据`、`功能点说明`、`说明详情` 等近义词。

## AI 调试页面方案

建议将 FPA 预览中的 `AI 调试信息` 移到独立页面，而不是继续放在 FPA 预览页折叠区。

推荐路由：

```text
/sessions/:sessionId/fpa/debug
```

该路由更偏工作流语义，明确调试信息属于某一次 session 的 FPA 结果。FPA 预览页跳转时必须带上当前 `sessionId`；如果没有可用 session，应禁用入口并提示先生成或恢复一次可预览的任务。

页面结构：

```text
+----------------------+-----------------------------------------------+
| 左侧导航             | FPA AI 调试信息                               |
|                      |-----------------------------------------------|
|   生成               | [返回 FPA 预览]   Session: :sessionId         |
| > 预览               |                                               |
|   历史               | 调试筛选                                      |
|   配置               | +-------------------------------------------+ |
|                      | | 阶段 / 功能点序号 / 生成方式 / 异常状态     | |
|                      | +-------------------------------------------+ |
|                      |                                               |
|                      | 调试详情                                      |
|                      | +-------------------------------------------+ |
|                      | | Prompt                                    | |
|                      | | 模型响应                                  | |
|                      | | 解析结果                                  | |
|                      | | 错误与告警                                | |
|                      | +-------------------------------------------+ |
+----------------------+-----------------------------------------------+
```

采用独立页面的原因：

- FPA 预览页的核心任务是人工审阅，不应被大段调试数据干扰。
- 调试信息主要服务开发和排障，用户角色与普通审阅不同。
- 独立且带 `sessionId` 的路由方便刷新、复制链接、从历史任务进入、复盘问题和后续扩展筛选。

数据源策略：

- 第一阶段先复用现有 AI 日志/交互接口，例如会话级 AI 对话日志和 prompts/responses 文件清单，让页面先跑通。
- 第二阶段如需筛选到某个 FPA 功能点、某次模型调用、某条解析错误，再新增结构化 FPA 调试接口。
- 新增结构化接口前，不要求后端重写现有日志产物格式。
- 无 `sessionId` 或 session 不可访问时，页面显示空态，提示“请先从 FPA 预览或历史任务进入”，不自动跳转。

## 实施路线

本方案按可独立提交、可独立验收的工作包推进。第一期先完成导航重构、基础配置中心、模板配置、FPA 预览与 AI 调试入口；第二期和第三期只预留结构，不阻塞第一期上线。

### 第一期交付目标

第一期完成后应满足：

- 左侧栏成为 Web UI 主导航。
- 生成页只保留高频启动路径、执行监控和低频任务设置。
- 配置页可以保存基础配置和模板配置，配置写入文件后即时生效。
- API Key 加密落盘，读取、日志、备份、导出均不泄露原文。
- FPA 预览页接入统一布局。
- FPA AI 调试页使用 `/sessions/:sessionId/fpa/debug`，第一阶段复用现有 AI 日志/交互接口。
- 运行中任务继续使用启动快照，不受后续配置修改影响。

### 第一期工作包

| 顺序 | 工作包 | 主要改动 | 验收标准 |
|---:|---|---|---|
| 1 | 应用骨架与左侧栏 | 新增 `AppShell`、`SideNav`，调整 `App.vue` 和路由元信息。 | `生成`、`预览`、`历史`、`配置`、FPA 预览、AI 调试页共享同一导航；移动端可通过菜单打开导航。 |
| 2 | 生成页职责收敛 | 拆分 `ConfigPanel` / `AdvancedOptions`，生成页保留输入、操作模式、启动、状态、执行监控和低频任务设置。 | `AI 配置`、模板上传/下载不再出现在生成页；输出目录位于低频任务设置中项目名称后面。 |
| 3 | 配置中心第一期 UI | 配置页新增 `ConfigCenterNav`、`AIConfigSection`、`WebRuntimeConfigSection`、`TemplateSettingsSection`。 | 配置页可编辑 AI 配置、Web/运行常用项、`out_templates` 模板映射。 |
| 4 | Web 配置接口 | 新增 `GET/PUT /api/web-config`，返回业务化脱敏配置视图。 | 前端不再直接依赖 `_env` / `_system` / `_biz` 结构；保存成功后返回最新脱敏配置。 |
| 5 | API Key 加密存储 | 新增 `secret_service`，Windows 优先 DPAPI，不可用时退到本机密钥文件。 | 配置文件只出现密文字段；读取接口、日志、备份、导出均不出现 API Key 原文。 |
| 6 | 配置备份、回滚与审计 | `config_service` 保存前按文件备份到 `~/.ai-gen-reimbursement-docs/backups/config/`，保留最近 5 个版本；新增配置变更审计。 | 保存前生成备份；可恢复备份；审计记录操作者、时间、文件和结果，不记录敏感值。 |
| 7 | 任务启动配置合并 | `tasks.py` 启动时合并请求显式值、个人配置、全局配置和系统默认值。 | 新任务使用最新配置默认值；运行中任务不受后续配置修改影响。 |
| 8 | 远程用户凭据策略 | 远程用户无个人 API Key 且未开启共享凭据时阻止 AI 任务启动。 | 返回明确错误，提示配置个人 API Key 或联系管理员开启共享凭据。 |
| 9 | FPA 预览和调试页 | FPA 预览接入统一布局；新增或迁移 `FpaAiDebugPage`。 | `查看 AI 调试信息` 携带 `sessionId` 跳转；无 session 时入口禁用并提示。 |
| 10 | 回归与打磨 | 补测试、移动端检查、错误态和空态文案。 | 前后端构建和指定 pytest 通过；人工验收清单通过。 |

### 第一期建议提交顺序

为降低风险，建议按以下提交顺序实现：

```text
1. layout: add app shell and side navigation
2. frontend: split generation and config sections
3. backend: add web-config read model and permissions
4. backend: add encrypted secret storage
5. backend: add config save, backup, audit, cache refresh
6. backend: merge config defaults into task start snapshot
7. frontend: wire config center to web-config API
8. frontend: add FPA AI debug route and session-aware links
9. tests: cover config, secret, audit, task snapshot behavior
10. polish: responsive QA, empty/error states, docs final check
```

### 第二期交付目标

第二期聚焦 FPA 和业务规则配置：

- `business_rules.yaml` 可通过结构化表单和高级 YAML 编辑器维护。
- `fpa_config.yaml` 可编辑常用 FPA 方案、策略、规则集，完整 YAML 可高级编辑。
- `fpa_judgement_rules.yaml` 可通过规则列表编辑器维护。
- 所有高级配置保存前必须通过语法校验和业务校验。
- 校验失败不得写入目标文件。

第二期工作包：

| 顺序 | 工作包 | 主要改动 | 验收标准 |
|---:|---|---|---|
| 1 | 高级配置编辑器基础 | 新增 YAML/JSON 编辑器、校验错误定位、保存前备份。 | 语法错误能定位；保存失败不覆盖原文件。 |
| 2 | FPA 配置校验接入 | 复用或补充 `validate_fpa_config` 等后端校验入口。 | 非法 profile、strategy、rule_set 不能保存。 |
| 3 | FPA 策略表单 | 常用 FPA profile、strategy、rule_set 表单化。 | 用户能编辑常用 FPA 策略，不必直接改完整 YAML。 |
| 4 | 业务规则编辑 | `business_rules.yaml` 支持表单和高级 YAML 双入口。 | 规则保存后下一次生成/预览即时生效。 |
| 5 | FPA 判定规则编辑 | `fpa_judgement_rules.yaml` 支持规则列表编辑。 | 保存前校验规则结构，失败不写入。 |

### 第三期交付目标

第三期聚焦 Prompt、领域上下文和配置运维能力：

- `ai_system_prompts_config.yaml` 支持按场景编辑 prompt。
- `domain_context.json` 支持 JSON 表单/编辑器。
- 配置历史版本可查看差异。
- 支持恢复默认、导入导出。
- 如 FPA AI 调试需要更细粒度筛选，再新增结构化 FPA 调试接口。

第三期工作包：

| 顺序 | 工作包 | 主要改动 | 验收标准 |
|---:|---|---|---|
| 1 | Prompt 配置 UI | 场景列表、多行编辑、YAML 校验。 | 可编辑 prompt，保存后后续 AI 调用生效。 |
| 2 | 领域上下文 UI | `domain_context.json` 表单/JSON 编辑器。 | JSON schema 校验通过才保存。 |
| 3 | 配置历史与差异 | 查看最近备份，展示 diff，支持恢复。 | 可选择备份恢复，恢复后清缓存。 |
| 4 | 导入导出 | 导出配置包时排除 API Key 原文和加密密钥。 | 导出包不含敏感原文；导入前校验。 |
| 5 | 结构化 FPA 调试接口 | 按 session、功能点、模型调用筛选调试数据。 | AI 调试页可定位到具体功能点和调用记录。 |

### 依赖关系

```text
AppShell / SideNav
  -> 生成页拆分
  -> 配置中心 UI

secret_service
  -> web-config 保存
  -> 远程用户凭据策略
  -> 任务启动配置合并

config backup / audit
  -> 基础配置保存
  -> 高级 YAML/JSON 编辑

session-aware FPA preview
  -> /sessions/:sessionId/fpa/debug
  -> 后续结构化 FPA 调试接口
```

### 第一期开工前检查

- 确认现有 `/api/config` 继续保留，新增 `/api/web-config` 不破坏旧功能。
- 确认 DPAPI 在 Windows 打包环境中的可用性；不可用时启用本机密钥文件兜底。
- 确认本机模式和远程用户模式的配置目录分别可读写。
- 确认现有模板上传/下载接口可以迁移到配置页复用。
- 确认现有 AI 日志/交互接口能支撑第一阶段 FPA AI 调试页。

## 组件拆分建议

| 当前位置 | 建议目标 | 说明 |
|---|---|---|
| `ConfigPanel.vue` 中的模板上传/下载 | `Config.vue` | 迁移为配置页的模板配置区。 |
| `AdvancedOptions.vue` 中的 AI 配置 | `Config.vue` | 拆成 `AIConfigSection.vue`。 |
| `AdvancedOptions.vue` 中的 FPA 策略 | `Home.vue` 执行监控下方 | 拆成 `FpaRunSettingsSection.vue`，作为低频任务设置。 |
| `ConfigPanel.vue` 中的 FPA 预览入口 | 左侧 `预览` 或生成页辅助入口 | 不再藏在高级选项附近。 |
| `PromptDebug.vue` | `FpaAiDebugPage.vue` 或复用后改名 | 作为独立调试页面承载 AI 调试信息。 |

建议新增或调整组件：

```text
web_app/src/components/layout/AppShell.vue
web_app/src/components/layout/SideNav.vue
web_app/src/components/config/AIConfigSection.vue
web_app/src/components/config/TemplateSettingsSection.vue
web_app/src/components/config/ConfigCenterNav.vue
web_app/src/components/config/WebRuntimeConfigSection.vue
web_app/src/components/config/FpaConfigSection.vue
web_app/src/components/config/PromptConfigSection.vue
web_app/src/components/config/DomainContextSection.vue
web_app/src/components/config/AdvancedConfigFileEditor.vue
web_app/src/components/run/FpaRunSettingsSection.vue
web_app/src/views/FpaAiDebugPage.vue
```

是否新增目录可按实际代码量决定；若项目暂不希望扩大目录结构，也可以先放在 `web_app/src/components/` 下。

## 拟修改文件范围

| 文件 | 修改目的 |
|---|---|
| `web_app/src/App.vue` | 接入左侧栏应用骨架。 |
| `web_app/src/router/index.ts` | 调整主导航路由，新增 `/sessions/:sessionId/fpa/debug`。 |
| `web_app/src/views/Home.vue` | 收敛为生成页，保留启动任务和执行监控。 |
| `web_app/src/views/Config.vue` | 承接 AI 配置、模板上传、模板下载。 |
| `web_app/src/views/FpaPreviewPage.vue` | 接入统一布局，增加 AI 调试页面跳转。 |
| `web_app/src/views/PromptDebug.vue` | 复用或迁移为 FPA AI 调试页面。 |
| `web_app/src/components/ConfigPanel.vue` | 移除全局配置职责，只保留生成相关输入。 |
| `web_app/src/components/AdvancedOptions.vue` | 拆分为 AI 配置与低频 FPA 运行设置。 |
| `web_app/src/components/TemplateUpload.vue` | 迁移挂载位置，不改变模板上传能力。 |
| `web_app/src/components/TemplateDownload.vue` | 迁移挂载位置，不改变模板下载能力。 |
| `web_app/src/assets/main.css` | 补齐左侧栏、移动端抽屉等布局样式。 |
| `web_app/routes/config.py` | 增加 Web 配置读写接口。 |
| `web_app/services/config_service.py` | 增加配置视图、脱敏、合并保存、缓存刷新、最近 5 个备份和回滚。 |
| `web_app/services/config_audit_service.py` | 新增配置变更审计能力，记录操作者、时间、文件和结果，不记录敏感值。 |
| `web_app/services/secret_service.py` | 新增 API Key 加密存储能力，Windows 优先 DPAPI，不可用时退到本机密钥文件。 |
| `ai_gen_reimbursement_docs/config_utils.py` | 补充配置校验和缓存清理入口，确保保存后即时生效。 |
| `web_app/routes/tasks.py` | 任务启动时合并请求参数与配置默认值，形成运行快照。 |
| `tests/test_web_config_service.py` | 覆盖配置文件写入、脱敏和敏感值保留。 |
| `tests/test_web_config_audit.py` | 覆盖配置变更审计不记录敏感值。 |
| `tests/test_web_secret_service.py` | 覆盖 API Key 加密、读取脱敏、DPAPI 不可用时兜底本机密钥文件。 |
| `tests/test_web_tasks.py` | 覆盖任务启动参数快照和配置默认值兜底。 |
| `tests/test_web_config_routes.py` | 覆盖 `/api/web-config` 读取、保存、权限、来源标记和脱敏响应。 |
| `tests/test_web_fpa_debug.py` | 覆盖 `/sessions/:sessionId/fpa/debug` 所需会话访问和日志数据读取。 |

## 验证方式

实施后建议验证：

```powershell
cd web_app
npm run build
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_config_service.py tests/test_web_config_routes.py tests/test_web_config_audit.py tests/test_web_secret_service.py tests/test_web_tasks.py tests/test_web_system.py tests/test_web_fpa_debug.py
```

人工检查：

- 左侧栏在 `生成`、`预览`、`历史`、`配置`、`FPA 预览`、`FPA AI 调试信息` 页面保持一致。
- 自定义输出模板、下载模板只出现在 `配置` 页。
- AI 配置只出现在 `配置` 页。
- 配置页保存后写入配置文件，刷新页面或重启后仍能读取。
- API Key 不明文落盘；配置文件、备份、导出、日志、错误信息和调试页面都不出现 API Key 原文。
- API Key 在 Windows 第一版优先使用 DPAPI 加密；DPAPI 不可用时退到本机密钥文件 `~/.ai-gen-reimbursement-docs/secrets/master.key`。
- API Key 不在读取接口中返回原文；省略 API Key 保存时保留旧的加密密文。
- `/api/web-config` 本机模式可读写全局配置；远程登录用户可读合并视图、写个人覆盖配置；未登录不可读写。
- 远程用户配置视图标记来源：个人 / 全局 / 默认。
- 共享系统 API Key 开关只本机管理员可见和可编辑，远程用户不可修改。
- 远程用户未配置个人 API Key 且 `allow_shared_ai_credentials: false` 时，不继承全局 API Key，并给出明确提示。
- 管理员显式开启 `allow_shared_ai_credentials: true` 后，远程用户才可使用服务端共享 API Key。
- 配置中心第一阶段可编辑基础配置和模板配置。
- 高级 YAML/JSON 配置保存前必须校验，保存失败不得覆盖原文件。
- 每次保存配置文件前按文件备份到 `~/.ai-gen-reimbursement-docs/backups/config/`，保留最近 5 个版本，并支持恢复上一版本。
- 配置变更审计写入 `~/.ai-gen-reimbursement-docs/audit/config_changes.jsonl`，记录谁在什么时候改了哪个配置文件，但不记录敏感值。
- FPA 策略和低频任务设置位于 `执行监控` 下方。
- FPA 预览页术语符合 `docs/fpa/result-review-terminology.md`。
- 移动端没有横向滚动，使用顶部栏 + 抽屉菜单。
- 第一期开工前检查项全部确认。
- 第一期 10 个工作包均可独立验收和提交。

状态验收矩阵：

| 状态 | 预期行为 |
|---|---|
| 后端离线 | 左侧栏和页面仍可访问；生成页禁用开始生成；配置页可编辑前端配置但提示后端未连接。 |
| 未选择输入文件 | 生成页明确提示选择上传文件或填写本地 Excel 路径；开始生成保持禁用或点击后给出明确错误。 |
| 任务运行中 | 左侧栏保持可导航；生成页展示执行监控；低频任务设置可查看但不应影响已启动任务；配置页保存的新配置只影响后续任务。 |
| 任务完成 | 执行监控展示完成状态和产物操作；FPA 预览和 AI 调试入口可携带当前 `sessionId` 跳转。 |
| 从历史记录恢复 session | 进入 FPA 预览或 AI 调试页时使用历史 session 上下文；`/sessions/:sessionId/fpa/debug` 刷新后仍能定位该 session。 |
| 保存配置后刷新页面 | 前端重新读取配置文件视图，AI 配置、模板配置和运行默认值保持一致。 |
| 保存配置后启动新任务 | 新任务使用最新配置作为默认值，同时保留生成页本次请求显式覆盖能力。 |
| 远程用户无个人 API Key | 默认不使用全局 API Key；仅当 `allow_shared_ai_credentials: true` 时使用共享凭据。 |
| 保存 API Key | 只写入加密密文；读取配置、备份、导出和日志均不可见原文。 |
| 高级配置校验失败 | 显示具体错误，不写入目标配置文件，保留原配置。 |
| 配置误保存 | 可从最近 5 个备份版本恢复配置，并在恢复后清理配置缓存。 |
| 配置变更审计 | 审计记录包含操作者、时间、配置文件和结果，不包含 API Key、密文原文或其他敏感值。 |
| FPA AI 调试无 session | 显示空态，提示“请先从 FPA 预览或历史任务进入”，不自动跳转。 |

## 风险与边界

- 本方案主要调整信息架构，并新增 Web 配置持久化接口；不改变核心 pipeline 执行接口。
- `config` store 中的字段仍可复用，但保存成功后应以后端返回的脱敏配置视图为准。
- 拆分 `AdvancedOptions.vue` 时要确保 `startTask()` 提交的字段不变，并且能用配置文件默认值兜底。
- API Key 输入应继续沿用现有敏感输入保护逻辑。
- 配置文件写入必须保护敏感字段：遮罩值不能覆盖真实 API Key 密文，空字符串不能误删旧 Key。
- API Key 不得明文保存；配置文件、备份、导出、日志、错误信息和调试页面都不得泄露原文。
- API Key 加密第一版在 Windows 优先使用 DPAPI；不可用时退到本机密钥文件。
- 在后端代调用 AI 服务的架构下，不能承诺拥有服务器最高权限的管理员绝对无法取得运行时凭据；默认实现只承诺配置文件、接口、日志、备份和导出中拿不到 API Key 原文。
- 远程用户个人配置不能被本机全局配置覆盖；全局配置变化只影响未设置个人覆盖项的普通配置。
- API Key 不能按普通配置继承全局默认值；共享系统 API Key 必须由 `allow_shared_ai_credentials` 显式开启。
- 保存配置后要清理后端配置读取缓存，否则 `system_config.yaml` 中的部分字段可能无法即时生效。
- 正在运行中的任务不得被新配置影响，避免不可复盘。
- 所有配置文件都进入 Web UI 是长期目标，第一阶段不应强行表单化复杂 FPA、Prompt 和领域上下文配置。
- 复杂配置必须保留高级 YAML/JSON 编辑入口，但保存前要经过语法校验和业务校验。
- 配置备份和回滚是高级配置编辑的前置能力，不应等线上出错后再补；备份保留最近 5 个版本。
- 配置变更审计必须脱敏，不记录 API Key、密文原文或其他敏感值。
- 如果后续要把调试信息做成可筛选、可复制、可导出页面，需要再确认后端是否已经提供足够结构化的数据。
