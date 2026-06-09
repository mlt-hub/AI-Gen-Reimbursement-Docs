import json
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import CUSTOM_RULES_PROFILE, UI_API_MAPPING_PROFILE


def _write_config(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: unified_ui
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      ILF: 1
      default: 1
profiles:
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  ui_api_mapping:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: ui_api_mapping_rs
    core_rules: ui_api_mapping_cr
    system_prompt: ui_api_mapping_sp
    user_prompt: ui_api_mapping_up
core_rules:
  unified_ui_cr: UNIFIED CORE
  ui_api_mapping_cr: MAPPING CORE
system_prompt_sets:
  unified_ui_sp: UNIFIED SYSTEM
  ui_api_mapping_sp: MAPPING SYSTEM
user_prompt_sets:
  unified_ui_up: |-
    UNIFIED
    ${core_rules}
    ${judgement_rules}
    PAYLOAD:
    ${payload_json}
  ui_api_mapping_up: |-
    MAPPING
    ${core_rules}
    ${judgement_rules}
    PAYLOAD:
    ${payload_json}
rule_sets:
  unified_ui_rs: {}
  ui_api_mapping_rs: {}
""",
        encoding="utf-8",
    )


def _payload_from_prompt(prompt: str) -> dict[str, object]:
    return json.loads(prompt.split("PAYLOAD:", 1)[1])


def test_unified_ui_prompt_payload_exposes_profile_agent_review_contract(tmp_path):
    _write_config(tmp_path)
    group = {
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

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        payload = _payload_from_prompt(CUSTOM_RULES_PROFILE.build_prompt(group, ["规则一"]))

    review = payload["agent_review"]
    assert review["profile"] == "unified_ui"
    assert review["applicability"] == "debug_only"
    assert review["contract_outputs"]["judgement"] == "workload_judgement"
    assert review["workload_judgement"]["judgements"][0]["recommended_categories"] == ["界面开发", "查询处理开发"]
    assert review["unified_merge_review"]["groups"][0]["kind"] == "same_module_ui"


def test_ui_api_mapping_prompt_payload_exposes_mapping_agent_review_contract(tmp_path):
    _write_config(tmp_path)
    group = {
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

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        payload = _payload_from_prompt(UI_API_MAPPING_PROFILE.build_prompt(group, ["规则一"]))

    review = payload["agent_review"]
    assert review["profile"] == "ui_api_mapping"
    assert review["applicability"] == "debug_only"
    assert review["contract_outputs"]["judgement"] == "mapping_judgement"
    assert review["mapping_judgement"]["judgements"][0]["expected_default_rows"] == [
        {"suffix": "界面开发", "type": "EI"},
        {"suffix": "接口开发", "type": "ILF"},
    ]
    assert review["mapping_judgement"]["judgements"][0]["explicit_backend_rows"] == [
        {"name": "OA 审批接口", "type": "ILF"}
    ]
