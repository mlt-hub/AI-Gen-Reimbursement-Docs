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

严格 FPA 口径。按数据功能和事务功能拆分，不按页面、按钮、弹窗、接口或数据库表字段拆分。对应现在的strict_fpa。

### unified_ui

统一界面口径。同一三级模块默认合并为 1 条界面类功能点，覆盖列表、查询条件、按钮、弹窗、状态切换等同页交互能力；非界面业务动作再按规则或 AI 结果补充。对应现在的custom_rules。

### multi_uis

多界面口径。允许同一三级模块按独立页面、独立业务对象、独立业务流程或独立用户端拆分为多条界面类功能点；每条多界面拆分行必须给出可审阅的拆分理由。

### ui_api_mapping

一界面一接口口径。同一三级模块保留 1 条界面类功能点，同时对明确输入的接口或后端交互能力按一接口一行补充功能点；接口行必须来源于输入材料中明确出现的接口、服务、调用或后端动作，不得凭空补齐。

拆分规则分为两层：

1. 界面层：同一三级模块只生成 1 条界面类功能点，覆盖列表、查询条件、新增按钮、编辑弹窗、删除按钮、状态切换等同页交互能力，不按按钮、弹窗、字段或查询条件继续拆分。
2. 接口/后端层：输入材料中明确出现的接口、服务调用、外部系统调用、数据同步、提交审批、导入导出或后端处理动作，按一项一行补充功能点。

示例输入：

```text
三级模块：合同管理
功能过程：
1. 查询合同列表。
2. 新增合同，保存后调用合同保存接口。
3. 提交合同审批，调用 OA 审批接口。
4. 同步客户信息，调用 CRM 客户查询服务。
```

`ui_api_mapping` 输出形态：

```text
合同管理-界面开发
合同保存接口处理
OA 审批接口调用
CRM 客户查询服务调用
```

边界约束：

- 不把查询条件、新增按钮、提交按钮、弹窗字段等同页交互拆成多条界面行。
- 不凭空补接口。输入只写“新增合同”但没有明确接口、服务、调用、后端处理或同步等信息时，不自动生成“合同新增接口”。
- 接口/后端行必须保留可追溯来源，能说明来自哪个功能过程、接口、服务、调用或后端动作。

### unified_ui 与 ui_api_mapping 的区别

共同点：两者都把同一三级模块默认合并为 1 条界面类功能点，不按查询条件、按钮、弹窗或字段拆分界面行。

差异在第二层补充行：

- `unified_ui` 是“一界面 + 业务动作补充”。它关注三级模块整体有哪些业务处理能力，界面合并后，非界面业务动作可以再按规则或 AI 结果补充，例如查询处理、导出处理、逻辑处理、数据维护等。
- `ui_api_mapping` 是“一界面 + 明确接口/后端调用补充”。它关注界面背后明确调用了哪些接口、服务或后端交互；额外行必须来自输入材料中明确出现的接口、服务、调用、同步、审批、导入导出或后端动作，不允许凭空补接口。

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
合同管理-界面开发
OA 审批接口调用
```

一句话区分：`unified_ui` 是“一个页面 + 业务处理行”；`ui_api_mapping` 是“一个页面 + 明确接口/后端调用行”。

## 配置目标

`fpa_config.yaml` 示例结构：

```yaml
default-profile: strict_fpa

profiles:
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    core_rules: strict_fpa
    system_prompt: strict_fpa
    user_prompt: strict_fpa
  unified_ui:
    strategy: rules_first
    rule_set: unified_ui_default
    core_rules: unified_ui
    system_prompt: unified_ui
    user_prompt: unified_ui
  multi_uis:
    strategy: rules_first
    rule_set: multi_uis_default
    core_rules: multi_uis
    system_prompt: multi_uis
    user_prompt: multi_uis
  ui_api_mapping:
    strategy: rules_first
    rule_set: ui_api_mapping_default
    core_rules: ui_api_mapping
    system_prompt: ui_api_mapping
    user_prompt: ui_api_mapping
```

## 实施切片

1. 放宽 profile 名称校验

`default-profile` 必须存在于 `profiles` 中。`profiles` 中的 profile 名称不再受固定白名单限制，但每个 profile entry 必须引用存在的 `rule_set`、`core_rules`、`system_prompt`、`user_prompt`。

2. 统一 profile 解析入口

CLI / Web / API 需要共享同一套 `load_fpa_profile` 和 profile entry 校验逻辑，避免 Web options 接口与生成流程读取不一致。

3. 增加 4 个 profile 配置样例

更新 `config/fpa_config.yaml.example`，补齐 4 个 profile 的 `profiles`、`core_rules`、`system_prompt_sets`、`user_prompt_sets`、`rule_sets` 示例。

4. 明确执行类复用策略

如果 profile 只通过配置控制 prompt 与规则集，可复用现有配置化执行逻辑；如果需要不同兜底拆分算法，再新增 profile 执行类或 profile kind 字段。

5. 更新 Web profile 选项

`/api/fpa/options` 返回所有配置 profile。未知 label 时使用 profile 名称兜底，避免新增 profile 无法显示。

## 验收标准

- `default-profile: strict_fpa` 可以正常加载默认 profile。
- 显式传入 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 均能通过配置校验。
- `default-profile` 指向不存在的 profile 时抛出清晰错误。
- profile entry 引用不存在的 `rule_set`、`core_rules`、`system_prompt`、`user_prompt` 时抛出清晰错误。
- Web options 接口返回 4 个 profile。
- 现有 `strict_fpa` 行为不回退。

## 测试建议

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config_utils.py tests\test_fpa_profiles.py tests\test_web_tasks.py
```

如果实施时改动生成行为，再补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py tests\test_fpa_external_data_rules.py
```

## 待确认问题

- `unified_ui` 是否完全替代原 `custom_rules`，还是保留 `custom_rules` 作为兼容别名。
- `ui_api_mapping` 的“接口”是否只包含明确接口/服务，还是也包含普通后端逻辑处理动作。
- `multi_uis` 的拆分理由是否必须进入用户可见的 `split_reason` 字段。
