from ai_gen_reimbursement_docs.fpa_agent_review import build_fpa_agent_review
from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    STRICT_FPA_PROFILE,
    UI_API_MAPPING_PROFILE,
)


def _group():
    return {
        "client_type": "地市后台",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户档案",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "查询客户",
                "description": "按客户名称查询客户列表。",
                "type": "新增",
            }
        ],
    }


def test_strict_fpa_agent_review_contract_is_primary():
    review = build_fpa_agent_review(
        group=_group(),
        profile_name=STRICT_FPA_PROFILE.name,
        profile_kind=STRICT_FPA_PROFILE.agent_review_profile_kind(),
    )

    assert review["profile"] == "strict_fpa"
    assert review["profile_kind"] == "strict_fpa"
    assert review["contract"] == "strict_fpa_contract"
    assert review["applicability"] == "primary"
    assert review["contract_outputs"]["judgement"] == "type_judgement"
    assert review["contract_outputs"]["merge_review"] == "merge_review"
    assert review["contract_outputs"]["quality_review"] == "quality_review"


def test_unified_ui_agent_review_contract_is_debug_only():
    review = build_fpa_agent_review(
        group=_group(),
        profile_name=CUSTOM_RULES_PROFILE.name,
        profile_kind=CUSTOM_RULES_PROFILE.agent_review_profile_kind(),
    )

    assert review["profile"] == "unified_ui"
    assert review["profile_kind"] == "unified_ui"
    assert review["contract"] == "unified_ui_contract"
    assert review["applicability"] == "debug_only"
    assert review["contract_outputs"]["judgement"] == "workload_judgement"
    assert review["contract_outputs"]["merge_review"] == "unified_merge_review"
    assert review["contract_outputs"]["quality_review"] == "unified_quality_review"


def test_ui_api_mapping_agent_review_contract_is_debug_only():
    review = build_fpa_agent_review(
        group=_group(),
        profile_name=UI_API_MAPPING_PROFILE.name,
        profile_kind=UI_API_MAPPING_PROFILE.agent_review_profile_kind(),
    )

    assert review["profile"] == "ui_api_mapping"
    assert review["profile_kind"] == "ui_api_mapping"
    assert review["contract"] == "ui_api_mapping_contract"
    assert review["applicability"] == "debug_only"
    assert review["contract_outputs"]["judgement"] == "mapping_judgement"
    assert review["contract_outputs"]["merge_review"] == "mapping_merge_review"
    assert review["contract_outputs"]["quality_review"] == "mapping_quality_review"
