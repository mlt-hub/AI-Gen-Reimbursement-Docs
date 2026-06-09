"""Deterministic validation and reports for COSMIC draft results."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from ai_gen_reimbursement_docs.cosmic_models import CosmicItem

IssueSeverity = Literal["error", "warning", "info"]
ValidationStatus = Literal["passed", "review_required", "blocked"]

_VALID_MOVE_TYPES = {"E", "X", "R", "W"}
_GENERIC_USER_WORDS = {
    "操作员", "用户", "管理员", "后台管理员", "管理人员", "业务人员",
    "系统管理员", "系统", "外部系统",
}


@dataclass
class CosmicIssue:
    severity: IssueSeverity
    code: str
    message: str
    field: str = ""
    module_path: str = ""
    process: str = ""
    movement_order: int | None = None
    scope: str = "item"


@dataclass
class CosmicValidationResult:
    item: CosmicItem
    status: ValidationStatus
    issues: list[CosmicIssue] = field(default_factory=list)
    basis: dict[str, object] = field(default_factory=dict)


@dataclass
class CosmicValidationReport:
    project: str
    status: ValidationStatus
    results: list[CosmicValidationResult]
    summary: dict[str, int]
    cfp_basis: dict[str, object] = field(default_factory=dict)
    issues: list[CosmicIssue] = field(default_factory=list)


def _issue(
    severity: IssueSeverity,
    code: str,
    message: str,
    field: str = "",
    movement_order: int | None = None,
    *,
    item: CosmicItem | None = None,
    scope: str = "item",
) -> CosmicIssue:
    module_path = ""
    process = ""
    if item is not None:
        module_path = " > ".join(
            part for part in [item.module_l1, item.module_l2, item.module_l3] if part
        )
        process = item.process
    return CosmicIssue(
        severity=severity,
        code=code,
        message=message,
        field=field,
        module_path=module_path,
        process=process,
        movement_order=movement_order,
        scope=scope,
    )


def global_cosmic_issue(
    severity: IssueSeverity,
    code: str,
    message: str,
    field: str = "",
) -> CosmicIssue:
    return _issue(severity, code, message, field, scope="global")


def _status_from_issues(issues: list[CosmicIssue]) -> ValidationStatus:
    if any(issue.severity == "error" for issue in issues):
        return "blocked"
    if any(issue.severity == "warning" for issue in issues):
        return "review_required"
    return "passed"


def _split_user_parts(user: str) -> list[str]:
    parts: list[str] = []
    for segment in (user or "").replace("\n", "|").split("|"):
        if "：" in segment:
            segment = segment.split("：", 1)[1]
        elif ":" in segment:
            segment = segment.split(":", 1)[1]
        value = segment.strip()
        if value:
            parts.append(value)
    return parts


def _function_user_basis(item: CosmicItem) -> dict[str, object]:
    parts = _split_user_parts(item.user)
    base = {
        "parts": parts,
        "matched": False,
        "match_source": "empty",
        "matched_term": "",
        "requires_review": True,
        "description": "功能用户为空，无法对应三级模块或最小颗粒度模块",
    }
    if not parts:
        return base

    module_l3 = (item.module_l3 or "").strip()
    matched_part = _matching_user_part(parts, module_l3, allow_partial_module=True)
    if matched_part:
        return {
            **base,
            "matched": True,
            "match_source": "module_l3",
            "matched_term": module_l3,
            "matched_part": matched_part,
            "requires_review": False,
            "description": "功能用户已匹配三级模块或最小颗粒度模块",
        }

    for source, module_name in [
        ("module_l2", (item.module_l2 or "").strip()),
        ("module_l1", (item.module_l1 or "").strip()),
    ]:
        matched_part = _matching_user_part(parts, module_name, allow_partial_module=False)
        if matched_part:
            return {
                **base,
                "match_source": "module_context_only",
                "matched_term": module_name,
                "matched_part": matched_part,
                "matched_module_level": source,
                "description": "功能用户只匹配到上级模块，仍需确认是否对应三级模块",
            }

    if all(part in _GENERIC_USER_WORDS for part in parts):
        return {
            **base,
            "match_source": "generic_only",
            "description": "功能用户仅为泛化角色，未能对应三级模块或最小颗粒度模块",
        }

    return {
        **base,
        "match_source": "unmatched",
        "description": "功能用户未能匹配模块路径，需要人工确认",
    }


def _matching_user_part(
    parts: list[str],
    module_name: str,
    *,
    allow_partial_module: bool,
) -> str:
    if not module_name:
        return ""
    for part in parts:
        if module_name in part or (allow_partial_module and part in module_name):
            return part
    return ""


def is_generic_function_user(item: CosmicItem) -> bool:
    """Return true when the user does not clearly bind to the L3 module."""
    return bool(_function_user_basis(item).get("requires_review"))


def validate_cosmic_item(item: CosmicItem) -> CosmicValidationResult:
    issues: list[CosmicIssue] = []
    basis = {
        "function_user": _function_user_basis(item),
    }

    if not item.module_l1 or not item.module_l2 or not item.module_l3:
        issues.append(_issue(
            "error", "MISSING_MODULE_PATH",
            "功能过程必须归属到完整的一、二、三级模块路径",
            "module_path", item=item,
        ))

    if not item.process:
        issues.append(_issue(
            "error", "MISSING_PROCESS_NAME", "功能过程名称不能为空",
            "process", item=item,
        ))

    if not item.trigger:
        issues.append(_issue(
            "error", "MISSING_TRIGGER", "功能过程必须由触发事件启动",
            "trigger", item=item,
        ))

    if basis["function_user"].get("requires_review"):
        issues.append(_issue(
            "warning", "GENERIC_FUNCTION_USER",
            "功能用户未能对应三级模块、最小颗粒度模块或元数据规则结果",
            "user", item=item,
        ))

    if len(item.movements) < 2:
        issues.append(_issue(
            "error", "TOO_FEW_MOVEMENTS",
            "一个功能过程至少包含两个子过程及相应数据移动",
            "movements", item=item,
        ))

    if item.movements:
        first = item.movements[0]
        last = item.movements[-1]
        if first.move_type != "E":
            issues.append(_issue(
                "error", "FIRST_MOVE_NOT_ENTRY", "第一个子过程必须为输入 E",
                "movements[0].move_type", first.order, item=item,
            ))
        if last.move_type not in {"W", "X"}:
            issues.append(_issue(
                "error", "LAST_MOVE_NOT_WRITE_OR_EXIT",
                "最后一个子过程必须为写 W 或输出 X",
                f"movements[{len(item.movements) - 1}].move_type",
                last.order, item=item,
            ))

    for index, movement in enumerate(item.movements):
        if movement.move_type not in _VALID_MOVE_TYPES:
            issues.append(_issue(
                "warning", "NON_STANDARD_MOVE_TYPE", "移动类型不是标准 E/X/R/W",
                f"movements[{index}].move_type", movement.order, item=item,
            ))
        if not movement.data_group:
            issues.append(_issue(
                "warning", "EMPTY_DATA_GROUP", "数据组不能为空",
                f"movements[{index}].data_group", movement.order, item=item,
            ))
        if not movement.data_attrs:
            issues.append(_issue(
                "warning", "EMPTY_DATA_ATTRS", "数据属性不能为空",
                f"movements[{index}].data_attrs", movement.order, item=item,
            ))

    return CosmicValidationResult(
        item=item,
        status=_status_from_issues(issues),
        issues=issues,
        basis=basis,
    )


def validate_cosmic_items(
    items: list[CosmicItem],
    *,
    project_name: str = "",
    cfp_formula: str = "",
    global_issues: list[CosmicIssue] | None = None,
) -> CosmicValidationReport:
    issues: list[CosmicIssue] = list(global_issues or [])
    if not items:
        issues.append(_issue(
            "error", "NO_COSMIC_ITEMS", "没有可送审的 COSMIC 功能过程",
            "items", scope="global",
        ))
    if not cfp_formula:
        issues.append(_issue(
            "error", "MISSING_CFP_FORMULA",
            "未配置 CFP计算公式，不能生成正式 CFP 总和",
            "cfp_formula", scope="global",
        ))

    results = [validate_cosmic_item(item) for item in items]
    return _build_report(project_name, results, issues, cfp_formula)


def _build_report(
    project_name: str,
    results: list[CosmicValidationResult],
    issues: list[CosmicIssue],
    cfp_formula: str,
) -> CosmicValidationReport:
    summary = {
        "passed": sum(1 for result in results if result.status == "passed"),
        "review_required": sum(1 for result in results if result.status == "review_required"),
        "blocked": sum(1 for result in results if result.status == "blocked"),
        "errors": sum(
            1 for result in results for issue in result.issues
            if issue.severity == "error"
        ),
        "warnings": sum(
            1 for result in results for issue in result.issues
            if issue.severity == "warning"
        ),
        "global_errors": sum(1 for issue in issues if issue.severity == "error"),
        "global_warnings": sum(1 for issue in issues if issue.severity == "warning"),
    }
    if any(issue.severity == "error" for issue in issues) or summary["blocked"]:
        status: ValidationStatus = "blocked"
    elif (
        any(issue.severity == "warning" for issue in issues)
        or summary["review_required"]
    ):
        status = "review_required"
    else:
        status = "passed"

    return CosmicValidationReport(
        project=project_name,
        status=status,
        results=results,
        summary=summary,
        cfp_basis=_build_cfp_basis(cfp_formula),
        issues=issues,
    )


def _build_cfp_basis(cfp_formula: str) -> dict[str, object]:
    if cfp_formula:
        return {
            "source": "template_formula",
            "formula_configured": True,
            "description": "正式 Excel CFP 以模板或元数据中的 CFP计算公式为准",
        }
    return {
        "source": "unconfirmed",
        "formula_configured": False,
        "description": "未配置 CFP计算公式，正式 CFP 来源未确认",
    }


def _issue_to_dict(issue: CosmicIssue) -> dict:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "field": issue.field,
        "module_path": issue.module_path,
        "process": issue.process,
        "movement_order": issue.movement_order,
        "scope": issue.scope,
    }


def _movement_to_dict(movement) -> dict:
    return {
        "order": movement.order,
        "sub_process": movement.sub_process,
        "move_type": movement.move_type,
        "data_group": movement.data_group,
        "data_attrs": movement.data_attrs,
        "reuse": movement.reuse,
    }


def cosmic_report_to_dict(report: CosmicValidationReport) -> dict:
    return {
        "project": report.project,
        "status": report.status,
        "cfp_basis": report.cfp_basis,
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "items": [
            {
                "project": result.item.project,
                "module_l1": result.item.module_l1,
                "module_l2": result.item.module_l2,
                "module_l3": result.item.module_l3,
                "user": result.item.user,
                "trigger": result.item.trigger,
                "process": result.item.process,
                "movements": [
                    _movement_to_dict(movement)
                    for movement in result.item.movements
                ],
                "status": result.status,
                "issues": [_issue_to_dict(issue) for issue in result.issues],
                "basis": result.basis,
            }
            for result in report.results
        ],
        "summary": report.summary,
    }


def write_cosmic_validation_json(
    report: CosmicValidationReport,
    output_path: str,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cosmic_report_to_dict(report), f, ensure_ascii=False, indent=2)
        f.write("\n")
    return output_path


def write_cosmic_validation_report_md(
    report: CosmicValidationReport,
    output_path: str,
    *,
    formal_excel_written: bool,
    draft_excel_written: bool,
    excel_reason: str,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    lines = [
        "# gen-cosmic 校验报告\n\n",
        "## 汇总\n\n",
        f"- 项目：{report.project}\n",
        f"- 总状态：{report.status}\n",
        f"- 功能过程数：{len(report.results)}\n",
        f"- 通过：{report.summary.get('passed', 0)}\n",
        f"- 待审：{report.summary.get('review_required', 0)}\n",
        f"- 阻断：{report.summary.get('blocked', 0)}\n",
        f"- error：{report.summary.get('errors', 0) + report.summary.get('global_errors', 0)}\n",
        f"- warning：{report.summary.get('warnings', 0) + report.summary.get('global_warnings', 0)}\n",
        f"- CFP 来源：{report.cfp_basis.get('description', '')}\n",
        f"- 正式 Excel 输出：{'已写入' if formal_excel_written else '未写入'}\n",
        f"- 草稿 Excel 输出：{'已写入' if draft_excel_written else '未写入'}\n",
        f"- 原因：{excel_reason}\n\n",
        "## 问题明细\n\n",
    ]

    if report.issues:
        lines.extend([
            "### 全局\n\n",
            "| 级别 | code | 字段 | 数据移动序号 | 说明 |\n",
            "| --- | --- | --- | --- | --- |\n",
        ])
        for issue in report.issues:
            lines.append(_issue_row(issue))
        lines.append("\n")

    item_issue_count = 0
    for result in report.results:
        if not result.issues:
            continue
        item_issue_count += len(result.issues)
        module_path = " > ".join(
            part for part in [
                result.item.module_l1, result.item.module_l2, result.item.module_l3,
            ]
            if part
        ) or "未填写模块路径"
        process = result.item.process or "未填写功能过程"
        lines.extend([
            f"### {module_path} / {process}\n\n",
            "| 级别 | code | 字段 | 数据移动序号 | 说明 |\n",
            "| --- | --- | --- | --- | --- |\n",
        ])
        for issue in result.issues:
            lines.append(_issue_row(issue))
        lines.append("\n")

    if not report.issues and item_issue_count == 0:
        lines.append("未发现问题。\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return output_path


def _issue_row(issue: CosmicIssue) -> str:
    order = "" if issue.movement_order is None else str(issue.movement_order)
    return (
        f"| {issue.severity} | `{issue.code}` | `{issue.field}` | "
        f"{order} | {issue.message} |\n"
    )
