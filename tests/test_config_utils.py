"""配置加载单元测试 —— _get_system_config_value, load_max_tokens 等。"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from cosmic_tool.config_utils import (
    _get_system_config_value,
    load_max_tokens,
    load_cfp_formula,
    load_cosmic_warn_marker,
    load_fpa_reduced_use_workload,
    load_model_name,
    _read_env_value,
)


class TestGetSystemConfigValue:
    def test_returns_default_when_key_missing(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("other_key: 42\n", encoding="utf-8")
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = _get_system_config_value("nonexistent", 99)
            assert result == 99

    def test_returns_default_when_file_missing(self, tmp_path):
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = _get_system_config_value("any_key", "fallback")
            assert result == "fallback"

    def test_returns_configured_value(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("max_tokens: 8000\n", encoding="utf-8")
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = _get_system_config_value("max_tokens", 2000)
            assert result == 8000

    def test_returns_default_on_yaml_error(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text(": broken: yaml: :\n", encoding="utf-8")
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = _get_system_config_value("key", "default_val")
            assert result == "default_val"

    def test_bool_type_preserved(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("cosmic_warn_marker: false\n", encoding="utf-8")
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = _get_system_config_value("cosmic_warn_marker", True)
            assert result is False


class TestLoadMaxTokens:
    def test_returns_default_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("cosmic_tool.config_utils._config_dir",
                       return_value=Path("/nonexistent")):
                result = load_max_tokens(default=2000)
                assert result == 2000

    def test_env_var_override(self):
        with patch.dict(os.environ, {"COSMIC_MAX_TOKENS": "16000"}, clear=True):
            result = load_max_tokens()
            assert result == 16000

    def test_env_var_8k_suffix(self):
        with patch.dict(os.environ, {"COSMIC_MAX_TOKENS": "8K"}, clear=True):
            result = load_max_tokens()
            assert result == 8000

    def test_env_var_1m_suffix(self):
        with patch.dict(os.environ, {"COSMIC_MAX_TOKENS": "1M"}, clear=True):
            result = load_max_tokens()
            assert result == 1_000_000

    def test_env_var_invalid_falls_back(self):
        with patch.dict(os.environ, {"COSMIC_MAX_TOKENS": "abc"}, clear=True):
            with patch("cosmic_tool.config_utils._config_dir",
                       return_value=Path("/nonexistent")):
                result = load_max_tokens(default=500)
                assert result == 500

    def test_yaml_config_8k(self, tmp_path):
        yaml_file = tmp_path / "system_config.yaml"
        yaml_file.write_text("max_tokens: 8K\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            with patch("cosmic_tool.config_utils._config_dir",
                       return_value=tmp_path):
                result = load_max_tokens(default=2000)
                assert result == 8000


class TestLoadCfpFormula:
    def test_default_formula(self):
        with patch("cosmic_tool.config_utils._config_dir",
                   return_value=Path("/nonexistent")):
            result = load_cfp_formula()
            assert "新增" in result
            assert "复用" in result
            assert "{row}" in result

    def test_custom_formula(self, tmp_path):
        rules_file = tmp_path / "business_rules.yaml"
        rules_file.write_text("cfp_formula: '=IF(A{row}=1,2,0)'\n", encoding="utf-8")
        with patch("cosmic_tool.config_utils._config_dir", return_value=tmp_path):
            result = load_cfp_formula()
            assert result == "=IF(A{row}=1,2,0)"


class TestBooleanLoaders:
    def test_load_cosmic_warn_marker_default(self):
        with patch("cosmic_tool.config_utils._config_dir",
                   return_value=Path("/nonexistent")):
            assert load_cosmic_warn_marker() is True

    def test_load_fpa_reduced_default(self):
        with patch("cosmic_tool.config_utils._config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_reduced_use_workload() is False


class TestLoadModelName:
    def test_returns_empty_when_not_configured(self):
        """未配置模型名时返回空字符串（由调用方提醒用户）。"""
        with patch("cosmic_tool.config_utils._config_dir",
                   return_value=Path("/nonexistent")):
            with patch.dict(os.environ, {}, clear=True):
                result = load_model_name()
                assert result == ""

    def test_env_var_override(self):
        with patch("cosmic_tool.config_utils._config_dir",
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
