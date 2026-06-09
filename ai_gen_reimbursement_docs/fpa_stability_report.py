"""Stability metrics for FPA generation audit traces."""

from collections import Counter
import json
import os
from typing import Any


def build_fpa_stability_report(audit_trace: dict[str, object]) -> dict[str, object]:
    """Aggregate module-level FPA stability signals from an audit trace."""
    modules = audit_trace.get("modules", [])
    if not isinstance(modules, list):
        modules = []

    module_reports: list[dict[str, object]] = []
    source_counts: Counter[str] = Counter()
    issue_code_counts: Counter[str] = Counter()
    profile_issue_code_counts: Counter[str] = Counter()
    warning_count = 0
    quality_issue_count = 0
    profile_quality_issue_count = 0
    retryable_quality_issue_count = 0
    retry_count = 0
    blocking_retry_count = 0
    confirmed_decision_count = 0
    retry_trigger_source_counts: Counter[str] = Counter()
    warning_source_counts: Counter[str] = Counter()
    agent_role_counts: Counter[str] = Counter()
    pending_agent_role_counts: Counter[str] = Counter()

    for index, module in enumerate(modules, 1):
        if not isinstance(module, dict):
            continue
        source = str(module.get("source", "") or "")
        if source:
            source_counts[source] += 1
        warnings = _string_list(module.get("warnings", []))
        raw_stability_warnings = [
            warning for warning in warnings
            if _counts_as_stability_warning(warning)
        ]
        quality_review = module.get("quality_review", {})
        issues, summary = _quality_parts(quality_review)
        module_issue_count = _int_or_default(summary.get("issue_count"), len(issues))
        module_retryable_count = _int_or_default(
            summary.get("retryable_count"),
            sum(1 for issue in issues if bool(issue.get("retryable"))),
        )
        module_confirmed_count = _int_or_default(summary.get("confirmed_decision_count"), 0)
        module_retry_count = sum(1 for warning in raw_stability_warnings if _is_retry_warning(warning))
        module_blocking_retry_count = module_retry_count if module_issue_count > 0 or module_retryable_count > 0 else 0
        stability_warnings = [
            warning for warning in raw_stability_warnings
            if not (_is_retry_warning(warning) and module_blocking_retry_count == 0)
        ]
        module_warning_count = len(stability_warnings)
        module_warning_sources = Counter(
            _classify_warning_source(warning, module)
            for warning in stability_warnings
        )
        warning_count += module_warning_count
        warning_source_counts.update(module_warning_sources)
        retry_count += module_retry_count
        blocking_retry_count += module_blocking_retry_count
        retry_trigger_source = str(module.get("retry_trigger_source", "") or "").strip()
        if retry_trigger_source:
            retry_trigger_source_counts[retry_trigger_source] += 1

        quality_issue_count += module_issue_count
        retryable_quality_issue_count += module_retryable_count
        confirmed_decision_count += module_confirmed_count

        agent_review = module.get("agent_review", {})
        profile_issues, profile_summary = _profile_quality_parts(agent_review)
        module_profile_issue_count = _int_or_default(profile_summary.get("issue_count"), len(profile_issues))
        profile_quality_issue_count += module_profile_issue_count
        module_agent_roles = _agent_roles(agent_review)
        agent_role_counts.update(
            str(role.get("name", "") or "").strip()
            for role in module_agent_roles
            if str(role.get("name", "") or "").strip()
        )
        pending_agent_role_counts.update(
            str(role.get("name", "") or "").strip()
            for role in module_agent_roles
            if str(role.get("status", "") or "").strip() == "pending_agent"
        )

        module_issue_codes = [
            str(issue.get("code", "") or "").strip()
            for issue in issues
            if str(issue.get("code", "") or "").strip()
        ]
        module_profile_issue_codes = [
            str(issue.get("code", "") or "").strip()
            for issue in profile_issues
            if str(issue.get("code", "") or "").strip()
        ]
        issue_code_counts.update(module_issue_codes)
        profile_issue_code_counts.update(module_profile_issue_codes)
        module_reports.append({
            "module_index": index,
            "module": str(module.get("module", "") or ""),
            "l3": str(module.get("l3", "") or ""),
            "source": source,
            "warning_count": module_warning_count,
            "warning_source_counts": dict(module_warning_sources),
            "quality_issue_count": module_issue_count,
            "profile_quality_issue_count": module_profile_issue_count,
            "retryable_quality_issue_count": module_retryable_count,
            "confirmed_decision_count": module_confirmed_count,
            "retry_count": module_retry_count,
            "blocking_retry_count": module_blocking_retry_count,
            "retry_trigger_source": retry_trigger_source,
            "issue_code_counts": dict(Counter(module_issue_codes)),
            "profile_issue_code_counts": dict(Counter(module_profile_issue_codes)),
            "agent_role_counts": dict(Counter(
                str(role.get("name", "") or "").strip()
                for role in module_agent_roles
                if str(role.get("name", "") or "").strip()
            )),
            "pending_agent_roles": [
                str(role.get("name", "") or "").strip()
                for role in module_agent_roles
                if str(role.get("status", "") or "").strip() == "pending_agent"
            ],
        })

    summary = {
        "module_count": len(module_reports),
        "warning_count": warning_count,
        "quality_issue_count": quality_issue_count,
        "profile_quality_issue_count": profile_quality_issue_count,
        "retryable_quality_issue_count": retryable_quality_issue_count,
        "confirmed_decision_count": confirmed_decision_count,
        "retry_count": retry_count,
        "blocking_retry_count": blocking_retry_count,
        "retry_trigger_source_counts": dict(retry_trigger_source_counts),
        "warning_source_counts": dict(warning_source_counts),
        "source_counts": dict(source_counts),
        "issue_code_counts": dict(issue_code_counts),
        "profile_issue_code_counts": dict(profile_issue_code_counts),
        "agent_role_counts": dict(agent_role_counts),
        "pending_agent_role_counts": dict(pending_agent_role_counts),
    }
    return {
        "summary": {
            **summary,
            "recommendations": _recommendations(summary),
        },
        "modules": module_reports,
    }


