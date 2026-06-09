# Profile Agent Review Harness 实施方案

日期：2026-06-09

## 背景

当前 `strict_fpa` 已经具备较完整的 Agent Review 契约、规则 harness 和真实模型复测记录。`unified_ui`、`multi_uis`、`ui_api_mapping` 也已经支持配置、fallback 和部分验收行为，但测试成熟度低于 `strict_fpa`，且当前 `agent_review` 中的 `type_judgement`、`merge_review`、`quality_review` 仍明显偏向严格 FPA 语义。

本实施方案的目标是补齐其他 profile 的 harness，并把 Agent Review 从 `strict_fpa` 专属骨架逐步演进为 profile contract 驱动的审阅框架。

## 实施状态

截至 2026-06-09，已完成以下切片：

| 提交 | 内容 |
|---|---|
| `1c716ed` | 增加 profile-aware Agent Review contract，标注 `primary` / `debug_only`。 |
| `f3e868f` | 新增 `unified_ui`、`multi_uis`、`ui_api_mapping` 分层 harness。 |
| `fdd4e12` | 为 `unified_ui` 增加只读 `workload_judgement`、`unified_merge_review`、`unified_quality_review`。 |
| `9d03d7d` | 为 `ui_api_mapping` 增加只读 `mapping_judgement`、`mapping_merge_review`、`mapping_quality_review`。 |
| `43dc38d` | 稳定性报告汇总 profile 专属 quality issue。 |
| `a96cfc7` | 补充非 strict profile 的 prompt payload contract 覆盖。 |
| `12c6abd` | 覆盖自定义 `unified_ui` / `ui_api_mapping` profile 的 prompt contract 继承。 |
| `96687da` | 为 `multi_uis` 增加独立 contract 变体。 |
| `854cdc2` | 真实模型验证模板补齐 profile 专属质量指标。 |
| 当前切片 | 增加自定义 profile 继承式 harness 示例，并对齐 `ui_api_mapping` 显式后端行提取与审阅口径。 |

当前实现约束：

- 非 strict profile 的专属 review 只进入 `agent_review` 和稳定性报告。
- profile 专属 warning 不阻断、不自动重试、不改写 rows。
- `strict_fpa` 的 `type_judgement`、`merge_review`、`quality_review` 语义保持不变。
- 真实模型抽样模板已经提供，但尚未执行真实模型基线。

## 目标行为

- `strict_fpa` 继续作为 certified 基线，保持现有 EI / EQ / EO / ILF / EIF 类型判断、合并边界和质量审查口径。
- 非 `strict_fpa` profile 可以复用 Agent Review 的审计外壳，但不得把 `strict_fpa` 的类型判断和合并建议当作硬约束。
- 每个 profile 都有明确的 harness 等级、fixture 覆盖范围和质量门。
- 新增或扩展 profile 时，优先新增 contract、规则和 fixture，而不是复制一整套 Python 流程。
- 稳定性报告和 audit trace 能记录 profile、kind、strategy、rule_set、prompt、model 和 fixture suite，便于定位退化来源。

## 实施范围

预计涉及以下文件：

```text
ai_gen_reimbursement_docs/fpa_agent_review.py
ai_gen_reimbursement_docs/fpa_facts.py
ai_gen_reimbursement_docs/fpa_merge_review.py
ai_gen_reimbursement_docs/fpa_quality_review.py
ai_gen_reimbursement_docs/fpa_type_judgement.py
ai_gen_reimbursement_docs/fpa_profiles.py

tests/test_fpa_agent_review.py
tests/test_fpa_profiles.py
tests/test_gen_fpa_strict_profile.py
tests/fpa_profiles/

docs/fpa/profile-agent-review-contract.md
docs/fpa/fpa-profiles.md
docs/fpa/fpa-multi-profile-real-model-validation.md
```

如果实施过程中涉及 FPA 预览、审阅或修改页面的用户可见文案，必须先确认并遵循 `docs/fpa/result-review-terminology.md`。

## 分阶段实施

### 第一阶段：标注 Agent Review 适用范围（已完成）

目标是先防止语义误用，不改变生成结果。

为 `build_fpa_agent_review()` 增加 profile/contract 相关输入或上下文，使输出包含：

```json
{
  "profile": "strict_fpa",
  "contract": "strict_fpa_contract",
  "applicability": "primary"
}
```

非 strict profile 输出：

```json
{
  "profile": "unified_ui",
  "contract": "unified_ui_contract",
  "applicability": "debug_only"
}
```

验收点：

- `strict_fpa` prompt payload 中仍包含现有 `process_facts`、`type_judgement`、`merge_review`、`agent_review`。
- 非 strict profile 的 payload 能明确标识当前审阅信息只适合作为调试信息。
- 现有 strict harness 不回退。

### 第二阶段：建立 Profile Contract 数据结构（已完成）

先使用 Python dataclass 或配置对象表达 contract，不急于实现 YAML 表达式引擎。

当前结构：

```python
@dataclass(frozen=True)
class FpaAgentReviewContract:
    name: str
    profile_kind: str
    categories: tuple[str, ...]
    judgement_output_key: str
    merge_review_output_key: str
    quality_review_output_key: str
    applicability: str
```

第一版 contract 只声明角色、输出 key 和适用范围。

验收点：

- `strict_fpa_contract` 显式声明 `type_judgement`、`merge_review`、`quality_review`。
- `unified_ui_contract` 可声明 `workload_judgement`、`unified_merge_review`、`unified_quality_review`，但第一版允许只输出 debug/warning。
- 自定义 profile 可以继承对应 kind 的默认 contract。

### 第三阶段：补 Profile Harness 分层（已完成基础覆盖）

