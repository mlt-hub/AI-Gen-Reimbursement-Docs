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
    workload_judgement = _build_unified_workload_judgement(process_facts) if contract.profile_kind == "unified_ui" else {}
    unified_merge_review = (
        _build_unified_merge_review(group, process_facts, workload_judgement)
        if contract.profile_kind == "unified_ui"
        else {}
    )
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
    unified_quality_review = (
        _build_unified_quality_review(
            group=group,
            rows=rows,
            process_facts=process_facts,
            workload_judgement=workload_judgement,
        )
        if contract.profile_kind == "unified_ui"
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
    if contract.profile_kind == "unified_ui":
        roles.extend([
            _role(
                name="workload_judge",
                label="统一界面工作量建议 Agent",
                implementation="deterministic:fpa_agent_review._build_unified_workload_judgement",
                status="completed",
                input_keys=["process_facts"],
                output_key="workload_judgement",
                summary=dict(workload_judgement.get("summary", {})),
            ),
            _role(
                name="unified_quality_reviewer",
                label="统一界面质量审核 Agent",
                implementation="deterministic:fpa_agent_review._build_unified_quality_review",
                status="completed" if rows is not None else "awaiting_rows",
                input_keys=["rows", "workload_judgement"],
                output_key="unified_quality_review",
                summary=dict(unified_quality_review.get("summary", {})),
            ),
        ])
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
        **_profile_review_outputs(
            contract=contract,
            workload_judgement=workload_judgement,
            unified_merge_review=unified_merge_review,
            unified_quality_review=unified_quality_review,
        ),
        "summary": _summary(
            roles,
            process_facts,
            merge_review,
            type_judgement,
            quality_review,
            unified_quality_review,
        ),
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
    unified_quality_review: dict[str, object] | None = None,
) -> dict[str, object]:
    profile_quality_summary = _quality_summary(unified_quality_review or {})
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
        "profile_quality_issue_count": profile_quality_summary.get("issue_count", 0),
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


def _profile_review_outputs(
    *,
    contract: FpaAgentReviewContract,
    workload_judgement: dict[str, object],
    unified_merge_review: dict[str, object],
    unified_quality_review: dict[str, object],
) -> dict[str, object]:
    if contract.profile_kind != "unified_ui":
        return {}
    return {
        "workload_judgement": workload_judgement,
        "unified_merge_review": unified_merge_review,
        "unified_quality_review": unified_quality_review,
    }


def _build_unified_workload_judgement(process_facts: list[dict[str, object]]) -> dict[str, object]:
    judgements: list[dict[str, object]] = []
    for fact in process_facts:
        categories = ["界面开发"]
        operation = str(fact.get("operation", "") or "")
        if operation == "query":
            categories.append("查询处理开发")
        elif operation == "output":
            categories.append("导出处理开发")
        elif bool(fact.get("changes_internal_data")):
            categories.append("逻辑处理开发")
        if bool(fact.get("ordinary_external_service")) or str(fact.get("external_data_group_evidence", "") or ""):
            categories.append("外部系统对接")
        judgements.append({
            "process_id": str(fact.get("process_id", "") or ""),
            "process_name": str(fact.get("process_name", "") or ""),
            "target_data_group": str(fact.get("target_data_group", "") or ""),
            "recommended_categories": categories,
            "confidence": str(fact.get("confidence", "") or "medium"),
            "reason": _unified_workload_reason(operation, categories),
        })
    return {
        "version": 1,
        "mode": "deterministic_debug",
        "judgements": judgements,
        "summary": {
            "judgement_count": len(judgements),
            "ui_recommendation_count": sum(1 for item in judgements if "界面开发" in item["recommended_categories"]),
            "process_recommendation_count": sum(
                1
                for item in judgements
                if any(category.endswith("处理开发") for category in item["recommended_categories"])
            ),
        },
    }


def _unified_workload_reason(operation: str, categories: list[str]) -> str:
    if operation == "query":
        return "查询类功能过程建议保留统一界面行，并补充查询处理开发审计建议。"
    if operation == "output":
        return "输出类功能过程建议保留统一界面行，并补充导出处理开发审计建议。"
    if "外部系统对接" in categories:
        return "存在外部服务或外部数据证据，建议在统一界面口径下审查外部系统对接表达。"
    return "维护或处理类功能过程建议保留统一界面行，并补充逻辑处理开发审计建议。"