def _agent_roles(agent_review: object) -> list[dict[str, object]]:
    if not isinstance(agent_review, dict):
        return []
    roles = agent_review.get("roles", [])
    if not isinstance(roles, list):
        return []
    return [role for role in roles if isinstance(role, dict)]


def load_fpa_stability_trace(path: str) -> dict[str, object]:
    """Load one FPA audit trace and ensure it has a stability report."""
    with open(path, encoding="utf-8") as f:
        trace = json.load(f)
    if not isinstance(trace, dict):
        raise ValueError(f"FPA audit trace must be a JSON object: {path}")
    modules = trace.get("modules", [])
    report = trace.get("stability_report", {})
    if isinstance(modules, list) and modules:
        report = build_fpa_stability_report(trace)
        trace["stability_report"] = report
    elif not isinstance(report, dict) or not report:
        report = build_fpa_stability_report(trace)
        trace["stability_report"] = report
    return trace


def build_fpa_stability_comparison(trace_paths: list[str]) -> dict[str, object]:
    """Compare stability summaries from multiple FPA audit traces."""
    runs: list[dict[str, object]] = []
    issue_details: list[dict[str, object]] = []
    total_modules = 0
    total_warnings = 0
    total_quality_issues = 0
    total_profile_quality_issues = 0
    total_retryable_issues = 0
    total_retries = 0
    total_blocking_retries = 0
    total_confirmed_decisions = 0
    source_counts: Counter[str] = Counter()
    issue_code_counts: Counter[str] = Counter()
    profile_issue_code_counts: Counter[str] = Counter()
    retry_trigger_source_counts: Counter[str] = Counter()
    warning_source_counts: Counter[str] = Counter()

    for index, path in enumerate(trace_paths, 1):
        trace = load_fpa_stability_trace(path)
        case_id = str(trace.get("case_id", "") or "")
        run_id = str(trace.get("run_id", "") or "")
        run_dir = str(trace.get("run_dir", "") or "")
        report = trace["stability_report"]
        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        if not isinstance(summary, dict):
            summary = {}
        module_count = _int_or_default(summary.get("module_count"), 0)
        warning_count = _int_or_default(summary.get("warning_count"), 0)
        quality_issue_count = _int_or_default(summary.get("quality_issue_count"), 0)
        profile_quality_issue_count = _int_or_default(summary.get("profile_quality_issue_count"), 0)
        retryable_count = _int_or_default(summary.get("retryable_quality_issue_count"), 0)
        retry_count = _int_or_default(summary.get("retry_count"), 0)
        blocking_retry_count = _int_or_default(summary.get("blocking_retry_count"), 0)
        confirmed_count = _int_or_default(summary.get("confirmed_decision_count"), 0)
        run_source_counts = _counter_from_dict(summary.get("source_counts", {}))
        run_issue_counts = _counter_from_dict(summary.get("issue_code_counts", {}))
        run_profile_issue_counts = _counter_from_dict(summary.get("profile_issue_code_counts", {}))
        run_retry_trigger_counts = _counter_from_dict(summary.get("retry_trigger_source_counts", {}))
        run_warning_source_counts = _counter_from_dict(summary.get("warning_source_counts", {}))

        total_modules += module_count
        total_warnings += warning_count
        total_quality_issues += quality_issue_count
        total_profile_quality_issues += profile_quality_issue_count
        total_retryable_issues += retryable_count
        total_retries += retry_count
        total_blocking_retries += blocking_retry_count
        total_confirmed_decisions += confirmed_count
        source_counts.update(run_source_counts)
        issue_code_counts.update(run_issue_counts)
        profile_issue_code_counts.update(run_profile_issue_counts)
        retry_trigger_source_counts.update(run_retry_trigger_counts)
        warning_source_counts.update(run_warning_source_counts)
        issue_details.extend(_issue_details_for_trace(index, trace, case_id, run_id))
        runs.append({
            "run_index": index,
            "case_id": case_id,
            "run_id": run_id,
            "run_dir": run_dir,
            "trace_path": path,
            "trace_name": os.path.basename(path),
            "profile": str(trace.get("profile", "") or ""),
            "strategy": str(trace.get("strategy", "") or ""),
            "rule_set": str(trace.get("rule_set", "") or ""),
            "module_count": module_count,
            "warning_count": warning_count,
            "quality_issue_count": quality_issue_count,
            "profile_quality_issue_count": profile_quality_issue_count,
            "retryable_quality_issue_count": retryable_count,
            "confirmed_decision_count": confirmed_count,
            "retry_count": retry_count,
            "blocking_retry_count": blocking_retry_count,
            "source_counts": dict(run_source_counts),
            "issue_code_counts": dict(run_issue_counts),
            "profile_issue_code_counts": dict(run_profile_issue_counts),
            "retry_trigger_source_counts": dict(run_retry_trigger_counts),
            "warning_source_counts": dict(run_warning_source_counts),
        })

    summary = {
        "run_count": len(runs),
        "module_count": total_modules,
        "warning_count": total_warnings,
        "quality_issue_count": total_quality_issues,
        "profile_quality_issue_count": total_profile_quality_issues,
        "retryable_quality_issue_count": total_retryable_issues,
        "confirmed_decision_count": total_confirmed_decisions,
        "retry_count": total_retries,
        "blocking_retry_count": total_blocking_retries,
        "retry_trigger_source_counts": dict(retry_trigger_source_counts),
        "warning_source_counts": dict(warning_source_counts),
        "source_counts": dict(source_counts),
        "issue_code_counts": dict(issue_code_counts),
        "profile_issue_code_counts": dict(profile_issue_code_counts),
    }
    return {
        "summary": {
            **summary,
            "recommendations": _recommendations(summary),
        },
        "runs": runs,
        "issue_details": issue_details,
    }


