# fallback 行计算依据归类同步判定方案

日期：2026-06-11

## 背景

在 `unified_ui` + `rules_first` 场景中，规则 fallback 行已经能判定 `类型`，但 `计算依据归类` 仍为空。已记录的诊断见：

`docs/fpa/unified-ui-rule-first-classification-basis-diagnosis.md`

根因不是 Excel 导出列映射，而是 fallback 行构造阶段没有同步写入 `计算依据归类`。

## 目标行为

fallback 行生成时，应在判定 `类型` 的同一阶段同步判定并写入 `计算依据归类`。

目标字段一起产出：

- `类型`
- `计算依据归类`
- `计算依据说明`
- `类型理由`
- `_规则命中详情`

后处理阶段只负责防漏：如果某条 fallback 行因为旧路径、异常路径或判定原则配置缺失导致 `计算依据归类` 仍为空，再做兜底补齐或记录可审计 warning。

目标流程：

```text
输入功能过程
  -> 规则/AI 判定功能点类型
  -> 同步选择计算依据归类
  -> 构造 FPA 行
  -> 后处理补漏和校验
  -> 导出 Excel
```

## 推荐方案

采用方案 A：让 `fallback_rows_for_l3` 接收 `judgement_rules`，在 fallback 行构造阶段同步填入 `计算依据归类`。

建议签名：

```python
def fallback_rows_for_l3(
    self,
    group: dict[str, object],
    meta: dict[str, str],
    start_seq: int = 1,
    judgement_rules: list[str] | None = None,
) -> list[dict[str, object]]:
    ...
```

`judgement_rules` 保持可选，避免旧调用点或测试替身立即失效。

## 设计细节

### 1. 抽出通用依据选择器

将现有 strict_fpa 专用的类型到判定原则匹配逻辑抽成通用函数。

建议函数：

```python
def _basis_for_fpa_type(fpa_type: str, judgement_rules: list[str]) -> str:
    ...
```

该函数可继续复用现有关键词优先级：

- `ILF` 匹配内部逻辑数据组、后台数据库、表、数据组等原则。
- `EIF` 匹配外部接口文件、外部应用维护数据组等原则。
- `EI` 匹配输入、维护、增加/修改界面、进入系统边界等原则。
- `EQ` 匹配查询、返回、展示等原则。
- `EO` 匹配报表、统计、文件、导出、输出等原则。

如果匹配不到，返回空字符串。

### 2. profile 层构造行时同步写入

`CustomRulesProfile.fallback_rows_for_l3(...)` 中有两类主要行：

界面合并行：

```python
fpa_type = ui_rule.fpa_type
basis = _basis_for_fpa_type(fpa_type, judgement_rules or [])
```

功能过程行：

```python
fpa_type, reason = self.infer_type(point_name, desc)
basis = _basis_for_fpa_type(fpa_type, judgement_rules or [])
```

构造 row 时写入：

```python
"类型": fpa_type,
"计算依据归类": basis,
"类型理由": reason,
```

### 3. 记录规则命中详情

如果成功写入 `计算依据归类`，应增加 `_规则命中详情`，便于 check 文件追溯。

建议规则 ID：

```text
{profile.name}.fallback_classification_basis
```

例如：

- `unified_ui.fallback_classification_basis`
- `strict_fpa.fallback_classification_basis`
- `ui_api_mapping.fallback_classification_basis`

建议规则说明：

```text
规则兜底行按 FPA 类型匹配判定原则，写入计算依据归类。
```

### 4. 保留通用后处理补漏

将当前 strict_fpa 专用函数：

```python
_fill_strict_fpa_fallback_classification_basis(...)
```

调整为通用补漏函数：

```python
_fill_fallback_classification_basis(...)
```

职责：

- 只处理 `生成方式` 为 `fallback` 或 `rules_fallback` 的行。
- 如果 `计算依据归类` 已有值，不覆盖。
- 如果为空，则按 `类型` 再匹配一次判定原则。
- 补齐时记录 `{profile.name}.fallback_classification_basis`。
- 如果匹配不到，可记录 warning 或只保留为空，具体取决于是否要把缺失视为质量问题。

该函数是防漏机制，不是主路径。

### 5. 更新调用点

所有调用：

```python
profile.fallback_rows_for_l3(group, meta, start_seq=seq)
```

应改为：

```python
profile.fallback_rows_for_l3(
    group,
    meta,
    start_seq=seq,
    judgement_rules=judgement_rules,
)
```

重点位置：

- `rules_only`
- `rules_first`
- AI 失败 fallback
- preview fallback
- supplement fallback 如有相关调用

## 测试方案

### 单元测试

在 `tests/test_gen_fpa_ai.py` 增加 unified_ui 覆盖：

- 输入包含界面能力和逻辑接口能力。
- 使用 `profile=unified_ui`、`strategy=rules_first` 或 `rules_only`。
- 提供可匹配 EI、ILF 的 `judgement_rules`。
- 断言 fallback 行 `计算依据归类` 非空。
- 断言 EI 行归类命中 EI 判定原则。
- 断言 ILF 行归类命中 ILF 判定原则。
- 断言 `_规则命中详情` 包含 `unified_ui.fallback_classification_basis`。

