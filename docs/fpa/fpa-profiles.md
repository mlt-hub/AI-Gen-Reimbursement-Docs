# FPA Profile 方案说明

日期：2026-06-04

## 可选 Profile

FPA 生成由三层配置决定：

```text
profile  = 业务口径名称
kind     = 代码行为类型
strategy = AI 与规则的执行优先级
rule_set = 具体规则集
```

初始化配置提供四个 profile：

```text
strict_fpa     严格 FPA 口径，kind: strict_fpa，默认 ai_first + strict_fpa_rs
unified_ui     统一界面口径，kind: unified_ui，默认 rules_first + unified_ui_rs
multi_uis      多界面口径，kind: multi_uis，默认 rules_first + multi_uis_rs
ui_api_mapping 界面接口映射口径，kind: ui_api_mapping，默认 rules_first + ui_api_mapping_rs
```

也就是说，当前输出结果口径有 4 套 profile，底层代码行为类型也有 4 类；其中 `multi_uis` 是独立 kind，但内部复用统一界面的兜底生成和审阅能力：

```text
strict_fpa      -> kind: strict_fpa
unified_ui      -> kind: unified_ui
multi_uis       -> kind: multi_uis
ui_api_mapping  -> kind: ui_api_mapping
```

`multi_uis` 使用独立 `kind: multi_uis` 和 `multi_uis_contract` 暴露审计身份；非界面业务动作仍沿用统一界面口径，避免为多界面 profile 复制整套 Python 流程。

用户配置可以只保留实际需要的 profile，也可以新增自定义 profile。自定义 profile 只要绑定支持的 `kind`，并引用存在的 `rule_set/core_rules/system_prompt/user_prompt` 即可；如果 user prompt 引用了 `${calculation_explanation_rules}`，还必须显式绑定 `profiles.<profile>.calculation_explanation_rules` 到顶层 `calculation_explanation_rules` 中存在的 key。

## 如何选择

`strict_fpa` 适合标准 FPA 复核：按数据功能和事务功能拆分，不生成“界面开发”“接口开发”“逻辑处理开发”等开发工作项表达。

`unified_ui` 适合报账模板友好口径：同一三级模块默认合并一条界面开发行；添加、编辑、查询、删除、状态更新、数据表新增修改等非界面能力按“逻辑接口开发 / ILF”补充；导入按“导入处理开发 / EQ”补充；导出、下载、报表输出和生成文件按“导出处理开发 / EO”补充；有明确外部边界证据时按“外部接口联调调用 / EIF”补充。

`multi_uis` 适合确有多个独立界面时使用：可按独立页面、独立业务对象、独立业务流程或独立用户端拆分多条界面开发行，拆分理由进入 check/review 元数据。

`ui_api_mapping` 适合需要展示“功能过程 -> 界面开发 + 接口开发”映射时使用：每个功能过程默认生成一条界面开发 EI 和一条接口开发 ILF；输入中明确出现的接口、服务、调用、请求、对接、同步、外部系统、第三方或 API 单独生成明确接口/后端调用 ILF。

## Profile 组合与 Harness 分层

FPA 的实际运行组合不只由 profile 决定，而是由以下维度共同决定：

```text
profile × kind × strategy × rule_set × prompt × model
```

因此，4 种 strategy 和不同 rule_set 可以形成很多混搭组合。Harness 仍然有用，但不能把所有组合都当成同等级质量保证。当前应按组合分层管理：

| 等级 | 含义 | Harness 要求 |
|---|---|---|
| `certified` | 推荐基线组合，承诺业务口径稳定。 | golden fixtures、行为断言、稳定性抽样、质量门。 |
| `supported` | 允许使用，规则和配置路径清楚。 | 配置校验、规则/AI smoke、输出 schema 和基本审计。 |
| `experimental` | 技术上可运行，但不承诺业务口径稳定。 | 防崩溃、清晰 warning、可追踪 audit。 |
| `invalid` | 语义明显不兼容或配置引用错误。 | 直接报错，不回退默认组合。 |

当前推荐分层：

| 组合 | 当前等级 | 说明 |
|---|---|---|
| `strict_fpa + ai_first + strict_fpa_rs` | `certified` | 已有 golden、validator、确认流、稳定性报告和真实模型 recommended 连续复测。 |
| `unified_ui + rules_first + unified_ui_rs` | `supported` | 有配置、规则兜底、分层 harness、只读 profile review 和真实模型归零记录。 |
| `multi_uis + rules_first + multi_uis_rs` | `supported` | 独立 kind、独立 contract、多界面同名行和拆分理由已有分层 harness，并有真实模型归零记录。 |
| `ui_api_mapping + rules_first + ui_api_mapping_rs` | `supported` | 规则兜底、固定 EI/ILF harness、只读 mapping review 和真实模型归零记录较清楚。 |
| 任意 profile + 自定义 rule_set | 视继承关系而定 | 继承推荐 rule_set 时复用 base harness，再补扩展断言。 |
| 任意 profile + 明显不匹配 rule_set | `experimental / invalid` | 只保证配置错误可见或输出可审计，不承诺业务正确。 |

规则集扩展不需要重写整套 harness。推荐采用：

```text
base harness + extension assertions
```

例如 `client_a_rules extends strict_fpa_rs` 时，继续复用 `strict_fpa` 的基础断言，再为客户 A 的外部数据组、特殊业务对象或合并边界补增量 fixture。

稳定性报告和 audit trace 必须记录组合指纹：

```text
profile
kind
strategy
rule_set
prompt ids
model
fixture suite
run_id
```

这样才能在 warning 上升时定位是哪个组合退化，而不是把单个混搭组合的问题误判为整个 `gen-fpa` 退化。

