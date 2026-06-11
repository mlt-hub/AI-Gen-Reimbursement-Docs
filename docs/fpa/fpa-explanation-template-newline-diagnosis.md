# FPA explanation_template 换行未生效排查

## 背景

测试目录：

`F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\8.4-unified-ui（rule-first）-完整\`

现象：

`config/fpa_config.yaml.example` 或实际配置中声明：

```yaml
explanation_template: "{name}，具体为以下：\n{items}"
```

但生成的 FPA 工作量评估中，`计算依据说明` 显示为：

```text
【地市后台】...界面开发，具体为以下： 1、添加垂直行业...
```

预期应保留 `具体为以下：` 后的换行：

```text
【地市后台】...界面开发，具体为以下：
1、添加垂直行业...
```

## 当前结论

`explanation_template` 中的 `\n` 不是没有解析，而是在写入 FPA Markdown 中间表时被压平成空格。

## 链路分析

### 1. fallback 行构造阶段

`ai_gen_reimbursement_docs/fpa_profiles.py` 中的 fallback 行会使用配置模板生成 `计算依据说明`：

```python
ui_rule.explanation_template.format(name=ui_name, items=ui_detail)
process_rule.explanation_template.format(...)
```

此时 YAML 中的 `\n` 会成为真实换行。

### 2. 写入 FPA Markdown 阶段

`ai_gen_reimbursement_docs/gen_fpa.py` 的 `_write_fpa_rows_md` 写 pipe table 时，对 `计算依据说明` 做了换行压平：

```python
str(row.get("计算依据说明", "")).replace("|", chr(92) + "|").replace(chr(10), " ")
```

因此 `具体为以下：\n{items}` 在 `1.1.gen-fpa-FPA-模板.md` / `1.3.gen-fpa-AI填充-FPA.md` 中变成：

```text
具体为以下： 1、...
```

### 3. Excel 生成阶段

`generate_fpa_xlsx_from_md` 从 Markdown 表反解析行数据。由于 Markdown 中已经没有原始换行，Excel 写入时无法恢复模板中的换行。

`_format_fpa_explanation` 会按部分标记重新加换行，例如 `；`、`业务规则`、`涉及表` 等；但当前逻辑不识别：

- `具体为以下：`
- `1、2、3、` 这类中文序号

所以测试输出中能看到部分由 `；` 补出来的换行，但看不到 `explanation_template` 里 `具体为以下：\n{items}` 的换行。

## 根因

FPA Markdown 中间表当前用普通 pipe table 承载结构化行数据。pipe table 是按单行解析的，直接写入真实换行会破坏表格行结构，因此实现选择把 `\n` 替换为空格。

这会导致配置模板中的排版意图丢失。

## 推荐修复方案

### 方案 A：Markdown 单元格换行可逆编码

写入 Markdown 表时，将单元格内部换行编码为 `<br>`：

```text
具体为以下：<br>1、...
```

读取 Markdown 表时，再将 `<br>` 还原为 `\n`。

优点：

- 不破坏当前 pipe table 的单行解析结构。
- Markdown 预览中 `<br>` 也能表达换行。
- Excel 生成阶段可以拿回真实换行。
- 改动集中在 FPA Markdown 序列化/反序列化边界。

注意：

- 需要统一处理 `计算依据说明`、`复杂度说明` 等可能含换行的字段。
- 需要确认 `<br>` 是否会和用户原始文本冲突；如需更严格，可只在读写边界做受控转义。

### 方案 B：Excel 写入阶段增强格式化兜底

在 `_format_fpa_explanation` 中补充规则：

```python
text = text.replace("具体为以下：", "具体为以下：\n")
text = re.sub(r"(?<!\n)\s+(?=\d+、)", "\n", text)
```

优点：

- 改动小。
- 能修复当前测试样例中 `具体为以下： 1、...` 的显示问题。

缺点：

- 这是启发式修复，不能真正保留模板中的任意换行。
- 如果未来模板中有更多自定义排版，仍可能丢失。

## 建议实施路径

推荐优先实施方案 A，并把方案 B 作为 Excel 展示层兜底。

实施步骤：

1. 新增 FPA Markdown 单元格转义/反转义函数。
2. `_write_fpa_rows_md` 写入 `计算依据说明`、`复杂度说明` 时，把内部换行编码为 `<br>`。
3. `_read_fpa_rows_md_for_audit` 与 `generate_fpa_xlsx_from_md` 读取相关字段时，把 `<br>` 解码为 `\n`。
4. `_format_fpa_explanation` 增强 `具体为以下：` 和中文序号换行兜底。
5. 增加回归测试，覆盖 `explanation_template: "{name}，具体为以下：\n{items}"`。

## 验收标准

1. `1.1.gen-fpa-FPA-模板.md` 或 `1.3.gen-fpa-AI填充-FPA.md` 中，`计算依据说明` 的换行语义不再被纯空格吞掉，至少以 `<br>` 保留。
2. 生成的 `FPA工作量评估.xlsx` 中，`计算依据说明` 在 `具体为以下：` 后换行。
3. `1、2、3、` 等条目序号在 Excel 中按行展示。
4. 现有 FPA Markdown 表解析不因单元格换行而断行。
5. 原有 `|` 转义行为不退化。
6. 相关自动化测试通过。

## 风险

- 如果有人直接编辑 Markdown 表中的 `<br>`，读取时会被当作换行还原。
- 如果历史 Markdown 中已经存在用户手写的 `<br>`，新逻辑可能改变其进入 Excel 后的表现。
- 若只做方案 B，Markdown 中间产物仍然丢失模板换行，不适合作为长期方案。
