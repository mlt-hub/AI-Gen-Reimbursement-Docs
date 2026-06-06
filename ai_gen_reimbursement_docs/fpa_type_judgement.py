"""Deterministic FPA type-judgement node.

This node turns process facts and merge recommendations into explicit type
suggestions. It is advisory only: final rows are still produced by the existing
rules/AI path, and validators remain non-destructive.
"""

from dataclasses import asdict, dataclass
from typing import Any

from ai_gen_reimbursement_docs.fpa_facts import extract_fpa_process_facts
from ai_gen_reimbursement_docs.fpa_merge_review import build_fpa_merge_review


@dataclass(frozen=True)
class FpaTypeJudgement:
    id: str
    candidate_name: str
    suggested_type: str
    judgement_kind: str
    target_data_group: str
    source_process_ids: list[str]
    source_process_names: list[str]
    confidence: str
    evidence: list[str]
    rationale: str
    applies_to_final_rows: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_fpa_type_judgement(group: dict[str, object]) -> dict[str, object]:
    """Build deterministic type suggestions from process facts and merge review."""
    facts = extract_fpa_process_facts(group)
    merge_review = build_fpa_merge_review(group)
    judgements: list[FpaTypeJudgement] = []
    covered_ids: set[str] = set()

    for review_group in _dict_list(merge_review.get("groups")):
        recommendation = str(review_group.get("recommendation", "") or "")
        process_ids = _string_list(review_group.get("process_ids"))
        if not process_ids:
            continue
        if recommendation == "merge":
            judgement = _judgement_from_merge_group(review_group)
            if judgement:
                judgements.append(judgement)
                covered_ids.update(process_ids)
        elif recommendation == "do_not_create_eif":
            judgements.append(_ordinary_service_judgement(review_group))
            covered_ids.update(process_ids)

    for fact in facts:
        process_id = str(fact.get("process_id", "") or "")
        if process_id and process_id in covered_ids:
            continue
        judgement = _judgement_from_fact(fact)
        if judgement:
            judgements.append(judgement)

    return {
        "judgements": [item.to_dict() for item in judgements],
        "summary": {
            "judgement_count": len(judgements),
            "high_confidence_count": sum(1 for item in judgements if item.confidence == "high"),
            "suggested_type_counts": _type_counts(judgements),
            "non_row_judgement_count": sum(1 for item in judgements if not item.applies_to_final_rows),
        },
    }


def _judgement_from_merge_group(review_group: dict[str, object]) -> FpaTypeJudgement | None:
    kind = str(review_group.get("kind", "") or "")
    target = str(review_group.get("target_data_group", "") or "业务数据")
    process_ids = _string_list(review_group.get("process_ids"))
    process_names = _string_list(review_group.get("process_names"))
    if kind == "maintenance_ei":
        return FpaTypeJudgement(
            id=f"type_maintenance_ei_{_slug(target)}",
            candidate_name=f"{target}维护",
            suggested_type="EI",
            judgement_kind=kind,
            target_data_group=target,
            source_process_ids=process_ids,
            source_process_names=process_names,
            confidence="high",
            evidence=[str(review_group.get("reason", "") or ""), "合并边界建议 recommendation=merge"],
            rationale="同一业务对象的新增、修改、删除或维护动作改变本系统内部数据，按维护类 EI 判断。",
        )
    if kind == "query_eq":
        return FpaTypeJudgement(
            id=f"type_query_eq_{_slug(target)}",
            candidate_name=f"{target}查询",
            suggested_type="EQ",
            judgement_kind=kind,
            target_data_group=target,
            source_process_ids=process_ids,
            source_process_names=process_names,
            confidence="high",
            evidence=[str(review_group.get("reason", "") or ""), "合并边界建议 recommendation=merge"],
            rationale="同一列表、搜索或查看场景只读取并展示同类数据，按查询类 EQ 判断。",
        )
    return None


