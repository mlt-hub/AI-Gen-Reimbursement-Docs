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
_DEFAULT_GOVERNANCE_RULE_MATRIX = [
    {
        "code": "NON_FUNCTIONAL_SCOPE",
        "target": "process",
        "severity": "warning",
        "message": "疑似非功能内容或技术改造事项，需确认是否应进入 COSMIC 功能规模",
        "scope_policy": "manual_exclude_process",
        "governance_category": "non_functional_scope",
        "description": "功能过程或模块路径疑似非功能内容或技术改造事项，通常不应拆成 COSMIC 功能规模",
        "terms": [
            "非功能", "系统迁移", "数据迁移", "多系统联调", "联调", "前端适配",
            "软硬件环境", "环境扩容", "服务器扩容", "资源扩容", "架构改造",
            "组件改造", "组件升级", "性能优化", "安全加固", "部署改造",
        ],
        "suggested_actions": [
            {"action": "exclude_process", "label": "排除功能过程"},
        ],
    },
    {
        "code": "CONTROL_COMMAND_MOVEMENT",
        "target": "movement",
        "severity": "warning",
        "message": "控制命令通常不移动兴趣对象数据，需确认是否应计列",
        "scope_policy": "manual_exclude_or_merge",
        "governance_category": "control_command",
        "description": "子过程疑似控制命令，通常不单独计为 COSMIC 数据移动",
        "terms": [
            "上一页", "下一页", "翻页", "分页", "排序", "筛选", "展示菜单",
            "隐藏菜单", "展开", "收起", "点击确认", "点击确定", "确认前一操作",
        ],
        "suggested_actions": [
            {"action": "exclude_movement", "label": "排除计数"},
            {"action": "merge_movement", "label": "合并到上一条"},
        ],
    },
    {
        "code": "DATA_OPERATION_ONLY_MOVEMENT",
        "target": "movement",
        "severity": "warning",
        "message": "数据运算或技术操作通常不单独计为数据移动，需确认是否应计列",
        "scope_policy": "manual_exclude_or_merge",
        "governance_category": "data_operation_only",
        "description": "子过程疑似仅为数据运算或技术操作，通常应归入相关数据移动或不单独计列",
        "terms": [
            "格式化", "校验", "验证", "分析", "统计", "计算", "汇总", "转换",
            "排序计算", "数据清洗", "连接数据库", "连接服务器", "建立容器",
        ],
        "suggested_actions": [
            {"action": "exclude_movement", "label": "排除计数"},
            {"action": "merge_movement", "label": "合并到上一条"},
        ],
    },
    {
        "code": "ERROR_CONFIRMATION_MESSAGE",
        "target": "movement",
        "severity": "warning",
        "message": "错误或确认消息通常需要按手册规则合并识别，需确认是否重复计列",
        "scope_policy": "manual_merge_or_exclude",
        "governance_category": "error_confirmation_message",
        "description": "子过程疑似错误或确认消息输出，通常需要按手册规则合并识别",
        "terms": [
            "错误提示", "错误消息", "异常提示", "失败提示", "确认消息", "确认提示",
            "成功提示", "操作成功", "操作失败", "保存成功", "保存失败", "提示信息",
        ],
        "suggested_actions": [
            {"action": "exclude_movement", "label": "排除计数"},
            {"action": "merge_movement", "label": "合并到上一条"},
        ],
    },
    {
        "code": "EXTERNAL_INTERFACE_BOUNDARY_REVIEW",
        "target": "movement",
        "severity": "warning",
        "message": "外部接口或跨系统交互需确认是否跨 COSMIC 有效边界",
        "scope_policy": "manual_confirm_boundary",
        "governance_category": "external_interface_boundary",
        "description": "子过程疑似调用外部系统、第三方平台或跨系统接口，需要结合接口清单和业务上下文确认是否计列",
        "terms": [
            "外部系统", "第三方", "第三方平台", "外部接口", "跨系统", "系统联调",
            "支付平台", "短信平台", "银行接口", "政务平台", "数据交换平台",
            "统一认证", "电子签章", "影像平台",
        ],
        "suggested_actions": [
            {"action": "exclude_movement", "label": "排除计数"},
            {"action": "merge_movement", "label": "合并到上一条"},
        ],
    },
    {
        "code": "INTERNAL_TECHNICAL_BOUNDARY",
        "target": "movement",
        "severity": "warning",
        "message": "内部技术交互通常不构成 COSMIC 有效边界，需确认是否应计列",
        "scope_policy": "manual_exclude_or_merge",
        "governance_category": "internal_technical_boundary",
        "description": "子过程疑似内部技术交互或无效软件边界，需确认是否跨有效 COSMIC 边界",
        "terms": [
            "前端/后端", "前台/后台", "前端", "后端", "前台", "后台",
            "内部接口", "临时接口", "接口响应", "接口调用", "微服务", "服务调用",
            "RPC", "HTTP接口", "API接口",
        ],
        "suggested_actions": [
            {"action": "exclude_movement", "label": "排除计数"},
            {"action": "merge_movement", "label": "合并到上一条"},
        ],
    },
    {
        "code": "COMPLEX_NON_FUNCTIONAL_SCOPE",
        "target": "process",
        "severity": "warning",
        "message": "复杂非功能或工程支撑事项需确认是否排除 COSMIC 功能规模",
        "scope_policy": "manual_exclude_process",
        "governance_category": "complex_non_functional_scope",
        "description": "功能过程疑似为联调、迁移、适配、部署或工程支撑内容，应结合模块树和元数据确认是否排除",
        "terms": [
            "上线切换", "灰度发布", "容灾", "备份恢复", "数据初始化", "存量数据",
            "批量迁移", "接口联调", "适配改造", "兼容性改造", "国产化适配",
            "中间件升级", "数据库升级", "脚本改造", "监控告警", "日志治理",
        ],
        "suggested_actions": [
            {"action": "exclude_process", "label": "排除功能过程"},
        ],
    },
]


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
    module_l3 = (item.module_l3 or "").strip()
    base = {
        "parts": parts,
        "matched": False,
        "match_source": "empty",
        "matched_term": "",
        "suggested_term": module_l3,
        "requires_review": True,
        "description": "功能用户为空，无法对应三级模块或最小颗粒度模块",
    }
    if not parts:
        return base

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


