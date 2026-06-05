# gen-fpa 阶段工作量计算逻辑

## 目标口径

`gen-fpa` 阶段支持通过配置选择两种 `调整值（FP）` 计算方式：

| 计算方式 | 含义 | 适用场景 |
|---|---|---|
| `legacy_workload` | 简化工作量口径，按配置中的类型权重表给出调整值。 | 需要沿用简化估算模型或快速生成时使用。 |
| `standard_fpa` | 按标准 FPA 类型、复杂度矩阵和权重表计算 FP。复杂度由 AI 输出证据，代码按矩阵复算。 | 需要更接近 FPA 标准、可审计复杂度依据和正式评审时使用。 |

无论选择哪种方式，最终工作量汇总仍沿用：

```text
单行 FPA 工作量 = 调整值 × 要素数量
总工作量 = 所有行工作量求和
```

其中：

- `调整值`
- `要素数量`

`legacy_workload` 中，`调整值` 是简化权重。`standard_fpa` 中，`调整值` 是按类型和复杂度得到的 FP 权重。

## 配置方式

建议在 FPA 专用配置 `fpa_config.yaml` 中增加：

```yaml
adjustment_value:
  method: standard_fpa
  complexity_source: ai
  fallback_complexity: low
  standard_fpa:
    weights:
      ILF:
        low: 7
        medium: 10
        high: 15
      EIF:
        low: 5
        medium: 7
        high: 10
      EI:
        low: 3
        medium: 4
        high: 6
      EO:
        low: 4
        medium: 5
        high: 7
      EQ:
        low: 3
        medium: 4
        high: 6
    data_function_complexity_matrix:
      # ILF/EIF: DET + RET，按 docs/fpa/fpa-calculation-method.md 的数据功能矩阵配置。
      # 具体结构由实现阶段确定，但必须完整表达 RET/DET 分段到 low/medium/high 的映射。
    transaction_complexity_matrices:
      # EI/EO/EQ: DET + FTR，按 docs/fpa/fpa-calculation-method.md 的事务功能矩阵配置。
      # EI 与 EO/EQ 的 DET/FTR 分段不同，应分别配置。
```

字段说明：

| 字段 | 可选值 | 说明 |
|---|---|---|
| `method` | `legacy_workload` / `standard_fpa` | 决定 `调整值` 的计算口径。 |
| `complexity_source` | `ai` / `explicit` / `default` | `standard_fpa` 下复杂度来源。当前推荐使用 `ai`。 |
| `fallback_complexity` | `low` / `medium` / `high` | AI 或显式字段缺失时的兜底复杂度，默认建议为 `low`。 |
| `standard_fpa.weights` | 类型到低/中/高权重表 | `standard_fpa` 下 `调整值（FP）` 的来源。 |
| `standard_fpa.data_function_complexity_matrix` | DET/RET 到复杂度映射 | `ILF` / `EIF` 复杂度矩阵。 |
| `standard_fpa.transaction_complexity_matrices` | DET/FTR 到复杂度映射 | `EI` / `EO` / `EQ` 复杂度矩阵。 |

`adjustment_value` 是必填配置。缺少该配置、缺少 `legacy_workload.type_weights` 或缺少 `default` 权重时，应直接报配置错误。系统不提供代码内置的历史权重回退。

## 字段来源

每一行 FPA 数据会包含以下关键字段：

- `新增/修改功能点`
- `类型`
- `计算依据归类`
- `计算依据说明`
- `变更状态`
- `调整值`
- `要素数量`

其中：

- `调整值` 根据配置选择的计算方式生成。
- `要素数量` 来自代码内部可选字段 `element_count`；如果行数据中不存在该字段，则默认使用 `1`。

`standard_fpa` 下还应保留以下内部审计字段：

| 字段 | 含义 |
|---|---|
| `复杂度` | AI 判定或代码复算后的复杂度，取值为低/中/高。 |
| `DET` | 用户可识别的数据项数量。 |
| `RET` | 数据功能中的用户可识别记录子组数量。 |
| `FTR` | 事务功能读取或维护的 ILF/EIF 数量。 |
| `复杂度说明` | AI 对 DET/RET/FTR 和复杂度判断的证据说明。 |
| `调整值计算方式` | 当前行使用的计算方式，例如 `legacy_workload` 或 `standard_fpa`。 |

## element_count 当前实际值

`element_count` 是代码内部字段，对应最终表格中的 `要素数量`。当前实现只读取它，不主动生成它：

```text
要素数量 = int(element_count or 1)
```

也就是说：