def _ordinary_service_judgement(review_group: dict[str, object]) -> FpaTypeJudgement:
    target = str(review_group.get("target_data_group", "") or "外部服务")
    return FpaTypeJudgement(
        id=f"type_no_eif_{_slug(target)}",
        candidate_name=f"{target}普通外部服务",
        suggested_type="NONE",
        judgement_kind="ordinary_external_service",
        target_data_group=target,
        source_process_ids=_string_list(review_group.get("process_ids")),
        source_process_names=_string_list(review_group.get("process_names")),
        confidence="high",
        evidence=[str(review_group.get("reason", "") or "")],
        rationale="普通校验、认证、短信、支付或消息调用没有外部维护数据组证据，不生成 EIF。",
        applies_to_final_rows=False,
    )


def _judgement_from_fact(fact: dict[str, object]) -> FpaTypeJudgement | None:
    operation = str(fact.get("operation", "") or "")
    target = str(fact.get("target_data_group", "") or "业务数据")
    process_id = str(fact.get("process_id", "") or "")
    process_name = str(fact.get("process_name", "") or "")
    source_ids = [process_id] if process_id else []
    source_names = [process_name] if process_name else []
    evidence = _string_list(fact.get("evidence"))
    if str(fact.get("external_data_group_evidence", "") or ""):
        return FpaTypeJudgement(
            id=f"type_eif_{_slug(target)}",
            candidate_name=f"{target}数据组",
            suggested_type="EIF",
            judgement_kind="external_data_function",
            target_data_group=target,
            source_process_ids=source_ids,
            source_process_names=source_names,
            confidence="high",
            evidence=[*evidence, str(fact.get("external_data_group_evidence", "") or "")],
            rationale="输入明确体现外部系统维护或本系统不维护的数据组，本系统读取或引用该数据组，按 EIF 判断。",
        )
    if bool(fact.get("ordinary_external_service")):
        return FpaTypeJudgement(
            id=f"type_no_eif_{_slug(target)}",
            candidate_name=f"{target}普通外部服务",
            suggested_type="NONE",
            judgement_kind="ordinary_external_service",
            target_data_group=target,
            source_process_ids=source_ids,
            source_process_names=source_names,
            confidence="high",
            evidence=evidence,
            rationale="仅体现普通外部服务或校验调用，缺少外部维护数据组证据，不生成 EIF。",
            applies_to_final_rows=False,
        )
    if bool(fact.get("produces_external_output")) or operation == "output":
        return FpaTypeJudgement(
            id=f"type_output_eo_{_slug(target)}",
            candidate_name=f"{target}输出",
            suggested_type="EO",
            judgement_kind="output_eo",
            target_data_group=target,
            source_process_ids=source_ids,
            source_process_names=source_names,
            confidence="high",
            evidence=evidence,
            rationale="导出、统计、汇总、报表或文件输出属于外部输出边界，按 EO 判断。",
        )
    if bool(fact.get("query_only")):
        return FpaTypeJudgement(
            id=f"type_query_eq_{_slug(target)}",
            candidate_name=f"{target}查询",
            suggested_type="EQ",
            judgement_kind="query_eq",
            target_data_group=target,
            source_process_ids=source_ids,
            source_process_names=source_names,
            confidence="high",
            evidence=evidence,
            rationale="流程只读取并展示数据，没有维护内部数据或派生输出，按 EQ 判断。",
        )
    if bool(fact.get("changes_internal_data")):
        return FpaTypeJudgement(
            id=f"type_maintenance_ei_{_slug(target)}",
            candidate_name=f"{target}维护",
            suggested_type="EI",
            judgement_kind="maintenance_ei",
            target_data_group=target,
            source_process_ids=source_ids,
            source_process_names=source_names,
            confidence="high" if str(fact.get("confidence", "") or "") == "high" else "medium",
            evidence=evidence,
            rationale="流程改变本系统维护的数据组或状态，按维护类 EI 判断。",
        )
    return None


def _type_counts(judgements: list[FpaTypeJudgement]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in judgements:
        counts[item.suggested_type] = counts.get(item.suggested_type, 0) + 1
    return counts


def _dict_list(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _slug(value: str) -> str:
    text = str(value or "").strip()
    return text or "business_data"
