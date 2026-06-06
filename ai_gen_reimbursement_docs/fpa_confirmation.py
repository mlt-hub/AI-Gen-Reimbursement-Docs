"""Confirmation contract for ambiguous FPA generation decisions."""

from dataclasses import dataclass
import re
from typing import Any

from ai_gen_reimbursement_docs.fpa_validator import FpaValidationIssue


VALID_FPA_CONFIRMATION_MODES = {"auto", "cautious", "strict"}


@dataclass(frozen=True)
class FpaConfirmationDecision:
    value: str
    scope: str = "current_run"


def normalize_confirmation_mode(value: str = "") -> str:
    mode = str(value or "").strip()
    if not mode:
        return "cautious"
    if mode not in VALID_FPA_CONFIRMATION_MODES:
        raise ValueError(f"未知 FPA confirmation mode: {value}")
    return mode


def normalize_confirmed_decisions(raw: object) -> dict[str, FpaConfirmationDecision]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, FpaConfirmationDecision] = {}
    for key, value in raw.items():
        decision_id = str(key or "").strip()
        if not decision_id:
            continue
        if isinstance(value, FpaConfirmationDecision):
            result[decision_id] = value
            continue
        if isinstance(value, dict):
            decision_value = str(value.get("value") or "").strip()
            scope = str(value.get("scope") or "current_run").strip() or "current_run"
        else:
            decision_value = str(value or "").strip()
            scope = "current_run"
        if not decision_value:
            continue
        result[decision_id] = FpaConfirmationDecision(decision_value, scope)
    return result


def build_fpa_confirmation_questions(
    *,
    group: dict[str, object],
    issues: list[FpaValidationIssue],
    mode: str = "",
    confirmed_decisions: object | None = None,
) -> list[dict[str, object]]:
    """Create structured confirmation questions from validator issues."""
    resolved_mode = normalize_confirmation_mode(mode)
    if resolved_mode == "auto":
        return []

    decisions = normalize_confirmed_decisions(confirmed_decisions or {})
    questions: list[dict[str, object]] = []
    seen: set[str] = set()
    for issue in issues:
        question = _question_for_issue(group, issue)
        if question is None:
            continue
        if resolved_mode == "cautious" and not bool(question.get("high_risk")):
            continue
        question_id = str(question["id"])
        if question_id in seen or question_id in decisions:
            continue
        seen.add(question_id)
        question.pop("high_risk", None)
        questions.append(question)
    return questions


def confirmation_feedback(confirmed_decisions: object | None) -> str:
    """Render confirmed decisions as hard constraints for the next AI call."""
    decisions = normalize_confirmed_decisions(confirmed_decisions or {})
    if not decisions:
        return ""
    lines = [
        "以下是用户已确认的 FPA 计量口径，本次生成必须作为硬约束执行：",
    ]
    for decision_id, decision in sorted(decisions.items()):
        lines.append(f"- {decision_id}: {decision.value}（scope={decision.scope}）")
    lines.append("不得在同一确认项上重新摇摆；如输入材料已改变，应重新识别争议点。")
    return "\n".join(lines)


def confirmed_decision_count(confirmed_decisions: object | None) -> int:
    return len(normalize_confirmed_decisions(confirmed_decisions or {}))


def _question_for_issue(
    group: dict[str, object],
    issue: FpaValidationIssue,
) -> dict[str, object] | None:
    module_key = _slug(
        "-".join(
            str(group.get(key, "") or "")
            for key in ("client_type", "l1", "l2", "l3")
        )
    )
    if issue.code == "validator.split_crud_ei":
        return {
            "id": f"merge_crud_{module_key}",
            "topic": "维护类 EI 合并",
            "question": "是否将同一业务对象的新增、修改、删除等维护动作合并为一个维护类 EI？",
            "recommendation": "yes",
            "reason": "这些操作针对同一数据组或同一管理场景，按 strict_fpa 口径应按逻辑事务合并。",
            "options": [
                {"value": "yes", "label": "合并为一个 EI"},
                {"value": "no", "label": "分别计为多个 EI"},
            ],
            "source_issue": issue.code,
            "high_risk": True,
        }
    if issue.code == "validator.split_query_eq":
        return {
            "id": f"merge_query_{module_key}",
            "topic": "查询类 EQ 合并",
            "question": "是否将同一列表或搜索场景的默认查询、条件搜索合并为一个查询类 EQ？",
            "recommendation": "yes",
            "reason": "这些查询读取同一类业务结果且不改变数据，按 strict_fpa 口径应按同一查询逻辑事务合并。",
            "options": [
                {"value": "yes", "label": "合并为一个 EQ"},
                {"value": "no", "label": "分别计为多个 EQ"},
            ],
            "source_issue": issue.code,
            "high_risk": True,
        }
    if issue.code == "validator.ordinary_service_as_eif":
        return {
            "id": f"eif_boundary_{module_key}_{_slug(issue.message)}",
            "topic": "EIF 识别",
            "question": "该普通校验、认证、权限或外部服务调用是否生成 EIF？",
            "recommendation": "no",
            "reason": "输入只体现服务调用或校验动作，没有明确外部系统维护的数据组证据。",
            "options": [
                {"value": "no", "label": "不生成 EIF"},
                {"value": "yes", "label": "生成 EIF"},
            ],
            "source_issue": issue.code,
            "high_risk": True,
        }
    if issue.code == "validator.query_as_ei":
        return {
            "id": f"query_type_{module_key}_{_slug(issue.message)}",
            "topic": "类型判定",
            "question": "该只读查询、搜索、列表或查看流程是否按 EQ 计量？",
            "recommendation": "eq",
            "reason": "流程名称或说明体现只读取并展示数据，不改变本系统维护数据。",
            "options": [
                {"value": "eq", "label": "按 EQ 计量"},
                {"value": "ei", "label": "按 EI 计量"},
            ],
            "source_issue": issue.code,
            "high_risk": True,
        }
    if issue.code == "validator.explanation_structure":
        return {
            "id": f"explanation_structure_{module_key}_{issue.row_index if issue.row_index is not None else 'row'}",
            "topic": "计算依据说明",
            "question": "是否要求该功能点补齐结构化计算依据说明？",
            "recommendation": "yes",
            "reason": "正式审阅页要求计算依据说明包含来源场景、业务数据、业务规则和计算说明。",
            "options": [
                {"value": "yes", "label": "补齐结构化说明"},
                {"value": "no", "label": "保留当前说明"},
            ],
            "source_issue": issue.code,
            "high_risk": False,
        }
    return None


def _slug(value: str) -> str:
    text = re.sub(r"\s+", "_", str(value or "").strip())
    text = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or "item"
