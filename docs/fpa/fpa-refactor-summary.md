# FPA 重构收口说明

本文档是 FPA 重构后的短入口，用于快速了解当前可用能力、使用方式、审核产物和后续暂缓事项。

## 当前可用能力

```text
profile：支持 strict_fpa、unified_ui、multi_ui、ui_api_mapping，并允许通过 kind 配置项目自定义 profile。
strategy：支持 rules_first、ai_first、rules_only、ai_only。
rule_set：支持在 fpa_config.yaml 中配置项目级规则集，并通过 extends 继承默认规则。
system_prompt_sets / user_prompt_sets：FPA prompt 已集中到 fpa_config.yaml，不再使用旧拆分 prompt 配置文件。
domain_context：支持在 domain_context.json 中配置系统边界、本系统数据组、外部数据组和普通外部服务；FPA 还会从功能清单元数据中的工单标题和工单内容自动生成 project_description。
Web 预览：支持选择 profile、strategy、rule_set，并返回 audit 审核信息。
正式生成：生成正式 FPA 工作量评估 Excel，同时生成审核副本。
```

默认组合：

```text
strict_fpa     = ai_first    + strict_fpa_rs
unified_ui     = rules_first + unified_ui_rs
multi_ui      = rules_first + multi_ui_rs
ui_api_mapping = ai_first    + ui_api_mapping_rs
```

## 用户怎么用

CLI 示例：

```bash
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
ard --from-excel 功能清单.xlsx --gen-all --fpa-profile unified_ui
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa --fpa-strategy ai_first --fpa-rule-set strict_fpa_rs
```

配置入口：

```text
~/.ai-gen-reimbursement-docs/fpa_config.yaml
~/.ai-gen-reimbursement-docs/domain_context.json
config/fpa_config.yaml.example
config/domain_context.json.example
```

`domain_context.json` 只维护稳定领域边界，不维护 `project_description`。`project_description` 来自功能清单录入模板中的工单标题和工单内容；建设目标、建设必要性等 AI 生成字段不会进入 FPA prompt。

详细用户说明：

```text
docs/fpa/fpa-profiles.md
```

## 审核产物

正式生成 FPA 时，系统会额外生成：

```text
FPA工作量评估-check.xlsx
```

该文件不替代正式 `FPA工作量评估.xlsx`，只用于审核和复核。当前包含五张 Sheet：

```text
FPA结果：逐行查看 generation、type_reason、source_processes、warnings 和规则集信息；正式审核主表不新增 source_process_ids 列。
覆盖审核：按三级模块查看功能过程覆盖、缺失过程和生成方式统计；内部覆盖统计优先使用 source_process_ids，source_processes 仅作展示和缺失 ID 时的兜底线索。
Warnings：集中查看行级 warning、模块级 warning 和来源规则 ID。
规则命中详情：查看规则 ID、规则说明、建议类型、是否采用和 warning。
AI原始返回：查看 AI 原始 rows JSON、source_process_ids、缓存命中、rules_fallback 和规则优先未调用 AI 等来源。
```

预览 audit 与正式审核副本已共用核心审核报告结构，重点检查：

```text
profile / strategy / rule_set 是否选对。
功能过程是否全部覆盖。
strict_fpa 是否出现不该出现的界面开发 / 接口开发 / 逻辑处理开发。
普通外部服务是否被误判为 EIF。
本系统维护数据组是否识别为 ILF。
外部维护且本系统引用的数据组是否识别为 EIF。
```

## 已收口事项

```text
A. 真实项目 Golden Case：已完成。
B. strict_fpa 数据组识别：已完成。
C. 类型冲突规则：已完成。
D. 配置校验：已完成。
E. 领域上下文：已完成。
F. 验收：已完成。
G. 可选增强：已完成当前确定项。
H. 旧兼容逻辑清理：已完成最终复核。
J. profile / strategy / rule_set 三层模型：已完成。
K. FPA 审核工作簿与预览审核面板：已完成当前收口。
```

旧兼容路径已清理：不保留旧版“每个功能过程固定生成界面开发 + 接口开发”、旧逐行 AI 填充、旧 10 列 FPA MD 读取、`current_project` 兼容别名和 `rule_set_version` 暴露。

## 后续入口

```text
用户文档：
docs/fpa/fpa-profiles.md

工程实施记录：
docs/fpa/gen-fpa-implementation-notes.md

暂缓任务与恢复指令：
docs/fpa/fpa-todo.md

gen-cosmic 重构后再评估的多预览页面扩展：
docs/fpa/fpa-deferred-preview-after-cosmic.md

strict_fpa 人工验收记录：
docs/fpa/strict-fpa-acceptance-record.md
```
