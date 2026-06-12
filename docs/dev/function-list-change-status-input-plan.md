# 功能清单录入模板变更状态字段调整说明

## 实施状态

已实施完成，相关提交为：

```text
cc893a7121480b8198f97eb1ea8381449dc28c8b fix: map function list change status input
a4008dd test: use change_status in FPA process fixtures
ffc8f37 Merge function list change status fixture follow-up
```

本次实施已完成以下事项：

- 输入功能清单链路已按新表头读取：H 列为 `功能过程描述`，I 列为 `变更状态`。
- 中间模块树 Markdown 已统一输出并解析新表头：`功能过程 | 功能过程描述 | 变更状态`。
- FPA 内部源需求状态已统一命名为 `change_status`，不再复用 `type`。
- FPA profile 聚合、AI prompt payload、业务事实层、采样器和真实模型验证脚本已同步改为读取 `change_status` / `变更状态`。
- `config/fpa_config.yaml.example` 已明确 `变更状态` 只是源需求状态参考，不作为 EI、EQ、EO、ILF、EIF 的 FPA 类型判定依据。
- 输入功能清单相关测试、golden fixtures、测试 Excel fixture、FPA profile/agent review 测试和 profile fixture 已切换到新字段结构。
- 项目需求清单输出模板中的 `功能过程类型` 保持不改；由于输入侧不再提供该类型，当前清单生成不会把 `变更状态` 误写入该输出列。

已完成验证：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

结果：

```text
921 passed, 2 skipped
```

另已使用主工作区真实模板 `data/in_templates/功能清单-录入模板.xlsx` 执行基础数据生成校验，确认生成的模块树表头为新表头，首行 `功能过程描述` 和 `变更状态` 分别来自 H、I 列。

补充检查结果：

- `rg -n '功能过程类型|p\.get\("type"\)|r\.get\("功能过程类型"\)|"type": "新增"|"type": "修改"|"type": "查询"' ai_gen_reimbursement_docs tests scripts config` 中，输入功能清单和 FPA 源状态链路已无旧字段读取或旧测试契约残留。
- 搜索结果中保留的 `功能过程类型` 仅位于 `constants.py` / `gen_list.py` 的项目需求清单输出模板相关逻辑。

遗留边界：

- 真实输入模板 `data/in_templates/功能清单-录入模板.xlsx` 本轮仅用于生成校验，未作为本轮文档收尾变更修改。
- 旧术语 `功能过程类型` 仅保留在项目需求清单输出模板相关常量和生成逻辑中，不再用于输入功能清单到 FPA 的传递链路。

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

## 实施步骤

### 1. 调整输入解析和中间 MD 结构

先修改 `ai_gen_reimbursement_docs/excel_source.py`，将输入功能清单的字段结构统一为新表头。

实施要点：

- 将 `tree_headers` 改为新顺序。
- 将 `generate_md_files()` 输出的模块树 Markdown 表头改为新表头。
- 将相关注释中的旧字段顺序同步改为新字段顺序。
- 将 `parse_module_tree_md()` 改为 `cells[7] -> 功能过程描述`、`cells[8] -> 变更状态`。
- 不增加旧 MD 表头兼容分支。

完成后应能保证：真实 Excel 模板读取后，内存结构和中间 MD 都不再出现输入侧 `功能过程类型`。

### 2. 调整 FPA 输入上下文构造

再修改 `ai_gen_reimbursement_docs/gen_fpa.py`。

实施要点：

- `_build_module_groups()` 从模块树行读取 `变更状态`。
- 内部流程对象使用 `change_status` 表示源变更状态。
- 不再把源输入状态写入 `type`。
- 保留 FPA 类型字段的独立语义，避免 `type` 同时承担源状态和 FPA 类型。

完成后应能保证：FPA prompt、规则后处理和结果构造读取的是明确的 `change_status`。

### 3. 调整 FPA profile 聚合逻辑

然后修改 `ai_gen_reimbursement_docs/fpa_profiles.py`。

实施要点：

- 将从 `p.get("type")` 读取源变更状态的逻辑改为 `p.get("change_status")`。
- `module_change_status(process_list)` 基于 `change_status` 聚合。
- FPA 结果行仍写入用户可见字段 `变更状态`。
- 不改变 FPA 类型判定字段的语义。

完成后应能保证：多个功能过程合并为一个 FPA 行时，输出 `变更状态` 来自源功能过程状态的聚合结果。

### 4. 调整采样器和真实模型验证脚本

同步修改：

- `ai_gen_reimbursement_docs/fpa_stability_sampler.py`
- `scripts/run_fpa_real_model_validation.py`

实施要点：

- Markdown 表头改为新表头。
- 测试或验证数据行从 `功能过程类型` 改为 `变更状态`。
- 保证采样链路、真实模型验证链路和正式生成链路使用同一输入结构。

### 5. 调整配置提示词

修改 `config/fpa_config.yaml.example`。

实施要点：

- 将“功能过程类型只能作为参考”改为“变更状态只能作为源需求状态参考”。
- 明确 `变更状态` 不作为 FPA 类型判定依据。
- 保持 FPA 类型判定仍基于功能过程名称、描述、数据维护行为、外部引用关系和规则集。

### 6. 调整测试和夹具

最后调整测试代码与 fixture。

实施要点：

- 输入功能清单相关数据从 `功能过程类型` 改为 `变更状态`。
- 旧模块树 Markdown 表头改为新表头。
- Golden case 中表示输入功能过程状态的字段改为 `变更状态` 或内部测试约定的 `change_status`。
- FPA 输出断言中的 `变更状态` 保持不变。
- 项目需求清单输出模板相关的 `功能过程类型` 暂不顺手修改。

### 7. 执行回归验证并检查遗留引用

