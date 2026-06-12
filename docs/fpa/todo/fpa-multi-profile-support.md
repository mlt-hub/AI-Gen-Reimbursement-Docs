# FPA 多 profile 支持收口记录

日期：2026-06-12

状态：已完成主线实施、二次收口、`multi_uis` 独立 kind 和 profile 级 golden fixture contract 覆盖。本文保留为需求与验收依据；当前用户文档入口见 [`../fpa-profiles.md`](../fpa-profiles.md)。

## 实施收口记录

提交记录：

```text
5f5affb Support configurable FPA profiles
```

已完成：

- FPA profile 已从固定白名单改为配置驱动，支持 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 和自定义 profile name + `kind`。
- `custom_rules` 已由 `unified_ui` 完全替代；旧 `default-profile: custom_rules` 和 `profiles.custom_rules` 会给出专门迁移错误。
- `config/fpa_config.yaml.example` 已补齐 4 个 profile 的 `profiles`、`rule_sets`、`core_rules`、`system_prompt_sets`、`user_prompt_sets` 示例，并使用 `_rs/_cr/_sp/_up` 命名。
- `/api/fpa/options` 已按实际配置顺序返回 profile，包含 `kind/strategy/rule_set`，并隐藏内部 prompt 配置 key。
- `ui_api_mapping` 已实现默认界面开发 EI、默认接口开发 ILF、明确接口/后端调用 ILF；明确接口同名按三级模块合并来源，默认行同名保留并提示。
- `multi_uis` 已记录拆分理由到 check/review 元数据；同名多界面开发行保留并提示。
- `multi_uis` 已提升为独立 `kind: multi_uis`，仍复用统一界面的非界面业务动作规则和审阅能力。
- `unified_ui`、`multi_uis`、`ui_api_mapping` 已补充 profile 级 golden fixture contract suite，并要求 profile quality issue 归零。
- `strict_fpa`、`unified_ui` / `multi_uis` 的规则兜底行已补齐同名同类型来源合并、同名不同类型保留并提示。
- `rule_set extends` 循环错误已提示循环路径。
- 常规配置说明、Golden Case 说明、验收记录和计算依据说明文档已更新到新 profile/config 键；旧键只保留在迁移说明和错误提示测试中。

后续可选增强：

- 如真实项目中 `multi_uis` 需要更强的多界面规则兜底拆分算法，可在现有 `kind: multi_uis` 下扩展专属规则，不复制整套 FPA 流程。
- 可继续扩充 `ui_api_mapping` 的明确接口/后端交互抽取词库，但必须保持“只来自输入材料显式信息”的边界。
- 可用更多真实项目样本复核 4 个 profile 的 prompt 稳定性，尤其是 `multi_uis.split_reason` 和 `ui_api_mapping` 固定 EI/ILF 类型规则，并将新边界沉淀为 profile golden fixtures。

## 目标

将 FPA profile 从固定少量内置口径扩展为配置驱动的多 profile 机制。`default-profile` 指定默认方案，CLI / Web / API 显式传入 profile 时仍优先使用显式值。

首批需要支持 4 个 profile：

```text
strict_fpa
unified_ui
multi_uis
ui_api_mapping
```

## profile 语义

### strict_fpa

严格 FPA 口径。按数据功能和事务功能拆分，不按页面、按钮、弹窗、接口或数据库表字段拆分。允许通过 rule_set 做项目级规则扩展；扩展为空时仍走内置 strict_fpa 默认规则和 AI 约束，不等于 AI-only。

### unified_ui

统一界面口径。同一三级模块默认合并为 1 条界面类功能点，覆盖列表、查询条件、按钮、弹窗、状态切换等同页交互能力；非界面业务动作再按规则或 AI 结果补充。`unified_ui` 完全替代原 `custom_rules`，不保留 `custom_rules` 兼容别名。

### multi_uis

多界面口径。允许同一三级模块按独立页面、独立业务对象、独立业务流程或独立用户端拆分为多条界面类功能点；每条多界面拆分行必须给出可审阅的拆分理由，拆分理由记录在 check 中，不强制进入用户可见 `split_reason` 字段。界面开发行统一为 EI，并继续补充非界面业务动作行；非界面业务动作行沿用 `unified_ui` 的类型规则。

### ui_api_mapping

