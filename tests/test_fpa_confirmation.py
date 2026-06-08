from ai_gen_reimbursement_docs.fpa_confirmation import (
    build_fpa_confirmation_questions,
    confirmation_feedback,
    normalize_confirmed_decisions,
    normalize_confirmation_mode,
)
from ai_gen_reimbursement_docs.fpa_validator import FpaValidationIssue


def _group():
    return {
        "client_type": "地市后台",
        "l1": "垂直行业营销",
        "l2": "垂直行业管理",
        "l3": "垂直行业管理",
    }


def test_confirmation_mode_defaults_to_cautious_and_validates_values():
    assert normalize_confirmation_mode("") == "cautious"
    assert normalize_confirmation_mode("auto") == "auto"

    try:
        normalize_confirmation_mode("unknown")
    except ValueError as exc:
        assert "未知 FPA confirmation mode" in str(exc)
    else:
        raise AssertionError("unknown confirmation mode should fail")


def test_cautious_mode_creates_high_risk_confirmation_question():
    questions = build_fpa_confirmation_questions(
        group=_group(),
        mode="cautious",
        issues=[
            FpaValidationIssue(
                code="validator.ordinary_service_as_eif",
                message="短信平台疑似将普通校验/外部服务调用识别为 EIF",
                retryable=True,
            )
        ],
    )

    assert len(questions) == 1
    assert questions[0]["topic"] == "EIF 识别"
    assert questions[0]["recommendation"] == "no"


def test_strict_mode_includes_explanation_confirmation_but_cautious_skips_it():
    issue = FpaValidationIssue(
        code="validator.explanation_structure",
        message="计算依据说明格式不完整",
        row_index=0,
    )

    cautious = build_fpa_confirmation_questions(group=_group(), mode="cautious", issues=[issue])
    strict = build_fpa_confirmation_questions(group=_group(), mode="strict", issues=[issue])

    assert cautious == []
    assert len(strict) == 1
    assert strict[0]["topic"] == "计算依据说明"


def test_confirmed_decision_suppresses_same_question_and_renders_prompt_feedback():
    issue = FpaValidationIssue(
        code="validator.split_crud_ei",
        message="同一业务对象的多个维护动作疑似被拆成多个 EI",
        retryable=True,
    )
    first_questions = build_fpa_confirmation_questions(group=_group(), mode="cautious", issues=[issue])
    decision_id = first_questions[0]["id"]

    decisions = normalize_confirmed_decisions({
        decision_id: {"value": "yes", "scope": "current_run"}
    })
    second_questions = build_fpa_confirmation_questions(
        group=_group(),
        mode="cautious",
        issues=[issue],
        confirmed_decisions=decisions,
    )

    assert second_questions == []
    feedback = confirmation_feedback(decisions)
    assert decision_id in feedback
    assert "必须作为硬约束执行" in feedback


def test_unknown_confirmation_scope_falls_back_to_current_run():
    decisions = normalize_confirmed_decisions({
        "query_type_demo": {"value": "eq", "scope": "unknown_scope"}
    })

    assert decisions["query_type_demo"].scope == "current_run"
