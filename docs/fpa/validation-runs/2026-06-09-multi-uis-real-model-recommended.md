# 2026-06-09 multi_uis 推荐样本真实模型验证

## 目标

承接 `calculation-basis-explanation-rules.md` 中的剩余推进项，把 `multi_uis` 从单样例试运行扩展到推荐样本集验证。

本轮新增正式 preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset multi-uis-real-model-recommended `
  --output-dir .\tmp_fpa_stability_ci_multi_uis_recommended
```

## 验证范围

该 preset 使用 `real-model-recommended` 样本集，覆盖以下 10 个 fixture：

| fixture | 观察重点 |
|---|---|
| `vertical_industry_management.json` | 多模块、多功能过程、查询/导出/维护混合 |
| `mixed_internal_external_data_functions.json` | 内外部数据功能边界 |
| `sms_notification_service.json` | 外部服务触发与通知类流程 |
| `external_user_center_reference.json` | 外部用户中心引用 |
| `master_data_org_reference.json` | 主数据引用 |
| `internal_vs_external_org_reference.json` | 内部/外部组织数据组区分 |
| `oa_approval_reference.json` | 审批、状态流和处理动作 |
| `payment_gateway_refund.json` | 支付网关、退款和外部平台协作 |
| `crm_customer_archive_reference.json` | 客户档案维护、查询和数据组 |
| `customer_list_import.json` | 导入、查询、列表和文件类输入输出 |

## 质量门

```text
profile_quality_issue_count=0
retryable_quality_issue_count=0
blocking_retry_count=0
```

本轮先不新增 profile-specific quality check。只有当推荐样本复跑稳定暴露同一类问题时，再补最小规则；避免在没有样本证据时复制一套 `_explanation_quality_warnings`。

## 验收口径

- `multi_uis` 界面开发行应保持 `EI`。
- 查询、导出、导入、审批、逻辑处理等非界面业务动作应按实际类型输出。
- `计算依据说明`应保持结构化，不编造输入中没有的表、服务、接口或外部系统。
- `multi_uis.split_reason` 作为 check/review 元数据保留，不作为说明质量失败。

## 执行记录

本轮在新 worktree 中执行三次真实模型批量验证，临时输出目录不纳入仓库提交：

```text
tmp_fpa_stability_ci_multi_uis_recommended
tmp_fpa_stability_ci_multi_uis_recommended_after_review_fix
tmp_fpa_stability_ci_multi_uis_recommended_after_import_fix
```

### 首轮

| runs | modules | warnings | quality issues | profile quality issues | retryable issues | retries | blocking retries | status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 11 | 25 | 0 | 12 | 0 | 5 | 0 | fail |

首轮问题集中在 `unified_ui.missing_ui_row`：`multi_uis` 模型按独立业务对象/业务流程输出 EI/EQ 行，并通过 `split_reason` 说明拆分依据；审阅层仍只按字面“界面开发”识别界面证据，导致 11 个模块误判缺界面开发行。

本轮修复：

- `multi_uis` 下，AI 生成的 `EI` 行如果带 `split_reason` 或源功能过程证据，可作为多界面开发证据，不再要求名称必须包含“界面开发”。

### 第二轮

| runs | modules | warnings | quality issues | profile quality issues | retryable issues | retries | blocking retries | status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 11 | 28 | 0 | 1 | 0 | 7 | 0 | fail |

第二轮 `unified_ui.missing_ui_row` 已归零，剩余 1 条 `unified_ui.missing_process_row`：

```text
功能过程“导入客户名单”建议存在逻辑处理开发，但结果行未体现。
```

实际输出和 rule_set 均使用 `导入处理开发`。根因是事实抽取没有 `import` 操作，导致导入类功能过程在审阅层被归到通用 `逻辑处理开发`。

本轮修复：

- `fpa_facts` 增加 `import` 操作识别，关键字为“导入”“上传”。
- 导入操作仍视为内部数据变化。
- unified/multi_uis workload judgement 将 `import` 映射为 `导入处理开发`。

### 第三轮

| runs | modules | warnings | quality issues | profile quality issues | retryable issues | retries | blocking retries | status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 11 | 22 | 0 | 0 | 0 | 3 | 0 | pass |

质量门结果：

```text
profile_quality_issue_count=0
retryable_quality_issue_count=0
blocking_retry_count=0
```

剩余 warning 主要来自稳定性重试、fallback 补齐和人工复核类观察，不构成本轮质量门失败。

## 结论

- `multi_uis` 推荐样本真实模型 preset 已可重复执行，并覆盖 10 个 recommended fixture。
- 批量样本证明单样例后剩余的主要问题在审阅层确定性口径，不是`计算依据说明`结构质量门。
- 后续推进已新增 profile 绑定式 `json_output_contract` fragment，并按最小增量方式追加 profile-specific `_explanation_quality_warnings`；未复制整套公共质量门。
