# FPA 稳定性 CI 配置

## 推荐接入顺序

1. 先运行规则基线，不需要任何密钥。
2. 配置真实模型 secrets 和变量。
3. 手动触发真实模型稳定性门禁。
4. 观察稳定后，再决定是否接入 PR 或定时任务。

## 本地规则基线

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset "" `
  --suite standard `
  --profiles strict_fpa `
  --strategies rules_only `
  --rule-sets strict_fpa_rs `
  --max-retries 0 `
  --output-dir .\tmp_fpa_stability_ci
```

## 本地真实模型门禁

真实模型门禁使用 `strict-real-model` preset：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model `
  --output-dir .\tmp_fpa_stability_ci
```

该 preset 使用：

- `suite=standard`
- `profile=strict_fpa`
- `strategy=ai_first`
- `rule_set=strict_fpa_rs`
- `max_retryable_issues=0`
- `max_retries=0`

质量门失败时，脚本返回退出码 `2`。

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
  "report_path": "tmp_fpa_stability_ci/fpa-stability-sampling-report.md",
  "run_count": 5
}
```

输出目录会包含：

- `fpa-stability-sampling-report.md`
- `fpa-stability-sampling-manifest.json`
- 每个样例和配置组合的 `fpa_audit_trace.json`

报告中的 `Runs` 表会展示 `case_id` 和 `run_id`。如果存在质量问题，`Issue Details` 会进一步列出触发问题的 run、case、module、issue code、是否可重试和问题说明。

建议解读顺序：

1. 先看 `Quality Gate` 是否 PASS/FAIL。
2. 再看 `Issue Details` 中是否有 `Retryable=yes` 的问题。
3. 最后根据具体 `case_id/run_id` 回到对应目录查看 `fpa.md`、`summary.md` 和 `fpa_audit_trace.json`。
