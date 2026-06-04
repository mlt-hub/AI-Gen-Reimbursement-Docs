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
multi_uis      多界面口径，kind: unified_ui，默认 rules_first + multi_uis_rs
ui_api_mapping 界面接口映射口径，kind: ui_api_mapping，默认 rules_first + ui_api_mapping_rs
```

用户配置可以只保留实际需要的 profile，也可以新增自定义 profile。自定义 profile 只要绑定支持的 `kind`，并引用存在的 `rule_set/core_rules/system_prompt/user_prompt` 即可。

## 如何选择

`strict_fpa` 适合标准 FPA 复核：按数据功能和事务功能拆分，不生成“界面开发”“接口开发”“逻辑处理开发”等开发工作项表达。

`unified_ui` 适合报账模板友好口径：同一三级模块默认合并一条界面开发行，查询、导出、导入和逻辑处理按功能动作补充。

`multi_uis` 适合确有多个独立界面时使用：可按独立页面、独立业务对象、独立业务流程或独立用户端拆分多条界面开发行，拆分理由进入 check/review 元数据。

`ui_api_mapping` 适合需要展示“功能过程 -> 界面开发 + 接口开发”映射时使用：每个功能过程默认生成一条界面开发 EI 和一条接口开发 ILF；输入中明确出现的接口、服务、调用、请求、对接、同步、外部系统、第三方或 API 单独生成明确接口/后端调用 ILF。

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
```

命名约定：

```text
rule_set: <profile>_rs
core_rules: <profile>_cr
system_prompt: <profile>_sp
user_prompt: <profile>_up
```

`default-profile` 必须是非空字符串并存在于 `profiles`。profile entry 必须显式配置 `kind`，且只允许 `strict_fpa`、`unified_ui`、`ui_api_mapping`。

## Strategy

```text
rules_first  规则优先，AI 只做补充或复核
ai_first     AI 优先，规则补齐 AI 未覆盖的行
rules_only   仅规则，不调用 AI
ai_only      仅 AI，不用规则兜底补行
```

`ui_api_mapping` 和 `multi_uis` 支持 `ai_only`；此时不会强制规则兜底生成默认行。

## Web 与 CLI

Web 高级选项和 FPA 预览页会从 `/api/fpa/options` 读取实际配置的 profile。接口返回 profile 的 `name/label/kind/strategy/rule_set`，不会返回内部 prompt 配置 key。

CLI 示例：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile unified_ui --fpa-strategy rules_only
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile ui_api_mapping --fpa-rule-set ui_api_mapping_rs
```

CLI / Web / API 显式传入 profile、strategy 或 rule_set 时优先使用显式值；显式传入未知值会报错，不回退默认值。

## 迁移提示

`unified_ui` 已替代旧的用户自定义规则口径，不保留兼容别名。旧配置会得到专门错误：

```text
custom_rules 已替换为 unified_ui，请更新 fpa_config.yaml
profiles.custom_rules 已废弃，请迁移到 profiles.unified_ui
```

旧配置键迁移关系：

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

## 审核副本

正式生成仍会额外输出：

```text
FPA工作量评估-check.xlsx
```

check/review 元数据记录 profile、kind、strategy、rule_set、规则命中来源、源功能过程、拆分理由和 warning，不新增正式 Excel 列。
