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
    external_data_rules:
      - source_aliases: ["行业平台"]
        data_name: "行业平台客户档案"
        data_nouns: ["客户", "档案"]
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
