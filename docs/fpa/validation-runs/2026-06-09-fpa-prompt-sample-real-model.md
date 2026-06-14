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

名称连接符规范化后四 profile 复跑结果文件保存在临时目录：

```text
tmp_validation_runs\20260609_175246_after_name_connector
```

误报收紧后第二轮复跑结果文件保存在临时目录：

```text
tmp_validation_runs\20260609_175558_after_connector_and_warning_filter
```

临时 JSON 结果不纳入仓库提交；本文只记录摘要和结论。

## 首轮结果

| profile | ai_called | parse_ok | normalized rows | warnings | quality warnings |
|---|---:|---:|---:|---:|---:|
| `strict_fpa` | yes | yes | 4 | 0 | 0 |
| `unified_ui` | yes | yes | 4 | 0 | 0 |
| `multi_ui` | yes | yes | 3 | 0 | 0 |
| `ui_api_mapping` | yes | yes | 4 | 4 | 3 |

结论：

- 四个 profile 均成功调用真实模型，且响应均能解析为 JSON rows。
- `strict_fpa` 和 `unified_ui` 的样例输出通过当前说明质量门。
- `multi_ui` 无后处理 warning，但模型把查询、导出行也输出为 `EI`，且说明中出现“客户表”等实现词；当前质量门没有把这类 profile 口径偏差作为 warning。
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

## 名称连接符规范化后复跑

针对 `strict_fpa`、`unified_ui`、`multi_ui`、`ui_api_mapping` 四个 profile 进行真实模型轻量复跑，四个 profile 首轮均完整跑通。

`ui_api_mapping` 继续生成 6 行，结构稳定；行名称已由后处理规范为短横线连接：

| 新增/修改功能点 | 类型 |
|---|---|
| `【后台】业务管理-客户管理-客户资料维护-新增客户-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-新增客户-接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户-接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单-接口开发` | `ILF` |

误报收紧后继续执行第二轮真实模型轻量复跑，本轮只完成 `strict_fpa` 和 `unified_ui`。`multi_ui` 和 `ui_api_mapping` 调用超时，未得到可记录的第二轮结果；该项不作为失败结论，保留为后续复跑观察项。

## 误报收紧后补充复跑

继续在新 worktree 中补齐四 profile 真实模型轻量复跑，临时结果目录为：

```text
tmp_validation_runs\20260609_192310_warning_filter_rerun
tmp_validation_runs\20260609_192310_warning_filter_rerun_final
```

复跑摘要：

| profile | ai_called | parse_ok | parsed rows | normalized rows | warnings | quality warnings |
|---|---:|---:|---:|---:|---:|---:|
| `strict_fpa` | yes | yes | 4 | 4 | 0 | 0 |
| `unified_ui` | yes | yes | 4 | 4 | 0 | 0 |
| `multi_ui` | yes | yes | 4 | 4 | 3 | 3 |
| `ui_api_mapping` | yes | yes | 6 | 6 | 0 | 0 |

本轮观察：

- `strict_fpa` 输出 1 条 `ILF` 数据组、1 条 `EI`、1 条 `EQ`、1 条 `EO`，无 warning。
- `unified_ui` 最终复跑输出 4 行，无 warning；复跑过程中暴露“列表”“代表”“导出/输出文件产物”被正文低置信系统元素检测误报，已收紧候选词过滤。
- `multi_ui` 本轮完整跑通，输出 4 行；3 条界面行触发 `计算说明未明确当前 FPA 类型: EI`，属于真实模型说明表达质量观察，后续可通过 profile prompt 强化。
- `ui_api_mapping` 最终复跑继续稳定输出 6 行，名称保持 `-界面开发` / `-接口开发` 短横线连接，无 warning。

`ui_api_mapping` 最终复跑的 6 行：

| 新增/修改功能点 | 类型 |
|---|---|
| `【后台】业务管理-客户管理-客户资料维护-新增客户-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-新增客户-接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-查询客户-接口开发` | `ILF` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单-界面开发` | `EI` |
| `【后台】业务管理-客户管理-客户资料维护-导出客户清单-接口开发` | `ILF` |

## 剩余观察项

1. `multi_ui` 输出无 warning，但查询、导出行被模型标为 `EI`，且 `计算依据归类`分别指向 `EQ` / `EO` 规则。后处理已新增 `postprocess.classification_basis_type_conflict`，后续复跑会将这类“类型”和“计算依据归类”不一致写入 warning。
2. `multi_ui` 和部分 profile 的说明中出现“客户表”，但没有使用 `系统元素：` 标签。后处理已新增正文低置信系统元素检测，后续复跑会将输入未明确提供的疑似表/服务/接口词写入 warning。
3. `multi_ui` 本轮完整复跑后主要剩余问题变为说明中未明确写出当前 `EI` 类型；已在后续小节通过 profile prompt 强化并复跑验证。

## 后续建议

优先级建议：

1. 后续扩大 `multi_ui` 真实模型样本，观察不同模块下“界面开发行固定 EI”和“查询/导出/逻辑处理开发行按实际类型”的稳定性。
2. 根据更多真实模型复跑结果，继续治理低置信 warning 误报和 profile 差异化规则。

## multi_ui EI 说明强化后复跑

本轮在临时配置目录中使用仓库最新默认 `fpa_config.yaml.example`，只替换 FPA prompt 配置，不修改用户配置目录。临时结果目录为：

```text
tmp_validation_runs\20260609_193744_multi_ui_ei_prompt
```

复跑摘要：

| profile | ai_called | parse_ok | parsed rows | normalized rows | warnings | quality warnings |
|---|---:|---:|---:|---:|---:|---:|
| `multi_ui` | yes | yes | 4 | 4 | 0 | 0 |

本轮 prompt 强化：

- `multi_ui` user prompt 新增约束：每条界面开发行的`计算说明`必须明确写出“按 EI 识别”或“按 EI 计量”，不能只写“界面开发行”“用户通过界面输入”等间接表述。
- 真实模型复跑中，三级模块级界面开发行的`计算说明`已写出“按EI识别”，后处理质量 warning 为 0。
- 本轮仍记录 `multi_ui.split_reason`，用于保留“无明确独立页面/业务对象/业务流程/用户端拆分证据，按三级模块合并为一条界面开发行”的拆分依据；这是 review 元数据，不是说明质量失败。

复跑后的 4 行：

| 新增/修改功能点 | 类型 | 后处理观察 |
|---|---|---|
| `【后台】业务管理-客户管理-客户资料维护-界面开发（客户资料维护界面）` | `EI` | 计算说明写出“按EI识别”；记录 `multi_ui.split_reason` |
| `【后台】业务管理-客户管理-客户资料维护-查询处理开发（查询客户）` | `EQ` | 无 warning |
| `【后台】业务管理-客户管理-客户资料维护-导出处理开发（导出客户清单）` | `EO` | 无 warning |
| `【后台】业务管理-客户管理-客户资料维护-逻辑处理开发（新增客户）` | `EI` | 无 warning |
