# FPA Prompt 配置化方案

## 完成记录

- 状态：已完成
- 关键实现提交：`f154da1 feat: configure FPA judgement rules source`
- 完成确认时间：2026-06-03

完成范围：

1. FPA Prompt、profile、rule_set 和核心口径已统一收敛到 `fpa_config.yaml`。
2. 配置缺失或非法时直接报错，不再静默降级到代码内置完整 Prompt。
3. FPA 预览和正式生成共用同一套 Prompt 来源规则。
4. 预览 AI 调试信息已展示安全 Prompt 来源标签，不暴露完整本机路径。
5. AI cache key 已包含实际渲染后的 system prompt、user prompt 和 rule_set 配置内容。
6. `judgement_rules_source` 与独立 `fpa_judgement_rules.yaml` 配置已补充到当前方案中。

验证结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_pipeline.py tests/test_web_tasks.py
```

结果：`168 passed`

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
    core_rules: custom_rules
    system_prompt: custom_rules
    user_prompt: custom_rules

  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    core_rules: strict_fpa
    system_prompt: strict_fpa
    user_prompt: strict_fpa

core_rules:
  custom_rules: |-
    FPA 核心口径：
    ...
  strict_fpa: |-
    严格 FPA 核心口径：
    ...

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
    row_planning_rules:
      ui_row:
        enabled: true
        scope: l3
        merge: single_row
        name_suffix: "界面开发"
        type: EI
        reason: "三级模块兜底合并界面能力。"
        empty_process_text: "完成三级模块页面交互能力"
        explanation_template: "{name}，具体为以下：\n{items}"
      process_rows:
        enabled: true
        one_row_per_process: true
        default_name_suffix: "逻辑处理开发"
        type_suffixes:
          EQ: "查询处理开发"
          EO: "导出处理开发"
          EI: "导入处理开发"
        explanation_template: "{name}，具体为以下：\n1、{description}"
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
profiles：每个 profile 绑定默认 strategy、rule_set、core_rules、system_prompt、user_prompt。
core_rules：可复用的核心口径文本。
system_prompt_sets：可复用的系统提示词文本。
user_prompt_sets：可复用的用户提示词模板。
rule_sets：可新增任意规则集，可用 extends 继承其他规则集。
row_planning_rules：配置 custom_rules 纯规则兜底时的三级模块界面行和功能过程行规划。
```

`profiles.<profile>.core_rules` 是引用名，指向 `core_rules.<name>`。该文本会注入用户提示词模板中的 `${core_rules}`。

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

核心口径由当前 profile 的 `core_rules` 引用顶层 `core_rules.<name>` 提供。

页面展示来源时使用安全标签，不展示完整本机路径：

```text
核心口径：用户配置（配置目录/fpa_config.yaml: core_rules.custom_rules）
系统提示词：用户配置（配置目录/fpa_config.yaml: system_prompt_sets.custom_rules）
用户提示词：用户配置（配置目录/fpa_config.yaml: user_prompt_sets.custom_rules）
```

## 模板变量

代码只负责构造结构化变量，不在生产路径维护完整中文 Prompt 兜底。

| 变量 | 作用 |
|---|---|
| `core_rules` | 当前 FPA profile 的 `core_rules.<name>` 核心口径文本 |
| `judgement_rules` | 按 `judgement_rules_source` 读取的计算依据归类判定原则，默认来自 `fpa_judgement_rules.yaml` |
| `payload_json` | 当前三级模块、功能过程和领域上下文的结构化 JSON |

用户提示词必须保留全部三个占位符：

```text
${core_rules}
${judgement_rules}
${payload_json}
```

除上述三个变量外，不支持其他占位符。`domain_context` 会放在 `${payload_json}` 的 JSON 内容中，不是独立模板变量。未知占位符、非法占位符或缺少任一核心占位符都会在读取 `fpa_config.yaml` 时直接报错。

### 计算依据归类判定原则来源

`fpa_config.yaml` 通过 `judgement_rules_source` 控制判定原则来源：

```yaml
judgement_rules_source: config
```

可选值：

```text
config：默认值，从配置目录/fpa_judgement_rules.yaml 读取 judgement_rules。
template：从 FPA 输出模板 Excel 附录 Sheet 读取，保留旧模板来源行为。
```

`config` 来源下，`fpa_judgement_rules.yaml` 必须存在，且 `judgement_rules` 必须是非空字符串列表。缺失、格式错误或空列表会直接报错，避免 AI 返回 `classification_basis_index` 后无法映射“计算依据归类”。

## 默认规则配置

`custom_rules_default` 和 `strict_fpa_default` 不再是空对象。可表达为规则数据的默认类型判断、关键词、外部数据组识别、覆盖补齐开关和 custom_rules 行规划策略已经写入 `rule_sets.<default>`。

`custom_rules_default.row_planning_rules` 控制纯规则兜底行：

```text
ui_row：是否生成三级模块级界面行，以及行名后缀、类型、类型理由、空过程文案和说明模板。
process_rows：是否按功能过程生成行，以及默认后缀、FPA 类型到后缀的映射和说明模板。
```

`strict_fpa_default` 不配置 `row_planning_rules`。strict_fpa 使用标准 FPA 算法识别数据功能和事务功能，不进入“界面开发 / 逻辑处理开发”这种开发工作项式行规划。

保留在代码中的内容是执行机制：

```text
rules_first / ai_first 的执行流程。
AI 失败、返回非法 JSON、返回非法类型时如何 fallback。
行覆盖检查和补齐算法。
Excel 结构字段构造，包括序号、子系统、资产标识、变更状态、调整值、要素数量和审核字段。
Prompt 渲染、JSON 解析和输出合法性校验。
规则集继承、合并、循环检测和配置结构校验。
strict_fpa 的标准数据功能识别流程。
postprocess 审核规则、warning 来源追踪和审计字段结构。
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
未找到 FPA 核心口径配置：配置目录/fpa_config.yaml 中的 core_rules.custom_rules
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
