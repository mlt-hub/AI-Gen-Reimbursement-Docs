# 2026-06-09 FPA prompt 样例试运行真实模型验证

## 执行信息

本次验证使用 Web 配置页同源的样例试运行 service：

```python
from web_app.services.config_service import config_dir, run_fpa_prompt_sample_preview

run_fpa_prompt_sample_preview(profile_name=profile, target_dir=config_dir())
```

运行配置：

- 配置目录：`C:\Users\Administrator\.ai-gen-reimbursement-docs`
- API Key：已配置，来源为 global
- 模型：使用当前本机配置的真实模型
- 样例输入：内置客户资料维护模块

首轮结果文件保存在临时目录：

```text
tmp_validation_runs\20260609_171735
```

修复后针对 `ui_api_mapping` 复跑结果文件保存在临时目录：

```text
tmp_validation_runs\20260609_172213_after_ui_mapping_fix
```

临时 JSON 结果不纳入仓库提交；本文只记录摘要和结论。

## 首轮结果

| profile | ai_called | parse_ok | normalized rows | warnings | quality warnings |
|---|---:|---:|---:|---:|---:|
| `strict_fpa` | yes | yes | 4 | 0 | 0 |
| `unified_ui` | yes | yes | 4 | 0 | 0 |
| `multi_uis` | yes | yes | 3 | 0 | 0 |
| `ui_api_mapping` | yes | yes | 4 | 4 | 3 |

结论：

- 四个 profile 均成功调用真实模型，且响应均能解析为 JSON rows。
- `strict_fpa` 和 `unified_ui` 的样例输出通过当前说明质量门。
- `multi_uis` 无后处理 warning，但模型把查询、导出行也输出为 `EI`，且说明中出现“客户表”等实现词；当前质量门没有把这类 profile 口径偏差作为 warning。
- `ui_api_mapping` 首轮暴露确定性后处理问题：模型原始输出了 3 条界面开发行和 3 条接口开发行，但后处理把多条界面开发行合并成 1 条，最终只剩 4 行。
- `ui_api_mapping` 首轮的 3 条接口开发行说明没有明确写出 `ILF`，触发 `postprocess.explanation_quality`。

## 确定性修复

本轮修复：

- `ui_api_mapping` 的“每个功能过程默认生成界面开发行”是合法输出。
- 多条界面开发行缺少 `split_reason` 时自动合并的规则不应作用于 `ui_api_mapping`。
- 后处理已改为排除 `ui_api_mapping`，保留其多条默认界面开发行。

回归测试：

- `test_ui_api_mapping_keeps_default_ui_rows_without_split_reason`

## 修复后复跑

针对 `ui_api_mapping` 复跑真实模型样例：

| profile | ai_called | parse_ok | parsed rows | normalized rows | warnings | quality warnings |
|---|---:|---:|---:|---:|---:|---:|
| `ui_api_mapping` | yes | yes | 6 | 6 | 0 | 0 |

复跑后的 6 行：

| 新增/修改功能点 | 类型 |
|---|---|
| `【后台】业务管理-客户管理-客户资料维护-新增客户_界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-新增客户_接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户_界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户_接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单_界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单_接口开发` | `ILF` |

## 剩余观察项

1. `multi_uis` 输出无 warning，但查询、导出行被模型标为 `EI`，且 `计算依据归类`分别指向 `EQ` / `EO` 规则。后处理已新增 `postprocess.classification_basis_type_conflict`，后续复跑会将这类“类型”和“计算依据归类”不一致写入 warning。
2. `multi_uis` 和部分 profile 的说明中出现“客户表”，但没有使用 `系统元素：` 标签，因此当前疑似编造系统元素检测不会触发。该检测目前只覆盖正式结构化 `系统元素` 行。
3. `ui_api_mapping` 复跑结果使用 `_界面开发` / `_接口开发` 作为名称连接符，而不是 `-界面开发` / `-接口开发`。当前后处理没有把下划线连接符规范化为短横线。

## 后续建议

优先级建议：

1. 对 `计算依据说明`中没有放在 `系统元素：` 行里的疑似表/服务/接口词，先只在 check/debug 中作为低置信 warning 观察，不直接阻断。
2. 对 FPA 行名称连接符做规范化，至少将 `_<界面开发|接口开发>` 规范成 `-<界面开发|接口开发>`。
3. 再运行一次四 profile 真实模型样例，确认 `ui_api_mapping` 的 6 行结构稳定，并观察新增一致性 warning 的命中情况。
