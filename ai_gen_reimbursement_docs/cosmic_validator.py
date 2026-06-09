"""Deterministic validation and reports for COSMIC draft results."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field as dataclass_field
from typing import Literal

from ai_gen_reimbursement_docs.cosmic_models import CosmicItem

IssueSeverity = Literal["error", "warning", "info"]
ValidationStatus = Literal["passed", "review_required", "blocked"]

_VALID_MOVE_TYPES = {"E", "X", "R", "W"}
_GENERIC_USER_WORDS = {
    "操作员", "用户", "管理员", "后台管理员", "管理人员", "业务人员",
    "系统管理员", "系统", "外部系统",
}
_CONTROL_COMMAND_WORDS = {
    "上一页", "下一页", "翻页", "分页", "排序", "筛选", "展示菜单",
    "隐藏菜单", "展开", "收起", "点击确认", "点击确定", "确认前一操作",
}
_DATA_OPERATION_WORDS = {
    "格式化", "校验", "验证", "分析", "统计", "计算", "汇总", "转换",
    "排序计算", "数据清洗", "连接数据库", "连接服务器", "建立容器",
}
_ERROR_CONFIRMATION_WORDS = {
    "错误提示", "错误消息", "异常提示", "失败提示", "确认消息", "确认提示",
    "成功提示", "操作成功", "操作失败", "保存成功", "保存失败", "提示信息",
}
_INTERNAL_TECHNICAL_BOUNDARY_WORDS = {
    "前端/后端", "前台/后台", "前端", "后端", "前台", "后台",
    "内部接口", "临时接口", "接口响应", "接口调用", "微服务", "服务调用",
    "RPC", "HTTP接口", "API接口",
}
_NON_FUNCTIONAL_SCOPE_WORDS = {
    "非功能", "系统迁移", "数据迁移", "多系统联调", "联调", "前端适配",
    "软硬件环境", "环境扩容", "服务器扩容", "资源扩容", "架构改造",
    "组件改造", "组件升级", "性能优化", "安全加固", "部署改造",
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
    details: dict[str, object] = dataclass_field(default_factory=dict)


@dataclass
class CosmicValidationResult:
    item: CosmicItem
    status: ValidationStatus
    issues: list[CosmicIssue] = dataclass_field(default_factory=list)
    basis: dict[str, object] = dataclass_field(default_factory=dict)


@dataclass
class CosmicValidationReport:
    project: str
    status: ValidationStatus
    results: list[CosmicValidationResult]
    summary: dict[str, int]
    issue_codes: dict[str, int] = dataclass_field(default_factory=dict)
    cfp_basis: dict[str, object] = dataclass_field(default_factory=dict)
    issues: list[CosmicIssue] = dataclass_field(default_factory=list)


def _issue(
    severity: IssueSeverity,
    code: str,
    message: str,
    field: str = "",
    movement_order: int | None = None,
    *,
    item: CosmicItem | None = None,
    scope: str = "item",
    details: dict[str, object] | None = None,
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
        details=details or {},
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


def _process_semantic_findings(item: CosmicItem) -> list[dict[str, object]]:
    text = " ".join([
        item.module_l1 or "",
        item.module_l2 or "",
        item.module_l3 or "",
        item.process or "",
    ])
    matched = _matched_words(text, _NON_FUNCTIONAL_SCOPE_WORDS)
    if not matched:
        return []
    return [{
        "code": "NON_FUNCTIONAL_SCOPE",
        "matched_terms": matched,
        "description": "功能过程或模块路径疑似非功能内容或技术改造事项，通常不应拆成 COSMIC 功能规模",
    }]


def _movement_semantic_findings(movement) -> list[dict[str, object]]:
    text = " ".join([
        str(getattr(movement, "sub_process", "") or ""),
        str(getattr(movement, "data_group", "") or ""),
        str(getattr(movement, "data_attrs", "") or ""),
    ])
    findings: list[dict[str, object]] = []
    matched = _matched_words(text, _CONTROL_COMMAND_WORDS)
    if matched:
        findings.append({
            "code": "CONTROL_COMMAND_MOVEMENT",
            "movement_order": movement.order,
            "matched_terms": matched,
            "description": "子过程疑似控制命令，通常不单独计为 COSMIC 数据移动",
        })
    matched = _matched_words(text, _DATA_OPERATION_WORDS)
    if matched:
        findings.append({
            "code": "DATA_OPERATION_ONLY_MOVEMENT",
            "movement_order": movement.order,
            "matched_terms": matched,
            "description": "子过程疑似仅为数据运算或技术操作，通常应归入相关数据移动或不单独计列",
        })
    matched = _matched_words(text, _ERROR_CONFIRMATION_WORDS)
    if matched:
        findings.append({
            "code": "ERROR_CONFIRMATION_MESSAGE",
            "movement_order": movement.order,
            "matched_terms": matched,
            "description": "子过程疑似错误或确认消息输出，通常需要按手册规则合并识别",
        })
    matched = _matched_words(text, _INTERNAL_TECHNICAL_BOUNDARY_WORDS)
    if matched:
        findings.append({
            "code": "INTERNAL_TECHNICAL_BOUNDARY",
            "movement_order": movement.order,
            "matched_terms": matched,
            "description": "子过程疑似内部技术交互或无效软件边界，需确认是否跨有效 COSMIC 边界",
        })
    return findings


def _matched_words(text: str, words: set[str]) -> list[str]:
    return sorted(word for word in words if word and word in text)


def _finding_details(finding: dict[str, object]) -> dict[str, object]:
    return {
        "matched_terms": list(finding.get("matched_terms", [])),
        "basis_description": str(finding.get("description", "")),
    }


def _function_user_details(function_user_basis: dict[str, object]) -> dict[str, object]:
    return {
        "function_user_parts": list(function_user_basis.get("parts", [])),
        "match_source": str(function_user_basis.get("match_source", "")),
        "matched_term": str(function_user_basis.get("matched_term", "")),
        "matched_part": str(function_user_basis.get("matched_part", "")),
        "basis_description": str(function_user_basis.get("description", "")),
    }


def validate_cosmic_item(item: CosmicItem) -> CosmicValidationResult:
    issues: list[CosmicIssue] = []
    basis = {
        "function_user": _function_user_basis(item),
        "process_semantics": _process_semantic_findings(item),
        "movement_semantics": [],
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
            details=_function_user_details(basis["function_user"]),
        ))

    for finding in basis["process_semantics"]:
        issues.append(_issue(
            "warning", finding["code"],
            "疑似非功能内容或技术改造事项，需确认是否应进入 COSMIC 功能规模",
            "process", item=item, details=_finding_details(finding),
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
        for finding in _movement_semantic_findings(movement):
            basis["movement_semantics"].append(finding)
            if finding["code"] == "CONTROL_COMMAND_MOVEMENT":
                message = "控制命令通常不移动兴趣对象数据，需确认是否应计列"
            elif finding["code"] == "DATA_OPERATION_ONLY_MOVEMENT":
                message = "数据运算或技术操作通常不单独计为数据移动，需确认是否应计列"
            elif finding["code"] == "ERROR_CONFIRMATION_MESSAGE":
                message = "错误或确认消息通常需要按手册规则合并识别，需确认是否重复计列"
            else:
                message = "内部技术交互通常不构成 COSMIC 有效边界，需确认是否应计列"
            issues.append(_issue(
                "warning", finding["code"], message,
                f"movements[{index}].sub_process", movement.order, item=item,
                details=_finding_details(finding),
            ))
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
        issue_codes=_count_issue_codes(results, issues),
        cfp_basis=_build_cfp_basis(cfp_formula),
        issues=issues,
    )


def _count_issue_codes(
    results: list[CosmicValidationResult],
    global_issues: list[CosmicIssue],
) -> dict[str, int]:
    counter: Counter[str] = Counter(issue.code for issue in global_issues)
    counter.update(
        issue.code
        for result in results
        for issue in result.issues
    )
    return dict(sorted(counter.items()))


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
        "details": issue.details,
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
    review_items = _review_items_to_dict(report)
    return {
        "project": report.project,
        "status": report.status,
        "cfp_basis": report.cfp_basis,
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "issue_codes": report.issue_codes,
        "review_items": review_items,
        "export_policy": _export_policy_to_dict(report, review_items),
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


def _export_policy_to_dict(
    report: CosmicValidationReport,
    review_items: list[dict],
) -> dict[str, object]:
    manual_confirmation_required = bool(review_items)
    if report.status == "passed":
        formal_excel = {
            "status": "allowed",
            "reason": "校验通过，可写正式 Excel",
        }
        draft_excel = {
            "status": "not_needed",
            "reason": "校验通过，不需要草稿 Excel",
            "requires_config": False,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }
    elif report.status == "review_required":
        formal_excel = {
            "status": "blocked",
            "reason": "存在待审问题，正式 Excel 需人工确认后再导出",
        }
        draft_excel = {
            "status": "eligible",
            "reason": "存在待审问题，可在配置开启后写草稿 Excel",
            "requires_config": True,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }
    else:
        formal_excel = {
            "status": "blocked",
            "reason": "存在阻断问题，未写正式 Excel",
        }
        draft_excel = {
            "status": "blocked",
            "reason": "存在阻断问题，不能写草稿 Excel",
            "requires_config": False,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }

    return {
        "manual_confirmation_required": manual_confirmation_required,
        "unconfirmed_review_item_count": len(review_items),
        "formal_excel": formal_excel,
        "draft_excel": draft_excel,
    }


def _review_items_to_dict(report: CosmicValidationReport) -> list[dict]:
    rows = [
        _review_item_to_dict(issue, item_index=None)
        for issue in report.issues
    ]
    for item_index, result in enumerate(report.results):
        rows.extend(
            _review_item_to_dict(issue, item_index=item_index)
            for issue in result.issues
        )
    return rows


def _review_item_to_dict(
    issue: CosmicIssue,
    *,
    item_index: int | None,
) -> dict:
    data = _issue_to_dict(issue)
    data["item_index"] = item_index
    data["review_id"] = _review_item_id(issue, item_index=item_index)
    data["confirmation"] = _default_review_confirmation()
    return data


def _default_review_confirmation() -> dict[str, str]:
    return {
        "status": "unconfirmed",
        "decision": "",
        "note": "",
        "confirmed_by": "",
        "confirmed_at": "",
    }


def _review_item_id(
    issue: CosmicIssue,
    *,
    item_index: int | None,
) -> str:
    index = "global" if item_index is None else str(item_index)
    order = "" if issue.movement_order is None else str(issue.movement_order)
    parts = [issue.scope, index, issue.code, issue.field, order]
    return "::".join(_review_id_part(part) for part in parts)


def _review_id_part(value: object) -> str:
    text = str(value or "")
    return (
        text
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("\n", " ")
    )


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
        f"- issue code：{_issue_code_summary_text(report.issue_codes)}\n",
        f"- CFP 来源：{report.cfp_basis.get('description', '')}\n",
        f"- 正式 Excel 输出：{'已写入' if formal_excel_written else '未写入'}\n",
        f"- 草稿 Excel 输出：{'已写入' if draft_excel_written else '未写入'}\n",
        f"- 原因：{excel_reason}\n\n",
        "## 问题明细\n\n",
    ]

    if report.issues:
        lines.extend([
            "### 全局\n\n",
            "| 级别 | code | 字段 | 数据移动序号 | 说明 | 依据 |\n",
            "| --- | --- | --- | --- | --- | --- |\n",
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
            "| 级别 | code | 字段 | 数据移动序号 | 说明 | 依据 |\n",
            "| --- | --- | --- | --- | --- | --- |\n",
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
    details = _issue_details_text(issue)
    return (
        f"| {issue.severity} | `{issue.code}` | `{issue.field}` | "
        f"{order} | {issue.message} | {details} |\n"
    )


def _issue_code_summary_text(issue_codes: dict[str, int]) -> str:
    if not issue_codes:
        return "无"
    return "、".join(
        f"{code}={count}"
        for code, count in issue_codes.items()
    )


def _issue_details_text(issue: CosmicIssue) -> str:
    if not issue.details:
        return ""
    matched_terms = issue.details.get("matched_terms") or []
    function_user_parts = issue.details.get("function_user_parts") or []
    match_source = str(issue.details.get("match_source", "") or "")
    matched_term = str(issue.details.get("matched_term", "") or "")
    basis_description = str(issue.details.get("basis_description", "") or "")
    parts = []
    if matched_terms:
        parts.append("命中：" + "、".join(str(term) for term in matched_terms))
    if function_user_parts:
        parts.append("功能用户：" + "、".join(str(part) for part in function_user_parts))
    if match_source:
        text = f"匹配来源：{match_source}"
        if matched_term:
            text += f"；匹配项：{matched_term}"
        parts.append(text)
    if basis_description:
        parts.append(basis_description)
    return "<br>".join(_escape_md_table_cell(part) for part in parts)


def _escape_md_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
