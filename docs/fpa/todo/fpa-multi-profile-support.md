# FPA 多 profile 支持 TODO

日期：2026-06-04

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
查询合同列表-界面开发：EI
查询合同列表-接口开发：ILF
新增合同-界面开发：EI
新增合同-接口开发：ILF
提交合同审批-界面开发：EI
提交合同审批-接口开发：ILF
OA 审批接口调用：ILF
CRM 客户查询服务调用：ILF
```

边界约束：

- 功能过程层的接口开发行来自功能过程本身，不要求输入材料显式写出接口名称。
- 明确接口/后端层不凭空补接口。输入没有明确接口、服务、调用、后端处理或同步等信息时，不额外生成明确接口/后端调用行。
- 明确接口/后端调用行不配套生成界面开发行，避免同一个后端调用重复产生界面工作量。
- 接口/后端行必须保留可追溯来源，能说明来自哪个功能过程、接口、服务、调用或后端动作。
- 功能过程层界面开发行统一为 EI，功能过程层接口开发行统一为 ILF，明确接口/后端调用行统一为 ILF。

### unified_ui 与 ui_api_mapping 的区别

共同点：两者都不按查询条件、按钮、弹窗或字段拆分界面行。

差异在界面行和补充行粒度：

- `unified_ui` 是“一界面 + 业务动作补充”。它关注三级模块整体有哪些业务处理能力，界面合并后，非界面业务动作可以再按规则或 AI 结果补充，例如查询处理、导出处理、逻辑处理、数据维护等。
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
查询合同-查询处理开发
新增合同-逻辑处理开发
提交合同审批-逻辑处理开发
```

`ui_api_mapping` 输出形态：

```text
查询合同列表-界面开发：EI
查询合同列表-接口开发：ILF
新增合同-界面开发：EI
新增合同-接口开发：ILF
提交合同审批-界面开发：EI
提交合同审批-接口开发：ILF
OA 审批接口调用：ILF
```

一句话区分：`unified_ui` 是“一个三级模块页面 + 业务处理行”；`ui_api_mapping` 是“一个功能过程对应 1 个界面开发和 1 个接口开发，明确接口/后端调用行单独列出且不生成界面开发”。

## 配置目标

`fpa_config.yaml` 示例结构：

```yaml
default-profile: strict_fpa

profiles:
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  multi_uis:
    kind: unified_ui
    strategy: rules_first
    rule_set: multi_uis_rs
    core_rules: multi_uis_cr
    system_prompt: multi_uis_sp
    user_prompt: multi_uis_up
  ui_api_mapping:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: ui_api_mapping_rs
    core_rules: ui_api_mapping_cr
    system_prompt: ui_api_mapping_sp
    user_prompt: ui_api_mapping_up
```

命名约定：

```text
rule_set: <profile>_rs
core_rules: <profile>_cr
system_prompt: <profile>_sp
user_prompt: <profile>_up
```

## 实施切片

1. 放宽 profile 名称校验

`default-profile` 必须存在于 `profiles` 中。`profiles` 中的 profile 名称不再受固定白名单限制，但每个 profile entry 必须引用存在的 `rule_set`、`core_rules`、`system_prompt`、`user_prompt`。

如果配置中出现旧 `custom_rules`，不自动迁移、不保留别名，直接报清晰错误并提示改为 `unified_ui`。

2. 统一 profile 解析入口

CLI / Web / API 需要共享同一套 `load_fpa_profile` 和 profile entry 校验逻辑，避免 Web options 接口与生成流程读取不一致。

3. 增加 4 个 profile 配置样例

更新 `config/fpa_config.yaml.example`，补齐 4 个 profile 的 `profiles`、`core_rules`、`system_prompt_sets`、`user_prompt_sets`、`rule_sets` 示例。

4. 明确执行类复用策略

采用“配置驱动 + 少量行为 kind”机制。profile 名称由配置决定，`kind` 决定兜底拆分、类型推断和后处理行为。

```text
strict_fpa -> kind: strict_fpa
unified_ui -> kind: unified_ui，复用现有 CustomRulesProfile 行为
multi_uis -> kind: unified_ui，主要通过 prompt/rule_set 控制；后续配置表达不了时再新增 kind
ui_api_mapping -> kind: ui_api_mapping，提供“每个功能过程 = 1 个界面开发 + 1 个接口开发”的特殊兜底逻辑
```

5. 更新 Web profile 选项

`/api/fpa/options` 返回所有配置 profile。未知 label 时使用 profile 名称兜底，避免新增 profile 无法显示。

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
- 初始化配置保留完整 4 个 profile，用户可直接切换默认 profile。
- 默认 strategy：`strict_fpa` 使用 `ai_first`，`unified_ui`、`multi_uis`、`ui_api_mapping` 使用 `rules_first`。
- 配置键命名采用 `<profile>_rs`、`<profile>_cr`、`<profile>_sp`、`<profile>_up`。
- `strict_fpa` 允许 rule_set 扩展；扩展为空时仍走内置 strict_fpa 默认规则和 AI 约束，不等于 AI-only。
- `ui_api_mapping` 的明确接口/后端调用行只包含输入中明确出现的接口、服务、调用、同步或外部系统交互；普通保存、提交、删除、审批等后端动作不额外生成第二条后端处理行。
- `ui_api_mapping` 类型规则：界面开发行统一 EI，接口开发行统一 ILF，明确接口/后端调用行统一 ILF。
- `multi_uis` 保持四类拆分理由：独立页面、独立业务对象、独立业务流程、独立用户端；拆分理由记录在 check 中，不强制进入用户可见 `split_reason` 字段。
- `multi_uis` 界面开发行统一 EI，并补充非界面业务动作行；非界面业务动作行沿用 `unified_ui` 的类型规则。
- profile 实现采用“配置驱动 + 少量行为 kind”，保留已有独立类逻辑作为 kind 行为实现。

## 验收标准

- `default-profile: strict_fpa` 可以正常加载默认 profile。
- 显式传入 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 均能通过配置校验。
- `default-profile` 指向不存在的 profile 时抛出清晰错误。
- profile entry 引用不存在的 `kind`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt` 时抛出清晰错误。
- 配置中出现旧 `custom_rules` 时抛出清晰错误，提示改为 `unified_ui`。
- Web options 接口返回 4 个 profile。
- 现有 `strict_fpa` 行为不回退。
- `ui_api_mapping` 生成的功能过程界面开发行为 EI，功能过程接口开发行为 ILF，明确接口/后端调用行为 ILF。
- `multi_uis` 生成的界面开发行为 EI，并保留非界面业务动作行。
- 示例配置使用 `_rs/_cr/_sp/_up` 命名，不再使用 `_default` 作为默认 rule_set 后缀。

## 测试建议

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config_utils.py tests\test_fpa_profiles.py tests\test_web_tasks.py
```

如果实施时改动生成行为，再补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py tests\test_fpa_external_data_rules.py
```
