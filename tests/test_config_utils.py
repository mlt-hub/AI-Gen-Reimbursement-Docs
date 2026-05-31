"""配置加载单元测试 —— _get_system_config_value, load_max_tokens 等。"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from ai_gen_reimbursement_docs.config_utils import (
    _get_system_config_value,
    copy_default_config_files,
    load_fpa_excel_recalc_check,
    load_max_tokens,
    load_cfp_formula,
    load_cosmic_warn_marker,
    load_fpa_reduced_use_workload,
    load_fpa_profile,
    load_fpa_rule_set,
    load_fpa_strategy,
    load_fpa_check_columns,
    load_fpa_rule_sets_config,
    load_fpa_external_data_rules,
    load_fpa_user_prompt_template,
    load_model_name,
    _read_env_value,
)


def test_copy_default_config_files_copies_all_templates_without_overwrite(tmp_path):
    source = tmp_path / "config"
    target = tmp_path / "home"
    source.mkdir()
    for name in [
        ".env.example",
        "system_config.yaml.example",
        "fpa_user_prompts_config.yaml.example",
        "fpa_rule_sets_config.yaml.example",
    ]:
        (source / name).write_text(f"{name}\n", encoding="utf-8")
    target.mkdir()
    (target / ".env").write_text("existing\n", encoding="utf-8")

    created = copy_default_config_files(target, source)

    assert sorted(path.name for path in created) == [
        "fpa_rule_sets_config.yaml",
        "fpa_user_prompts_config.yaml",
        "system_config.yaml",
    ]
    assert (target / ".env").read_text(encoding="utf-8") == "existing\n"
    assert (target / "system_config.yaml").exists()
    assert (target / "fpa_user_prompts_config.yaml").exists()
    assert (target / "fpa_rule_sets_config.yaml").exists()


class TestGetSystemConfigValue:
    def test_returns_default_when_key_missing(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("other_key: 42\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = _get_system_config_value("nonexistent", 99)
            assert result == 99

    def test_returns_default_when_file_missing(self, tmp_path):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = _get_system_config_value("any_key", "fallback")
            assert result == "fallback"

    def test_returns_configured_value(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("max_tokens: 8000\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = _get_system_config_value("max_tokens", 2000)
            assert result == 8000

    def test_returns_default_on_yaml_error(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(": broken: yaml: :\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = _get_system_config_value("key", "default_val")
            assert result == "default_val"

    def test_bool_type_preserved(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("cosmic_warn_marker: false\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = _get_system_config_value("cosmic_warn_marker", True)
            assert result is False


class TestLoadMaxTokens:
    def test_returns_default_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                       return_value=Path("/nonexistent")):
                result = load_max_tokens(default=2000)
                assert result == 2000

    def test_env_var_override(self):
        with patch.dict(os.environ, {"AI_REIMBURSEMENT_MAX_TOKENS": "16000"}, clear=True):
            result = load_max_tokens()
            assert result == 16000

    def test_env_var_8k_suffix(self):
        with patch.dict(os.environ, {"AI_REIMBURSEMENT_MAX_TOKENS": "8K"}, clear=True):
            result = load_max_tokens()
            assert result == 8000

    def test_env_var_1m_suffix(self):
        with patch.dict(os.environ, {"AI_REIMBURSEMENT_MAX_TOKENS": "1M"}, clear=True):
            result = load_max_tokens()
            assert result == 1_000_000

    def test_env_var_invalid_falls_back(self):
        with patch.dict(os.environ, {"AI_REIMBURSEMENT_MAX_TOKENS": "abc"}, clear=True):
            with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                       return_value=Path("/nonexistent")):
                result = load_max_tokens(default=500)
                assert result == 500

    def test_yaml_config_8k(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("max_tokens: 8K\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                       return_value=tmp_path):
                result = load_max_tokens(default=2000)
                assert result == 8000


class TestLoadCfpFormula:
    def test_default_formula(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            result = load_cfp_formula()
            assert "新增" in result
            assert "复用" in result
            assert "{row}" in result

    def test_custom_formula(self, tmp_path):
        rules_file = tmp_path / "business_rules.yaml"
        rules_file.write_text("cfp_formula: '=IF(A{row}=1,2,0)'\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_cfp_formula()
            assert result == "=IF(A{row}=1,2,0)"


class TestBooleanLoaders:
    def test_load_cosmic_warn_marker_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_cosmic_warn_marker() is True

    def test_load_fpa_reduced_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_reduced_use_workload() is False

    def test_load_fpa_excel_recalc_check_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_excel_recalc_check() is False


class TestLoadFpaProfile:
    def test_default_profile(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_profile() == "custom_rules"

    def test_configured_profile(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("fpa_profile: strict_fpa\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_profile() == "strict_fpa"

    def test_invalid_configured_profile_uses_default(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("fpa_profile: fpa_profile\n", encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_profile() == "custom_rules"


class TestLoadFpaExecutionOptions:
    def test_strategy_and_rule_set_default_to_empty(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_strategy() == ""
            assert load_fpa_rule_set() == ""

    def test_strategy_and_rule_set_from_config(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(
            "fpa_strategy: ai_first\nfpa_rule_set: strict_fpa_default\n",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_strategy() == "ai_first"
            assert load_fpa_rule_set() == "strict_fpa_default"

    def test_rule_sets_config_from_separate_file(self, tmp_path):
        yaml_file = tmp_path / "fpa_rule_sets_config.yaml"
        yaml_file.write_text(
            """
