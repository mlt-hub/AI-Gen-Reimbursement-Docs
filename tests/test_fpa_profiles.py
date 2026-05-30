import pytest

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


def test_strict_profile_normalizes_development_suffixes():
    assert STRICT_FPA_PROFILE.normalize_output_name("添加客户-逻辑处理开发") == "添加客户"
    assert STRICT_FPA_PROFILE.normalize_output_name("客户管理-界面开发") == "客户管理"