保留并更新 strict_fpa 既有测试：

- strict_fpa fallback 仍能补齐 `计算依据归类`。
- 规则 ID 可保持兼容，或统一为 `strict_fpa.fallback_classification_basis`。

### 集成验证

修复后使用实际测试目录重新生成 `gen-fpa`：

`F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\8.3-unfied-ui（rule-first）\`

检查：

- `FPA功能点估算` sheet 的 F 列数据行不再为空。
- `-check.xlsx` 的 `规则命中详情` 有 `unified_ui.fallback_classification_basis`。
- `Warnings` 不新增无关异常。

推荐命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py
```

如 profile 层测试受影响，再执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_fpa_profiles.py
```

## 实施清单

实施时按以下顺序推进：

1. 在 `ai_gen_reimbursement_docs/gen_fpa.py` 中保留或泛化 `_basis_for_fpa_type(...)`，确保它不再只服务 strict_fpa。
2. 将 `_fill_strict_fpa_fallback_classification_basis(...)` 改为通用补漏函数，例如 `_fill_fallback_classification_basis(...)`。
3. 更新 `ai_gen_reimbursement_docs/fpa_profiles.py` 中所有 `fallback_rows_for_l3(...)` 实现，增加可选参数 `judgement_rules: list[str] | None = None`。
4. 在 `CustomRulesProfile.fallback_rows_for_l3(...)` 构造界面合并行时，基于 `ui_rule.fpa_type` 立即选择并写入 `计算依据归类`。
5. 在 `CustomRulesProfile.fallback_rows_for_l3(...)` 构造功能过程行时，基于 `self.infer_type(point_name, desc)` 返回的 `fpa_type` 立即选择并写入 `计算依据归类`。
6. 如其他 profile 子类也直接构造 fallback 行，同步接入相同参数和依据选择逻辑。
7. 命中依据归类时统一使用现有 `_add_rule_hit(...)` 记录 `_规则命中详情`，不要在 profile 中手写命中结构。
8. 更新所有 `profile.fallback_rows_for_l3(...)` 调用点，传入 `judgement_rules=judgement_rules`。
9. 更新测试替身、monkeypatch 或 fake fallback 方法签名，优先使用 `**kwargs` 保持兼容。
10. 增加 unified_ui/rules_first 回归测试，并确认 strict_fpa 既有测试仍通过。

## 验收标准

代码实施完成后，必须满足以下标准：

- `unified_ui` + `rules_first` 在规则结果完整且不调用 AI 时，fallback 行的 `计算依据归类` 不为空。
- `unified_ui` + `rules_only` 的 fallback 行同样应尽量写入 `计算依据归类`。
- `计算依据归类` 必须来自 `judgement_rules` 原文，不得硬编码或编造新的归类文案。
- 界面合并行应按 `ui_rule.fpa_type` 匹配判定原则。
- 功能过程行应按 `self.infer_type(...)` 得出的 `fpa_type` 匹配判定原则。
- 如果无法从 `judgement_rules` 匹配到依据归类，不得覆盖为空字段为伪造文本，应在 check 文件中保留可追溯信息。
- `规则命中详情` 应能看到 `{profile.name}.fallback_classification_basis` 或等价的依据归类命中记录。
- strict_fpa fallback 行补齐行为保持兼容，既有 strict_fpa 测试继续通过。
- Excel `FPA功能点估算` sheet 中 `计算依据归类` 列的用户可见文案仍使用该术语，不引入 `功能点类型`、`类型判定依据` 等替代表述。
- 实际测试目录重新生成后，目标文件 F 列数据行非空，`-check.xlsx` 无新增无关 warning。

## 风险与兼容

### 签名变更风险

`fallback_rows_for_l3` 增加参数会影响：

- profile 子类实现
- 测试 monkeypatch 替身
- 直接调用 fallback 行规划的工具函数

缓解方式：

- 新参数设为可选：`judgement_rules: list[str] | None = None`
- 调用 helper 时统一使用 `judgement_rules or []`
- 对测试替身按需补参数或使用 `**kwargs`

### 判定原则匹配风险

类型到判定原则的匹配依赖关键词。如果模板判定原则文案变化较大，可能匹配不到。

缓解方式：

- 先复用 strict_fpa 已验证的关键词匹配。
- 对 unified_ui 常见 EI/ILF/EQ/EO/EIF 判定原则补充关键词。
- 如果匹配不到，在 check 文件中留下可追溯提示。

### 语义风险

不能把 `计算依据归类` 当作纯类型映射。它应来自模板判定原则，而不是硬编码一段说明。

因此实现时应优先写入判定原则原文，保证 Excel F 列和模板附录口径一致。

## 结论

推荐把 `计算依据归类` 的判定前移到 fallback 行构造阶段，与 `类型` 判定同步完成。

通用后处理补漏仍保留，但只作为防御机制。这样可以让 `unified_ui/rules_first` 的规则结果在不调用 AI 的情况下，也生成完整可审计的 FPA 行。
