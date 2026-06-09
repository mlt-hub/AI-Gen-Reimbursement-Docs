# FPA 多 profile 真实模型抽样验证

日期：2026-06-04

## 目标

验证 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 四个 profile 在真实模型调用下的输出稳定性。

本验证不替代自动化测试。自动化测试负责固定规则、配置校验、fallback、Web/API 和 check 工作簿链路；真实模型抽样验证负责观察 prompt 是否稳定约束模型输出。

## 验证范围

建议选择 2-3 个样例：

- 一个已有 Golden Case fixture，用于对照固定期望。
- 一个包含查询、新增、修改、导出等常规功能过程的真实模块。
- 一个包含明确接口、服务、调用、同步或外部系统交互的模块，用于验证 `ui_api_mapping`。

每个样例分别运行四个 profile：

```text
strict_fpa
unified_ui
multi_uis
ui_api_mapping
```

## 重点观察

`strict_fpa`：

- 是否按事务功能和数据功能拆分。
- 是否避免输出“界面开发”“接口开发”“逻辑处理开发”等开发工作项。
- 是否正确区分 ILF / EIF、EI / EQ / EO。

`unified_ui`：

- 同一三级模块是否保持统一界面口径。
- 是否保留模板友好的“界面开发 / 查询处理开发 / 导出处理开发 / 逻辑处理开发”等表达。
- 是否避免按查询条件、按钮、弹窗或字段过度拆分。

`multi_uis`：

- 多界面拆分是否有明确 `split_reason`。
- 拆分理由是否属于独立页面、独立业务对象、独立业务流程或独立用户端。
- 同名多界面开发行是否进入 check/review 元数据提示。

`ui_api_mapping`：

- 功能过程默认界面开发行是否固定为 EI。
- 功能过程默认接口开发行是否固定为 ILF。
- 明确接口/后端调用行是否固定为 ILF。
- 明确接口/后端调用行是否只来自输入材料显式信息。
- 默认接口开发行与明确接口/后端调用行是否同时保留。

## 执行步骤

1. 准备输入样例和输出目录。
2. 对每个样例分别运行四个 profile。
3. 为每次运行保留正式 `FPA工作量评估.xlsx` 和 `FPA工作量评估-check.xlsx`。
4. 检查 check 工作簿中的 `FPA结果`、`Warnings`、`规则命中详情`、`AI原始返回`。
5. 检查 audit trace / stability report 中的 `agent_review.contract`、`agent_review.applicability`、`profile_quality_issue_count` 和 `profile_issue_code_counts`。
6. 记录每个 profile 的通过项、异常项、是否需要调整 prompt。

## 建议命令

按实际输入路径替换命令中的 Excel 或 MD 文件：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile unified_ui
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile multi_uis
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile ui_api_mapping
```

如需固定策略或规则集：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile ui_api_mapping --fpa-strategy ai_first --fpa-rule-set ui_api_mapping_rs
```

## 记录模板

可直接复制 [`validation-runs/multi-profile-run-template.md`](validation-runs/multi-profile-run-template.md) 作为单次验证记录。

```text
样例：
输入：
执行日期：
模型端点：
模型：
profile：
contract：
applicability：
strategy：
rule_set：

结果概览：
- FPA 行数：
- 类型分布：
- warning 数量：
- quality_issue_count：
- profile_quality_issue_count：
- profile_issue_code_counts：
- check.xlsx 是否生成：

观察结论：
- profile 语义是否符合预期：
- 类型规则是否稳定：
- 命名是否使用完整模块路径：
- 来源追溯是否完整：
- prompt 是否需要调整：

问题与处理：
- 问题：
- 影响：
- 建议修复：
- 是否阻塞：
```

## 通过标准

- 四个 profile 均能完成真实模型生成并产出 check 工作簿。
- 结果行名称使用完整模块路径前缀。
- check/review 元数据记录 profile、strategy、rule_set、规则命中来源和 warning。
- audit trace 中记录 `agent_review.contract`、`agent_review.applicability` 和 profile 专属 quality issue 汇总。
- `strict_fpa` 不回退到开发工作项口径。
- `multi_uis` 的多界面拆分理由可审阅。
- `ui_api_mapping` 的 EI / ILF 固定类型规则稳定。
- 明显偏离 profile 语义的问题已记录，并能归因到 prompt、输入质量或模型波动。

## 后续处理

如果真实模型输出只是措辞差异，不调整代码。

如果模型稳定违反某个 profile 语义，优先调整 `config/fpa_config.yaml.example` 中对应 profile 的 `system_prompt` 或 `user_prompt`。

如果 prompt 无法稳定表达某类规则，再评估是否新增规则后处理或新的 profile kind。