功能过程界面接口映射口径。每个功能过程默认生成 1 条界面开发行和 1 条接口开发行；同时保留明确输入的接口或后端调用行，这类行不再额外生成界面开发。明确接口/后端调用行必须来源于输入材料中明确出现的接口、服务、调用或后端动作，不得凭空补齐。

拆分规则分为两层：

1. 功能过程层：每个功能过程生成 1 条界面开发行和 1 条接口开发行，形成“功能过程 -> 界面开发 + 接口开发”的映射。
2. 明确接口/后端层：输入材料中额外明确出现的接口、服务调用、外部系统调用、数据同步、提交审批、导入导出或后端处理动作，按一项一行补充功能点；这类行只表示接口/后端调用，不再配套生成界面开发行。

示例输入：

```text
三级模块：合同管理
功能过程：
1. 查询合同列表。
2. 新增合同。
3. 提交合同审批，调用 OA 审批接口。
4. 同步客户信息，调用 CRM 客户查询服务。
```

`ui_api_mapping` 输出形态：

```text
【业务端】销售管理-合同中心-合同管理-查询合同列表-界面开发：EI
【业务端】销售管理-合同中心-合同管理-查询合同列表-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-新增合同-界面开发：EI
【业务端】销售管理-合同中心-合同管理-新增合同-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发：EI
【业务端】销售管理-合同中心-合同管理-提交合同审批-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-OA 审批接口：ILF
【业务端】销售管理-合同中心-合同管理-CRM 客户查询服务：ILF
```

边界约束：

- 功能过程层的接口开发行来自功能过程本身，不要求输入材料显式写出接口名称。
- 明确接口/后端层不凭空补接口。输入没有明确接口、服务、调用、后端处理或同步等信息时，不额外生成明确接口/后端调用行。
- 明确接口/后端层只由显式接口/调用类词触发，例如“接口、服务、调用、请求、对接、同步、外部系统、第三方、API”；普通动作词“保存、提交、删除、审批、新增、修改”不触发额外明确接口/后端调用行。
- 同一功能过程中出现多个明确接口、服务、调用、同步或外部系统交互时，一项一行生成多条明确接口/后端调用行，不合并为复合行。
- 明确接口/后端调用行不配套生成界面开发行，避免同一个后端调用重复产生界面工作量。
- 功能过程默认接口开发行与明确接口/后端调用行不去重。默认接口开发表示本系统功能过程接口开发；明确接口/后端调用表示输入材料明确写出的接口、服务或外部/后端调用。
- 明确接口/后端调用行跨三级模块不去重；同一三级模块内同名明确接口/后端调用行合并为 1 条，来源功能过程合并记录到 check/review 元数据。
- 功能过程默认界面开发行和默认接口开发行不合并，严格保持“每个功能过程 = 1 条界面开发 + 1 条接口开发”；同一三级模块内功能过程同名导致默认行同名时，在 check/review 元数据中提示。
- 明确接口/后端调用行尽量保留原文接口/服务名称主体，不主动追加“调用”后缀，也不主动删除原文已有的“调用/请求/对接/同步”等动词，并加完整模块路径前缀。
- 接口/后端行必须保留可追溯来源，能说明来自哪个功能过程、接口、服务、调用或后端动作。
- 功能过程层界面开发行统一为 EI，功能过程层接口开发行统一为 ILF，明确接口/后端调用行统一为 ILF。

### unified_ui 与 ui_api_mapping 的区别

共同点：两者都不按查询条件、按钮、弹窗或字段拆分界面行。

差异在界面行和补充行粒度：

- `unified_ui` 是“一界面 + 业务动作补充”。它关注三级模块整体有哪些业务处理能力，界面合并后，非界面业务动作可以再按规则或 AI 结果补充，例如逻辑接口、导入处理、导出处理、外部接口联调调用等。
- `ui_api_mapping` 是“一功能过程一界面开发 + 一功能过程一接口开发 + 明确接口/后端调用补充”。它按功能过程建立界面开发和接口开发映射；额外明确接口/后端调用行必须来自输入材料中明确出现的接口、服务、调用、同步、审批、导入导出或后端动作，并且不再配套生成界面开发。

对比示例：

```text
功能过程：
1. 查询合同列表。
2. 新增合同。
3. 提交合同审批，调用 OA 审批接口。
```

`unified_ui` 输出形态：

```text
合同管理-界面开发
查询合同-逻辑接口开发
新增合同-逻辑接口开发
提交合同审批-逻辑接口开发
```

