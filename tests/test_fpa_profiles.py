import pytest
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    STRICT_FPA_PROFILE,
    get_fpa_profile,
    resolve_fpa_execution_config,
    set_current_fpa_rule_set_config,
    reset_current_fpa_rule_set_config,
)


def _write_fpa_config(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text(
        """
profile: custom_rules
profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    system_prompt: custom_rules
    user_prompt: custom_rules
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    system_prompt: strict_fpa
    user_prompt: strict_fpa
prompt_sets:
  custom_rules:
    system: CUSTOM SYSTEM
    user: |-
      自定义 custom 模板
      ${core_rules}
      CUSTOM_RULES:
      ${judgement_rules}
      PAYLOAD:
      ${payload_json}
  strict_fpa:
    system: STRICT SYSTEM
    user: |-
      自定义 strict 模板
      ${core_rules}
      RULES:
      ${judgement_rules}
      PAYLOAD:
      ${payload_json}
      UNKNOWN:
      ${unknown_placeholder}
rule_sets:
  custom_rules_default: {}
  strict_fpa_default: {}
  telecom_rules:
    extends: strict_fpa_default
    keyword_rules:
      merge: append
      items:
        - type: EO
          keywords: ["打印客户清单"]
          reason: "客户清单打印属于格式化输出，按 EO。"
    type_mapping_rules:
      merge: append
      items:
        - type: ILF
          keywords: ["本地报表快照"]
          reason: "本系统持久化报表快照，按 ILF。"
        - type: EIF
          keywords: ["第三方评分标签"]
          reason: "第三方评分标签由外部维护，按 EIF。"
    internal_data_rules:
      merge: append
      items:
        - keywords: ["认证授权关系"]
          data_name: "认证授权关系"
          reason: "本系统维护认证授权关系，按 ILF。"
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["行业平台"]
          data_name: "行业平台客户档案"
          data_nouns: ["客户", "档案"]
  telecom_replace_rules:
    extends: telecom_rules
    keyword_rules:
      merge: replace
      items:
        - type: EQ
          keywords: ["浏览客户清单"]
    type_mapping_rules:
      merge: replace
      items:
        - type: EIF
          keywords: ["标签平台客户标签"]
    internal_data_rules:
      merge: replace
      items:
        - keywords: ["客户标签关系"]
          data_name: "客户标签关系"
    external_data_rules:
      merge: replace
      items:
        - source_aliases: ["标签平台"]
          data_name: "标签平台客户标签"
          data_nouns: ["客户", "标签"]
""",
        encoding="utf-8",
    )


def test_default_profile_is_custom_rules():
    assert get_fpa_profile() is CUSTOM_RULES_PROFILE
    assert get_fpa_profile("custom_rules") is CUSTOM_RULES_PROFILE
    assert get_fpa_profile("strict_fpa") is STRICT_FPA_PROFILE


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="未知 FPA profile"):
        get_fpa_profile("unknown_profile")


