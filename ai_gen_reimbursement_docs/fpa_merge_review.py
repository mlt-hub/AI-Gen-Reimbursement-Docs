"""Merge-boundary review for FPA process facts.

This is the second deterministic intermediate layer after `process_facts`.
It recommends logical transaction merges but does not rewrite final FPA rows.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from ai_gen_reimbursement_docs.fpa_facts import extract_fpa_process_facts


MAINTENANCE_OPERATIONS = {"create", "update", "delete", "enable_disable", "maintain"}


@dataclass(frozen=True)
class FpaMergeReviewGroup:
    kind: str
    target_data_group: str
    process_ids: list[str]
    process_names: list[str]
    recommendation: str
    reason: str
    needs_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_fpa_merge_review(group: dict[str, object]) -> dict[str, object]:
    """Build deterministic merge recommendations from process_facts."""
    facts = extract_fpa_process_facts(group)
    review_groups: list[FpaMergeReviewGroup] = []
    review_groups.extend(_maintenance_groups(facts))
    review_groups.extend(_query_groups(facts))
    review_groups.extend(_standalone_groups(facts, review_groups))
    return {
        "groups": [item.to_dict() for item in review_groups],
        "questions": _confirmation_questions(review_groups),
    }


def _maintenance_groups(facts: list[dict[str, object]]) -> list[FpaMergeReviewGroup]:
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        if (
            str(fact.get("operation", "")) in MAINTENANCE_OPERATIONS
            and bool(fact.get("changes_internal_data"))
            and not bool(fact.get("ordinary_external_service"))
        ):
            buckets[_data_group_key(fact)].append(fact)
    result: list[FpaMergeReviewGroup] = []
    for target, items in buckets.items():
        if len(items) < 2:
            continue
        operations = {str(item.get("operation", "")) for item in items}
        result.append(FpaMergeReviewGroup(
            kind="maintenance_ei",
            target_data_group=target,
            process_ids=_ids(items),
            process_names=_names(items),
            recommendation="merge",
            reason="同一业务对象的数据维护动作按一个维护类 EI 合并。"
            if len(operations) > 1
            else "同一业务对象的多项维护动作按一个维护类 EI 合并。",
        ))
    return result


def _query_groups(facts: list[dict[str, object]]) -> list[FpaMergeReviewGroup]:
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        if bool(fact.get("query_only")) and not bool(fact.get("produces_external_output")):
            buckets[_data_group_key(fact)].append(fact)
    result: list[FpaMergeReviewGroup] = []
    for target, items in buckets.items():
        if len(items) < 2:
            continue
        result.append(FpaMergeReviewGroup(
            kind="query_eq",
            target_data_group=target,
            process_ids=_ids(items),
            process_names=_names(items),
            recommendation="merge",
            reason="同一业务对象的默认查询、条件搜索或查看动作按一个查询类 EQ 合并。",
        ))
    return result


def _standalone_groups(
    facts: list[dict[str, object]],
    merge_groups: list[FpaMergeReviewGroup],
) -> list[FpaMergeReviewGroup]:
    merged_ids = {process_id for group in merge_groups for process_id in group.process_ids}
    result: list[FpaMergeReviewGroup] = []
    for fact in facts:
        process_id = str(fact.get("process_id", "") or "")
        if not process_id or process_id in merged_ids:
            continue
        if bool(fact.get("ordinary_external_service")):
            result.append(FpaMergeReviewGroup(
                kind="ordinary_external_service",
                target_data_group=str(fact.get("target_data_group", "") or ""),
                process_ids=[process_id],
                process_names=[str(fact.get("process_name", "") or "")],
                recommendation="do_not_create_eif",
                reason="普通外部服务、校验、认证或消息调用不作为 EIF 数据功能。",
            ))
        elif str(fact.get("operation", "")) == "output":
            result.append(FpaMergeReviewGroup(
                kind="output_eo",
                target_data_group=str(fact.get("target_data_group", "") or ""),
                process_ids=[process_id],
                process_names=[str(fact.get("process_name", "") or "")],
                recommendation="standalone",
                reason="导出、报表、统计或文件输出通常保持独立 EO 边界。",
            ))
    return result


def _confirmation_questions(groups: list[FpaMergeReviewGroup]) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []
    for group in groups:
        if not group.needs_confirmation:
            continue
        questions.append({
            "id": f"merge_review_{group.kind}_{group.target_data_group}",
            "topic": "合并边界",
            "question": f"是否采纳 {group.target_data_group} 的 {group.kind} 合并建议？",
            "recommendation": group.recommendation,
            "reason": group.reason,
            "process_ids": group.process_ids,
        })
    return questions


def _data_group_key(fact: dict[str, Any]) -> str:
    value = str(fact.get("target_data_group", "") or "").strip()
    return value or "业务数据"


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [str(item.get("process_id", "") or "") for item in items if str(item.get("process_id", "") or "")]


def _names(items: list[dict[str, object]]) -> list[str]:
    return [str(item.get("process_name", "") or "") for item in items if str(item.get("process_name", "") or "")]