`ui_api_mapping` 输出形态：

```text
【业务端】销售管理-合同中心-合同管理-查询合同列表-界面开发：EI
【业务端】销售管理-合同中心-合同管理-查询合同列表-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-新增合同-界面开发：EI
【业务端】销售管理-合同中心-合同管理-新增合同-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发：EI
【业务端】销售管理-合同中心-合同管理-提交合同审批-接口开发：ILF
【业务端】销售管理-合同中心-合同管理-OA 审批接口：ILF
```

一句话区分：`unified_ui` 是“一个三级模块页面 + 业务处理行”；`ui_api_mapping` 是“一个功能过程对应 1 个界面开发和 1 个接口开发，明确接口/后端调用行单独列出且不生成界面开发”。

## 命名规则

所有 profile、所有最终结果行名称都必须使用完整模块路径前缀：

```text
【客户端类型】一级模块-二级模块-三级模块-功能点名称
```

该规则覆盖：

- `strict_fpa` 的事务功能行、ILF/EIF 数据功能行。
- `unified_ui` 的界面开发行和逻辑接口、导入处理、导出处理、外部接口联调调用等非界面业务动作行。
- `multi_uis` 的多条界面开发行和非界面业务动作行。
- `ui_api_mapping` 的功能过程界面开发行、功能过程接口开发行、明确接口/后端调用行。

## 来源追溯元数据

所有 profile 的结果行都必须记录来源信息到现有 check/review 元数据中，不新增正式 Excel 列。

记录规则：

- `strict_fpa` 的 EI/EQ/EO 事务功能行记录来源功能过程；ILF/EIF 数据功能行记录数据组识别来源，例如来自哪个功能过程、模块描述或外部系统描述。
- `strict_fpa` 同一三级模块内同名同类型结果行合并为 1 条，来源信息合并记录到 check/review 元数据；跨三级模块不合并。
- `strict_fpa` 同名但类型不同的结果行不自动改类型、不合并，保留冲突行并在 check/review 元数据中提示类型冲突。
- `unified_ui` 和 `multi_uis` 的非界面业务动作行记录来源功能过程。
- `unified_ui` 和 `multi_uis` 的非界面业务动作行在同一三级模块内同名时合并为 1 条，来源功能过程合并记录到 check/review 元数据；跨三级模块不合并。
- `multi_uis` 的多界面拆分理由记录在 check/review 元数据中，不新增正式结果列。
- `multi_uis` 的多界面开发行同名时不合并，在 check/review 元数据中提示同名多界面开发行。
- `ui_api_mapping` 的功能过程默认界面开发行、功能过程默认接口开发行记录来源功能过程。
- `ui_api_mapping` 的明确接口/后端调用行记录来源功能过程；同一三级模块内同名明确接口/后端调用行合并时，合并记录多个来源功能过程。
- `ui_api_mapping` 的功能过程默认行不合并；同一三级模块内功能过程同名导致默认行同名时，在 check/review 元数据中提示输入存在同名功能过程或结果存在同名默认行。
- `ui_api_mapping` 显式后端交互词没有更具体接口名时，保留原文动作短语作为行名主体，例如“同步客户信息”“对接统一认证平台”。

## 配置目标

`fpa_config.yaml` 示例结构：

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
    adjustment_value_method: legacy_workload
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
    calculation_explanation_rules: unified_ui_ce
  multi_uis:
    kind: multi_uis
    strategy: rules_first
    rule_set: multi_uis_rs
    adjustment_value_method: legacy_workload
    core_rules: multi_uis_cr
    system_prompt: multi_uis_sp
    user_prompt: multi_uis_up
    calculation_explanation_rules: multi_uis_ce
  ui_api_mapping:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: ui_api_mapping_rs
    adjustment_value_method: legacy_workload
    core_rules: ui_api_mapping_cr
    system_prompt: ui_api_mapping_sp
    user_prompt: ui_api_mapping_up
    calculation_explanation_rules: ui_api_mapping_workload_eval_ce

calculation_explanation_rules:
  strict_fpa_ce: |-
    计算依据说明生成规则...
  unified_ui_ce: |-
    统一界面口径计算依据说明生成规则...
  multi_uis_ce: |-
    统一界面口径计算依据说明生成规则...
  ui_api_mapping_ce: |-
    统一界面口径计算依据说明生成规则...
  ui_api_mapping_workload_eval_ce: |-
    ui_api_mapping 计算依据说明生成规则...
