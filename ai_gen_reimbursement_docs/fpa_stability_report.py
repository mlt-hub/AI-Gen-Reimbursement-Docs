"""Stability metrics for FPA generation audit traces."""

from collections import Counter
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
