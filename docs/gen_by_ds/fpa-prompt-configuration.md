# FPA Prompt 配置化方案

## 背景

FPA AI 生成当前存在两类 Prompt 来源：

- 用户配置目录中的 YAML 配置。
- Python 代码中的内置默认 Prompt 或 Prompt 拼接逻辑。

这会带来一个实际问题：用户修改配置后，如果某个配置没有命中，系统可能继续使用代码内置 Prompt，导致用户误以为“还是旧提示词”。

本方案目标是让 FPA Prompt 来源可观测、可审计，并逐步移除生产路径中的完整代码内置 Prompt 兜底。

---

## 目标原则

### 配置管话术，代码管数据

Prompt 的中文话术、输出要求、任务说明和格式说明应由配置文件负责。

代码只负责构造模板变量，例如：

| 变量 | 作用 |
|---|---|
| `core_rules` | 当前 FPA profile 的核心规则文本 |
| `judgement_rules` | 从 FPA 模板中读取的计算依据归类判定原则 |
| `payload_json` | 当前三级模块、功能过程和领域上下文的结构化 JSON |
| `domain_context` | 子系统、资产标识、功能用户等上下文 |

也就是说，代码可以保留 `_prompt_payload()`、`_numbered_judgement_rules()` 这类小型 helper，用于把 Excel、模块树和配置整理成稳定数据；但不应在生产路径中继续维护完整 Prompt 文案兜底。

---

## 推荐 Prompt 来源

### 系统提示词

来源：

```text
配置目录/ai_system_prompts_config.yaml
```

配置 key：

```text
ai_prompts.fpa_eval.system
```

页面展示：

```text
系统提示词：用户配置（配置目录/ai_system_prompts_config.yaml）
```

### 用户提示词

来源：

```text
配置目录/fpa_user_prompts_config.yaml
```

配置 key 应按 profile 和场景区分，例如：

```text
custom_rules.fpa_eval
strict_fpa.fpa_eval
```

页面展示：

```text
用户提示词：用户配置（配置目录/fpa_user_prompts_config.yaml）
```

---

## 来源展示规则

FPA 预览页 `AI 调试信息` 应展示 Prompt 来源，但不展示完整本机路径。

| 来源状态 | 页面展示 |
|---|---|
| 用户配置命中 | `用户配置（配置目录/文件名）` |
| 未配置 | `未配置` |
| 系统默认 | 暂不推荐继续作为生产路径展示 |

不推荐展示：

```text
<完整本机路径>/ai_system_prompts_config.yaml
```

推荐展示：

```text
配置目录/ai_system_prompts_config.yaml
配置目录/fpa_user_prompts_config.yaml
```

如需帮助用户定位配置目录，页面或文档可提示：

```text
配置目录为 ard 启动日志中显示的“配置文件目录”。
```

---

## 缺失配置处理

推荐行为：配置缺失时报错，不再静默降级到代码内置 Prompt。

示例错误：

```text
未找到 FPA 系统提示词配置：配置目录/ai_system_prompts_config.yaml 中的 ai_prompts.fpa_eval.system
未找到 FPA 用户提示词配置：配置目录/fpa_user_prompts_config.yaml 中的 custom_rules.fpa_eval
```

这样可以保证用户看到的 Prompt 来源与实际调用一致，避免旧 Prompt 隐性生效。

---

## 影响范围建议

推荐同步影响：

- FPA 预览。
- 正式 FPA AI 生成。

原因是预览和正式生成应使用同一套 Prompt 来源，否则用户在预览中验证的 Prompt 与正式生成实际使用的 Prompt 可能不同。

---

## 保留的小型 Helper

删除代码内置 Prompt 兜底，并不等于删除所有 Prompt 相关代码。

可以保留的 helper：

- 构造模块输入 JSON。
- 构造判定原则编号列表。
- 构造模板变量字典。
- 校验必需变量是否存在。
- 渲染用户配置模板。

不应保留在生产兜底路径中的内容：

- 完整中文 Prompt 文案。
- 当配置缺失时继续调用 AI 的内置默认 Prompt。
- 与配置文件中 Prompt 语义重复的长字符串模板。

---

## 待确认决策

以下决策在实施前需要用户逐项确认：

| 决策 | 推荐值 | 说明 |
|---|---|---|
| 删除 FPA 代码内置 Prompt 兜底 | 删除 | 配置缺失时不再使用硬编码 Prompt |
| 配置缺失处理 | 报错 | 不静默降级 |
| 来源展示文案 | `用户配置（配置目录/文件名）` / `未配置` | 不展示完整本机路径 |
| 影响范围 | 同步影响预览和正式生成 | 保证预览与正式生成一致 |
| 代码保留范围 | 只保留小型 helper | 代码管数据，配置管话术 |

---

## 验收标准

- FPA AI 调用前必须能明确系统提示词和用户提示词来源。
- FPA 预览 `AI 调试信息` 显示 Prompt 来源。
- 页面不展示完整本机路径、API Key、请求头或环境变量。
- 配置缺失时给出明确错误，不继续使用代码内置完整 Prompt。
- 正式 FPA 生成与 FPA 预览使用同一套 Prompt 来源规则。