已新增目录：

```text
tests/fpa_profiles/
  test_strict_fpa_harness.py
  test_custom_profile_harness.py
  test_unified_ui_harness.py
  test_multi_uis_harness.py
  test_ui_api_mapping_harness.py
  test_profile_agent_review_contract.py
  test_profile_prompt_payload_contract.py
```

如果暂时不迁移文件，也应在现有测试中按 profile 分组命名，避免 `tests/test_fpa_profiles.py` 继续膨胀。

各 profile 最小覆盖：

```text
strict_fpa:
  - 数据功能 ILF / EIF
  - 事务功能 EI / EQ / EO
  - 同业务对象维护动作合并
  - 查询动作合并
  - 普通外部服务不误判 EIF

unified_ui:
  - 同一三级模块默认合并界面开发行
  - 查询 / 导出 / 导入 / 逻辑处理后缀稳定
  - 同名非界面过程行合并来源
  - 禁止按按钮、查询条件、字段过度拆分

multi_uis:
  - 多界面行允许保留多条
  - 拆分理由进入 check/review 元数据
  - 同名多界面开发行不合并但提示
  - 非界面业务动作沿用 unified_ui 合并规则

ui_api_mapping:
  - 每个功能过程生成界面开发 EI
  - 每个功能过程生成接口开发 ILF
  - 明确接口 / 服务 / 调用生成额外 ILF
  - 普通保存、提交、审批不触发额外明确接口行
  - 同三级模块同名明确接口合并来源

custom profile:
  - 自定义 `kind: unified_ui` 继承统一界面口径的生成规则和 `unified_ui_contract`
  - 自定义 `kind: ui_api_mapping` 继承界面接口映射口径的生成规则和 `ui_api_mapping_contract`
  - 通过配置解析路径进入 harness，不直接手工构造 profile 对象
```

### 第四阶段：为 unified_ui 增加专属审阅输出（已完成，只读）

先只增加 warning 和 audit trace，不参与自动重试，不改写 rows。

当前输出：

```text
workload_judgement
unified_merge_review
unified_quality_review
```

建议检查项：

- 有界面流程但缺少界面开发行。
- 有查询流程但缺少查询处理开发行。
- 有导出流程但缺少导出处理开发行。
- 明确维护内部数据但缺少对应处理或数据库变更说明。
- 同一类别同一目标重复计数。
- `source_process_ids` 超出当前模块流程范围。

验收点：

- warning 进入 `agent_review` 和 check/review 元数据。
- 不影响正式 Excel 列。
- 不改变 `strict_fpa` 的 `type_judgement` 输出。

### 第五阶段：为 ui_api_mapping 增加专属审阅输出（已完成，只读）

当前输出：

```text
mapping_judgement
mapping_merge_review
mapping_quality_review
```

建议检查项：

- 功能过程缺少默认界面开发行。
- 功能过程缺少默认接口开发行。
- 默认界面开发行类型不是 EI。
- 默认接口开发行类型不是 ILF。
- 明确接口/后端调用行类型不是 ILF。
- 明确接口行没有来源功能过程。
- 非显式接口触发额外后端调用行。

验收点：

- 规则 harness 固定 EI / ILF 类型。
- 明确接口来源可追溯。
- 默认接口行和明确接口行不互相去重。

### 第六阶段：真实模型抽样基线（待执行）

沿用 `docs/fpa/fpa-multi-profile-real-model-validation.md`，但建议新增按日期记录的验证结果：

```text
docs/fpa/validation-runs/YYYY-MM-DD-multi-profile.md
```

每次记录至少包含：

```text
profile
kind
strategy
rule_set
prompt ids
model
fixture suite
run_id
row count
warning count
人工结论
```

通过标准：

- 四个 profile 均能完成真实模型生成。
- check 工作簿存在并包含 profile/kind/strategy/rule_set。
- `strict_fpa` 不输出界面开发、接口开发、逻辑处理开发等开发工作项。
- `unified_ui` 不过度拆分界面。
- `multi_uis` 拆分理由可审阅。
- `ui_api_mapping` 固定 EI / ILF 类型规则稳定。

## 验证命令

当前 profile contract / harness / stability 汇总建议运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\fpa_profiles tests\test_fpa_agent_review.py
.\.venv\Scripts\python.exe -m pytest tests\test_fpa_profiles.py tests\test_fpa_stability_report.py
```

如果改动生成主流程，再补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py tests\test_fpa_external_data_rules.py
```

如果改动 Web/API profile options 或预览结构，再补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_tasks.py
```

## 风险与控制

| 风险 | 控制方式 |
|---|---|
| 非 strict profile 误用 strict 类型判断作为硬约束 | 先增加 `applicability`，非 strict 标记为 `debug_only` |
| contract 抽象过早变复杂 | 第一版只做 dataclass 声明，不做 YAML 表达式引擎 |
| harness 只测 fallback，不覆盖真实模型波动 | 单元测试固定规则，真实模型抽样单独记录 |
| 新 profile 复制 Python 流程导致分叉 | 新增 profile 优先新增 contract、规则和 fixture |
| warning 过多影响审阅体验 | 第一版 warning 只进入 audit/check，不阻断正式生成 |

## 后续切片

1. 按 `docs/fpa/validation-runs/multi-profile-run-template.md` 执行真实模型抽样并归档。
2. 根据真实模型抽样结果判断是否把 `workload_judgement`、`mapping_judgement` 写入 prompt 硬约束。
3. 如果 `multi_uis` 真实项目需求稳定，评估是否新增独立 `kind: multi_uis` 和独立 contract。

每个切片都应保持现有生成行为可回归，并按仓库规则单独提交。