def _build_unified_merge_review(
    group: dict[str, object],
    process_facts: list[dict[str, object]],
    workload_judgement: dict[str, object],
) -> dict[str, object]:
    judgements = _list_value(workload_judgement.get("judgements"))
    process_ids = [
        str(fact.get("process_id", "") or fact.get("process_name", "") or "")
        for fact in process_facts
        if str(fact.get("process_id", "") or fact.get("process_name", "") or "")
    ]
    groups: list[dict[str, object]] = []
    if judgements:
        groups.append({
            "kind": "same_module_ui",
            "category": "界面开发",
            "target": str(group.get("l3", "") or ""),
            "process_ids": process_ids,
            "recommendation": "merge",
            "reason": "统一界面口径下同一三级模块默认合并为一条界面开发行。",
        })
    for category in ("查询处理开发", "导出处理开发", "逻辑处理开发"):
        category_processes = [
            str(item.get("process_id", "") or item.get("process_name", "") or "")
            for item in judgements
            if category in _list_value(item.get("recommended_categories"))
        ]
        if len(category_processes) > 1:
            groups.append({
                "kind": "same_category_process",
                "category": category,
                "target": str(group.get("l3", "") or ""),
                "process_ids": category_processes,
                "recommendation": "review_merge",
                "reason": f"同一三级模块存在多条{category}建议，需审查是否应按业务动作合并。",
            })
    return {
        "version": 1,
        "mode": "deterministic_debug",
        "groups": groups,
        "summary": {
            "group_count": len(groups),
            "merge_recommendation_count": sum(1 for group_item in groups if group_item.get("recommendation") == "merge"),
        },
    }


def _build_unified_quality_review(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]] | None,
    process_facts: list[dict[str, object]],
    workload_judgement: dict[str, object],
) -> dict[str, object]:
    if rows is None:
        return {}
    issues: list[dict[str, object]] = []
    row_names = [str(row.get("新增/修改功能点", "") or row.get("name", "") or "") for row in rows]
    if process_facts and not any("界面开发" in name for name in row_names):
        issues.append(_unified_issue(
            code="unified_ui.missing_ui_row",
            severity="warning",
            message="存在功能过程但未发现界面开发行。",
            suggestion="审查 unified_ui 是否应保留三级模块级界面开发行。",
        ))
    for judgement in _list_value(workload_judgement.get("judgements")):
        process_name = str(judgement.get("process_name", "") or "")
        categories = [str(category) for category in _list_value(judgement.get("recommended_categories"))]
        for category in categories:
            if not category.endswith("处理开发"):
                continue
            if not any(category in name and (not process_name or process_name in name) for name in row_names):
                issues.append(_unified_issue(
                    code="unified_ui.missing_process_row",
                    severity="warning",
                    message=f"功能过程“{process_name}”建议存在{category}，但结果行未体现。",
                    suggestion="审查 AI 或 fallback 是否漏掉对应处理开发行。",
                    process_name=process_name,
                    category=category,
                ))
    issues.extend(_duplicate_unified_rows(rows))
    issues.extend(_source_process_scope_issues(group=group, rows=rows))
    return {
        "version": 1,
        "mode": "deterministic_debug",
        "issues": issues,
        "summary": {
            "issue_count": len(issues),
            "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
            "blocking_count": 0,
        },
    }


def _unified_issue(
    *,
    code: str,
    severity: str,
    message: str,
    suggestion: str,
    process_name: str = "",
    category: str = "",
) -> dict[str, object]:
    issue: dict[str, object] = {
        "code": code,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
    }
    if process_name:
        issue["process_name"] = process_name
    if category:
        issue["category"] = category
    return issue


def _duplicate_unified_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("新增/修改功能点", "") or row.get("name", "") or ""), str(row.get("类型", "") or row.get("type", "") or ""))
        if not key[0]:
            continue
        if key in seen and key not in duplicates:
            duplicates.add(key)
            issues.append(_unified_issue(
                code="unified_ui.duplicate_same_name_type",
                severity="warning",
                message=f"结果中存在同名同类型重复行：{key[0]} / {key[1]}。",
                suggestion="审查是否应合并来源流程或保留人工审阅提示。",
            ))
        seen.add(key)
    return issues


def _source_process_scope_issues(group: dict[str, object], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    valid_names = {
        str(process.get("process_name", "") or process.get("name", "") or "")
        for process in _list_value(group.get("processes"))
        if isinstance(process, dict)
    }
    issues: list[dict[str, object]] = []
    for row in rows:
        source_names = [
            part.strip()
            for part in str(row.get("源功能过程", "") or row.get("source_processes", "") or "").split("、")
            if part.strip()
        ]
        out_of_scope = [name for name in source_names if name not in valid_names]
        if out_of_scope:
            issues.append(_unified_issue(
                code="unified_ui.source_process_out_of_scope",
                severity="warning",
                message=f"结果行来源功能过程超出当前模块范围：{'、'.join(out_of_scope)}。",
                suggestion="审查 source_processes / 源功能过程 是否来自当前三级模块。",
            ))
    return issues
