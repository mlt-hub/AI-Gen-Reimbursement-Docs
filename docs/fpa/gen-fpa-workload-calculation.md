# gen-fpa 阶段工作量计算逻辑

## 目标口径

`gen-fpa` 阶段支持通过配置选择两种 `调整值（FP）` 计算方式：

| 计算方式 | 含义 | 适用场景 |
|---|---|---|
| `legacy_workload` | 现有简化工作量口径，按类型给出简化调整值。 | 需要延续现有估算结果、快速生成或模板兼容时使用。 |
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
```

字段说明：

| 字段 | 可选值 | 说明 |
|---|---|---|
| `method` | `legacy_workload` / `standard_fpa` | 决定 `调整值` 的计算口径。 |
| `complexity_source` | `ai` / `explicit` / `default` | `standard_fpa` 下复杂度来源。当前推荐使用 `ai`。 |
| `fallback_complexity` | `low` / `medium` / `high` | AI 或显式字段缺失时的兜底复杂度，默认建议为 `low`。 |

`legacy_workload` 是兼容模式；未配置时应保持现有行为，避免既有结果突然变化。

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

`legacy_workload` 沿用当前实现中的规则：

```text
EI => 2
其他类型 => 1
```

也就是说：

```text
类型为 EI 的功能点，默认工作量权重为 2
类型为 EO / EQ / ILF / EIF 等其他功能点，默认工作量权重为 1
```

## standard_fpa 调整值规则

`standard_fpa` 按 `docs/fpa/fpa-calculation-method.md` 中的 FPA 权重表计算 `调整值（FP）`。

### AI 复杂度判定

AI 不直接决定最终 `调整值（FP）`。AI 负责输出复杂度判定证据，代码负责按矩阵复算复杂度和权重。

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

1. 根据 `类型` 判断数据功能还是事务功能。
2. 如果存在有效的 DET + RET/FTR，按复杂度矩阵复算复杂度。
3. 如果指标缺失但存在 AI 输出的 `complexity`，使用 AI 输出复杂度。
4. 如果复杂度仍缺失，使用配置中的 `fallback_complexity`。
5. 根据类型和复杂度，从标准权重表得到 `调整值（FP）`。

标准权重如下：

| 类型 | 低 | 中 | 高 |
|---|---:|---:|---:|
| ILF | 7 | 10 | 15 |
| EIF | 5 | 7 | 10 |
| EI | 3 | 4 | 6 |
| EO | 4 | 5 | 7 |
| EQ | 3 | 4 | 6 |

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

- `legacy_workload` 保持现有简化权重，兼容历史结果。
- `standard_fpa` 由 AI 输出复杂度证据，代码按 FPA 矩阵复算复杂度和 FP 权重。
- check Excel 展示复杂度、DET、RET、FTR、复杂度说明和调整值计算方式，保证人工审阅时可追溯。
