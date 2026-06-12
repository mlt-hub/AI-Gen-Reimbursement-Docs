from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_agent_review import build_fpa_agent_review
from ai_gen_reimbursement_docs.fpa_profiles import (
    reset_current_fpa_rule_set_config,
    resolve_fpa_execution_config,
    set_current_fpa_rule_set_config,
)


def _write_config(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: client_ui
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      ILF: 1
      default: 1
profiles:
  client_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    adjustment_value_method: legacy_workload
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  contract_api:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: ui_api_mapping_rs
    adjustment_value_method: legacy_workload
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
  unified_ui_up: UNIFIED ${core_rules} ${judgement_rules} ${payload_json}
  ui_api_mapping_up: MAPPING ${core_rules} ${judgement_rules} ${payload_json}
rule_sets:
  unified_ui_rs:
    row_planning_rules:
      ui_row:
        enabled: true
        scope: l3
        merge: single_row
        name_suffix: "界面开发"
        type: EI
        reason: "三级模块兜底合并界面能力。"
        empty_process_text: "完成三级模块页面交互能力"
        explanation_template: "{name}，具体为以下：\\n{items}"
      process_rows:
        enabled: true
        one_row_per_process: true
        default_name_suffix: "逻辑接口开发"
        type_suffixes:
          ILF: "逻辑接口开发"
          EO: "导出处理开发"
          EQ: "导入处理开发"
        explanation_template: "{name}，具体为以下：\\n1、{description}"
    keyword_rules:
      items:
        - type: ILF
          keywords: ["查询", "列表"]
          reason: "查询类逻辑接口按 ILF。"
        - type: ILF
          keywords: ["保存", "提交", "新增", "修改"]
          reason: "维护类逻辑接口按 ILF。"
  ui_api_mapping_rs:
    row_planning_rules:
      process_rows:
        enabled: true
        one_row_per_process: true
        default_name_suffix: "接口开发"
        type_suffixes:
          EI: "界面开发"
          ILF: "接口开发"
        explanation_template: "{name}，具体为以下：\\n1、{description}"
""",
        encoding="utf-8",
    )


def _unified_group():
    return {
        "client_type": "业务端",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户档案",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "查询客户",
                "name": "查询客户",
                "description": "按客户名称查询客户列表。",
                "desc": "按客户名称查询客户列表。",
                "change_status": "新增",
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
                "name": "提交合同审批",
                "description": "提交合同审批，调用 OA 审批接口。",
                "desc": "提交合同审批，调用 OA 审批接口。",
                "change_status": "新增",
            }
        ],
    }


def _point(group: dict[str, object], name: str) -> str:
    return f"【{group['client_type']}】{group['l1']}-{group['l2']}-{group['l3']}-{name}"


def test_custom_unified_ui_profile_harness_inherits_generation_and_review_contract(tmp_path):
    _write_config(tmp_path)
    group = _unified_group()

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("client_ui")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = config.profile.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)

    names = {str(row["新增/修改功能点"]) for row in rows}
    assert config.profile.name == "client_ui"
    assert config.profile.agent_review_profile_kind() == "unified_ui"
    assert _point(group, "界面开发") in names
    assert _point(group, "查询客户-逻辑接口开发") in names

    review = build_fpa_agent_review(
        group=group,
        rows=rows,
        profile_name=config.profile.name,
        profile_kind=config.profile.agent_review_profile_kind(),
    )

    assert review["profile"] == "client_ui"
    assert review["contract"] == "unified_ui_contract"
    assert review["unified_quality_review"]["summary"]["issue_count"] == 0


def test_custom_ui_api_mapping_profile_harness_inherits_generation_and_review_contract(tmp_path):
    _write_config(tmp_path)
    group = _mapping_group()

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("contract_api")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = config.profile.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)

    types = {str(row["新增/修改功能点"]): str(row["类型"]) for row in rows}
    assert config.profile.name == "contract_api"
    assert config.profile.agent_review_profile_kind() == "ui_api_mapping"
    assert types[_point(group, "提交合同审批-界面开发")] == "EI"
    assert types[_point(group, "提交合同审批-接口开发")] == "ILF"
    assert types[_point(group, "OA 审批接口")] == "ILF"

    review = build_fpa_agent_review(
        group=group,
        rows=rows,
        profile_name=config.profile.name,
        profile_kind=config.profile.agent_review_profile_kind(),
    )

    assert review["profile"] == "contract_api"
    assert review["contract"] == "ui_api_mapping_contract"
    assert review["mapping_quality_review"]["summary"]["issue_count"] == 0
