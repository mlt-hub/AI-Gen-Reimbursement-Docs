"""Quality-review node for generated FPA rows.

The review is a structured, non-destructive audit layer. It can later be
implemented by a dedicated agent as long as it preserves this JSON contract.
"""

from dataclasses import asdict, dataclass
from typing import Any

from ai_gen_reimbursement_docs.fpa_merge_review import build_fpa_merge_review
from ai_gen_reimbursement_docs.fpa_validator import validate_fpa_rows


@dataclass(frozen=True)
class FpaQualityIssue:
    code: str
    severity: str
    message: str
    source_process_ids: list[str]
    suggested_action: str
    row_index: int | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_fpa_quality_review(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]],
    merge_review: dict[str, object] | None = None,
    confirmed_decisions: object | None = None,
) -> dict[str, object]:
    """Review generated FPA rows against validator and merge recommendations."""
    issues: list[FpaQualityIssue] = []
    for issue in validate_fpa_rows(group=group, rows=rows):
        issues.append(FpaQualityIssue(
            code=issue.code,
            severity=issue.severity,
            message=issue.message,
            source_process_ids=[],
            suggested_action="retry_or_confirm" if issue.retryable else "review",
            row_index=issue.row_index,
            retryable=issue.retryable,
        ))
    review = merge_review or build_fpa_merge_review(group)
    issues.extend(_merge_review_issues(rows=rows, merge_review=review))
    summary = {
        "issue_count": len(issues),
        "retryable_count": sum(1 for issue in issues if issue.retryable),
        "confirmed_decision_count": _confirmed_decision_count(confirmed_decisions),
    }
    return {
        "issues": [issue.to_dict() for issue in issues],
        "summary": summary,
    }


def _merge_review_issues(
    *,
    rows: list[dict[str, object]],
    merge_review: dict[str, object],
) -> list[FpaQualityIssue]:
    issues: list[FpaQualityIssue] = []
    groups = merge_review.get("groups", [])
    if not isinstance(groups, list):
        return issues
    for group in groups:
        if not isinstance(group, dict) or group.get("recommendation") != "merge":
            continue
        process_ids = _string_list(group.get("process_ids", []))
        if len(process_ids) < 2:
            continue
        matching_rows = [
            row for row in rows
            if _row_source_ids(row) & set(process_ids)
        ]
        exact_merge_rows = [
            row for row in matching_rows
            if set(process_ids).issubset(_row_source_ids(row))
        ]
        if exact_merge_rows:
            continue
        if len(matching_rows) >= 2:
            issues.append(FpaQualityIssue(
                code="quality.merge_review_not_applied",
                severity="warning",
                message=(
                    f"{group.get('target_data_group', '业务对象')} {group.get('kind', '')} "
                    "建议合并，但当前结果疑似拆成多行。"
                ),
                source_process_ids=process_ids,
                suggested_action="retry_or_confirm",
                retryable=True,
            ))
    return issues


def _row_source_ids(row: dict[str, object]) -> set[str]:
    raw = row.get("source_process_ids", [])
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if isinstance(raw, str):
        return {item.strip() for item in raw.replace("，", ",").replace("、", ",").split(",") if item.strip()}
    return set()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _confirmed_decision_count(confirmed_decisions: object | None) -> int:
    if isinstance(confirmed_decisions, dict):
        return len([key for key in confirmed_decisions if str(key).strip()])
    return 0