rule_sets:
  client_a_rules:
    extends: strict_fpa_default
    version: "2026.05"
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_rule_sets_config()["client_a_rules"]["version"] == "2026.05"

    def test_fpa_check_columns_are_normalized(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(
            """
fpa_check_columns:
  FPA结果: ["序号", "新增/修改功能点", "类型"]
  Warnings: "Warning"
  空列: []
  非法列: 123
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_check_columns() == {
                "FPA结果": ["序号", "新增/修改功能点", "类型"],
                "Warnings": ["Warning"],
            }


class TestLoadFpaExternalDataRules:
    def test_default_rules_empty_when_not_configured(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_external_data_rules() == []

    def test_configured_rules_are_normalized(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(
            """
fpa_external_data_rules:
  - source_aliases: ["统一认证平台", "统一认证"]
    data_name: "统一认证账号"
    data_nouns: ["账号", "账户"]
  - source_aliases: "供应商平台"
    data_name: "供应商档案"
    data_nouns: "供应商"
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_external_data_rules() == [
                {
                    "source_aliases": ["统一认证平台", "统一认证"],
                    "data_name": "统一认证账号",
                    "data_nouns": ["账号", "账户"],
                },
                {
                    "source_aliases": ["供应商平台"],
                    "data_name": "供应商档案",
                    "data_nouns": ["供应商"],
                },
            ]

    def test_invalid_rules_are_ignored(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(
            """
fpa_external_data_rules:
  - source_aliases: []
    data_name: "空来源"
  - source_aliases: ["缺名称"]
  - "not a dict"
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_external_data_rules() == []


class TestLoadFpaUserPromptTemplate:
    def test_default_template_empty_when_not_configured(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_user_prompt_template("strict_fpa") == ""

    def test_configured_template(self, tmp_path):
        yaml_file = tmp_path / "fpa_user_prompts_config.yaml"
        yaml_file.write_text(
            """
fpa_eval:
  user_templates:
    strict_fpa: |-
      STRICT ${core_rules}
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_user_prompt_template("strict_fpa") == "STRICT ${core_rules}"


class TestLoadModelName:
    def test_returns_empty_when_not_configured(self):
        """未配置模型名时返回空字符串（由调用方提醒用户）。"""
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with patch.dict(os.environ, {}, clear=True):
                result = load_model_name()
                assert result == ""

    def test_env_var_override(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-sonnet-4-6"},
                            clear=True):
                result = load_model_name()
                assert result == "claude-sonnet-4-6"


class TestReadEnvValue:
    def test_reads_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=sk-test123\n", encoding="utf-8")
        result = _read_env_value("ANTHROPIC_API_KEY", env_file)
        assert result == "sk-test123"

    def test_rejects_placeholder(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=your_api_key_here\n", encoding="utf-8")
        result = _read_env_value("ANTHROPIC_API_KEY", env_file)
        assert result == ""

    def test_file_not_exists(self, tmp_path):
        result = _read_env_value("KEY", tmp_path / "nonexistent.env")
        assert result == ""