```

命名约定：

```text
rule_set: <profile>_rs
adjustment_value_method: standard_fpa | legacy_workload
core_rules: <profile>_cr
system_prompt: <profile>_sp
user_prompt: <profile>_up
calculation_explanation_rules: <profile>_ce
```

rule_set 校验规则：

- `rule_sets` 顶层必须存在且必须是对象。
- profile 引用的 `rule_set` 必须存在，不存在时报错，不使用空规则集兜底。
- `extends` 指向不存在的 rule_set 时报错。
- rule_set 循环继承时报错，并提示循环路径。
- rule_set 继承不设硬编码深度，只要不存在循环即可。
- merge 模式只允许 `append` 和 `replace`。
- rule_set 列表字段允许为空列表，表示没有额外规则。
- `coverage_rules` 缺省时默认 `require_process_coverage: true`、`require_data_function: true`。

旧配置键迁移：

```text
custom_rules_default -> unified_ui_rs
core_rules.custom_rules -> core_rules.unified_ui_cr
system_prompt_sets.custom_rules -> system_prompt_sets.unified_ui_sp
user_prompt_sets.custom_rules -> user_prompt_sets.unified_ui_up

strict_fpa_default -> strict_fpa_rs
core_rules.strict_fpa -> core_rules.strict_fpa_cr
system_prompt_sets.strict_fpa -> system_prompt_sets.strict_fpa_sp
user_prompt_sets.strict_fpa -> user_prompt_sets.strict_fpa_up
```

`custom_rules` 的规则、core_rules、system_prompt、user_prompt 内容迁移到 `unified_ui_rs/_cr/_sp/_up` 后删除旧键；不是直接丢弃原内容。`strict_fpa` 现有配置内容也迁移到 `strict_fpa_rs/_cr/_sp/_up`，保持行为不回退。

## Strategy 行为

所有 profile 的 strategy 继续限制在 `rules_first`、`ai_first`、`rules_only`、`ai_only` 四个枚举值。

strategy 行为规则：

- `ui_api_mapping` 允许 `ai_only`；在 `ai_only` 下不生成“每功能过程两行”的规则兜底，只做 AI 结果解析和校验。
- `multi_uis` 允许 `ai_only`；在 `ai_only` 下不强制多界面拆分规则兜底，只做 AI 结果解析和校验。
- `strict_fpa` 在 `rules_only` 下完全跳过 AI，使用规则生成。
- `rules_first` 下规则优先，AI 作为补充或复核，不覆盖规则结果。
- `ai_first` 下允许规则补齐 AI 未生成的行，用于覆盖率或数据功能补齐。

## 实施切片

1. 放宽 profile 名称校验

配置校验先检查旧 `custom_rules` 专门错误，再检查普通未知 profile/kind，以便旧配置优先得到迁移提示。

`default-profile` 必须是非空字符串并存在于 `profiles` 中；缺失或为空时报错，不自动默认 `strict_fpa`。`profiles` 中的 profile 名称不再受固定白名单限制，但每个 profile entry 必须引用存在的 `rule_set`、`core_rules`、`system_prompt`、`user_prompt`。

用户配置不要求包含完整 4 个 profile，只要 `default-profile` 指向的 profile 有效即可；Web options 返回实际配置的 profile。初始化模板 `config/fpa_config.yaml.example` 必须包含完整 4 个 profile。

每个 profile entry 必须显式配置 `kind`。缺失 `kind` 时报错；配置未知 `kind` 时报错并提示支持的 kind。首批支持的 kind 固定为：

```text
strict_fpa
unified_ui
multi_uis
ui_api_mapping
```

`multi_uis` 使用独立 `kind: multi_uis`，但继续复用统一界面非界面业务动作规则和审阅能力。

自定义 profile 可以复用任意已支持 kind，包括 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping`；kind 与 profile 名不一致是正常配置能力，不需要额外 check/log 提示。

多个 profile 允许共用同一个 `rule_set`、`core_rules`、`system_prompt` 或 `user_prompt` 配置键。profile entry 不允许额外未知字段，未知字段直接报错，保持配置干净。

rule_set entry 允许额外未知字段，只有已识别字段生效，方便未来扩展。`core_rules`、`system_prompt`、`user_prompt` 内容必须非空，不回退内置内容。所有 user_prompt 必须包含 `${core_rules}`、`${judgement_rules}`、`${payload_json}`，缺失或出现未知占位符时报错。strategy 仍限制在 `rules_first`、`ai_first`、`rules_only`、`ai_only` 四个枚举值。

