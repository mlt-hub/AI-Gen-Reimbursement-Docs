# 2026-06-09 FPA 多 profile 真实模型抽样：prompt hardening + deterministic review

> 历史记录：本文保留当时真实运行名 `multi_uis`。当前现行 profile 已改为 `multi_ui`。

## 执行信息

```powershell
$env:AI_REIMBURSEMENT_FPA_CONFIG_DIR=(Resolve-Path tmp_fpa_runtime_config_hardened).Path
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset multi-profile-real-model `
  --output-dir artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_review_fixed_20260609
```

输出：

- `artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_review_fixed_20260609/fpa-stability-sampling-manifest.json`
- `artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_review_fixed_20260609/fpa-stability-sampling-report.md`

## 抽样范围

| profile | strategy | rule_set |
|---|---|---|
| `strict_fpa` | `ai_first` | `strict_fpa_rs` |
| `unified_ui` | `ai_first` | `unified_ui_rs` |
| `multi_uis` | `ai_first` | `multi_uis_rs` |
| `ui_api_mapping` | `ai_first` | `ui_api_mapping_rs` |

Fixture suite: `standard`

样例数：5

运行数：20

模型来源统计：`{"ai": 20}`

## 结果摘要

| 指标 | 数值 |
|---|---:|
| run_count | 20 |
| module_count | 20 |
| warning_count | 50 |
| quality_issue_count | 0 |
| profile_quality_issue_count | 0 |
| retryable_quality_issue_count | 0 |
| confirmed_decision_count | 0 |
| retry_count | 10 |
| blocking_retry_count | 0 |

## Quality Gate

状态：PASS

| Metric | Actual | Threshold | Passed |
|---|---:|---:|---|
| profile_quality_issue_count | 0 | 0 | yes |
| retryable_quality_issue_count | 0 | 0 | yes |
| blocking_retry_count | 0 | 0 | yes |

## 与基线对比

| 阶段 | profile_quality_issue_count | 主要问题 |
|---|---:|---|
| 初始真实模型基线 | 49 | `unified_ui` 缺界面/处理行，`ui_api_mapping` 缺默认界面/API 行或默认 API 类型错误 |
| prompt hardening 后 | 3 | `multi_uis` 界面行命名误报，`ui_api_mapping` 默认接口行被显式后端检测误报 |
| deterministic supplement/review 后 | 0 | profile contract gate 通过 |

## 结论

本次验证证明 `multi-profile-real-model` preset 在 5 个 standard fixture、4 个 profile、共 20 次真实模型生成下通过门禁。当前通过条件为：

- `profile_quality_issue_count=0`
- `retryable_quality_issue_count=0`
- `blocking_retry_count=0`

本轮修正方向是让非 strict profile 的 contract 不依赖模型完全遵守 prompt：生成后处理负责补齐 profile 必需行、修正 `ui_api_mapping` 默认接口行类型；审阅层避免把合法界面命名和默认接口开发行误判为缺失或显式后端行。
