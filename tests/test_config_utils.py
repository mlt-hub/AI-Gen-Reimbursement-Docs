"""配置加载单元测试 —— _get_system_config_value, load_max_tokens 等。"""
import os
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from ai_gen_reimbursement_docs.config_utils import (
    _get_system_config_value,
    copy_default_config_files,
    api_key_fingerprint,
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
    FpaConfigError,
    load_fpa_system_prompt_config,
    load_fpa_user_prompt_config,
    load_fpa_user_prompt_template,
    load_model_name,
    log_api_key_resolution,
    resolve_api_key,
    _read_env_value,
)


def test_copy_default_config_files_copies_all_templates_without_overwrite(tmp_path):
    source = tmp_path / "config"
    target = tmp_path / "home"
    source.mkdir()
    for name in [
        ".env.example",
        "system_config.yaml.example",
        "fpa_config.yaml.example",
    ]:
        (source / name).write_text(f"{name}\n", encoding="utf-8")
    target.mkdir()
    (target / ".env").write_text("existing\n", encoding="utf-8")

    created = copy_default_config_files(target, source)

    assert sorted(path.name for path in created) == [
        "fpa_config.yaml",
        "system_config.yaml",
    ]
    assert (target / ".env").read_text(encoding="utf-8") == "existing\n"
    assert (target / "system_config.yaml").exists()
    assert (target / "fpa_config.yaml").exists()


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
    user: CUSTOM ${core_rules}
  strict_fpa:
    system: STRICT SYSTEM
    user: STRICT ${core_rules}
rule_sets:
  custom_rules_default: {}
  strict_fpa_default: {}
  client_a_rules:
    extends: strict_fpa_default
    keyword_rules:
      - type: EO
        keywords: ["打印供应商清单"]
        reason: "打印清单属于格式化输出，按 EO。"
    internal_data_rules:
      - keywords: ["供应商准入关系"]
        data_name: "供应商准入关系"
        reason: "本系统维护供应商准入关系，按 ILF。"
    external_data_rules:
      - source_aliases: ["供应商平台"]
        data_name: "供应商档案"
        data_nouns: ["供应商"]