如果配置中出现旧 `custom_rules`，不自动迁移、不保留别名，并使用专门错误提示：

```text
custom_rules 已替换为 unified_ui，请更新 fpa_config.yaml
```

如果 `profiles.custom_rules` 仍存在，使用专门错误提示：

```text
profiles.custom_rules 已废弃，请迁移到 profiles.unified_ui
```

2. 统一 profile 解析入口

CLI / Web / API 需要共享同一套 `load_fpa_profile` 和 profile entry 校验逻辑，避免 Web options 接口与生成流程读取不一致。

3. 增加 4 个 profile 配置样例

更新 `config/fpa_config.yaml.example`，补齐 4 个 profile 的 `profiles`、`core_rules`、`system_prompt_sets`、`user_prompt_sets`、`rule_sets` 示例。

4. 明确执行类复用策略

采用“配置驱动 + 少量行为 kind”机制。profile 名称由配置决定，`kind` 决定兜底拆分、类型推断和后处理行为。

```text
strict_fpa -> kind: strict_fpa
unified_ui -> kind: unified_ui，使用统一界面口径行为
multi_uis -> kind: multi_uis，复用统一界面非界面业务动作规则，并暴露独立 contract
ui_api_mapping -> kind: ui_api_mapping，提供“每个功能过程 = 1 个界面开发 + 1 个接口开发”的特殊兜底逻辑
```

5. 更新 Web profile 选项

`/api/fpa/options` 返回所有配置 profile。未知 label 时使用 profile 名称兜底，避免新增 profile 无法显示。

`/api/fpa/options` 必须返回每个 profile 的 `kind`，方便审阅和调试；Web 运行参数联动已需要返回 `core_rules`、`system_prompt`、`user_prompt` 绑定 key 和可选 key 列表，但只返回配置 key，不返回规则正文或 prompt 正文。

Web options 的 profile 顺序按配置文件 `profiles` 顺序返回，不按固定列表重排。四个内置 profile 使用固定中文显示名；其他自定义 profile 不新增 `label` 配置字段，显示名回退为 profile 名。

Web/API 输出和错误规则：

- `/api/fpa/options` 返回 profile 的 `rule_set`、`strategy`、`kind`。
- `/api/fpa/options` 返回支持的 strategy 枚举和 kind 枚举。
- `/api/fpa/options` 返回 `core_rules`、`system_prompt`、`user_prompt` 配置 key；不得返回对应正文。
- 配置无效时，Web options 返回 400 和配置错误详情，不返回空 options。
- API 显式传入未知 profile、未知 strategy 或未知 rule_set 时均报错，不回退 default-profile 或 profile 默认值。

首批 Web 显示名固定为：

```text
strict_fpa：严格 FPA 口径
unified_ui：统一界面口径
multi_uis：多界面口径
ui_api_mapping：界面接口映射口径
```

## 已决策事项

