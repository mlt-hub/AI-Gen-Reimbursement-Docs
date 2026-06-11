# unified_ui rule-first 计算依据归类为空诊断记录

日期：2026-06-11

## 问题

测试目录：

`F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\8.3-unfied-ui（rule-first）\`

目标输出：

`关于构建垂直行业场景化营销的需求\闽市移需【202501】17658 号-关于构建垂直行业场景化营销的需求（和乐业）-FPA工作量评估.xlsx`

现象：

- `FPA功能点估算` sheet 中，F 列表头为 `计算依据归类`。
- 数据行 F3:F77 均为空。
- 同一批数据行的 G 列 `计算依据说明` 有规则兜底说明文本。

## 复现确认

使用 `openpyxl` 读取输出文件确认：

- `FPA功能点估算` 行数为 77，列数为 14。
- F 列非空单元格只有表头。
- 第一条数据行的 `生成方式` 在 check 文件中为 `fallback`。

对应 check 文件：

`闽市移需【202501】17658 号-关于构建垂直行业场景化营销的需求（和乐业）-FPA工作量评估-check.xlsx`

其中 `规则命中详情` 显示：

- `rule_set = unified_ui_rs`
- `生成方式 = fallback`
- 规则命中包括 `unified_ui.ui_merge`、`unified_ui.keyword.ilf`
- `Warnings` 中有 `规则优先策略未调用 AI：规则结果覆盖完整且基础字段有效`

## 根因

本次输出使用的是 `unified_ui` profile 的 `rules_first` 策略。规则优先判定规则结果完整，因此未调用 AI。

Excel 导出链路本身会写入 `计算依据归类`：

- `ai_gen_reimbursement_docs/gen_fpa.py` 中 `generate_fpa_xlsx_from_md` 将 `classification_basis` 映射到表头 `计算依据归类`。
- 导出时逐列写入 `fpa_row["计算依据归类"]`。

但 `unified_ui` 规则兜底行构造时，字段被初始化为空：

- `ai_gen_reimbursement_docs/fpa_profiles.py` 的 `CustomRulesProfile.fallback_rows_for_l3` 中，界面合并行设置 `"计算依据归类": ""`。
- 同函数中，功能过程逻辑接口行同样设置 `"计算依据归类": ""`。

当前只有 strict_fpa 有专用补齐逻辑：

- `ai_gen_reimbursement_docs/gen_fpa.py` 中 `_fill_strict_fpa_fallback_classification_basis(...)`
- 该函数第一层条件限制为 `profile.name == "strict_fpa"`。
- 因此 `unified_ui` / `unified_ui_rs` 的 fallback 行不会按 FPA 类型反查模板判定原则来补齐 `计算依据归类`。

所以 F 列为空不是模板列映射问题，而是 `unified_ui` 规则兜底输出未生成该字段。

## 影响范围

已确认影响：

- `unified_ui` profile
- `rules_first` 或 `rules_only` 且规则结果直接采用 fallback 行的场景
- Excel 正式输出 `FPA功能点估算` 的 `计算依据归类` 列
- 预览接口中的 `classification_basis` 也会随之为空

不属于本问题：

- `strict_fpa` fallback 行已有补齐测试覆盖。
- AI 输出行如果提供 `classification_basis_index`，后处理会通过判定原则序号补齐 `计算依据归类`。
- Excel manifest 表头定位和导出列映射工作正常。

## 建议修复方向

建议将 fallback 行补齐 `计算依据归类` 的能力从 strict_fpa 专用扩展为 profile 可复用逻辑。

可选实现方向：

1. 将 `_fill_strict_fpa_fallback_classification_basis` 改为通用函数，例如 `_fill_fallback_classification_basis`。
2. 根据 `row["类型"]` 与模板判定原则匹配，补齐 `row["计算依据归类"]`。
3. 对 `unified_ui` 增加规则命中记录，例如 `unified_ui.fallback_classification_basis`。
4. 保留 strict_fpa 既有行为和测试预期。
5. 新增 `unified_ui_rs` / `rules_first` 回归测试，断言 fallback 行 `计算依据归类` 非空并来自判定原则。

## 验证建议

修复后建议执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py
```

并用同一测试目录重新生成 `gen-fpa` 输出，确认：

- `FPA功能点估算` 的 F 列数据行不再为空。
- `-check.xlsx` 的 `规则命中详情` 出现对应补齐规则命中。
- `Warnings` 不新增无关质量问题。