def _governance_rule_matrix(
    governance_config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    rules = [dict(rule) for rule in _DEFAULT_GOVERNANCE_RULE_MATRIX]
    if not isinstance(governance_config, dict):
        return rules
    rules = _apply_boundary_context_to_rules(
        rules,
        governance_config.get("boundary_context"),
    )
    raw_rules = governance_config.get("rule_matrix")
    if not isinstance(raw_rules, list):
        return rules

    by_code = {str(rule.get("code") or ""): index for index, rule in enumerate(rules)}
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue
        normalized = _normalize_governance_rule(raw_rule)
        if not normalized:
            continue
        code = str(normalized["code"])
        if code in by_code:
            rules[by_code[code]] = normalized
        else:
            by_code[code] = len(rules)
            rules.append(normalized)
    return rules


def _apply_boundary_context_to_rules(
    rules: list[dict[str, object]],
    raw_context: object,
) -> list[dict[str, object]]:
    if not isinstance(raw_context, dict):
        return rules
    context_mapping = {
        "EXTERNAL_INTERFACE_BOUNDARY_REVIEW": "external_systems",
        "INTERNAL_TECHNICAL_BOUNDARY": "internal_components",
        "COMPLEX_NON_FUNCTIONAL_SCOPE": "non_functional_terms",
    }
    for rule in rules:
        code = str(rule.get("code") or "")
        context_key = context_mapping.get(code)
        if not context_key:
            continue
        context_terms = _context_terms(raw_context.get(context_key))
        if not context_terms:
            continue
        existing_terms = [
            str(term)
            for term in rule.get("terms", [])
            if str(term or "")
        ] if isinstance(rule.get("terms"), list) else []
        rule["terms"] = list(dict.fromkeys([*existing_terms, *context_terms]))
        rule["context_source"] = f"gen_cosmic.governance.boundary_context.{context_key}"
    return rules


def _context_terms(raw_terms: object) -> list[str]:
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    if not isinstance(raw_terms, list):
        return []
    return [
        str(term).strip()
        for term in raw_terms
        if str(term or "").strip()
    ]


def _normalize_governance_rule(raw_rule: dict[str, object]) -> dict[str, object] | None:
    code = str(raw_rule.get("code") or "").strip()
    target = str(raw_rule.get("target") or "").strip()
    if not code or target not in {"process", "movement"}:
        return None
    terms = [
        str(term).strip()
        for term in raw_rule.get("terms", [])
        if str(term or "").strip()
    ] if isinstance(raw_rule.get("terms"), list) else []
    if not terms:
        return None
    severity = str(raw_rule.get("severity") or "warning").strip()
    if severity not in {"error", "warning", "info"}:
        severity = "warning"
    suggested_actions = raw_rule.get("suggested_actions")
    if not isinstance(suggested_actions, list):
        suggested_actions = []
    return {
        "code": code,
        "target": target,
        "severity": severity,
        "message": str(raw_rule.get("message") or "命中 COSMIC 治理规则，需人工确认").strip(),
        "scope_policy": str(raw_rule.get("scope_policy") or "manual_review").strip(),
        "governance_category": str(raw_rule.get("governance_category") or code.lower()).strip(),
        "description": str(raw_rule.get("description") or raw_rule.get("message") or "").strip(),
        "terms": terms,
        "suggested_actions": [
            dict(action)
            for action in suggested_actions
            if isinstance(action, dict) and str(action.get("action") or "").strip()
        ],
    }


def _process_semantic_findings(
    item: CosmicItem,
    governance_config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    text = " ".join([
        item.module_l1 or "",
        item.module_l2 or "",
        item.module_l3 or "",
        item.process or "",
    ])
    findings: list[dict[str, object]] = []
    for rule in _governance_rule_matrix(governance_config):
        if rule.get("target") != "process":
            continue
        matched = _matched_words(text, set(rule.get("terms", [])))
        if matched:
            findings.append(_finding_from_rule(rule, matched))
    return findings


def _movement_semantic_findings(
    movement,
    governance_config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    text = " ".join([
        str(getattr(movement, "sub_process", "") or ""),
        str(getattr(movement, "data_group", "") or ""),
        str(getattr(movement, "data_attrs", "") or ""),
    ])
    findings: list[dict[str, object]] = []
    for rule in _governance_rule_matrix(governance_config):
        if rule.get("target") != "movement":
            continue
        matched = _matched_words(text, set(rule.get("terms", [])))
        if matched:
            finding = _finding_from_rule(rule, matched)
            finding["movement_order"] = movement.order
            findings.append(finding)
    return findings


def _matched_words(text: str, words: set[str]) -> list[str]:
    return sorted(word for word in words if word and word in text)


def _finding_from_rule(rule: dict[str, object], matched_terms: list[str]) -> dict[str, object]:
    return {
        "code": str(rule.get("code") or ""),
        "severity": str(rule.get("severity") or "warning"),
        "message": str(rule.get("message") or ""),
        "scope_policy": str(rule.get("scope_policy") or "manual_review"),
        "governance_category": str(rule.get("governance_category") or ""),
        "matched_terms": matched_terms,
        "description": str(rule.get("description") or rule.get("message") or ""),
        "context_source": str(rule.get("context_source") or ""),
        "suggested_actions": [
            dict(action)
            for action in rule.get("suggested_actions", [])
            if isinstance(action, dict)
        ] if isinstance(rule.get("suggested_actions"), list) else [],
    }


def _finding_severity(finding: dict[str, object]) -> IssueSeverity:
    severity = str(finding.get("severity") or "warning")
    if severity in {"error", "warning", "info"}:
        return severity  # type: ignore[return-value]
    return "warning"


def _finding_message(finding: dict[str, object]) -> str:
    message = str(finding.get("message") or "").strip()
    if message:
        return message
    return str(finding.get("description") or "命中 COSMIC 治理规则，需人工确认")


def _finding_details(finding: dict[str, object]) -> dict[str, object]:
    category = str(finding.get("governance_category", ""))
    details = {
        "matched_terms": list(finding.get("matched_terms", [])),
        "basis_description": str(finding.get("description", "")),
        "scope_policy": str(finding.get("scope_policy", "manual_review")),
        "governance_category": category,
        "review_required_reason": _governance_review_reason(category),
    }
    context_source = str(finding.get("context_source", "") or "")
    if context_source:
        details["context_source"] = context_source
    movement_order = finding.get("movement_order")
    suggested_actions = finding.get("suggested_actions")
    if isinstance(suggested_actions, list) and suggested_actions:
        details["suggested_actions"] = []
        for raw_action in suggested_actions:
            if not isinstance(raw_action, dict):
                continue
            action = dict(raw_action)
            if isinstance(movement_order, int) and "movement_order" not in action:
                action["movement_order"] = movement_order
            if "reason" not in action:
                action["reason"] = details["basis_description"]
            details["suggested_actions"].append(action)
    return details


def _governance_review_reason(category: str) -> str:
    if category == "external_interface_boundary":
        return "需要结合接口清单、外部系统清单或业务上下文确认是否跨有效软件边界"
    if category == "internal_technical_boundary":
        return "需要确认该交互是否只是被度量软件内部技术实现细节"
    if category in {"non_functional_scope", "complex_non_functional_scope"}:
        return "需要确认该事项是否属于 COSMIC 无法度量的非功能或工程支撑范围"
    if category == "error_confirmation_message":
        return "需要确认消息是否已由前置读写数据移动覆盖，避免重复计列"
    if category == "data_operation_only":
        return "需要确认该子过程是否只是数据运算或技术准备步骤"
    if category == "control_command":
        return "需要确认该操作是否移动兴趣对象数据"
    return "需要人工确认治理规则命中是否适用于当前业务上下文"


def _function_user_details(function_user_basis: dict[str, object]) -> dict[str, object]:
    matched_term = str(function_user_basis.get("matched_term", "") or "")
    suggested_term = str(function_user_basis.get("suggested_term", "") or matched_term)
    suggested_user = ""
    if suggested_term:
        suggested_user = f"发起者：{suggested_term}|接收者：{suggested_term}"
    return {
        "function_user_parts": list(function_user_basis.get("parts", [])),
        "match_source": str(function_user_basis.get("match_source", "")),
        "matched_term": matched_term,
        "suggested_term": suggested_term,
        "matched_part": str(function_user_basis.get("matched_part", "")),
        "basis_description": str(function_user_basis.get("description", "")),
        "suggested_user": suggested_user,
        "suggested_actions": (
            [{
                "action": "apply_function_user",
                "label": "采用候选功能用户",
                "suggested_user": suggested_user,
                "reason": "将功能用户绑定到当前模块路径中最接近的业务模块",
            }]
            if suggested_user else []
        ),
    }


def _has_function_user_role_conflict(function_user_basis: dict[str, object]) -> bool:
    if function_user_basis.get("requires_review"):
        return False
    parts = {
        str(part).strip()
        for part in function_user_basis.get("parts", [])
        if str(part or "").strip()
    }
    if len(parts) <= 1:
        return False
    matched_part = str(function_user_basis.get("matched_part", "") or "")
    return any(part != matched_part and part not in _GENERIC_USER_WORDS for part in parts)


def validate_cosmic_item(
    item: CosmicItem,
    *,
    governance_config: dict[str, object] | None = None,
) -> CosmicValidationResult:
    governance_config = governance_config or {}
    issues: list[CosmicIssue] = []
    basis = {
        "function_user": _function_user_basis(item),
        "process_semantics": _process_semantic_findings(item, governance_config),
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
    elif (
        governance_config.get("require_unique_function_user") is True
        and _has_function_user_role_conflict(basis["function_user"])
    ):
        matched_part = str(basis["function_user"].get("matched_part", ""))
        suggested_user = (
            f"发起者：{matched_part}|接收者：{matched_part}"
            if matched_part else ""
        )
        issues.append(_issue(
            "warning", "FUNCTION_USER_ROLE_CONFLICT",
            "功能用户包含多个不一致业务角色，需确认功能用户与功能过程是否一对一",
            "user", item=item,
            details={
                "function_user_parts": list(basis["function_user"].get("parts", [])),
                "matched_part": matched_part,
                "match_source": str(basis["function_user"].get("match_source", "")),
                "basis_description": "启用强绑定治理后，功能用户应稳定对应当前功能过程和最小颗粒度模块",
                "approval_required": True,
                "conflict_resolution_policy": "manual_apply_or_waive",
                "suggested_actions": (
                    [{
                        "action": "apply_function_user",
                        "label": "统一为匹配功能用户",
                        "suggested_user": suggested_user,
                        "reason": "消除同一功能过程内多个不一致业务角色",
                    }]
                    if suggested_user else []
                ),
            },
        ))

    for finding in basis["process_semantics"]:
        issues.append(_issue(
            _finding_severity(finding), str(finding["code"]),
            _finding_message(finding),
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
        for finding in _movement_semantic_findings(movement, governance_config):
            basis["movement_semantics"].append(finding)
            issues.append(_issue(
                _finding_severity(finding), str(finding["code"]), _finding_message(finding),
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
    governance_config: dict[str, object] | None = None,
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

    results = [
        validate_cosmic_item(item, governance_config=governance_config)
        for item in items
    ]
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
            "formula": cfp_formula,
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
    data = {
        "order": movement.order,
        "sub_process": movement.sub_process,
        "move_type": movement.move_type,
        "data_group": movement.data_group,
        "data_attrs": movement.data_attrs,
        "reuse": movement.reuse,
    }
    if getattr(movement, "cfp_override", None) is not None:
        data["cfp_override"] = movement.cfp_override
    cfp_basis = getattr(movement, "cfp_basis", None)
    if isinstance(cfp_basis, dict) and cfp_basis:
        data["cfp_basis"] = cfp_basis
    return data


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
        "preview_rows": _preview_rows_to_dict(report, review_items),
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


def _preview_rows_to_dict(
    report: CosmicValidationReport,
    review_items: list[dict],
) -> list[dict[str, object]]:
    review_ids_by_item_index: dict[int, list[str]] = {}
    for review_item in review_items:
        item_index = review_item.get("item_index")
        if not isinstance(item_index, int):
            continue
        review_ids_by_item_index.setdefault(item_index, []).append(
            str(review_item.get("review_id", ""))
        )

    rows: list[dict[str, object]] = []
    for item_index, result in enumerate(report.results):
        item = result.item
        module_parts = [
            item.module_l1,
            item.module_l2,
            item.module_l3,
        ]
        module_path = " > ".join(part for part in module_parts if part)
        movement_types = [
            movement.move_type
            for movement in item.movements
            if movement.move_type
        ]
        rows.append({
            "item_index": item_index,
            "module_path": module_path,
            "module_l1": item.module_l1,
            "module_l2": item.module_l2,
            "module_l3": item.module_l3,
            "process": item.process,
            "user": item.user,
            "trigger": item.trigger,
            "movement_count": len(item.movements),
            "movement_types": movement_types,
            "status": result.status,
            "issue_count": len(result.issues),
            "review_item_ids": review_ids_by_item_index.get(item_index, []),
        })
    return rows


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