- `custom_rules` 由 `unified_ui` 完全替代，不保留兼容别名，不自动迁移旧配置。
- `default-profile` 默认值为 `strict_fpa`。
- 配置校验优先检查旧 `custom_rules` 专门错误，再检查普通未知 profile/kind。
- `default-profile` 必须是非空字符串并存在于 `profiles` 中，缺失或为空不自动默认 `strict_fpa`。
- 用户配置可以只保留部分 profile，只要 `default-profile` 有效；初始化配置保留完整 4 个 profile，用户可直接切换默认 profile。
- 允许新增自定义 profile 名称，只要 `kind` 是已支持 kind，且 `rule_set/core_rules/system_prompt/user_prompt` 引用有效；`default-profile` 可以指向有效自定义 profile。
- 自定义 profile 可以复用 `strict_fpa`、`unified_ui`、`ui_api_mapping` 任一已支持 kind；kind 与 profile 名不一致不提示。
- 多个 profile 允许共用同一个 `rule_set`、`core_rules`、`system_prompt` 或 `user_prompt`。
- profile entry 不允许额外未知字段，未知字段报错；rule_set entry 允许额外未知字段，只有已识别字段生效。
- `core_rules`、`system_prompt`、`user_prompt` 内容必须非空，不回退内置内容。
- user_prompt 必须包含 `${core_rules}`、`${judgement_rules}`、`${payload_json}`，缺失或出现未知占位符时报错。
- strategy 限制在 `rules_first`、`ai_first`、`rules_only`、`ai_only` 四个枚举值。
- rule_set 校验：`rule_sets` 顶层必填；profile 引用的 rule_set 必须存在；`extends` 不存在或循环继承时报错；继承深度不限；merge 只允许 `append/replace`；列表字段允许为空；`coverage_rules` 缺省时默认打开 process coverage 和 data function coverage。
- strategy 行为：`ui_api_mapping` 和 `multi_uis` 允许 `ai_only`，且 `ai_only` 下不强制规则兜底；`strict_fpa` 的 `rules_only` 完全跳过 AI；`rules_first` 规则优先；`ai_first` 允许规则补齐。
- 默认 strategy：`strict_fpa` 使用 `ai_first`，`unified_ui`、`multi_uis`、`ui_api_mapping` 使用 `rules_first`。
- 配置键命名采用 `<profile>_rs`、`<profile>_cr`、`<profile>_sp`、`<profile>_up`。
- 旧 `custom_rules` 配置内容迁移到 `unified_ui_rs/_cr/_sp/_up` 后删除旧键；旧 `strict_fpa_default` 和同名 prompt/core_rules 键迁移到 `strict_fpa_rs/_cr/_sp/_up`。
- `strict_fpa` 允许 rule_set 扩展；扩展为空时仍走内置 strict_fpa 默认规则和 AI 约束，不等于 AI-only。
- `strict_fpa` 同一三级模块内同名同类型结果行合并，来源合并记录到 check/review；跨三级模块不合并。同名但类型不同的结果行不自动改类型、不合并，并提示类型冲突。
- 每个 profile entry 必须显式配置 `kind`；未知 kind 直接报错。首批支持 kind：`strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping`。
- `/api/fpa/options` 返回每个 profile 的 `kind`、`strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt` 绑定 key；不得返回对应正文。
- `/api/fpa/options` 按配置文件 `profiles` 顺序返回实际配置的 profile；四个内置 profile 使用固定中文显示名，自定义 profile 显示名回退为 profile 名，不新增 `label` 配置字段。
- `/api/fpa/options` 返回 `rule_set`、`strategy`、`kind`、支持的 strategy 枚举和 kind 枚举；配置无效时返回 400 和错误详情。
- API 显式传入未知 profile、strategy 或 rule_set 时直接报错，不回退默认值。
- 自定义 profile 必须遵守完整模块路径命名和 check/review 来源记录规则，具体行为由 `kind` 决定。
- `default-profile: custom_rules` 时报专门错误：`custom_rules 已替换为 unified_ui，请更新 fpa_config.yaml`。
- `profiles.custom_rules` 出现时报专门错误：`profiles.custom_rules 已废弃，请迁移到 profiles.unified_ui`。
- `ui_api_mapping` 的明确接口/后端调用行只由显式接口/调用类词触发，例如“接口、服务、调用、请求、对接、同步、外部系统、第三方、API”；普通保存、提交、删除、审批、新增、修改等动作词不触发额外行。
- `ui_api_mapping` 中同一功能过程出现多个明确接口、服务、调用、同步或外部系统交互时，一项一行生成多条明确接口/后端调用行。
- `ui_api_mapping` 类型规则：界面开发行统一 EI，接口开发行统一 ILF，明确接口/后端调用行统一 ILF。
- `multi_uis` 保持四类拆分理由：独立页面、独立业务对象、独立业务流程、独立用户端；拆分理由记录在 check 中，不强制进入用户可见 `split_reason` 字段。
- `multi_uis` 拆分理由使用现有 check/review 元数据记录，不新增正式结果列。
- `multi_uis` 界面开发行统一 EI，并补充非界面业务动作行；非界面业务动作行沿用 `unified_ui` 的类型规则。
- `multi_uis` 多界面开发行同名不合并，在 check/review 元数据中提示；`unified_ui` 和 `multi_uis` 非界面业务动作行同一三级模块内同名时合并，来源功能过程合并记录，跨三级模块不合并。
- `ui_api_mapping` 的功能过程默认接口开发行与明确接口/后端调用行不去重，保留两类行。
- `ui_api_mapping` 明确接口/后端调用行跨三级模块不去重；同一三级模块内同名明确接口/后端调用行合并为 1 条，来源功能过程合并记录。
- `ui_api_mapping` 功能过程默认界面开发行和默认接口开发行不合并；同名功能过程导致默认行同名时，在 check/review 元数据中提示。
- `ui_api_mapping` 的明确接口/后端调用行尽量保留原文接口/服务名称主体，不主动追加“调用”后缀，也不主动删除原文已有的“调用/请求/对接/同步”等动词，并加完整模块路径前缀。
- `ui_api_mapping` 的显式后端交互词没有更具体接口名时，保留原文动作短语作为行名主体。
- 所有 profile 的结果行来源信息记录在现有 check/review 元数据中，不新增正式 Excel 列。
- check/review 元数据不写入正式 Excel，只用于审阅页、检查副本或内部元数据。
- check/review 元数据记录 profile、kind、strategy、rule_set，并记录规则命中来源 `rule_id/rule_desc`。
- 同名合并后的来源功能过程按输入功能过程顺序记录，并去重保留首次出现顺序。
- 类型冲突提示不阻断生成，只进入 check/review；严重配置错误阻断生成。
- 所有 profile、所有最终结果行名称都使用完整模块路径前缀：`【客户端类型】一级模块-二级模块-三级模块-功能点名称`。
- profile 实现采用“配置驱动 + 少量行为 kind”，保留已有独立类逻辑作为 kind 行为实现。

