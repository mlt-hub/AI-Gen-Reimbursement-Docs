"""Agent-role contract for FPA generation.

The current implementation keeps each role deterministic. The contract makes
the role split explicit so later AI agents can replace individual nodes without
changing prompt payloads, audit traces, or stability reports.
"""

from dataclasses import dataclass
from typing import Any

from ai_gen_reimbursement_docs.fpa_facts import extract_fpa_process_facts
from ai_gen_reimbursement_docs.fpa_merge_review import build_fpa_merge_review
from ai_gen_reimbursement_docs.fpa_quality_review import build_fpa_quality_review
from ai_gen_reimbursement_docs.fpa_type_judgement import build_fpa_type_judgement


@dataclass(frozen=True)
class FpaAgentReviewContract:
    """Profile-level contract metadata for agent review outputs."""

    name: str
    profile_kind: str
    categories: tuple[str, ...]
    judgement_output_key: str
    merge_review_output_key: str
    quality_review_output_key: str
    applicability: str


STRICT_FPA_AGENT_REVIEW_CONTRACT = FpaAgentReviewContract(
    name="strict_fpa_contract",
    profile_kind="strict_fpa",
    categories=("EI", "EQ", "EO", "ILF", "EIF"),
    judgement_output_key="type_judgement",
    merge_review_output_key="merge_review",
    quality_review_output_key="quality_review",
    applicability="primary",
)

UNIFIED_UI_AGENT_REVIEW_CONTRACT = FpaAgentReviewContract(
    name="unified_ui_contract",
    profile_kind="unified_ui",
    categories=("界面开发", "查询处理开发", "导出处理开发", "导入处理开发", "逻辑处理开发"),
    judgement_output_key="workload_judgement",
    merge_review_output_key="unified_merge_review",
    quality_review_output_key="unified_quality_review",
    applicability="debug_only",
)

UI_API_MAPPING_AGENT_REVIEW_CONTRACT = FpaAgentReviewContract(
    name="ui_api_mapping_contract",
    profile_kind="ui_api_mapping",
    categories=("界面开发", "接口开发", "明确接口/后端调用"),
    judgement_output_key="mapping_judgement",
    merge_review_output_key="mapping_merge_review",
    quality_review_output_key="mapping_quality_review",
    applicability="debug_only",
)


def build_fpa_agent_review(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]] | None = None,
    confirmed_decisions: object | None = None,
    profile_name: str = "strict_fpa",
    profile_kind: str = "strict_fpa",
) -> dict[str, object]:
    """Build a structured review for the FPA agent role split."""
    contract = resolve_fpa_agent_review_contract(profile_name=profile_name, profile_kind=profile_kind)
    process_facts = extract_fpa_process_facts(group)
    merge_review = build_fpa_merge_review(group)
    type_judgement = build_fpa_type_judgement(group)
    quality_review = (
        build_fpa_quality_review(
            group=group,
            rows=rows,
            merge_review=merge_review,
            type_judgement=type_judgement,
            confirmed_decisions=confirmed_decisions,
        )
        if rows is not None
        else {}
    )
    roles = [
        _role(
            name="business_fact_extractor",
            label="业务事实抽取 Agent",
            implementation="deterministic:fpa_facts.extract_fpa_process_facts",
            status="completed",
            input_keys=["module", "processes"],
            output_key="process_facts",
            summary={
                "fact_count": len(process_facts),
                "low_confidence_count": sum(
                    1 for fact in process_facts
                    if str(fact.get("confidence", "") or "") != "high"
                ),
            },
        ),
        _role(
            name="fpa_type_judge",
            label="FPA 类型判定 Agent",
            implementation="deterministic:fpa_type_judgement.build_fpa_type_judgement",
            status="completed",
            input_keys=["process_facts", "merge_review", "domain_context"],
            output_key="type_judgement",
            summary=_type_summary(type_judgement),
        ),
        _role(
            name="merge_boundary_reviewer",
            label="合并边界审查 Agent",
            implementation="deterministic:fpa_merge_review.build_fpa_merge_review",
            status="completed",
            input_keys=["process_facts"],
            output_key="merge_review",
            summary={
                "group_count": len(_list_value(merge_review.get("groups"))),
                "question_count": len(_list_value(merge_review.get("questions"))),
            },
        ),
        _role(
            name="quality_reviewer",
            label="质量审核 Agent",
            implementation="deterministic:fpa_quality_review.build_fpa_quality_review",
            status="completed" if rows is not None else "awaiting_rows",
            input_keys=["rows", "merge_review", "confirmed_decisions"],
            output_key="quality_review",
            summary=_quality_summary(quality_review),
        ),
    ]
    return {
        "version": 1,
        "mode": "deterministic_contract",
        "profile": profile_name or contract.profile_kind,
        "profile_kind": contract.profile_kind,
        "contract": contract.name,
        "applicability": contract.applicability,
        "contract_outputs": {
            "judgement": contract.judgement_output_key,
            "merge_review": contract.merge_review_output_key,
            "quality_review": contract.quality_review_output_key,
        },
        "categories": list(contract.categories),
        "roles": roles,
        "process_facts": process_facts,
        "merge_review": merge_review,
        "type_judgement": type_judgement,
        "quality_review": quality_review,
        "summary": _summary(roles, process_facts, merge_review, type_judgement, quality_review),
    }


def resolve_fpa_agent_review_contract(
    *,
    profile_name: str = "strict_fpa",
    profile_kind: str = "strict_fpa",
) -> FpaAgentReviewContract:
    kind = (profile_kind or profile_name or "strict_fpa").strip()
    if kind == "strict_fpa":
        return STRICT_FPA_AGENT_REVIEW_CONTRACT
    if kind == "ui_api_mapping":
        return UI_API_MAPPING_AGENT_REVIEW_CONTRACT
    return UNIFIED_UI_AGENT_REVIEW_CONTRACT


def _role(
    *,
    name: str,
    label: str,
    implementation: str,
    status: str,
    input_keys: list[str],
    output_key: str,
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "name": name,
        "label": label,
        "implementation": implementation,
        "status": status,
        "input_keys": input_keys,
        "output_key": output_key,
        "summary": summary,
    }


def _summary(
    roles: list[dict[str, object]],
    process_facts: list[dict[str, object]],
    merge_review: dict[str, object],
    type_judgement: dict[str, object],
    quality_review: dict[str, object],
) -> dict[str, object]:
    return {
        "role_count": len(roles),
        "completed_role_count": sum(1 for role in roles if role.get("status") == "completed"),
        "pending_agent_roles": [
            str(role.get("name", "") or "")
            for role in roles
            if str(role.get("status", "") or "") == "pending_agent"
        ],
        "process_fact_count": len(process_facts),
        "merge_group_count": len(_list_value(merge_review.get("groups"))),
        "type_judgement_count": _type_summary(type_judgement).get("judgement_count", 0),
        "quality_issue_count": _quality_summary(quality_review).get("issue_count", 0),
    }


def _quality_summary(quality_review: dict[str, object]) -> dict[str, object]:
    summary = quality_review.get("summary", {}) if isinstance(quality_review, dict) else {}
    if isinstance(summary, dict):
        return dict(summary)
    return {}


def _type_summary(type_judgement: dict[str, object]) -> dict[str, object]:
    summary = type_judgement.get("summary", {}) if isinstance(type_judgement, dict) else {}
    if isinstance(summary, dict):
        return dict(summary)
    return {}


def _list_value(value: Any) -> list[object]:
    return value if isinstance(value, list) else []
