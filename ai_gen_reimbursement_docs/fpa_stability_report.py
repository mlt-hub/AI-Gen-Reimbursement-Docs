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
        runs.append({
            "run_index": index,
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
    }


def render_fpa_stability_comparison_markdown(comparison: dict[str, object]) -> str:
    """Render a multi-run stability comparison as Markdown."""
    summary = comparison.get("summary", {}) if isinstance(comparison, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    runs = comparison.get("runs", []) if isinstance(comparison, dict) else []
    if not isinstance(runs, list):
        runs = []
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
        "## Runs",
        "",
        "| # | Trace | Profile | Strategy | Rule Set | Modules | Warnings | Quality Issues | Retryable | Confirmations | Retries |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        if not isinstance(run, dict):
            continue
        lines.append(
            f"| {_int_or_default(run.get('run_index'), 0)} "
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