def evaluate_fpa_stability_comparison(
    comparison: dict[str, object],
    thresholds: dict[str, int],
) -> dict[str, object]:
    """Evaluate a stability comparison against optional max-value thresholds."""
    summary = comparison.get("summary", {}) if isinstance(comparison, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    checks: list[dict[str, object]] = []
    for metric, threshold in thresholds.items():
        if threshold < 0:
            continue
        actual = _int_or_default(summary.get(metric), 0)
        checks.append({
            "metric": metric,
            "actual": actual,
            "threshold": threshold,
            "passed": actual <= threshold,
        })
    return {
        "status": "pass" if all(bool(check["passed"]) for check in checks) else "fail",
        "checks": checks,
    }


def render_fpa_stability_comparison_markdown(comparison: dict[str, object]) -> str:
    """Render a multi-run stability comparison as Markdown."""
    summary = comparison.get("summary", {}) if isinstance(comparison, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    runs = comparison.get("runs", []) if isinstance(comparison, dict) else []
    if not isinstance(runs, list):
        runs = []
    issue_details = comparison.get("issue_details", []) if isinstance(comparison, dict) else []
    if not isinstance(issue_details, list):
        issue_details = []
    lines = [
        "# FPA 稳定性对比报告",
        "",
        "## Summary",
        "",
        "| Runs | Modules | Warnings | Quality Issues | Profile Quality Issues | Retryable Issues | Confirmations | Retries | Blocking Retries |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {_int_or_default(summary.get('run_count'), 0)} "
            f"| {_int_or_default(summary.get('module_count'), 0)} "
            f"| {_int_or_default(summary.get('warning_count'), 0)} "
            f"| {_int_or_default(summary.get('quality_issue_count'), 0)} "
            f"| {_int_or_default(summary.get('profile_quality_issue_count'), 0)} "
            f"| {_int_or_default(summary.get('retryable_quality_issue_count'), 0)} "
            f"| {_int_or_default(summary.get('confirmed_decision_count'), 0)} "
            f"| {_int_or_default(summary.get('retry_count'), 0)} "
            f"| {_int_or_default(summary.get('blocking_retry_count'), 0)} |"
        ),
        "",
    ]
    evaluation = comparison.get("evaluation", {}) if isinstance(comparison, dict) else {}
    if isinstance(evaluation, dict) and evaluation.get("checks"):
        lines.extend([
            "## Quality Gate",
            "",
            f"Status: **{str(evaluation.get('status', '')).upper()}**",
            "",
            "| Metric | Actual | Threshold | Passed |",
            "|---|---:|---:|---|",
        ])
        checks = evaluation.get("checks", [])
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                lines.append(
                    f"| {_escape_md(str(check.get('metric', '') or ''))} "
                    f"| {_int_or_default(check.get('actual'), 0)} "
                    f"| {_int_or_default(check.get('threshold'), 0)} "
                    f"| {'yes' if check.get('passed') else 'no'} |"
                )
        lines.append("")
    recommendations = summary.get("recommendations", []) if isinstance(summary, dict) else []
    if isinstance(recommendations, list) and recommendations:
        lines.extend([
            "## Recommendations",
            "",
            "| Priority | Area | Recommendation | Evidence |",
            "|---|---|---|---|",
        ])
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {_escape_md(str(item.get('priority', '') or ''))} "
                f"| {_escape_md(str(item.get('area', '') or ''))} "
                f"| {_escape_md(str(item.get('message', '') or ''))} "
                f"| {_escape_md(str(item.get('evidence', '') or ''))} |"
            )
        lines.append("")
    lines.extend([
        "## Runs",
        "",
        "| # | Case ID | Run ID | Trace | Profile | Strategy | Rule Set | Modules | Warnings | Quality Issues | Profile Quality Issues | Retryable | Confirmations | Retries | Blocking Retries |",
        "|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for run in runs:
        if not isinstance(run, dict):
            continue
        lines.append(
            f"| {_int_or_default(run.get('run_index'), 0)} "
            f"| {_escape_md(str(run.get('case_id', '') or ''))} "
            f"| {_escape_md(str(run.get('run_id', '') or ''))} "
            f"| {_escape_md(str(run.get('trace_name', '') or ''))} "
            f"| {_escape_md(str(run.get('profile', '') or ''))} "
            f"| {_escape_md(str(run.get('strategy', '') or ''))} "
            f"| {_escape_md(str(run.get('rule_set', '') or ''))} "
            f"| {_int_or_default(run.get('module_count'), 0)} "
            f"| {_int_or_default(run.get('warning_count'), 0)} "
            f"| {_int_or_default(run.get('quality_issue_count'), 0)} "
            f"| {_int_or_default(run.get('profile_quality_issue_count'), 0)} "
            f"| {_int_or_default(run.get('retryable_quality_issue_count'), 0)} "
            f"| {_int_or_default(run.get('confirmed_decision_count'), 0)} "
            f"| {_int_or_default(run.get('retry_count'), 0)} "
            f"| {_int_or_default(run.get('blocking_retry_count'), 0)} |"
        )
    if issue_details:
        lines.extend([
            "",
            "## Issue Details",
            "",
            "| Run | Case ID | Module | Code | Retryable | Message |",
            "|---:|---|---|---|---|---|",
        ])
        for issue in issue_details:
            if not isinstance(issue, dict):
                continue
            lines.append(
                f"| {_int_or_default(issue.get('run_index'), 0)} "
                f"| {_escape_md(str(issue.get('case_id', '') or ''))} "
                f"| {_escape_md(str(issue.get('module', '') or issue.get('l3', '') or ''))} "
                f"| {_escape_md(str(issue.get('code', '') or ''))} "
                f"| {'yes' if issue.get('retryable') else 'no'} "
                f"| {_escape_md(str(issue.get('message', '') or ''))} |"
            )
    lines.extend([
        "",
        "## Issue Codes",
        "",
        "| Code | Count |",
        "|---|---:|",
    ])
    for code, count in sorted(_counter_from_dict(summary.get("issue_code_counts", {})).items()):
        lines.append(f"| {_escape_md(code)} | {count} |")
    profile_issue_counts = _counter_from_dict(summary.get("profile_issue_code_counts", {}))
    if profile_issue_counts:
        lines.extend([
            "",
            "## Profile Issue Codes",
            "",
            "| Code | Count |",
            "|---|---:|",
        ])
        for code, count in sorted(profile_issue_counts.items()):
            lines.append(f"| {_escape_md(code)} | {count} |")
    retry_trigger_counts = _counter_from_dict(summary.get("retry_trigger_source_counts", {}))
    warning_source_counts = _counter_from_dict(summary.get("warning_source_counts", {}))
    if retry_trigger_counts:
        lines.extend([
            "",
            "## Retry Triggers",
            "",
            "| Source | Count |",
            "|---|---:|",
        ])
        for source, count in sorted(retry_trigger_counts.items()):
            lines.append(f"| {_escape_md(source)} | {count} |")
    if warning_source_counts:
        lines.extend([
            "",
            "## Warning Sources",
            "",
            "| Source | Count |",
            "|---|---:|",
        ])
        for source, count in sorted(warning_source_counts.items()):
            lines.append(f"| {_escape_md(source)} | {count} |")
    lines.extend([
        "",
        "## Sources",
        "",
        "| Source | Count |",
        "|---|---:|",
    ])
    for source, count in sorted(_counter_from_dict(summary.get("source_counts", {})).items()):
        lines.append(f"| {_escape_md(source)} | {count} |")
    return "\n".join(lines) + "\n"


def _quality_parts(value: object) -> tuple[list[dict[str, Any]], dict[str, object]]:
    if not isinstance(value, dict):
        return [], {}
    raw_issues = value.get("issues", [])
    issues = [issue for issue in raw_issues if isinstance(issue, dict)] if isinstance(raw_issues, list) else []
    summary = value.get("summary", {})
    return issues, summary if isinstance(summary, dict) else {}


def _profile_quality_parts(agent_review: object) -> tuple[list[dict[str, Any]], dict[str, object]]:
    if not isinstance(agent_review, dict):
        return [], {}
    outputs = agent_review.get("contract_outputs", {})
    quality_key = ""
    if isinstance(outputs, dict):
        quality_key = str(outputs.get("quality_review", "") or "")
    if not quality_key or quality_key == "quality_review":
        return [], {}
    return _quality_parts(agent_review.get(quality_key, {}))


def _classify_warning_source(warning: str, module: dict[str, object]) -> str:
    text = str(warning or "")
    source = str(module.get("source", "") or "")
    retry_trigger_source = str(module.get("retry_trigger_source", "") or "")
    if "FPA 配置 warning" in text or "config." in text:
        return "config"
    if (
        source == "rules_fallback"
        or "规则兜底" in text
        or "兜底" in text
        or "解析失败" in text
        or "AI 调用或解析失败" in text
        or "未配置 API Key" in text
    ):
        return "fallback"
    if "稳定性校验触发一次重试" in text and retry_trigger_source in {"validator", "quality_review"}:
        return retry_trigger_source
    if "validator." in text or "查询流程不应判为 EI" in text or "普通校验" in text:
        return "validator"
    if "quality." in text or "type_judgement" in text or "merge_review" in text or "类型建议" in text or "合并建议" in text:
        return "quality_review"
    if "人工复核" in text or "需人工" in text or "外部数据组边界" in text:
        return "manual_review"
    if (
        "已规范化" in text
        or "规范化" in text
        or "classification_basis_index" in text
        or "source_process_id" in text
        or "计算依据归类" in text
    ):
        return "postprocess_normalization"
    return "other"


def _counts_as_stability_warning(warning: str) -> bool:
    text = str(warning or "")
    if (
        "AI 结果未覆盖" in text
        and "已追加" in text
        and "rules_fallback 行" in text
    ):
        return False
    if (
        "AI 结果未包含数据功能行" in text
        and "已追加" in text
        and "rules_fallback 行" in text
    ):
        return False
    return True


def _is_retry_warning(warning: str) -> bool:
    return "稳定性校验触发一次重试" in str(warning or "")


def _recommendations(summary: dict[str, object]) -> list[dict[str, object]]:
    issue_counts = _counter_from_dict(summary.get("issue_code_counts", {}))
    retry_triggers = _counter_from_dict(summary.get("retry_trigger_source_counts", {}))
    source_counts = _counter_from_dict(summary.get("source_counts", {}))
    warning_sources = _counter_from_dict(summary.get("warning_source_counts", {}))
    recommendations: list[dict[str, object]] = []
    _add_recommendation(
        recommendations,
        condition=issue_counts.get("validator.explanation_structure", 0) > 0,
        priority="P1",
        area="explanation",
        message="优先修复计算依据说明结构化输出，减少人工审阅成本。",
        evidence=f"validator.explanation_structure={issue_counts.get('validator.explanation_structure', 0)}",
    )
    _add_recommendation(
        recommendations,
        condition=issue_counts.get("quality.type_judgement_mismatch", 0) > 0
        or retry_triggers.get("quality_review", 0) > 0,
        priority="P1",
        area="type_judgement",
        message="强化 prompt 对 type_judgement 的引用，检查 AI 是否偏离高置信类型建议。",
        evidence=(
            f"quality.type_judgement_mismatch={issue_counts.get('quality.type_judgement_mismatch', 0)}, "
            f"quality_review_retries={retry_triggers.get('quality_review', 0)}"
        ),
    )
    _add_recommendation(
        recommendations,
        condition=issue_counts.get("quality.merge_review_not_applied", 0) > 0
        or issue_counts.get("validator.split_crud_ei", 0) > 0
        or issue_counts.get("validator.split_query_eq", 0) > 0,
        priority="P1",
        area="merge_review",
        message="强化维护/查询合并口径，检查规则兜底和 AI 输出是否仍按 process 拆分。",
        evidence=(
            f"merge_not_applied={issue_counts.get('quality.merge_review_not_applied', 0)}, "
            f"split_crud={issue_counts.get('validator.split_crud_ei', 0)}, "
            f"split_query={issue_counts.get('validator.split_query_eq', 0)}"
        ),
    )
    _add_recommendation(
        recommendations,
        condition=issue_counts.get("validator.query_as_ei", 0) > 0
        or issue_counts.get("validator.ordinary_service_as_eif", 0) > 0
        or retry_triggers.get("validator", 0) > 0,
        priority="P1",
        area="validator",
        message="继续前置基础类型边界到 prompt 和 type_judgement，降低 validator 重试压力。",
        evidence=(
            f"query_as_ei={issue_counts.get('validator.query_as_ei', 0)}, "
            f"ordinary_service_as_eif={issue_counts.get('validator.ordinary_service_as_eif', 0)}, "
            f"validator_retries={retry_triggers.get('validator', 0)}"
        ),
    )
    deterministic_rule_count = source_counts.get("rules", 0) + source_counts.get("rules_fallback", 0)
    _add_recommendation(
        recommendations,
        condition=deterministic_rule_count > 0 and _int_or_default(summary.get("quality_issue_count"), 0) > 0,
        priority="P0",
        area="rules_only_baseline",
        message="rules/rules_only 基线仍有质量问题时，先修确定性规则，再评估真实模型波动。",
        evidence=f"rule_sources={deterministic_rule_count}, quality_issues={_int_or_default(summary.get('quality_issue_count'), 0)}",
    )
    _add_recommendation(
        recommendations,
        condition=warning_sources.get("manual_review", 0) > 0,
        priority="P2",
        area="manual_review",
        message="保留人工复核类 warning，并优先沉淀为 project_profile 或领域上下文规则。",
        evidence=f"manual_review_warnings={warning_sources.get('manual_review', 0)}",
    )
    _add_recommendation(
        recommendations,
        condition=warning_sources.get("postprocess_normalization", 0) > 0,
        priority="P2",
        area="postprocess_normalization",
        message="确定性规范化 warning 可评估降级为 rule hit，避免干扰真实模型质量判断。",
        evidence=f"postprocess_normalization_warnings={warning_sources.get('postprocess_normalization', 0)}",
    )
    _add_recommendation(
        recommendations,
        condition=warning_sources.get("fallback", 0) > 0,
        priority="P1",
        area="fallback",
        message="规则兜底 warning 需要区分 AI 解析失败、缺少 API Key 和规则结果待复核。",
        evidence=f"fallback_warnings={warning_sources.get('fallback', 0)}",
    )
    _add_recommendation(
        recommendations,
        condition=not recommendations and _int_or_default(summary.get("module_count"), 0) > 0,
        priority="P2",
        area="real_model_sampling",
        message="当前质量信号稳定，可推进真实模型批量抽样并比较 prompt/model/rule_set 趋势。",
        evidence=f"modules={_int_or_default(summary.get('module_count'), 0)}",
    )
    return recommendations


def _add_recommendation(
    recommendations: list[dict[str, object]],
    *,
    condition: bool,
    priority: str,
    area: str,
    message: str,
    evidence: str,
) -> None:
    if condition:
        recommendations.append({
            "priority": priority,
            "area": area,
            "message": message,
            "evidence": evidence,
        })


def _issue_details_for_trace(
    run_index: int,
    trace: dict[str, object],
    case_id: str,
    run_id: str,
) -> list[dict[str, object]]:
    modules = trace.get("modules", [])
    if not isinstance(modules, list):
        return []
    details: list[dict[str, object]] = []
    for module_index, module in enumerate(modules, 1):
        if not isinstance(module, dict):
            continue
        issues, _summary = _quality_parts(module.get("quality_review", {}))
        for issue in issues:
            details.append({
                "run_index": run_index,
                "case_id": case_id,
                "run_id": run_id,
                "module_index": module_index,
                "module": str(module.get("module", "") or ""),
                "l3": str(module.get("l3", "") or ""),
                "code": str(issue.get("code", "") or ""),
                "severity": str(issue.get("severity", "") or ""),
                "retryable": bool(issue.get("retryable")),
                "message": str(issue.get("message", "") or ""),
                "suggested_action": str(issue.get("suggested_action", "") or ""),
            })
        profile_issues, _profile_summary = _profile_quality_parts(module.get("agent_review", {}))
        for issue in profile_issues:
            details.append({
                "run_index": run_index,
                "case_id": case_id,
                "run_id": run_id,
                "module_index": module_index,
                "module": str(module.get("module", "") or ""),
                "l3": str(module.get("l3", "") or ""),
                "code": str(issue.get("code", "") or ""),
                "severity": str(issue.get("severity", "") or ""),
                "retryable": False,
                "message": str(issue.get("message", "") or ""),
                "suggested_action": str(issue.get("suggestion", "") or issue.get("suggested_action", "") or ""),
                "source": "profile_quality_review",
            })
    return details


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _counter_from_dict(value: object) -> Counter[str]:
    counter: Counter[str] = Counter()
    if not isinstance(value, dict):
        return counter
    for key, raw_count in value.items():
        name = str(key).strip()
        if not name:
            continue
        counter[name] += _int_or_default(raw_count, 0)
    return counter


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