实施完成后，按本文“回归测试矩阵”运行测试。

同时用文本搜索检查输入链路是否仍存在旧字段读取：

```powershell
rg -n "功能过程类型|p\.get\(\"type\"\)|r\.get\(\"功能过程类型\"\)" ai_gen_reimbursement_docs tests scripts config
```

搜索结果需要人工分类：

- 输入功能清单链路中的旧字段读取应清除。
- 项目需求清单输出模板或历史设计文档中的合理引用可以保留。
- FPA 类型相关 `type` 字段可以保留，但不能再表示源输入 `变更状态`。

## 验收清单

### 输入模板解析

- `2、功能清单-内容录入` 按新表头读取。
- H 列被识别为 `功能过程描述`。
- I 列被识别为 `变更状态`。
- 输入链路不再读取 `功能过程类型`。
- 旧 MD 表头不会被特殊兼容。

### 中间产物

- `0.1.gen-basedata-功能清单-模块树.md` 表头为：

```text
入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程描述 | 变更状态
```

- 中间 MD 行数据中，功能过程描述不会落到 `变更状态` 列。
- 中间 MD 行数据中，`新增`、`修改` 等状态不会落到 `功能过程描述` 列。

### FPA 内部数据结构

- 功能过程对象包含 `change_status`。
- 功能过程对象中的 `type` 不再表示源输入变更状态。
- 模块级变更状态聚合读取 `change_status`。
- FPA 类型判定和源变更状态语义保持分离。

### FPA 输出

- `FPA工作量评估.xlsx` 的 `FPA功能点估算` Sheet 仍包含 `变更状态`。
- 输出 `变更状态` 来自输入模板 I 列或基于该列的模块聚合结果。
- `变更状态` 不影响 EI、EQ、EO、ILF、EIF 的类型判定。
- 当输入同一模块下存在多个不同变更状态时，聚合行为可解释、可测试。

### 配置和提示词

- `config/fpa_config.yaml.example` 不再把输入字段称为 `功能过程类型`。
- 提示词明确 `变更状态` 不是 FPA 类型。
- 测试中覆盖提示词关键文本，避免后续回退。

### 测试与文档边界

- 输入功能清单测试数据使用 `变更状态`。
- FPA 输出测试继续使用 `变更状态`。
- 项目需求清单输出模板中的 `功能过程类型` 未经确认不改。
- 文档中保留的旧字段引用只出现在历史说明、迁移说明或明确不属于本次输入链路的位置。

## 回归测试矩阵

| 验证项 | 覆盖范围 | 建议命令或方法 | 通过标准 |
|---|---|---|---|
| 输入 Excel 解析 | `excel_source.py` 读取 `2、功能清单-内容录入` | 使用真实模板执行基础数据生成 | H 列进入 `功能过程描述`，I 列进入 `变更状态` |
| 模块树 MD 生成 | `generate_md_files()` | 检查 `0.1.gen-basedata-功能清单-模块树.md` | 表头为新表头，无输入侧 `功能过程类型` |
| 模块树 MD 解析 | `parse_module_tree_md()` | 运行 FPA acceptance 相关测试 | `cells[7]` 和 `cells[8]` 映射正确 |
| FPA 输入上下文 | `_build_module_groups()` | `.\.venv\Scripts\python.exe -m pytest tests/test_fpa_acceptance.py` | 功能过程对象有 `change_status`，描述不串列 |
| FPA profile 聚合 | `fpa_profiles.py` | `.\.venv\Scripts\python.exe -m pytest tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_golden_cases.py` | 输出变更状态来自 `change_status` |
| FPA AI 生成链路 | `gen_fpa.py` AI prompt 与后处理 | `.\.venv\Scripts\python.exe -m pytest tests/test_gen_fpa_ai.py` | AI 上下文不再使用输入侧 `功能过程类型` |
| 稳定性采样 | `fpa_stability_sampler.py` | `.\.venv\Scripts\python.exe -m pytest tests/test_fpa_stability_sampler.py` | 采样模块树使用新表头和 `变更状态` |
| 输出模板边界 | `gen_list.py` 与项目需求清单 manifest | `.\.venv\Scripts\python.exe -m pytest tests/test_gen_list_manifest.py` | 未误改项目需求清单输出模板字段 |
| SPEC 链路 | `gen_spec.py` 读取功能过程描述 | `.\.venv\Scripts\python.exe -m pytest tests/test_gen_spec_manifest.py` | SPEC 使用正确的 `功能过程描述` |
| 配置提示词 | `config/fpa_config.yaml.example` | `.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py` | 文案不再要求读取输入侧 `功能过程类型` |
| 真实模型验证脚本 | `scripts/run_fpa_real_model_validation.py` | 人工运行脚本或静态检查 | 构造的模块树表头为新表头 |
| 全局遗留引用 | 输入链路旧字段残留 | `rg -n "功能过程类型|r\\.get\\(\"功能过程类型\"\\)|p\\.get\\(\"type\"\\)" ai_gen_reimbursement_docs tests scripts config` | 输入链路无旧字段读取，保留项均有明确理由 |
| 真实模板端到端 | 从真实 xlsx 到 FPA 输出 | 使用 `data/in_templates/功能清单-录入模板.xlsx` 跑完整 FPA 链路 | FPA 输出 `变更状态` 可追溯到输入 I 列 |

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

本次变更已作为输入模板结构调整完成，而不是简单的文案替换。

最终已将 `功能过程类型` 从输入链路中移除，并建立清晰的一对一映射：

```text
输入模板 I列 变更状态 -> 中间模块树 变更状态 -> FPA 内部 change_status -> FPA 输出 变更状态
```

旧 MD 表头不需要兼容。代码、提示词、测试夹具和真实模型验证脚本已同步切换到新字段结构。