""",
        encoding="utf-8",
    )


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
    def test_missing_config_raises(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with pytest.raises(FpaConfigError, match="未找到 FPA 配置文件"):
                load_fpa_profile()

    def test_configured_profile(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace("profile: custom_rules", "profile: strict_fpa"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_profile() == "strict_fpa"

    def test_invalid_configured_profile_raises(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace("profile: custom_rules", "profile: fpa_profile"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="未知 FPA profile"):
                load_fpa_profile()


class TestLoadFpaExecutionOptions:
    def test_strategy_and_rule_set_from_profile_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_strategy("strict_fpa") == "ai_first"
            assert load_fpa_rule_set("strict_fpa") == "strict_fpa_default"

    def test_rule_sets_config_from_fpa_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_rule_sets_config()["client_a_rules"]["extends"] == "strict_fpa_default"

    def test_missing_profile_reference_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "profile: custom_rules", "profile: missing_profile"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="未知 FPA profile"):
                load_fpa_profile()

    def test_profile_rule_set_reference_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "rule_set: strict_fpa_default", "rule_set: missing_rule_set"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"profiles\.strict_fpa\.rule_set 指向不存在"):
                load_fpa_strategy("strict_fpa")

    def test_prompt_set_text_is_required(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "system: CUSTOM SYSTEM", 'system: ""'
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"prompt_sets\.custom_rules\.system 必须是非空字符串"):
                load_fpa_profile()

    def test_rule_set_extends_missing_parent_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "extends: strict_fpa_default", "extends: missing_parent"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"rule_sets\.client_a_rules\.extends 指向不存在"):
                load_fpa_rule_sets_config()

    def test_rule_set_extends_cycle_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace("custom_rules_default: {}", "custom_rules_default:\n    extends: client_a_rules")
        content = content.replace("extends: strict_fpa_default", "extends: custom_rules_default")
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="FPA rule_set 继承出现循环"):
                load_fpa_rule_sets_config()

    def test_rule_set_version_field_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "client_a_rules:\n    extends: strict_fpa_default",
                'client_a_rules:\n    version: "2026.05"\n    extends: strict_fpa_default',
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"rule_sets\.client_a_rules\.version 已废弃"):
                load_fpa_rule_sets_config()

    def test_external_data_rules_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                'source_aliases: ["供应商平台"]', 'source_aliases: "供应商平台"'
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"external_data_rules\[0\]\.source_aliases 必须是非空字符串列表"):
                load_fpa_rule_sets_config()

    def test_keyword_rules_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "type: EO", "type: ILF"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"keyword_rules\[0\]\.type 必须是 EI / EQ / EO"):
                load_fpa_rule_sets_config()

    def test_internal_data_rules_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                'keywords: ["供应商准入关系"]', 'keywords: []'
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"internal_data_rules\[0\]\.keywords 必须是非空字符串列表"):
                load_fpa_rule_sets_config()

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


class TestLoadFpaUserPromptTemplate:
    def test_missing_template_raises_when_not_configured(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with pytest.raises(FpaConfigError, match="未找到 FPA 配置文件"):
                load_fpa_user_prompt_template("strict_fpa")

    def test_configured_template(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_user_prompt_template("strict_fpa") == "STRICT ${core_rules}"

    def test_configured_template_exposes_safe_source_label(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_user_prompt_config("strict_fpa")

        assert result.text == "STRICT ${core_rules}"
        assert result.source_label == "用户配置（配置目录/fpa_config.yaml: prompt_sets.strict_fpa.user）"

    def test_fpa_system_prompt_exposes_safe_source_label(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_system_prompt_config("strict_fpa")

        assert result.text == "STRICT SYSTEM"
        assert result.source_label == "用户配置（配置目录/fpa_config.yaml: prompt_sets.strict_fpa.system）"


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


class TestResolveApiKey:
    def test_prefers_provided_key_and_uses_safe_fingerprint(self, caplog):
        caplog.set_level(logging.INFO)
        result = resolve_api_key(
            " sk-session ",
            provided_source="session_override",
        )

        assert result.value == "sk-session"
        assert result.source == "session_override"
        assert result.fingerprint == api_key_fingerprint("sk-session")
        assert result.fingerprint.startswith("sha256:")
        assert "sk-session" not in result.log_summary()

        log_api_key_resolution(
            logging.getLogger("ai_gen_reimbursement_docs.test"),
            result,
            context="unit",
        )

        assert "source=session_override" in caplog.text
        assert result.fingerprint in caplog.text
        assert "sk-session" not in caplog.text

    def test_resolves_user_env_file_before_system_env_by_default(self, tmp_path):
        (tmp_path / ".env").write_text(
            "ANTHROPIC_API_KEY=sk-file\n",
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}, clear=True):
                result = resolve_api_key()

        assert result.value == "sk-file"
        assert result.source == "user_env_file"

    def test_can_resolve_system_env_before_user_env(self, tmp_path):
        (tmp_path / ".env").write_text(
            "ANTHROPIC_API_KEY=sk-file\n",
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}, clear=True):
                result = resolve_api_key(override=False)

        assert result.value == "sk-env"
        assert result.source == "system_env"

    def test_falls_back_to_config_json_source(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with patch.dict(os.environ, {}, clear=True):
                with patch("ai_gen_reimbursement_docs.config_utils._read_json_value",
                           return_value="sk-json"):
                    result = resolve_api_key()

        assert result.value == "sk-json"
        assert result.source == "config_json"

    def test_missing_source_has_no_fingerprint(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with patch.dict(os.environ, {}, clear=True):
                with patch("ai_gen_reimbursement_docs.config_utils._read_json_value",
                           return_value=""):
                    result = resolve_api_key()

        assert result.value == ""
        assert result.source == "missing"
        assert result.fingerprint == ""
        assert result.log_summary() == "missing, source=missing"
