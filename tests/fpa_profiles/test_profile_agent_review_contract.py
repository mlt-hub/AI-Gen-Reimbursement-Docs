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


def _mapping_group():
    return {
        "client_type": "业务端",
        "l1": "销售管理",
        "l2": "合同中心",
        "l3": "合同管理",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "提交合同审批",
                "description": "提交合同审批，调用 OA 审批接口。",
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
    assert "workload_judgement" not in review
    assert "unified_quality_review" not in review


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
    assert review["workload_judgement"]["judgements"][0]["recommended_categories"] == ["界面开发", "查询处理开发"]
    assert review["unified_merge_review"]["groups"][0]["kind"] == "same_module_ui"
    roles = {role["name"]: role for role in review["roles"]}
    assert roles["workload_judge"]["output_key"] == "workload_judgement"
    assert roles["unified_quality_reviewer"]["status"] == "awaiting_rows"


def test_ui_api_mapping_agent_review_contract_is_debug_only():
    review = build_fpa_agent_review(
        group=_mapping_group(),
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
    assert "workload_judgement" not in review
    assert "unified_quality_review" not in review
    judgement = review["mapping_judgement"]["judgements"][0]
    assert judgement["expected_default_rows"] == [
        {"suffix": "界面开发", "type": "EI"},
        {"suffix": "接口开发", "type": "ILF"},
    ]
    assert judgement["explicit_backend_rows"] == [{"name": "OA 审批接口", "type": "ILF"}]
    roles = {role["name"]: role for role in review["roles"]}
    assert roles["mapping_judge"]["output_key"] == "mapping_judgement"
    assert roles["mapping_quality_reviewer"]["status"] == "awaiting_rows"


def test_unified_ui_quality_review_warns_without_changing_rows():
    rows = [
        {
            "新增/修改功能点": "【地市后台】客户管理-客户中心-客户档案-查询客户-查询处理开发",
            "类型": "EQ",
            "源功能过程": "查询客户",
        }
    ]

    review = build_fpa_agent_review(
        group=_group(),
        rows=rows,
        profile_name=CUSTOM_RULES_PROFILE.name,
        profile_kind=CUSTOM_RULES_PROFILE.agent_review_profile_kind(),
    )

    issue_codes = {issue["code"] for issue in review["unified_quality_review"]["issues"]}
    assert "unified_ui.missing_ui_row" in issue_codes
    assert review["summary"]["profile_quality_issue_count"] >= 1
    assert rows[0]["新增/修改功能点"].endswith("查询客户-查询处理开发")


def test_unified_ui_quality_review_accepts_expected_ui_and_process_rows():
    rows = [
        {
            "新增/修改功能点": "【地市后台】客户管理-客户中心-客户档案-界面开发",
            "类型": "EI",
            "源功能过程": "查询客户",
        },
        {
            "新增/修改功能点": "【地市后台】客户管理-客户中心-客户档案-查询客户-查询处理开发",
            "类型": "EQ",
            "源功能过程": "查询客户",
        },
    ]

    review = build_fpa_agent_review(
        group=_group(),
        rows=rows,
        profile_name=CUSTOM_RULES_PROFILE.name,
        profile_kind=CUSTOM_RULES_PROFILE.agent_review_profile_kind(),
    )

    assert review["unified_quality_review"]["summary"]["issue_count"] == 0
    roles = {role["name"]: role for role in review["roles"]}
    assert roles["unified_quality_reviewer"]["status"] == "completed"


def test_ui_api_mapping_quality_review_accepts_expected_rows():
    rows = [
        {
            "新增/修改功能点": "【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发",
            "类型": "EI",
            "源功能过程": "提交合同审批",
        },
        {
            "新增/修改功能点": "【业务端】销售管理-合同中心-合同管理-提交合同审批-接口开发",
            "类型": "ILF",
            "源功能过程": "提交合同审批",
        },
        {
            "新增/修改功能点": "【业务端】销售管理-合同中心-合同管理-OA 审批接口",
            "类型": "ILF",
            "源功能过程": "提交合同审批",
        },
    ]

    review = build_fpa_agent_review(
        group=_mapping_group(),
        rows=rows,
        profile_name=UI_API_MAPPING_PROFILE.name,
        profile_kind=UI_API_MAPPING_PROFILE.agent_review_profile_kind(),
    )

    assert review["mapping_quality_review"]["summary"]["issue_count"] == 0
    roles = {role["name"]: role for role in review["roles"]}
    assert roles["mapping_quality_reviewer"]["status"] == "completed"


def test_ui_api_mapping_quality_review_warns_for_missing_and_wrong_type_rows():
    rows = [
        {
            "新增/修改功能点": "【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发",
            "类型": "ILF",
            "源功能过程": "提交合同审批",
        },
        {
            "新增/修改功能点": "【业务端】销售管理-合同中心-合同管理-OA 审批接口",
            "类型": "EI",
            "源功能过程": "",
        },
    ]

    review = build_fpa_agent_review(
        group=_mapping_group(),
        rows=rows,
        profile_name=UI_API_MAPPING_PROFILE.name,
        profile_kind=UI_API_MAPPING_PROFILE.agent_review_profile_kind(),
    )

    issue_codes = {issue["code"] for issue in review["mapping_quality_review"]["issues"]}
    assert "ui_api_mapping.wrong_default_ui_type" in issue_codes
    assert "ui_api_mapping.missing_default_api_row" in issue_codes
    assert "ui_api_mapping.wrong_explicit_backend_type" in issue_codes
    assert "ui_api_mapping.explicit_backend_missing_source" in issue_codes
    assert review["summary"]["profile_quality_issue_count"] >= 4
