# 2026-06-09 FPA 多 profile 真实模型抽样

> 历史记录：本文保留当时真实运行名 `multi_uis`。当前现行 profile 已改为 `multi_ui`。

## 执行信息

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset multi-profile-real-model `
  --output-dir artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_real_model_ai_first_20260609
```

输出：

- `artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_real_model_ai_first_20260609/fpa-stability-sampling-manifest.json`
- `artifacts/fpa-stability-ci/tmp_fpa_stability_ci_multi_profile_real_model_ai_first_20260609/fpa-stability-sampling-report.md`

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
| warning_count | 16 |
| quality_issue_count | 0 |
| profile_quality_issue_count | 49 |
| retryable_quality_issue_count | 0 |
| confirmed_decision_count | 0 |
| retry_count | 10 |
| blocking_retry_count | 0 |

## Quality Gate

状态：FAIL

| Metric | Actual | Threshold | Passed |
|---|---:|---:|---|
| profile_quality_issue_count | 49 | 0 | no |
| retryable_quality_issue_count | 0 | 0 | yes |
| blocking_retry_count | 0 | 0 | yes |

## Profile Issue Codes

| Code | Count |
|---|---:|
| `unified_ui.missing_ui_row` | 10 |
| `unified_ui.missing_process_row` | 10 |
| `ui_api_mapping.missing_default_api_row` | 10 |
| `ui_api_mapping.missing_default_ui_row` | 13 |
| `ui_api_mapping.wrong_default_api_type` | 4 |
| `ui_api_mapping.unexpected_explicit_backend_row` | 2 |

## 结论

本次基线证明 `multi-profile-real-model` preset 可以完成 5 个 standard fixture、4 个 profile、共 20 次真实模型生成，且均命中 AI 路径。

基础 strict 质量门已经干净：`quality_issue_count=0`、`retryable_quality_issue_count=0`、`blocking_retry_count=0`。非 strict profile 的 `applicability=debug_only` 基础 `quality_review` 未进入 retryable 硬门禁，符合当前 contract 设计。

失败点集中在 profile 专属 contract：`profile_quality_issue_count=49`。主要问题是 `unified_ui` / `multi_uis` 未稳定输出统一界面行或功能过程处理行，`ui_api_mapping` 未稳定补齐每个功能过程的默认界面开发行、默认接口开发行，且存在少量默认接口类型和显式后端行判定偏差。

## 后续处理

1. 收敛 `unified_ui` / `multi_uis` prompt，明确有功能过程时必须保留三级模块级界面开发行，并按查询、导出、导入、逻辑处理输出对应处理开发行。
2. 收敛 `ui_api_mapping` prompt，明确每个功能过程固定生成默认界面开发 EI 和默认接口开发 ILF，且显式后端/接口行只能来自输入材料中的明确证据。
3. prompt 调整后重新运行 `multi-profile-real-model` preset，并以 `profile_quality_issue_count=0` 作为通过标准。
