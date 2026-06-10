# 功能清单录入模板变更状态字段调整说明

## 背景

`data/in_templates/功能清单-录入模板.xlsx` 中的 `2、功能清单-内容录入` Sheet 已调整字段结构：

- 原字段 `功能过程类型` 已改为 `变更状态`。
- `变更状态` 已移动到 I 列。
- H 列现在是 `功能过程描述`。

当前实际表头顺序为：

| 列 | 字段 |
|---|---|
| A | 入口 |
| B | 一级模块 |
| C | 二级模块 |
| D | 三级模块 |
| E | 客户端类型 |
| F | 三级模块整体功能描述 |
| G | 功能过程 |
| H | 功能过程描述 |
| I | 变更状态 |

该 `变更状态` 与 FPA 输出文件 `FPA工作量评估.xlsx` 中 `FPA功能点估算` Sheet 的 `变更状态` 字段对应。

## 目标行为

系统应将功能清单录入模板中的 `变更状态` 作为源需求的变更状态读取，并沿链路传递到 FPA 功能点估算结果中：

```text
功能清单-录入模板.xlsx
  -> 2、功能清单-内容录入!I列 变更状态
  -> 0.1.gen-basedata-功能清单-模块树.md 的 变更状态
  -> FPA 内部 change_status
  -> FPA工作量评估.xlsx / FPA功能点估算 / 变更状态
```

不再把该字段理解为 `功能过程类型`。`变更状态` 不是 EI、EQ、EO、ILF、EIF 等 FPA 类型，也不是功能过程分类；它只表示源需求或功能过程的新增、修改等变更状态。

## 兼容策略

本系统尚未上线，本次调整不保留旧版本兼容路径。

因此不需要兼容旧 MD 表头：

```text
入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述
```

后续统一采用新 MD 表头：

```text
入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程描述 | 变更状态
```

## 需要修改的代码范围

### `ai_gen_reimbursement_docs/excel_source.py`

该文件负责读取功能清单 Excel，并生成或解析中间模块树 Markdown，是本次变更的核心入口。

需要调整：

- `tree_headers` 中的字段顺序。
- `generate_md_files()` 写出的模块树 Markdown 表头。
- 模块树 Markdown 行注释和字段说明。
- `parse_module_tree_md()` 的解析逻辑。

新的解析关系应为：

| 单元格索引 | 字段 |
|---|---|
| `cells[0]` | 入口 |
| `cells[1]` | 一级模块 |
| `cells[2]` | 二级模块 |
| `cells[3]` | 三级模块 |
| `cells[4]` | 客户端类型 |
| `cells[5]` | 三级模块整体功能描述 |
| `cells[6]` | 功能过程 |
| `cells[7]` | 功能过程描述 |
| `cells[8]` | 变更状态 |

不再生成或解析 `功能过程类型`。

### `ai_gen_reimbursement_docs/gen_fpa.py`

该文件会将模块树行组装为 FPA 输入上下文。

当前风险点：

- `_build_module_groups()` 中仍从 `r.get("功能过程类型")` 读取并写入内部 `type` 字段。
- 这会导致新模板下把 H 列 `功能过程描述` 误当成类型，或在旧链路中继续污染 FPA 变更状态推导。

建议调整：

- 从 `r.get("变更状态")` 读取源状态。
- 内部字段明确命名为 `change_status`。
- 如果仍需要保留 `type` 字段给 FPA 类型使用，应避免把输入 `变更状态` 塞入 `type`。
- FPA 输出行中的 `变更状态` 应优先来自源功能过程或模块聚合得到的 `change_status`。

### `ai_gen_reimbursement_docs/fpa_profiles.py`

该文件中已有多处 FPA profile 逻辑会构造或聚合 `变更状态`。

当前风险点：

- 部分逻辑使用 `p.get("type")` 作为 `change_status` 来源。
- `module_change_status(process_list)` 可能基于 `type` 聚合。

需要调整：

- 统一使用 `p.get("change_status")` 读取输入变更状态。
- `module_change_status(process_list)` 应基于 `change_status` 聚合。
- 构造 FPA 结果行时，`变更状态` 仍写入输出表的 `变更状态` 字段。

### `ai_gen_reimbursement_docs/fpa_stability_sampler.py`

该文件会构造用于稳定性采样的模块树 Markdown。

需要调整：

- 硬编码模块树表头改为新表头。
- 行数据从 `功能过程类型` 改为 `变更状态`。
- `功能过程描述` 和 `变更状态` 的列顺序按 H、I 列同步。

### `scripts/run_fpa_real_model_validation.py`

该脚本用于真实模型验证，也硬编码了旧模块树表头。

需要调整：

- 表头改为新表头。
- 行数据字段从 `功能过程类型` 改为 `变更状态`。
- 保证真实模型验证输入与正式链路一致。