- 如果行数据中存在有效的 `element_count`，则使用该值。
- 如果行数据中没有 `element_count`，则使用 `1`。
- 如果 `element_count` 是空值、`0` 或 `None`，也会回退为 `1`。

截至当前实现，仓库中没有其他代码分支主动给 `element_count` 赋值。因此在常规 `gen-fpa` 流程中：

```text
最终要素数量 = 1
```

除非后续某个规则分支或 AI 输出显式提供 `element_count`，否则每行的 `要素数量` 都按 `1` 计算。

## legacy_workload 调整值规则

`legacy_workload` 使用配置中的类型权重表计算 `调整值`。示例配置可以延续历史取值：

```text
EI => 2
其他类型 => 1
```

也就是说：

```text
类型为 EI 的功能点，默认工作量权重为 2
类型为 EO / EQ / ILF / EIF 等其他功能点，默认工作量权重为 1
```

对应配置示例为：

```yaml
adjustment_value:
  method: legacy_workload
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
```

项目可以按需要覆盖任意 FPA 类型的权重，例如为 `EO` 单独配置权重：

```yaml
adjustment_value:
  method: legacy_workload
  legacy_workload:
    type_weights:
      EI: 2
      EO: 3
      default: 1
```

读取规则：

- 优先读取当前 `类型` 对应的权重。
- 当前 `类型` 未配置时读取 `default`。
- `default` 必须配置，作为配置文件中的显式兜底权重。
- `adjustment_value` 不提供代码内置兼容回退；项目必须在配置文件中明确写出权重。

实现约束：

- 不允许在代码中硬编码 `EI => 2`、`其他类型 => 1` 这类分支。
- 不允许在配置缺失、`type_weights` 缺失或 `default` 缺失时静默回退。
- 不允许为了防御异常而在运行路径中返回固定 `1`；配置错误应暴露为配置错误。

## standard_fpa 调整值规则

`standard_fpa` 按配置中的 FPA 复杂度矩阵和权重表计算 `调整值（FP）`。

`docs/fpa/fpa-calculation-method.md` 描述标准 FPA 方法和建议矩阵，`fpa_config.yaml` 承载运行时实际采用的矩阵和权重。实现时不得把标准权重表或复杂度矩阵硬编码到代码中。

### AI 复杂度判定

AI 不直接决定最终 `调整值（FP）`。AI 负责输出复杂度判定证据，代码负责按矩阵复算复杂度和权重。

生成 AI prompt 时，应从当前 `fpa_config.yaml` 中读取并注入以下运行时配置：

- 当前业务上下文：当前模块、功能过程、功能过程描述、项目领域上下文、内部/外部数据组和外部服务上下文。
- FPA 计数原则：用户视角、业务意图、系统边界、不要按按钮/页面/接口/数据库表/字段/代码组件计数。
- FPA 类型说明：`ILF` / `EIF` / `EI` / `EO` / `EQ`。
- DET / RET / FTR 识别口径。
- 计算依据归类判定原则 `judgement_rules`。
- `standard_fpa.data_function_complexity_matrix`。
- `standard_fpa.transaction_complexity_matrices`。
- `standard_fpa.weights`。
- 输出 JSON schema 和不确定性处理规则。

注入这些配置的目的，是让 AI 的 DET/RET/FTR 识别、复杂度初判和 `complexity_reason` 与当前项目配置口径一致。AI 不得依赖自身记忆中的 FPA 标准表，也不得编造 prompt 中没有提供的矩阵或权重。

`rule_set_config` 不应作为完整结构注入 AI prompt。外部数据规则、内部数据规则、类型映射规则、关键词规则、覆盖规则、冲突规则和行规划规则属于代码规则/后处理路径，应继续由程序执行并进入 audit trace，而不是交给 AI 自行解释或模拟执行。

在 `rules_first` 等需要 AI 复核或补充的场景中，可以把规则执行结果的摘要喂给 AI，例如“已有规则行覆盖了哪些功能过程”“仍缺少哪些类型的候选行”“为什么需要补充”。不应把完整规则配置表交给 AI。

prompt 约束应明确：

```text
你可以参考以下配置矩阵判断复杂度，但最终调整值由系统代码复算。
不要自行编造未提供的复杂度矩阵或权重表。
不要把你返回的 FP 作为最终调整值；如需说明 FP，只能作为解释性参考。
不要模拟执行未提供的 rule_set_config；规则集由系统代码执行。
如果输入证据不足，输出保守复杂度并说明不确定点。
```

AI 行输出建议包含：

