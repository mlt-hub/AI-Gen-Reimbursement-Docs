# FPA Prompt 配置化方案

## 背景

FPA AI 生成的 Prompt、profile 默认值和 rule_set 规则统一收敛到一份 FPA 专用配置：

```text
配置目录/fpa_config.yaml
```

模板示例：

```text
config/fpa_config.yaml.example
```

旧的三份拆分配置不再作为生产入口：

```text
fpa_system_prompts_config.yaml
fpa_user_prompts_config.yaml
fpa_rule_sets_config.yaml
```

系统尚未上线，不保留旧配置兼容路径。缺少 `fpa_config.yaml` 时直接报错，避免用户以为改了配置但实际仍在使用旧 Prompt 或旧规则。

## 配置结构

`fpa_config.yaml` 顶层结构：

```yaml
profile: custom_rules

profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    system_prompt: custom_rules
    user_prompt: custom_rules

  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    system_prompt: strict_fpa
    user_prompt: strict_fpa

system_prompt_sets:
  custom_rules: |-
    ...
  strict_fpa: |-
    ...

user_prompt_sets:
  custom_rules: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}
  strict_fpa: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}

rule_sets:
  custom_rules_default:
    keyword_rules:
      merge: append
      items:
        - type: EQ
          keywords: ["查询", "查看", "详情", "列表检索", "检索"]
          reason: "关键词命中查询/查看能力，按 EQ 兜底。"
  strict_fpa_default:
    keyword_rules:
      merge: append
      items:
        - type: EI
          keywords: ["新增", "修改", "删除", "保存", "提交", "导入"]
          reason: "事务功能进入或改变系统边界内数据，按 EI。"
```

含义：

```text
profile：默认 FPA 方案，只允许 custom_rules 或 strict_fpa。
profiles：每个 profile 绑定默认 strategy、rule_set、system_prompt、user_prompt。
system_prompt_sets：可复用的系统提示词文本。
user_prompt_sets：可复用的用户提示词模板。
rule_sets：可新增任意规则集，可用 extends 继承其他规则集。
```

`profiles.<profile>.system_prompt` 是引用名，指向 `system_prompt_sets.<name>`。

`profiles.<profile>.user_prompt` 是引用名，指向 `user_prompt_sets.<name>`。

system prompt 和 user prompt 允许使用不同名称，例如：

```yaml
profiles:
  custom_rules:
    system_prompt: default_fpa
    user_prompt: custom_rules_v2
```

`rule_sets` 不再配置 `version`。用户不需要手动维护版本号，生成结果、预览结果、审核副本和 AI cache key 都不再暴露 `rule_set_version`。

## Prompt 来源

系统提示词由当前 profile 的 `system_prompt` 指向 `system_prompt_sets.<name>`。

用户提示词模板由当前 profile 的 `user_prompt` 指向 `user_prompt_sets.<name>`。

页面展示来源时使用安全标签，不展示完整本机路径：

```text
系统提示词：用户配置（配置目录/fpa_config.yaml: system_prompt_sets.custom_rules）
用户提示词：用户配置（配置目录/fpa_config.yaml: user_prompt_sets.custom_rules）
```

## 模板变量

代码只负责构造结构化变量，不在生产路径维护完整中文 Prompt 兜底。

| 变量 | 作用 |
|---|---|
| `core_rules` | 当前 FPA profile 的核心规则文本 |
| `judgement_rules` | 从 FPA 模板中读取的计算依据归类判定原则 |
| `payload_json` | 当前三级模块、功能过程和领域上下文的结构化 JSON |

用户提示词必须保留全部三个占位符：

```text
${core_rules}
${judgement_rules}
${payload_json}
```

除上述三个变量外，不支持其他占位符。`domain_context` 会放在 `${payload_json}` 的 JSON 内容中，不是独立模板变量。未知占位符、非法占位符或缺少任一核心占位符都会在读取 `fpa_config.yaml` 时直接报错。

## 默认规则配置

`custom_rules_default` 和 `strict_fpa_default` 不再是空对象。可表达为规则数据的默认类型判断、关键词、外部数据组识别和覆盖补齐开关已经写入 `rule_sets.<default>`。

保留在代码中的内容是执行机制：

```text
rules_first / ai_first 的执行流程。
AI 失败、返回非法 JSON、返回非法类型时如何 fallback。
行覆盖检查和补齐算法。
Prompt 渲染、JSON 解析和输出合法性校验。
规则集继承、合并、循环检测和配置结构校验。
```

边界原则：

```text
规则数据放进 YAML。
执行算法留在代码。
```

## 缺失配置处理

配置缺失时报错，不静默降级到代码内置 Prompt。

示例错误：

```text
未找到 FPA 配置文件：配置目录/fpa_config.yaml
未找到 FPA 系统提示词配置：配置目录/fpa_config.yaml 中的 system_prompt_sets.custom_rules
未找到 FPA 用户提示词配置：配置目录/fpa_config.yaml 中的 user_prompt_sets.custom_rules
FPA 配置无效：配置目录/fpa_config.yaml 中的 user_prompt_sets.strict_fpa 包含未知占位符: ${unknown_placeholder}
FPA 配置无效：配置目录/fpa_config.yaml 中的 user_prompt_sets.strict_fpa 必须包含占位符: ${judgement_rules}
```

这样可以保证用户看到的 Prompt 来源与实际调用一致。

## 影响范围

同步影响：

```text
FPA 预览。
正式 FPA AI 生成。
AI cache key。
FPA 审核副本。
Web 用户配置初始化。
CLI --init-config / migrate_config。
```

预览和正式生成必须使用同一套 Prompt 来源，否则用户在预览中验证的 Prompt 与正式生成实际使用的 Prompt 可能不同。

## 保留的小型 Helper

可以保留的代码 helper：

```text
构造模块输入 JSON。
构造判定原则编号列表。
构造模板变量字典。
校验必需变量是否存在。
渲染用户配置模板。
```

不应保留在生产兜底路径中的内容：

```text
完整中文 Prompt 文案。
当配置缺失时继续调用 AI 的内置默认 Prompt。
与 fpa_config.yaml 中 Prompt 语义重复的长字符串模板。
```

## 验收标准

```text
FPA AI 调用前必须能明确系统提示词和用户提示词来源。
FPA 预览 AI 调试信息显示 Prompt 来源。
页面不展示完整本机路径、API Key、请求头或环境变量。
配置缺失时给出明确错误，不继续使用代码内置完整 Prompt。
正式 FPA 生成与 FPA 预览使用同一套 Prompt 来源规则。
FPA AI 缓存 key 包含实际渲染后的 system prompt 和 user prompt，避免 Prompt 配置修改后仍命中旧缓存。
FPA AI 缓存 key 包含 rule_set 的实际配置内容，避免规则集内容修改后仍命中旧缓存。
```