## 配置和提示词需要同步

### `config/fpa_config.yaml.example`

现有提示词中包含类似表述：

```text
输入中的功能过程类型只能作为参考；当功能过程类型与功能过程名称或描述冲突时，以名称和描述为准。
```

需要改为围绕 `变更状态` 的表述，例如：

```text
输入中的变更状态只能作为源需求状态参考；不得将变更状态当作 FPA 类型判定依据。
当变更状态与功能过程名称或描述冲突时，以功能过程名称和描述中的业务行为为准。
```

注意：这里的核心不是让 AI 用 `变更状态` 判断 EI、EQ、EO、ILF、EIF，而是避免把 `新增`、`修改` 等源状态误当成 FPA 类型。

### `config/system_config.yaml.example`

该文件目前主要配置 `func_list: "2、功能清单-内容录入"` 等 Sheet 名称，不涉及列名映射。本次通常不需要修改。

## 测试和夹具需要同步

输入功能清单相关测试和夹具需要从 `功能过程类型` 改为 `变更状态`。

重点检查：

- `tests/test_fpa_acceptance.py`
- `tests/test_gen_fpa_ai.py`
- `tests/test_gen_list_manifest.py`
- `tests/test_gen_spec_manifest.py`
- `tests/test_fpa_stability_sampler.py`
- `tests/test_gen_fpa_strict_profile.py`
- `tests/test_gen_fpa_golden_cases.py`
- `tests/fixtures/fpa_golden_cases/*.json`

处理原则：

- 如果测试数据表示的是输入功能清单，应改成 `变更状态`。
- 如果测试目标是输出 `FPA工作量评估.xlsx` 的 `变更状态`，字段名继续保持 `变更状态`。
- 如果测试目标是“项目需求清单”输出模板中的 `功能过程类型`，不应盲目改动，需确认该输出模板是否也要变更。

## 不建议本次修改的内容

### `ai_gen_reimbursement_docs/constants.py` 中的项目需求清单列常量

例如：

```python
REQ_COL_PROC_TYPE = 7     # 功能过程类型
REQ_COL_KEY_MAP = {
    5: "二级模块", 6: "三级模块", 7: "功能过程类型",
}
```

这些常量看起来服务于“项目需求清单”输出模板，而不是 `2、功能清单-内容录入` 输入 Sheet。

除非同时决定调整项目需求清单输出模板，否则本次不建议修改这些常量。

### FPA 输出表中的 `变更状态`

FPA 输出表本来就存在 `变更状态` 字段，本次不是删除或重命名该字段，而是把输入模板 I 列的 `变更状态` 正确传递到该输出字段。

## 风险点

### 字段错位

如果只改 Excel 模板，不改解析代码，会出现：

- H 列 `功能过程描述` 被读成旧字段 `功能过程类型`。
- I 列 `变更状态` 被读成 `功能过程描述`。
- FPA AI prompt 和规则上下文被错误污染。
- FPA 输出中的 `变更状态` 无法可靠追溯到源功能清单。

### `type` 语义混淆

历史代码中 `type` 有时表示源输入的功能过程类型，有时又容易与 FPA 类型混淆。

本次建议将源输入状态明确命名为 `change_status`，避免和 FPA 类型字段混用。

### 项目需求清单输出模板是否另行调整

当前讨论只确认了输入模板 `2、功能清单-内容录入` 的变化，以及它到 FPA 工作量评估表 `变更状态` 的映射。

项目需求清单输出模板中的 `功能过程类型` 是否也要变更，尚未在本次讨论中确认，不应顺手改。

## 建议验证方式

实施代码修改后，至少运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_acceptance.py tests/test_gen_fpa_ai.py tests/test_gen_list_manifest.py tests/test_gen_spec_manifest.py
```

如果改动覆盖 FPA profile 和稳定性采样，还应补充运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_stability_sampler.py tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_golden_cases.py
```

还应使用真实模板执行一次基础数据生成或完整 FPA 链路，检查：

- `0.1.gen-basedata-功能清单-模块树.md` 表头为新表头。
- Markdown 中 H 列为 `功能过程描述`。
- Markdown 中 I 列为 `变更状态`。
- FPA 输出文件 `FPA工作量评估.xlsx` 的 `FPA功能点估算` Sheet 中 `变更状态` 来自输入模板 I 列。

## 本轮结论

本次变更应作为输入模板结构调整来处理，而不是简单的文案替换。

最终目标是将 `功能过程类型` 从输入链路中移除，并建立清晰的一对一映射：

```text
输入模板 I列 变更状态 -> 中间模块树 变更状态 -> FPA 内部 change_status -> FPA 输出 变更状态
```

旧 MD 表头不需要兼容。代码、提示词、测试夹具和真实模型验证脚本应同步切换到新字段结构。