```json
{
  "name": "<功能点名称>",
  "type": "EI/EO/EQ/ILF/EIF",
  "classification_basis_index": 1,
  "explanation": "来源场景：...\n业务数据：...\n业务规则：...\n计算说明：...",
  "complexity": "low/medium/high",
  "det_count": 8,
  "ret_count": null,
  "ftr_count": 2,
  "complexity_reason": "输入包含申请人、金额、费用类型等 8 个用户可识别数据项，维护报销单和审批记录 2 个逻辑数据组，按 EI 矩阵为中。"
}
```

字段要求：

- `ILF` / `EIF` 行输出 `det_count`、`ret_count` 和 `complexity_reason`。
- `EI` / `EO` / `EQ` 行输出 `det_count`、`ftr_count` 和 `complexity_reason`。
- 无法可靠判断 DET、RET 或 FTR 时，AI 应给出保守复杂度，并在 `complexity_reason` 中说明不确定点。
- 即使 AI 返回了 `complexity`，代码仍应优先使用 DET/RET/FTR 按矩阵复算复杂度。

### 代码复算规则

代码计算顺序：

1. 从当前 FPA 配置读取 `standard_fpa` 权重表和复杂度矩阵。
2. 根据 `类型` 判断数据功能还是事务功能。
3. 如果存在有效的 DET + RET/FTR，按配置中的复杂度矩阵复算复杂度。
4. 如果指标缺失但存在 AI 输出的 `complexity`，使用 AI 输出复杂度。
5. 如果复杂度仍缺失，使用配置中的 `fallback_complexity`。
6. 根据类型和复杂度，从配置中的 `standard_fpa.weights` 得到 `调整值（FP）`。

标准权重配置示例如下：

| 类型 | 低 | 中 | 高 |
|---|---:|---:|---:|
| ILF | 7 | 10 | 15 |
| EIF | 5 | 7 | 10 |
| EI | 3 | 4 | 6 |
| EO | 4 | 5 | 7 |
| EQ | 3 | 4 | 6 |

实现约束：

- 不允许在代码中硬编码 `ILF/EI/EO/EQ/EIF` 的低/中/高权重表。
- 不允许在代码中硬编码 DET/RET/FTR 到低/中/高的复杂度矩阵。
- 缺少 `standard_fpa.weights`、复杂度矩阵或必要类型/复杂度权重时，应直接报配置错误。
- `docs/fpa/fpa-calculation-method.md` 中的标准表只能作为配置模板来源，不能作为代码内置默认值。

## check Excel 审计展示

`standard_fpa` 下，check Excel 应新增复杂度审计字段，便于人工复核 AI 判定和代码复算结果。

建议在 `FPA结果` sheet 中新增：

| 列名 | 说明 |
|---|---|
| `复杂度` | 最终采用的复杂度，低/中/高。 |
| `DET` | 用户可识别数据项数量。 |
| `RET` | 数据功能记录子组数量；事务功能留空。 |
| `FTR` | 事务功能读取或维护的 ILF/EIF 数量；数据功能留空。 |
| `复杂度说明` | AI 输出的复杂度证据，以及代码矩阵复算说明。 |
| `调整值计算方式` | 当前行使用的计算方式。 |

展示规则：

- `ILF` / `EIF` 展示 `DET` + `RET`，`FTR` 留空。
- `EI` / `EO` / `EQ` 展示 `DET` + `FTR`，`RET` 留空。
- `legacy_workload` 下可以保留这些列为空，或仅展示 `调整值计算方式=legacy_workload`。
- 如果正式 Excel 模板暂不新增列，复杂度审计先进入 check Excel，不影响正式交付模板结构。

## Markdown 汇总

生成 FPA Markdown 时，系统会根据每一行的：

```text
调整值 × 要素数量
```

计算总工作量，并写入 FPA 工作量总和文件。

## Excel 公式

导出 Excel 时，系统会将数据写入模板：

| 列 | 字段 |
|---|---|
| J 列 | 调整值 |
| K 列 | 要素数量 |
| L 列 | FPA 工作量 |

L 列公式为：

```text
=J3*K3
=J4*K4
...
```

汇总公式为：

```text
=SUM(L3:L最后一行)
```

## 结论

`gen-fpa` 阶段的工作量计算应收敛为配置驱动模型：

```text
FPA 工作量 = 调整值 × 要素数量
```

其中：

- `legacy_workload` 使用配置化简化权重；示例配置延续历史结果。
- `standard_fpa` 由 AI 输出复杂度证据，代码按配置中的 FPA 矩阵复算复杂度并按配置权重计算 FP。
- check Excel 展示复杂度、DET、RET、FTR、复杂度说明和调整值计算方式，保证人工审阅时可追溯。