def test_execution_config_uses_profile_defaults(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        custom = resolve_fpa_execution_config("custom_rules")
        assert custom.profile is CUSTOM_RULES_PROFILE
        assert custom.strategy == "rules_first"
        assert custom.rule_set == "custom_rules_default"

        strict = resolve_fpa_execution_config("strict_fpa")
        assert strict.profile is STRICT_FPA_PROFILE
        assert strict.strategy == "ai_first"
        assert strict.rule_set == "strict_fpa_default"


def test_execution_config_accepts_explicit_strategy_and_rule_set(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_only", "strict_fpa_default")
        assert config.strategy == "ai_only"
        assert config.rule_set == "strict_fpa_default"


def test_rule_set_extends_are_loaded(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")

    assert config.rule_set == "telecom_rules"
    assert config.rule_set_config.extends == "strict_fpa_default"
    assert config.rule_set_config.keyword_rules[0].fpa_type == "EO"
    assert config.rule_set_config.type_mapping_rules[0].fpa_type == "ILF"
    assert config.rule_set_config.internal_data_rules[0].data_name == "认证授权关系"
    assert config.rule_set_config.external_data_rules[0].data_name == "行业平台客户档案"


def test_rule_set_external_data_rules_affect_strict_profile(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            fpa_type, reason = STRICT_FPA_PROFILE.infer_type(
                "行业平台客户档案",
                "引用行业平台维护的客户档案，本系统不维护。",
            )
        finally:
            reset_current_fpa_rule_set_config(token)

    assert fpa_type == "EIF"
    assert "外部系统维护" in reason


def test_rule_set_replace_discards_parent_rule_sections(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_replace_rules")

    assert [rule.keywords for rule in config.rule_set_config.keyword_rules] == [("浏览客户清单",)]
    assert [rule.keywords for rule in config.rule_set_config.type_mapping_rules] == [("标签平台客户标签",)]
    assert [rule.data_name for rule in config.rule_set_config.internal_data_rules] == ["客户标签关系"]
    assert [rule.data_name for rule in config.rule_set_config.external_data_rules] == ["标签平台客户标签"]


def test_rule_set_keyword_rules_affect_strict_profile(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            fpa_type, reason = STRICT_FPA_PROFILE.infer_type(
                "打印客户清单",
                "按查询条件生成客户清单打印文件。",
            )
        finally:
            reset_current_fpa_rule_set_config(token)

    assert fpa_type == "EO"
    assert reason == "客户清单打印属于格式化输出，按 EO。"


def test_rule_set_type_mapping_rules_affect_strict_profile(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            fpa_type, reason = STRICT_FPA_PROFILE.infer_type(
                "本地报表快照",
                "查询条件生成后持久化保存本地报表快照。",
            )
            has_conflict = STRICT_FPA_PROFILE.has_obvious_conflict(
                "本地报表快照",
                "查询条件生成后持久化保存本地报表快照。",
                "EO",
            )
            desc_only_type, desc_only_reason = STRICT_FPA_PROFILE.infer_type(
                "评分标签",
                "读取第三方评分标签并展示。",
            )
        finally:
            reset_current_fpa_rule_set_config(token)

    assert fpa_type == "ILF"
    assert reason == "本系统持久化报表快照，按 ILF。"
    assert has_conflict
    assert desc_only_type == "EIF"
    assert desc_only_reason == "第三方评分标签由外部维护，按 EIF。"


def test_rule_set_internal_data_rules_affect_strict_profile(tmp_path):
    _write_fpa_config(tmp_path)
    group = {
        "client_type": "后台",
        "l1": "认证",
        "l2": "授权",
        "l3": "授权管理",
        "l3_desc": "维护认证授权关系。",
        "processes": [
            {
                "name": "维护认证授权关系",
                "type": "新增",
                "desc": "本系统维护认证授权关系，并支持新增和删除授权。",
            }
        ],
    }
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = STRICT_FPA_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)

    types = {str(row["新增/修改功能点"]): str(row["类型"]) for row in rows}
    assert types["认证授权关系"] == "ILF"


def test_custom_rules_prompt_is_rendered_from_config(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        prompt = CUSTOM_RULES_PROFILE.build_prompt(
            {
                "client_type": "后台",
                "l1": "业务",
                "l2": "管理",
                "l3": "客户管理",
                "processes": [],
            },
            ["规则一"],
        )

    assert CUSTOM_RULES_PROFILE.core_rules in prompt
    assert "自定义 custom 模板" in prompt
    assert "1) 规则一" in prompt


def test_missing_fpa_user_prompt_config_raises(tmp_path):
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        with pytest.raises(ValueError, match="未找到 FPA 配置文件"):
            STRICT_FPA_PROFILE.build_prompt(
                {
                    "client_type": "后台",
                    "l1": "业务",
                    "l2": "管理",
                    "l3": "客户管理",
                    "processes": [],
                },
                ["规则一"],
            )


def test_fpa_user_prompt_template_can_be_loaded_from_separate_config(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        prompt = STRICT_FPA_PROFILE.build_prompt(
            {
                "client_type": "后台",
                "l1": "业务",
                "l2": "管理",
                "l3": "客户管理",
                "l3_desc": "维护客户信息。",
                "processes": [],
            },
            ["规则一"],
        )

    assert "自定义 strict 模板" in prompt
    assert STRICT_FPA_PROFILE.core_rules in prompt
    assert "1) 规则一" in prompt
    assert '"l3": "客户管理"' in prompt
    assert "${unknown_placeholder}" in prompt


def test_strict_profile_normalizes_development_suffixes():
    assert STRICT_FPA_PROFILE.normalize_output_name("添加客户-逻辑处理开发") == "添加客户"
    assert STRICT_FPA_PROFILE.normalize_output_name("客户管理-界面开发") == "客户管理"


def test_strict_profile_prefers_explicit_name_action_over_description_keywords():
    fpa_type, _ = STRICT_FPA_PROFILE.infer_type(
        "添加垂直行业",
        "保存后刷新垂直行业列表，并展示查询结果。",
    )

    assert fpa_type == "EI"
    assert STRICT_FPA_PROFILE.has_obvious_conflict(
        "添加垂直行业",
        "保存后刷新垂直行业列表，并展示查询结果。",
        "EI",
    ) is False


def test_strict_profile_transaction_keyword_priority_for_mixed_actions():
    assert STRICT_FPA_PROFILE.infer_type(
        "导入并查看客户名单",
        "上传客户名单文件，导入后查看校验结果。",
    )[0] == "EI"
    assert STRICT_FPA_PROFILE.infer_type(
        "同步并查看组织信息",
        "从主数据平台同步组织基础信息，写入本系统后查看同步结果。",
    )[0] == "EI"
    assert STRICT_FPA_PROFILE.infer_type(
        "发起退款并查询结果",
        "调用支付网关发起退款，并查询支付网关返回的退款状态。",
    )[0] == "EI"
    assert STRICT_FPA_PROFILE.infer_type(
        "查询并导出客户清单",
        "按查询条件生成客户清单导出文件。",
    )[0] == "EO"


def test_strict_profile_external_service_query_is_not_eif():
    fpa_type, _ = STRICT_FPA_PROFILE.infer_type(
        "调用支付网关查询支付状态",
        "调用支付网关查询支付状态，不引用外部维护数据组。",
    )

    assert fpa_type == "EQ"


def test_strict_profile_type_conflict_matrix_for_transactions_and_data_functions():
    conflict_cases = [
        ("保存客户配置", "保存后刷新列表。", "EQ"),
        ("查看客户详情", "查看客户基础信息。", "EI"),
        ("导出客户清单", "导出客户清单文件。", "EQ"),
        ("客户档案", "本系统维护的客户基础信息。", "EI"),
        ("统一用户中心账号", "统一用户中心维护的人员账号，本系统只引用。", "EQ"),
    ]
    for name, desc, ai_type in conflict_cases:
        assert STRICT_FPA_PROFILE.has_obvious_conflict(name, desc, ai_type), (name, ai_type)

    non_conflict_cases = [
        ("保存客户配置", "保存后刷新列表。", "EI"),
        ("查看客户详情", "查看客户基础信息。", "EQ"),
        ("导出客户清单", "导出客户清单文件。", "EO"),
        ("客户档案", "本系统维护的客户基础信息。", "ILF"),
        ("统一用户中心账号", "统一用户中心维护的人员账号，本系统只引用。", "EIF"),
    ]
    for name, desc, ai_type in non_conflict_cases:
        assert not STRICT_FPA_PROFILE.has_obvious_conflict(name, desc, ai_type), (name, ai_type)
