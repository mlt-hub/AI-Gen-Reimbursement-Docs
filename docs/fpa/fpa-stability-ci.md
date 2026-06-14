# FPA 稳定性 CI 配置

## 推荐接入顺序

1. 先运行规则基线，不需要任何密钥。
2. 配置真实模型 secrets 和变量。
3. 手动触发真实模型稳定性门禁。
4. 观察稳定后，再决定是否接入 PR 或定时任务。

## 本地规则基线

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --suite standard `
  --max-retries 0 `
  --max-quality-issues 0 `
  --max-retryable-issues 0 `
  --output-dir .\artifacts\fpa-stability-ci\tmp_fpa_stability_ci
```

脚本默认不启用真实模型 preset；仅指定 `--suite standard` 时，默认使用 `profile=strict_fpa`、`strategy=rules_only`、`rule_set=strict_fpa_rs`。

运行前可用 dry-run 查看计划，不会调用模型：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --dry-run `
  --suite standard
```

## 本地真实模型门禁

真实模型门禁使用 `strict-real-model` preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model `
  --output-dir .\artifacts\fpa-stability-ci\tmp_fpa_stability_ci
```

该 preset 使用：

- `suite=standard`
- `profile=strict_fpa`
- `strategy=ai_first`
- `rule_set=strict_fpa_rs`
- `max_retryable_issues=0`
- `max_retries=0`

更完整的真实模型抽样使用 `strict-real-model-recommended` preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model-recommended `
  --output-dir .\artifacts\fpa-stability-ci\tmp_fpa_stability_ci_recommended
```

该 preset 使用：

- `suite=real-model-recommended`
- `profile=strict_fpa`
- `strategy=ai_first`
- `rule_set=strict_fpa_rs`
- `max_retryable_issues=0`
- `max_retries=0`

`multi_ui` 专项推荐样本抽样使用 `multi-ui-real-model-recommended` preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset multi-ui-real-model-recommended `
  --output-dir .\artifacts\fpa-stability-ci\tmp_fpa_stability_ci_multi_ui_recommended
```

该 preset 使用：

- `suite=real-model-recommended`
- `profile=multi_ui`
- `strategy=ai_first`
- `rule_set=multi_ui_rs`
- `profile_quality_issue_count=0`
- `retryable_quality_issue_count=0`
- `blocking_retry_count=0`

它用于扩大 `multi_ui` 真实模型样本，重点观察界面开发行固定 `EI`、查询/导出/逻辑处理行按实际类型输出，以及`计算依据说明`质量 warning 的稳定性。

多 profile 真实模型抽样使用 `multi-profile-real-model` preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset multi-profile-real-model `
  --output-dir .\artifacts\fpa-stability-ci\tmp_fpa_stability_ci_multi_profile
```

该 preset 使用 `suite=standard`，并显式展开为四条配置，避免 `profiles × strategies × rule_sets` 笛卡尔积产生无意义组合：

| profile | strategy | rule_set |
|---|---|---|
| `strict_fpa` | `ai_first` | `strict_fpa_rs` |
| `unified_ui` | `ai_first` | `unified_ui_rs` |
| `multi_ui` | `ai_first` | `multi_ui_rs` |
| `ui_api_mapping` | `ai_first` | `ui_api_mapping_rs` |

多 profile preset 的质量门检查：

- `profile_quality_issue_count=0`
- `retryable_quality_issue_count=0`
- `blocking_retry_count=0`

其中 `retryable_quality_issue_count` 只统计 `agent_review.applicability=primary` 的基础 `quality_review`。非 strict profile 的 `applicability=debug_only` 基础 quality review 不作为门禁硬约束；它们的 profile 专属审阅问题单独进入 `profile_quality_issue_count` 和 `profile_issue_code_counts`。

质量门失败时，脚本返回退出码 `2`。

真实模型运行前建议先 dry-run 确认会调用模型：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --dry-run `
  --preset strict-real-model-recommended
```

## GitHub Actions 示例

仓库提供示例文件：

```text
.github/workflows/fpa-stability.example.yml
```

该文件不会自动启用。确认 secrets 和变量配置后，可复制为：

```text
.github/workflows/fpa-stability.yml
```

## Secrets 和 Variables

不要把 API Key、私有网关地址或 token 明文写入仓库。

推荐配置：

- `secrets.AI_REIMBURSEMENT_API_KEY`
- `secrets.AI_REIMBURSEMENT_BASE_URL`
- `vars.AI_REIMBURSEMENT_MODEL`
- `vars.FPA_STABILITY_REAL_MODEL_ENABLED=true`

`AI_REIMBURSEMENT_MODEL` 如果包含敏感部署名，也可以改放 secret。

## 输出

脚本会输出 JSON 摘要：

```json
{
  "status": "pass",
  "report_path": "artifacts/fpa-stability-ci/tmp_fpa_stability_ci/fpa-stability-sampling-report.md",
  "run_count": 5
}
```

输出目录会包含：

- `fpa-stability-sampling-report.md`
- `fpa-stability-sampling-manifest.json`
- 每个样例和配置组合的 `fpa_audit_trace.json`

报告中的 `Runs` 表会展示 `case_id` 和 `run_id`。如果存在质量问题，`Issue Details` 会进一步列出触发问题的 run、case、module、issue code、是否可重试和问题说明。`Warning Sources` 会把 warning 分成 `validator`、`quality_review`、`postprocess_normalization`、`fallback`、`manual_review`、`config` 和 `other`，用于区分真实复核点、规则兜底、确定性规范化提示和可继续收敛的问题。

建议解读顺序：

1. 先看 `Quality Gate` 是否 PASS/FAIL。
2. 再看 `Issue Details` 中是否有 `Retryable=yes` 的问题。
3. 再看 `Warning Sources` 是否集中在 `fallback` 或 `manual_review`。
4. 最后根据具体 `case_id/run_id` 回到对应目录查看 `fpa.md`、`summary.md` 和 `fpa_audit_trace.json`。
