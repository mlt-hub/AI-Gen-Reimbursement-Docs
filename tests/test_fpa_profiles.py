import pytest
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import (
    CURRENT_PROJECT_PROFILE,
    STRICT_FPA_PROFILE,
    get_fpa_profile,
)


def test_default_profile_is_current_project():
    assert get_fpa_profile() is CURRENT_PROJECT_PROFILE
    assert get_fpa_profile("current_project") is CURRENT_PROJECT_PROFILE
    assert get_fpa_profile("strict_fpa") is STRICT_FPA_PROFILE


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="未知 FPA profile"):
        get_fpa_profile("unknown_profile")


def test_current_project_prompt_contains_profile_rules():
    prompt = CURRENT_PROJECT_PROFILE.build_prompt(
        {
            "client_type": "后台",
            "l1": "业务",
            "l2": "管理",
            "l3": "客户管理",
            "processes": [],
        },
        ["规则一"],
    )

    assert CURRENT_PROJECT_PROFILE.core_rules in prompt
    assert "默认生成 1 条三级模块级界面开发行" in prompt


def test_strict_prompt_forbids_development_work_items():
    prompt = STRICT_FPA_PROFILE.build_prompt(
        {
            "client_type": "后台",
            "l1": "业务",
            "l2": "管理",
            "l3": "客户管理",
            "processes": [],
        },
        ["规则一"],
    )

    assert STRICT_FPA_PROFILE.core_rules in prompt
    assert "禁止输出界面开发、接口开发、逻辑处理开发" in prompt


def test_fpa_user_prompt_template_can_be_loaded_from_separate_config(tmp_path):
    yaml_file = tmp_path / "fpa_user_prompts_config.yaml"
    yaml_file.write_text(
        """
fpa_eval:
  user_templates:
    strict_fpa: |-
      自定义 strict 模板
      ${core_rules}
      RULES:
      ${judgement_rules}
      PAYLOAD:
      ${payload_json}
      UNKNOWN:
      ${unknown_placeholder}
""",
        encoding="utf-8",
    )

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