## Prompt 与配置内容

- 4 个 profile 的 prompt、core_rules、rule_sets 都完整放入 `config/fpa_config.yaml.example`。
- `multi_uis` prompt 必须强调拆分理由进入 check/review。
- `ui_api_mapping` prompt 必须明确固定类型规则：界面开发 EI，接口开发 ILF，明确接口/后端调用 ILF。
- `strict_fpa` prompt 保留严格 FPA 口径，禁止“界面开发”“接口开发”“逻辑处理开发”等开发工作项表达。
- `unified_ui` 继续使用“界面开发/逻辑接口开发/导入处理开发/导出处理开发/外部接口联调调用”等模板友好表达。

## 验收标准

- `default-profile: strict_fpa` 可以正常加载默认 profile。
- `default-profile` 缺失或为空时抛出清晰错误，不自动默认 `strict_fpa`。
- 显式传入 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 均能通过配置校验。
- 用户配置只包含有效自定义 profile 且 `default-profile` 指向该 profile 时可以通过配置校验。
- `default-profile` 指向不存在的 profile 时抛出清晰错误。
- profile entry 引用不存在的 `kind`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt` 时抛出清晰错误。
- profile entry 缺失 `kind` 时抛出清晰错误；配置未知 `kind` 时抛出清晰错误并提示支持的 kind。
- 自定义 profile 可以使用 `kind: strict_fpa`、`kind: unified_ui`、`kind: multi_uis`、`kind: ui_api_mapping`，且 kind 与 profile 名不一致时不产生额外提示。
- 多个 profile 共用同一个 `rule_set`、`core_rules`、`system_prompt` 或 `user_prompt` 时可以通过配置校验。
- profile entry 出现未知字段时抛出清晰错误；rule_set entry 出现未知字段时不报错，未知字段不生效。
- `core_rules`、`system_prompt`、`user_prompt` 内容为空时抛出清晰错误。
- user_prompt 缺少 `${core_rules}`、`${judgement_rules}`、`${payload_json}` 或包含未知占位符时抛出清晰错误。
- profile strategy 不在 `rules_first`、`ai_first`、`rules_only`、`ai_only` 时抛出清晰错误。
- `rule_sets` 缺失、profile 引用不存在 rule_set、`extends` 指向不存在 rule_set、rule_set 循环继承、非法 merge 模式时抛出清晰错误。
- rule_set 列表字段为空时可以通过配置校验；`coverage_rules` 缺省时使用默认开启的覆盖规则。
- `default-profile: custom_rules` 时抛出专门错误：`custom_rules 已替换为 unified_ui，请更新 fpa_config.yaml`。
- `profiles.custom_rules` 出现时抛出专门错误：`profiles.custom_rules 已废弃，请迁移到 profiles.unified_ui`。
- Web options 接口返回 4 个 profile，且每个 profile 返回 `kind`。
- Web options 接口返回 `rule_set`、`strategy`、支持的 strategy 枚举和支持的 kind 枚举。
- Web options 接口按配置文件 `profiles` 顺序返回实际配置的 profile。
- Web options 对内置 profile 使用固定中文显示名，对自定义 profile 使用 profile 名作为显示名。
- Web options 接口返回 `core_rules`、`system_prompt`、`user_prompt` 配置 key；不得返回对应正文。
- Web options 在配置无效时返回 400 和配置错误详情。
- API 显式传入未知 profile、未知 strategy 或未知 rule_set 时抛出清晰错误。
- 现有 `strict_fpa` 行为不回退。
- `strict_fpa` 同一三级模块内同名同类型结果行合并，来源合并记录；同名不同类型结果行保留并提示类型冲突。
- `ui_api_mapping` 生成的功能过程界面开发行为 EI，功能过程接口开发行为 ILF，明确接口/后端调用行为 ILF。
- `ui_api_mapping` 在功能过程明确写出接口调用时，仍同时保留默认接口开发行和明确接口/后端调用行。
- `ui_api_mapping` 普通动作词“保存、提交、删除、审批、新增、修改”不会触发额外明确接口/后端调用行。
- `ui_api_mapping` 同一功能过程出现多个明确接口/服务时，生成多条明确接口/后端调用行。
- `ui_api_mapping` 同一三级模块内同名明确接口/后端调用行合并为 1 条，check/review 元数据合并多个来源功能过程；跨三级模块不合并。
- `ui_api_mapping` 功能过程默认行不因同名而合并；同名默认行在 check/review 元数据中提示。
- `ui_api_mapping` 显式后端交互词没有更具体接口名时，结果行主体保留原文动作短语。
- `ui_api_mapping` 明确接口/后端调用行保留原文接口/服务名称主体，不主动追加“调用”后缀，也不主动删除原文已有的“调用/请求/对接/同步”等动词，并使用完整模块路径前缀。
- `multi_uis` 生成的界面开发行为 EI，并保留非界面业务动作行。
- `multi_uis` 同一三级模块内同名多界面开发行不合并，并在 check/review 元数据中提示。
- `unified_ui` 和 `multi_uis` 同一三级模块内同名非界面业务动作行合并为 1 条，check/review 元数据合并来源功能过程；跨三级模块不合并。
- `multi_uis` 拆分理由出现在 check/review 元数据中，不新增正式结果列。
- `strict_fpa` 事务功能行、数据功能行，`unified_ui`/`multi_uis` 非界面业务动作行，`ui_api_mapping` 功能过程默认行和明确接口/后端调用行均记录来源到 check/review 元数据，不新增正式 Excel 列。
- check/review 元数据记录 profile、kind、strategy、rule_set 和规则命中来源；不写入正式 Excel。
- 同名合并后的来源功能过程按输入顺序去重记录。
- 类型冲突不阻断生成；严重配置错误阻断生成。
- `strict_fpa` 数据功能行、`unified_ui`/`multi_uis` 非界面业务动作行、`ui_api_mapping` 所有行均使用完整模块路径前缀。
- 示例配置使用 `_rs/_cr/_sp/_up` 命名，不再使用 `_default` 作为默认 rule_set 后缀。
- 实施后的示例配置、测试 fixture、常规配置说明不得再引用旧 profile/config 键：`profiles.custom_rules`、`custom_rules_default`、`core_rules.custom_rules`、`system_prompt_sets.custom_rules`、`user_prompt_sets.custom_rules`、`strict_fpa_default`、`core_rules.strict_fpa`、`system_prompt_sets.strict_fpa`、`user_prompt_sets.strict_fpa`。迁移说明和错误提示测试可以引用旧键。
- 示例配置完整包含 4 个 profile 的 prompt/core_rules/rule_sets。
- prompt 验收：`multi_uis` 强调拆分理由进入 check/review；`ui_api_mapping` 明确固定 EI/ILF 类型规则；`strict_fpa` 禁止开发工作项表达；`unified_ui` 保留模板友好表达。
- 测试覆盖旧 `custom_rules` 两类错误、自定义 profile、Web options 自定义 profile 顺序和 label fallback、`ui_api_mapping` 同三级模块同名明确接口合并、`multi_uis` 多界面同名不合并但提示、`strict_fpa` 同名同类型合并和同名不同类型冲突。

## 测试建议

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config_utils.py tests\test_fpa_profiles.py tests\test_web_tasks.py
```

如果实施时改动生成行为，再补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py tests\test_fpa_external_data_rules.py
```
