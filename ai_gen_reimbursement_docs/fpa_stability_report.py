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
    warning_count = 0
    quality_issue_count = 0
    retryable_quality_issue_count = 0
    retry_count = 0
    confirmed_decision_count = 0

    for index, module in enumerate(modules, 1):
        if not isinstance(module, dict):
            continue
        source = str(module.get("source", "") or "")
        if source:
            source_counts[source] += 1
        warnings = _string_list(module.get("warnings", []))
        module_warning_count = len(warnings)
        warning_count += module_warning_count
        module_retry_count = sum(1 for warning in warnings if "稳定性校验触发一次重试" in warning)
        retry_count += module_retry_count

        quality_review = module.get("quality_review", {})
        issues, summary = _quality_parts(quality_review)
        module_issue_count = _int_or_default(summary.get("issue_count"), len(issues))
        module_retryable_count = _int_or_default(
            summary.get("retryable_count"),
            sum(1 for issue in issues if bool(issue.get("retryable"))),
        )
        module_confirmed_count = _int_or_default(summary.get("confirmed_decision_count"), 0)
        quality_issue_count += module_issue_count
        retryable_quality_issue_count += module_retryable_count
        confirmed_decision_count += module_confirmed_count

        module_issue_codes = [
            str(issue.get("code", "") or "").strip()
            for issue in issues
            if str(issue.get("code", "") or "").strip()
        ]
        issue_code_counts.update(module_issue_codes)
        module_reports.append({
            "module_index": index,
            "module": str(module.get("module", "") or ""),
            "l3": str(module.get("l3", "") or ""),
            "source": source,
            "warning_count": module_warning_count,
            "quality_issue_count": module_issue_count,
            "retryable_quality_issue_count": module_retryable_count,
            "confirmed_decision_count": module_confirmed_count,
            "retry_count": module_retry_count,
            "issue_code_counts": dict(Counter(module_issue_codes)),
        })

    return {
        "summary": {
            "module_count": len(module_reports),
            "warning_count": warning_count,
            "quality_issue_count": quality_issue_count,
            "retryable_quality_issue_count": retryable_quality_issue_count,
            "confirmed_decision_count": confirmed_decision_count,
            "retry_count": retry_count,
            "source_counts": dict(source_counts),
            "issue_code_counts": dict(issue_code_counts),
        },
        "modules": module_reports,
    }


def load_fpa_stability_trace(path: str) -> dict[str, object]:
    """Load one FPA audit trace and ensure it has a stability report."""
    with open(path, encoding="utf-8") as f:
        trace = json.load(f)
    if not isinstance(trace, dict):
        raise ValueError(f"FPA audit trace must be a JSON object: {path}")
    report = trace.get("stability_report", {})
    if not isinstance(report, dict) or not report:
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
    total_retryable_issues = 0
    total_retries = 0
    total_confirmed_decisions = 0
    source_counts: Counter[str] = Counter()
    issue_code_counts: Counter[str] = Counter()

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
        retryable_count = _int_or_default(summary.get("retryable_quality_issue_count"), 0)
        retry_count = _int_or_default(summary.get("retry_count"), 0)
        confirmed_count = _int_or_default(summary.get("confirmed_decision_count"), 0)
        run_source_counts = _counter_from_dict(summary.get("source_counts", {}))
        run_issue_counts = _counter_from_dict(summary.get("issue_code_counts", {}))

        total_modules += module_count
        total_warnings += warning_count
        total_quality_issues += quality_issue_count
        total_retryable_issues += retryable_count
        total_retries += retry_count
        total_confirmed_decisions += confirmed_count
        source_counts.update(run_source_counts)
        issue_code_counts.update(run_issue_counts)
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
            "retryable_quality_issue_count": retryable_count,
            "confirmed_decision_count": confirmed_count,
            "retry_count": retry_count,
            "source_counts": dict(run_source_counts),
            "issue_code_counts": dict(run_issue_counts),
        })

    return {
        "summary": {
            "run_count": len(runs),
            "module_count": total_modules,
            "warning_count": total_warnings,
            "quality_issue_count": total_quality_issues,
            "retryable_quality_issue_count": total_retryable_issues,
            "confirmed_decision_count": total_confirmed_decisions,
            "retry_count": total_retries,
            "source_counts": dict(source_counts),
            "issue_code_counts": dict(issue_code_counts),
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
        "| Runs | Modules | Warnings | Quality Issues | Retryable Issues | Confirmations | Retries |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {_int_or_default(summary.get('run_count'), 0)} "
            f"| {_int_or_default(summary.get('module_count'), 0)} "
            f"| {_int_or_default(summary.get('warning_count'), 0)} "
            f"| {_int_or_default(summary.get('quality_issue_count'), 0)} "
            f"| {_int_or_default(summary.get('retryable_quality_issue_count'), 0)} "
            f"| {_int_or_default(summary.get('confirmed_decision_count'), 0)} "
            f"| {_int_or_default(summary.get('retry_count'), 0)} |"
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
    lines.extend([
        "## Runs",
        "",
        "| # | Case ID | Run ID | Trace | Profile | Strategy | Rule Set | Modules | Warnings | Quality Issues | Retryable | Confirmations | Retries |",
        "|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
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
            f"| {_int_or_default(run.get('retryable_quality_issue_count'), 0)} "
            f"| {_int_or_default(run.get('confirmed_decision_count'), 0)} "
            f"| {_int_or_default(run.get('retry_count'), 0)} |"
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