## 配置文件

配置文件位置：

```text
~/.ai-gen-reimbursement-docs/fpa_config.yaml
```

示例模板：

```text
config/fpa_config.yaml.example
```

核心结构：

```yaml
default-profile: strict_fpa

profiles:
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    adjustment_value_method: standard_fpa
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
    calculation_explanation_rules: strict_fpa_ce
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    adjustment_value_method: standard_fpa
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
    calculation_explanation_rules: unified_ui_ce
  multi_uis:
    kind: multi_uis
    strategy: rules_first
    rule_set: multi_uis_rs
    adjustment_value_method: standard_fpa
    core_rules: multi_uis_cr
    system_prompt: multi_uis_sp
    user_prompt: multi_uis_up
    calculation_explanation_rules: multi_uis_ce

calculation_explanation_rules:
  strict_fpa_ce: |-
    计算依据说明生成规则...
  unified_ui_ce: |-
    统一界面口径计算依据说明生成规则...
```

`unified_ui` 绑定的 `unified_ui_ce` 不是 `strict_fpa_ce` 的同文复用。它用于约束 `计算依据说明` 按统一界面建设内容叙述：界面行合并同一三级模块内的列表、条件查询组件、按钮、弹窗、状态组件和关联管理界面；逻辑接口/表能力行描述添加、编辑、查询、删除、状态更新或数据结构调整归属；导入、导出和外部接口联调调用行只写输入中有证据的系统建设内容。`multi_uis_ce` 和 `ui_api_mapping_ce` 当前可与 `unified_ui_ce` 内容保持一致，但保留独立 key，避免后续差异化时影响 `unified_ui`。

命名约定：

```text
rule_set: <profile>_rs
adjustment_value_method: standard_fpa | legacy_workload
core_rules: <profile>_cr
system_prompt: <profile>_sp
user_prompt: <profile>_up
calculation_explanation_rules: <profile>_ce
```

`default-profile` 必须是非空字符串并存在于 `profiles`。profile entry 必须显式配置 `kind`，且只允许 `strict_fpa`、`unified_ui`、`ui_api_mapping`。

## Domain Context

FPA AI prompt 会把部分上下文放入 `payload_json.domain_context`。其中 `project_description` 由功能清单录入模板中的 `工单标题` 和 `工单内容` 自动拼成；不读取 `建设目标`、`建设必要性` 等 AI 生成字段，避免把生成结果再次作为 FPA 输入。

`fpa_domain_context.json` 只维护可复用的领域边界信息，例如 `system_boundary`、`internal_data_groups`、`external_data_groups`、`external_services`。不要在该配置文件中维护 `project_description`；即使出现同名字段，FPA prompt 也会忽略配置值，优先使用 Excel 工单标题和工单内容。

## Rule Set 规则段

`keyword_rules` 和 `type_mapping_rules` 都是按关键词辅助判断 FPA 类型，但用途不同。

`keyword_rules` 是动作关键词规则，可用于 `EI/EQ/EO/ILF/EIF`。在 `unified_ui` 中，查询、查看、检索等可直接映射为 `ILF` 以表达逻辑接口/表能力，导入映射为 `EQ`，导出、报表、下载等映射为 `EO`；在 `strict_fpa` 中，它仍主要用于标准事务功能 `EI/EQ/EO`。

`type_mapping_rules` 是更通用的直接类型映射，支持 `EI/EQ/EO/ILF/EIF`。它适合项目级特例、业务对象或数据组边界，例如“本地报表快照”虽然包含“报表”，但如果本系统持久化维护它，可以直接映射为 `ILF`。

在 `strict_fpa` 类型推断中，`type_mapping_rules` 会先于普通事务关键词判断生效，用来覆盖少量明确项目口径；普通动作词仍优先放在 `keyword_rules` 中维护。

## Strategy

```text
rules_first  规则优先，AI 只做补充或复核
ai_first     AI 优先，规则补齐 AI 未覆盖的行
rules_only   仅规则，不调用 AI
ai_only      仅 AI，不用规则兜底补行
```

`ai_only` 的“仅 AI”只约束行生成和失败处理：系统不使用规则生成行，不追加 `rules_fallback` 补齐行，AI 调用失败、解析失败或被 AI 调用限制跳过时直接报错。

即使选择 `ai_only`，profile 仍必须绑定有效 `rule_set`。该规则集仍用于配置校验、AI 结果后处理、非法类型兜底、明显类型冲突 warning、审核追踪和 AI cache key。合法 AI type 与规则建议冲突时，`ai_only` 保留 AI type，只记录 warning；AI 返回非法 type 时仍会用 profile/rule_set 推断出的类型兜底。

`ui_api_mapping` 和 `multi_uis` 支持 `ai_only`；此时不会强制规则兜底生成默认行。

## Web 与 CLI

Web 高级选项和 FPA 预览页会从 `/api/fpa/options` 读取实际配置的 profile。接口返回 profile 的 `name/label/kind/strategy/rule_set/core_rules/system_prompt/user_prompt/editable` 以及可选 key 列表；只返回配置 key，不返回 core rules 或 prompt 正文。

CLI 示例：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile unified_ui --fpa-strategy rules_only
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile ui_api_mapping --fpa-rule-set ui_api_mapping_rs
```

CLI / Web / API 显式传入 profile、strategy 或 rule_set 时优先使用显式值；显式传入未知值会报错，不回退默认值。

## 审核副本

正式生成仍会额外输出：

```text
FPA工作量评估-check.xlsx
```

check/review 元数据记录 profile、kind、strategy、rule_set、规则命中来源、源功能过程、拆分理由和 warning，不新增正式 Excel 列。
