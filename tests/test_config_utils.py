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
    diagnose_fpa_prompt_config,
    diagnose_fpa_user_prompt,
    inspect_fpa_runtime_config_files,
    load_fpa_excel_recalc_check,
    load_fpa_domain_context,
    load_max_tokens,
    load_cfp_formula,
    load_cosmic_warn_marker,
    load_gen_cosmic_allow_draft_excel_output,
    load_gen_cosmic_cfp_policy,
    load_fpa_reduced_use_workload,
    load_fpa_adjustment_value_config,
    load_fpa_profile,
    load_fpa_rule_set,
    load_fpa_strategy,
    load_fpa_check_columns,
    load_fpa_core_rules_config,
    load_fpa_calculation_explanation_rules,
    load_fpa_judgement_rules_config,
    load_fpa_judgement_rules_source,
    load_fpa_rule_sets_config,
    FpaConfigError,
    load_fpa_system_prompt_config,
    load_fpa_user_prompt_config,
    load_fpa_user_prompt_template,
    load_model_name,
    load_output_template_profile,
    log_api_key_resolution,
    resolve_api_key,
    validate_fpa_runtime_config_files,
    _read_env_value,
)
from ai_gen_reimbursement_docs.fpa_profiles import adjust_value_for_type, calculate_fpa_adjustment_for_row


def test_copy_default_config_files_copies_all_templates_without_overwrite(tmp_path):
    source = tmp_path / "config"
    target = tmp_path / "home"
    source.mkdir()
    for name in [
        ".env.example",
        "system_config.yaml.example",
        "fpa_config.yaml.example",
        "fpa_judgement_rules.yaml.example",
        "domain_context.json.example",
    ]:
        (source / name).write_text(f"{name}\n", encoding="utf-8")
    target.mkdir()
    (target / ".env").write_text("existing\n", encoding="utf-8")

    created = copy_default_config_files(target, source)

    assert sorted(path.name for path in created) == [
        "domain_context.json",
        "fpa_config.yaml",
        "fpa_judgement_rules.yaml",
        "system_config.yaml",
    ]
    assert (target / ".env").read_text(encoding="utf-8") == "existing\n"
    assert (target / "system_config.yaml").exists()
    assert (target / "fpa_config.yaml").exists()
    assert (target / "fpa_judgement_rules.yaml").exists()
    assert (target / "domain_context.json").exists()


def test_inspect_fpa_runtime_config_files_reports_missing_files(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text("profiles: {}\n", encoding="utf-8")

    status = inspect_fpa_runtime_config_files(tmp_path)

    assert status["config_dir"] == str(tmp_path)
    assert status["files"] == {
        "fpa_config.yaml": True,
        "fpa_judgement_rules.yaml": False,
        "domain_context.json": False,
    }
    assert status["missing"] == ["fpa_judgement_rules.yaml", "domain_context.json"]
    assert status["present"] is False


def test_validate_fpa_runtime_config_files_accepts_copied_defaults(tmp_path):
    source = Path(__file__).resolve().parents[1] / "config"
    copy_default_config_files(tmp_path, source)

    status = validate_fpa_runtime_config_files(tmp_path)

    assert status["present"] is True
    assert status["missing"] == []


def test_validate_fpa_runtime_config_files_rejects_missing_files(tmp_path):
    with pytest.raises(FpaConfigError, match="FPA 运行配置缺失"):
        validate_fpa_runtime_config_files(tmp_path)


def _write_fpa_config(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: unified_ui
adjustment_value_method_default: standard_fpa
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
  standard_fpa:
    complexity_source: ai
    fallback_complexity: low
    weights:
      ILF: {low: 7, medium: 10, high: 15}
      EIF: {low: 5, medium: 7, high: 10}
      EI: {low: 3, medium: 4, high: 6}
      EO: {low: 4, medium: 5, high: 7}
      EQ: {low: 3, medium: 4, high: 6}
    data_function_complexity_matrix:
      - {ret_min: 1, det_min: 1, complexity: low}
    transaction_complexity_matrices:
      EI:
        - {ftr_min: 0, ftr_max: 1, det_min: 1, det_max: 4, complexity: low}
        - {ftr_min: 2, ftr_max: 2, det_min: 5, det_max: 15, complexity: medium}
      EO:
        - {ftr_min: 0, det_min: 1, complexity: low}
      EQ:
        - {ftr_min: 0, det_min: 1, complexity: low}
profiles:
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
core_rules:
  unified_ui_cr: CUSTOM CORE RULES
  strict_fpa_cr: STRICT CORE RULES
system_prompt_sets:
  unified_ui_sp: CUSTOM SYSTEM
  strict_fpa_sp: STRICT SYSTEM
user_prompt_sets:
  unified_ui_up: CUSTOM ${core_rules} ${judgement_rules} ${payload_json}
  strict_fpa_up: STRICT ${core_rules} ${judgement_rules} ${payload_json}
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
        explanation_template: "{name}，具体为以下：\n{items}"
      process_rows:
        enabled: true
        one_row_per_process: true
        default_name_suffix: "逻辑处理开发"
        type_suffixes:
          EQ: "查询处理开发"
          EO: "导出处理开发"
          EI: "导入处理开发"
        explanation_template: "{name}，具体为以下：\n1、{description}"
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  client_a_rules:
    extends: strict_fpa_rs
    keyword_rules:
      merge: append
      items:
        - type: EO
          keywords: ["打印供应商清单"]
          reason: "打印清单属于格式化输出，按 EO。"
    internal_data_rules:
      merge: append
      items:
        - keywords: ["供应商准入关系"]
          data_name: "供应商准入关系"
          reason: "本系统维护供应商准入关系，按 ILF。"
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["供应商平台"]
          data_name: "供应商档案"
          data_nouns: ["供应商"]
""",
        encoding="utf-8",
    )


def _write_fpa_domain_context(tmp_path):
    (tmp_path / "domain_context.json").write_text(
        """
{
  "system_boundary": "本系统维护供应商准入协同数据，不维护供应商主档。",
  "internal_data_groups": [
    {"name": "供应商准入关系", "aliases": ["供应商关系"]}
  ],
  "external_data_groups": [
    {"name": "供应商档案", "source": "供应商平台", "aliases": ["供应商主档"]}
  ],
  "external_services": [
    {"name": "短信平台", "aliases": ["短信服务"]}
  ]
}
""",
        encoding="utf-8",
    )


def _append_calculation_rules_fragment(tmp_path, *, strict_value: str | None = None) -> None:
    content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
    lines = [
        "",
        "prompt_fragments:",
        "  calculation_explanation_rules:",
        "    default: DEFAULT EXPLANATION RULES",
    ]
    if strict_value is not None:
        lines.append(f"    strict_fpa: {strict_value!r}")
    (tmp_path / "fpa_config.yaml").write_text(content + "\n".join(lines) + "\n", encoding="utf-8")


def test_default_fpa_prompt_diagnostics_resolve_calculation_rules(tmp_path):
    source = Path(__file__).resolve().parents[1] / "config"
    copy_default_config_files(tmp_path, source)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        for profile in ("strict_fpa", "unified_ui", "multi_uis", "ui_api_mapping"):
            diagnostics = diagnose_fpa_prompt_config(profile)

            assert diagnostics.ok is True, profile
            assert diagnostics.referenced is True, profile
            assert diagnostics.resolved is True, profile
            assert diagnostics.errors == (), profile
            assert diagnostics.unresolved_placeholders == (), profile
            assert "prompt_fragments.calculation_explanation_rules.default" in diagnostics.fragment_source
            assert "${" not in diagnostics.final_prompt_preview


def test_prompt_diagnostics_warn_when_calculation_rules_not_referenced(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_prompt_config("strict_fpa")

    assert diagnostics.ok is True
    assert diagnostics.referenced is False
    assert diagnostics.resolved is False
    assert any("未引用 calculation_explanation_rules" in item for item in diagnostics.warnings)


def test_prompt_diagnostics_error_when_referenced_fragment_is_missing(tmp_path):
    _write_fpa_config(tmp_path)
    path = tmp_path / "fpa_config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${calculation_explanation_rules}",
        ),
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_prompt_config("strict_fpa")

    assert diagnostics.ok is False
    assert diagnostics.referenced is True
    assert diagnostics.resolved is False
    assert any("缺少 prompt_fragments.calculation_explanation_rules.default" in item for item in diagnostics.errors)
    assert "${calculation_explanation_rules}" in diagnostics.unresolved_placeholders


def test_prompt_diagnostics_uses_profile_override_source(tmp_path):
    _write_fpa_config(tmp_path)
    path = tmp_path / "fpa_config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${calculation_explanation_rules}",
        ),
        encoding="utf-8",
    )
    _append_calculation_rules_fragment(tmp_path, strict_value="STRICT EXPLANATION RULES")

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_prompt_config("strict_fpa")

    assert diagnostics.ok is True
    assert diagnostics.resolved is True
    assert "prompt_fragments.calculation_explanation_rules.strict_fpa" in diagnostics.fragment_source
    assert "STRICT EXPLANATION RULES" in diagnostics.final_prompt_preview
    assert "DEFAULT EXPLANATION RULES" not in diagnostics.final_prompt_preview


def test_prompt_diagnostics_blank_profile_override_falls_back_to_default(tmp_path):
    _write_fpa_config(tmp_path)
    path = tmp_path / "fpa_config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${calculation_explanation_rules}",
        ),
        encoding="utf-8",
    )
    _append_calculation_rules_fragment(tmp_path, strict_value=" ")

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_prompt_config("strict_fpa")

    assert diagnostics.ok is True
    assert "prompt_fragments.calculation_explanation_rules.default" in diagnostics.fragment_source
    assert "DEFAULT EXPLANATION RULES" in diagnostics.final_prompt_preview
    assert any("strict_fpa 为空，已回退 default" in item for item in diagnostics.warnings)


def test_prompt_diagnostics_reports_unknown_placeholder(tmp_path):
    _write_fpa_config(tmp_path)
    path = tmp_path / "fpa_config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${unknown_placeholder}",
        ),
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_prompt_config("strict_fpa")

    assert diagnostics.ok is False
    assert diagnostics.unknown_placeholders == ("unknown_placeholder",)
    assert "${unknown_placeholder}" in diagnostics.unresolved_placeholders


def test_legacy_prompt_diagnostics_wrapper_returns_fragment_entry(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        diagnostics = diagnose_fpa_user_prompt("strict_fpa")

    assert diagnostics["profile"] == "strict_fpa"
    assert diagnostics["fragments"][0]["name"] == "calculation_explanation_rules"
    assert diagnostics["rendered_prompt"] == diagnostics["final_prompt_preview"]


class TestLoadFpaDomainContext:
    def test_loads_project_domain_boundary_context(self, tmp_path):
        _write_fpa_domain_context(tmp_path)

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            context = load_fpa_domain_context()

        assert context["system_boundary"] == "本系统维护供应商准入协同数据，不维护供应商主档。"
        assert context["internal_data_groups"] == [{"name": "供应商准入关系", "aliases": ["供应商关系"]}]
        assert context["external_data_groups"] == [
            {"name": "供应商档案", "source": "供应商平台", "aliases": ["供应商主档"]}
        ]
        assert context["external_services"] == [{"name": "短信平台", "aliases": ["短信服务"]}]

    def test_missing_domain_context_file_is_rejected(self, tmp_path):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="未找到 FPA 领域上下文文件"):
                load_fpa_domain_context()

    def test_external_data_group_source_is_required(self, tmp_path):
        _write_fpa_domain_context(tmp_path)
        path = tmp_path / "domain_context.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"source": "供应商平台", ', ""), encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"external_data_groups\[0\]\.source 必须是非空字符串"):
                load_fpa_domain_context()

    def test_external_services_must_be_a_list(self, tmp_path):
        _write_fpa_domain_context(tmp_path)
        path = tmp_path / "domain_context.json"
        path.write_text(path.read_text(encoding="utf-8").replace(
            '"external_services": [\n    {"name": "短信平台", "aliases": ["短信服务"]}\n  ]',
            '"external_services": "短信平台"',
        ), encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="external_services 必须是列表"):
                load_fpa_domain_context()


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

    def test_load_gen_cosmic_allow_draft_excel_output_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_gen_cosmic_allow_draft_excel_output() is False

    def test_load_gen_cosmic_allow_draft_excel_output_nested(self, tmp_path):
        (tmp_path / "system_config.yaml").write_text(
            "gen_cosmic:\n  allow_draft_excel_output: true\n",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=tmp_path):
            assert load_gen_cosmic_allow_draft_excel_output() is True

    def test_load_gen_cosmic_allow_draft_excel_output_ignores_flat_key(self, tmp_path):
        (tmp_path / "system_config.yaml").write_text(
            "gen_cosmic_allow_draft_excel_output: true\n",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=tmp_path):
            assert load_gen_cosmic_allow_draft_excel_output() is False

    def test_load_gen_cosmic_cfp_policy_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_gen_cosmic_cfp_policy() == {}

    def test_load_gen_cosmic_cfp_policy_nested_filters_invalid_values(self, tmp_path):
        (tmp_path / "system_config.yaml").write_text(
            "\n".join([
                "gen_cosmic:",
                "  cfp_policy:",
                "    新增: 1",
                "    复用: 0.5",
                "    利旧: 0",
                "    非法: bad",
                "    负数: -1",
            ]),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=tmp_path):
            assert load_gen_cosmic_cfp_policy() == {
                "新增": 1.0,
                "复用": 0.5,
                "利旧": 0.0,
            }

    def test_load_fpa_reduced_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_reduced_use_workload() is False

    def test_load_fpa_excel_recalc_check_default(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            assert load_fpa_excel_recalc_check() is False


class TestOutputTemplateProfiles:
    def test_load_output_template_profile_reads_direct_templates(self, tmp_path):
        (tmp_path / "system_config.yaml").write_text(
            "\n".join([
                "active_output_template_profile: delivery_a",
                "output_template_profiles:",
                "  delivery_a:",
                "    templates:",
                "      fpa_out_template: data/custom/FPA.xlsx",
                "      list: data/custom/list.xlsx",
            ]),
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_output_template_profile() == {
                "fpa_out_template": "data/custom/FPA.xlsx",
                "list": "data/custom/list.xlsx",
            }

    def test_load_output_template_profile_reads_template_pack(self, tmp_path):
        pack = tmp_path / "packs" / "standard"
        pack.mkdir(parents=True)
        (pack / "manifest.yaml").write_text(
            "\n".join([
                "template_pack_id: standard",
                "templates:",
                "  fpa: FPA.xlsx",
                "  spec_out_template: spec.docx",
            ]),
            encoding="utf-8",
        )
        (tmp_path / "system_config.yaml").write_text(
            "\n".join([
                "active_output_template_profile: standard",
                "output_template_profiles:",
                "  standard:",
                "    template_pack: packs/standard",
                "    templates:",
                "      list_out_template: data/list.xlsx",
            ]),
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_output_template_profile(project_root_path=tmp_path) == {
                "fpa": str(pack / "FPA.xlsx"),
                "spec_out_template": str(pack / "spec.docx"),
                "list_out_template": "data/list.xlsx",
            }

    def test_load_output_template_profile_returns_empty_without_active_profile(self, tmp_path):
        (tmp_path / "system_config.yaml").write_text(
            "output_template_profiles:\n  standard:\n    templates:\n      fpa: FPA.xlsx\n",
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_output_template_profile() == {}


class TestLoadFpaProfile:
    def test_missing_config_raises(self):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir",
                   return_value=Path("/nonexistent")):
            with pytest.raises(FpaConfigError, match="未找到 FPA 配置文件"):
                load_fpa_profile()

    def test_configured_profile(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace("default-profile: unified_ui", "default-profile: strict_fpa"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_profile() == "strict_fpa"

    def test_invalid_configured_profile_raises(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace("default-profile: unified_ui", "default-profile: fpa_profile"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="profiles\\.fpa_profile"):
                load_fpa_profile()

    def test_fpa_config_dir_env_overrides_only_fpa_runtime_config(self, tmp_path):
        home_config = tmp_path / "home"
        fpa_config = tmp_path / "fpa"
        home_config.mkdir()
        fpa_config.mkdir()
        _write_fpa_config(home_config)
        _write_fpa_config(fpa_config)
        fpa_path = fpa_config / "fpa_config.yaml"
        fpa_path.write_text(
            fpa_path.read_text(encoding="utf-8").replace(
                "CUSTOM ${core_rules} ${judgement_rules} ${payload_json}",
                "OVERRIDE ${core_rules} ${judgement_rules} ${payload_json}",
            ),
            encoding="utf-8",
        )

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=home_config):
            with patch.dict(os.environ, {"AI_REIMBURSEMENT_FPA_CONFIG_DIR": str(fpa_config)}):
                assert load_fpa_user_prompt_template("unified_ui").startswith("OVERRIDE")

class TestLoadFpaExecutionOptions:
    def test_adjustment_value_config_requires_explicit_legacy_weights(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_adjustment_value_config()

        assert result["method"] == "standard_fpa"
        assert result["methods"]["legacy_workload"]["type_weights"] == {"EI": 2, "default": 1}
        assert result["methods"]["standard_fpa"]["weights"]["EI"]["medium"] == 4

    def test_adjustment_value_config_rejects_missing_adjustment_value(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        content = path.read_text(encoding="utf-8")
        start = content.index("adjustment_value_method_default:")
        end = content.index("profiles:")
        path.write_text(content[:start] + content[end:], encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="adjustment_value_method_default"):
                load_fpa_adjustment_value_config()

    def test_adjustment_value_config_accepts_custom_legacy_weights(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                """      EI: 2
      default: 1""",
                """      EI: 5
      EO: 3
      default: 2""",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_adjustment_value_config()

        assert result["methods"]["legacy_workload"]["type_weights"] == {"EI": 5, "EO": 3, "default": 2}

    def test_adjust_value_for_type_uses_configured_legacy_weights(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "adjustment_value_method_default: standard_fpa",
                "adjustment_value_method_default: legacy_workload",
            ).replace(
                """      EI: 2
      default: 1""",
                """      EI: 5
      EO: 3
      default: 2""",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert adjust_value_for_type("EI") == 5
            assert adjust_value_for_type("EO") == 3
            assert adjust_value_for_type("EQ") == 2

    def test_standard_fpa_recalculates_complexity_and_weight_from_matrix(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = calculate_fpa_adjustment_for_row({
                "类型": "EI",
                "det_count": 8,
                "ftr_count": 2,
                "complexity": "low",
                "complexity_reason": "AI 初判为低。",
            })

        assert result["method"] == "standard_fpa"
        assert result["complexity"] == "中"
        assert result["adjustment_value"] == 4
        assert result["det_count"] == "8"
        assert result["ftr_count"] == "2"
        assert "代码按配置矩阵复算" in result["complexity_reason"]

    def test_standard_fpa_uses_fallback_complexity_when_evidence_missing(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = calculate_fpa_adjustment_for_row({"类型": "EO"})

        assert result["method"] == "standard_fpa"
        assert result["complexity"] == "低"
        assert result["adjustment_value"] == 4
        assert "配置兜底复杂度" in result["complexity_reason"]

    def test_adjustment_value_config_rejects_missing_default_weight(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                """    type_weights:
      EI: 2
      default: 1""",
                """    type_weights:
      EI: 5""",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="type_weights 必须包含 default"):
                load_fpa_adjustment_value_config()

    def test_strategy_and_rule_set_from_profile_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_strategy("strict_fpa") == "ai_first"
            assert load_fpa_rule_set("strict_fpa") == "strict_fpa_rs"

    def test_core_rules_from_profile_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_core_rules_config("strict_fpa")

        assert result.text == "STRICT CORE RULES"
        assert result.source_label == "用户配置（配置目录/fpa_config.yaml: core_rules.strict_fpa_cr）"

    def test_rule_sets_config_from_fpa_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_rule_sets_config()["client_a_rules"]["extends"] == "strict_fpa_rs"

    def test_judgement_rules_source_defaults_to_config(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_judgement_rules_source() == "config"

    def test_judgement_rules_source_accepts_template(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace("default-profile: unified_ui", "default-profile: unified_ui\njudgement_rules_source: template"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_judgement_rules_source() == "template"

    def test_judgement_rules_source_rejects_unknown_value(self, tmp_path):
        _write_fpa_config(tmp_path)
        path = tmp_path / "fpa_config.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace("default-profile: unified_ui", "default-profile: unified_ui\njudgement_rules_source: xxx"),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="未知 FPA judgement_rules_source: xxx"):
                load_fpa_judgement_rules_source()

    def test_load_fpa_judgement_rules_config(self, tmp_path):
        (tmp_path / "fpa_judgement_rules.yaml").write_text(
            """
judgement_rules:
  -  规则一
  - 规则二
""",
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            assert load_fpa_judgement_rules_config() == ["规则一", "规则二"]

    def test_missing_fpa_judgement_rules_config_is_rejected(self, tmp_path):
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="未找到 FPA 判定原则配置文件"):
                load_fpa_judgement_rules_config()

    @pytest.mark.parametrize(
        "content, message",
        [
            ("judgement_rules: []\n", "judgement_rules 必须是非空字符串列表"),
            ("judgement_rules: 规则一\n", "judgement_rules 必须是非空字符串列表"),
            ("judgement_rules:\n  - 规则一\n  - ''\n", r"judgement_rules\[1\] 必须是非空字符串"),
        ],
    )
    def test_invalid_fpa_judgement_rules_config_is_rejected(self, tmp_path, content, message):
        (tmp_path / "fpa_judgement_rules.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=message):
                load_fpa_judgement_rules_config()

    def test_missing_profile_reference_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "default-profile: unified_ui", "default-profile: missing_profile"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match="profiles\\.missing_profile"):
                load_fpa_profile()

    def test_profile_rule_set_reference_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "rule_set: strict_fpa_rs", "rule_set: missing_rule_set"
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
                "unified_ui_sp: CUSTOM SYSTEM", 'unified_ui_sp: ""'
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"system_prompt_sets\.unified_ui_sp 必须是非空字符串"):
                load_fpa_profile()

    def test_user_prompt_unknown_placeholder_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
                "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${unknown_placeholder}",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"user_prompt_sets\.strict_fpa_up 包含未知占位符: \$\{unknown_placeholder\}"):
                load_fpa_profile()

    def test_user_prompt_missing_required_placeholder_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
                "STRICT ${core_rules} ${payload_json}",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"user_prompt_sets\.strict_fpa_up 必须包含占位符: \$\{judgement_rules\}"):
                load_fpa_profile()

    def test_user_prompt_invalid_placeholder_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
                "STRICT ${core_rules} ${judgement_rules} ${payload_json} ${",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"user_prompt_sets\.strict_fpa_up 包含非法占位符"):
                load_fpa_profile()

    def test_rule_set_extends_missing_parent_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "extends: strict_fpa_rs", "extends: missing_parent"
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"rule_sets\.client_a_rules\.extends 指向不存在"):
                load_fpa_rule_sets_config()

    def test_rule_set_extends_cycle_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            "unified_ui_rs:\n    row_planning_rules:",
            "unified_ui_rs:\n    extends: client_a_rules\n    row_planning_rules:",
        )
        content = content.replace("extends: strict_fpa_rs", "extends: unified_ui_rs")
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(
                FpaConfigError,
                match="FPA rule_set 继承出现循环: unified_ui_rs -> client_a_rules -> unified_ui_rs",
            ):
                load_fpa_rule_sets_config()

    def test_rule_set_version_field_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "client_a_rules:\n    extends: strict_fpa_rs",
                'client_a_rules:\n    version: "2026.05"\n    extends: strict_fpa_rs',
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
            with pytest.raises(FpaConfigError, match=r"external_data_rules\.items\[0\]\.source_aliases 必须是非空字符串列表"):
                load_fpa_rule_sets_config()

    def test_rule_section_list_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                """external_data_rules:
      merge: append
      items:
        - source_aliases: ["供应商平台"]
          data_name: "供应商档案"
          data_nouns: ["供应商"]""",
                """external_data_rules:
      - source_aliases: ["供应商平台"]
        data_name: "供应商档案"
        data_nouns: ["供应商"]""",
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"external_data_rules 必须是对象"):
                load_fpa_rule_sets_config()

    def test_rule_section_merge_mode_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        (tmp_path / "fpa_config.yaml").write_text(
            (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8").replace(
                "merge: append", "merge: override", 1
            ),
            encoding="utf-8",
        )
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"keyword_rules\.merge 必须是 append 或 replace"):
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
            with pytest.raises(FpaConfigError, match=r"keyword_rules\.items\[0\]\.type 必须是 EI / EQ / EO"):
                load_fpa_rule_sets_config()

    def test_type_mapping_rules_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            """    internal_data_rules:
      merge: append""",
            """    type_mapping_rules:
      merge: append
      items:
        - type: BAD
          keywords: ["供应商风险快照"]
    internal_data_rules:
      merge: append""",
        )
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"type_mapping_rules\.items\[0\]\.type 必须是 EI / EQ / EO / ILF / EIF"):
                load_fpa_rule_sets_config()

    def test_ai_type_conflict_rules_shape_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            """    internal_data_rules:
      merge: append""",
            """    ai_type_conflict_rules:
      merge: append
      items:
        - expected_type: BAD
          ai_type: EO
          keywords: ["供应商风险快照"]
          conflict: "false"
    internal_data_rules:
      merge: append""",
        )
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"ai_type_conflict_rules\.items\[0\]\.expected_type 必须是 EI / EQ / EO / ILF / EIF"):
                load_fpa_rule_sets_config()

    def test_ai_type_conflict_rule_conflict_bool_is_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            """    internal_data_rules:
      merge: append""",
            """    ai_type_conflict_rules:
      merge: append
      items:
        - expected_type: ILF
          ai_type: EO
          keywords: ["供应商风险快照"]
          conflict: "false"
    internal_data_rules:
      merge: append""",
        )
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"ai_type_conflict_rules\.items\[0\]\.conflict 必须是布尔值"):
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
            with pytest.raises(FpaConfigError, match=r"internal_data_rules\.items\[0\]\.keywords 必须是非空字符串列表"):
                load_fpa_rule_sets_config()

    def test_coverage_rules_bool_fields_are_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            """    external_data_rules:
      merge: append""",
            """    coverage_rules:
      require_process_coverage: "false"
      require_data_function: true
    external_data_rules:
      merge: append""",
        )
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"coverage_rules\.require_process_coverage 必须是布尔值"):
                load_fpa_rule_sets_config()

    def test_row_planning_rules_required_fields_are_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace('        name_suffix: "界面开发"\n', "")
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"row_planning_rules\.ui_row\.name_suffix 为必填项"):
                load_fpa_rule_sets_config()

    def test_row_planning_rules_type_suffixes_are_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace('          EQ: "查询处理开发"', '          UNKNOWN: "查询处理开发"')
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"type_suffixes 包含非法类型: UNKNOWN"):
                load_fpa_rule_sets_config()

    def test_row_planning_rules_template_placeholders_are_rejected(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace("{items}", "{unknown}")
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"ui_row\.explanation_template 包含未知占位符: \{unknown\}"):
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
            assert load_fpa_user_prompt_template("strict_fpa") == "STRICT ${core_rules} ${judgement_rules} ${payload_json}"

    def test_configured_template_exposes_safe_source_label(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_user_prompt_config("strict_fpa")

        assert result.text == "STRICT ${core_rules} ${judgement_rules} ${payload_json}"
        assert result.source_label == "用户配置（配置目录/fpa_config.yaml: user_prompt_sets.strict_fpa_up）"

    def test_prompt_diagnostics_warns_when_fragment_is_not_referenced(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            diagnostics = diagnose_fpa_user_prompt("strict_fpa")

        assert diagnostics["profile"] == "strict_fpa"
        assert diagnostics["errors"] == []
        assert diagnostics["unresolved_placeholders"] == []
        assert diagnostics["fragments"] == [
            {
                "name": "calculation_explanation_rules",
                "referenced": False,
                "resolved": False,
                "source": "",
            }
        ]
        assert "未引用 calculation_explanation_rules" in diagnostics["warnings"][0]
        assert "[core_rules preview]" in diagnostics["rendered_prompt"]

    def test_prompt_diagnostics_reports_resolved_fragment(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${calculation_explanation_rules} ${payload_json}",
        )
        content += """
prompt_fragments:
  calculation_explanation_rules:
    default: DEFAULT RULES
"""
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            diagnostics = diagnose_fpa_user_prompt("strict_fpa")

        assert diagnostics["errors"] == []
        assert diagnostics["unresolved_placeholders"] == []
        assert diagnostics["fragments"][0]["referenced"] is True
        assert diagnostics["fragments"][0]["resolved"] is True
        assert diagnostics["fragments"][0]["source"] == (
            "用户配置（配置目录/fpa_config.yaml: prompt_fragments.calculation_explanation_rules.default）"
        )
        assert "DEFAULT RULES" in diagnostics["rendered_prompt"]

    def test_prompt_diagnostics_reports_profile_override_source(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${calculation_explanation_rules} ${payload_json}",
        )
        content += """
prompt_fragments:
  calculation_explanation_rules:
    default: DEFAULT RULES
    strict_fpa: STRICT OVERRIDE RULES
"""
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            diagnostics = diagnose_fpa_user_prompt("strict_fpa")

        assert diagnostics["warnings"] == []
        assert diagnostics["fragments"][0]["source"] == (
            "用户配置（配置目录/fpa_config.yaml: prompt_fragments.calculation_explanation_rules.strict_fpa）"
        )
        assert "STRICT OVERRIDE RULES" in diagnostics["rendered_prompt"]

    def test_prompt_diagnostics_reports_unknown_placeholder(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace("${payload_json}", "${payload_json} ${unknown}")
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            diagnostics = diagnose_fpa_user_prompt("strict_fpa")

        assert "${unknown}" in diagnostics["rendered_prompt"]
        assert diagnostics["unresolved_placeholders"] == ["${unknown}"]
        assert any("${unknown}" in error for error in diagnostics["errors"])

    def test_default_fpa_prompt_example_contains_calculation_explanation_rules(self, tmp_path):
        source = Path(__file__).resolve().parents[1] / "config"
        copy_default_config_files(tmp_path, source)

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            unified = load_fpa_user_prompt_template("unified_ui")
            multi_uis = load_fpa_user_prompt_template("multi_uis")
            mapping = load_fpa_user_prompt_template("ui_api_mapping")
            strict = load_fpa_user_prompt_template("strict_fpa")
            explanation_rules = load_fpa_calculation_explanation_rules("strict_fpa")
            unified_system = load_fpa_system_prompt_config("unified_ui").text
            multi_uis_system = load_fpa_system_prompt_config("multi_uis").text
            mapping_system = load_fpa_system_prompt_config("ui_api_mapping").text
            strict_system = load_fpa_system_prompt_config("strict_fpa").text

        for template in (unified, strict, multi_uis, mapping):
            assert "${calculation_explanation_rules}" in template
        assert "计算依据说明生成规则" in explanation_rules.text
        assert "来源场景" in explanation_rules.text
        assert "业务数据" in explanation_rules.text
        assert "业务规则" in explanation_rules.text
        assert "系统元素" in explanation_rules.text
        assert "计算说明" in explanation_rules.text
        assert "不得把数据库表直接等同为 ILF" in explanation_rules.text
        assert "不要写“未识别到”" in explanation_rules.text
        assert "按后台数据库变更的表个数计量" in explanation_rules.text
        assert "不要把" in explanation_rules.text
        assert "ILF/EIF 数据功能使用" in explanation_rules.text
        assert "数据组名称" in explanation_rules.text
        assert explanation_rules.source_label == (
            "用户配置（配置目录/fpa_config.yaml: prompt_fragments.calculation_explanation_rules.default）"
        )
        assert "功能过程类型只能作为参考" in strict
        assert "不是功能点计数单位" in strict
        assert "必须合并为一个维护类 EI" in strict
        assert "必须合并为一个查询类 EQ" in strict
        assert "普通外部服务调用" in strict
        assert "xxx数据组" in strict
        assert "xxx维护" in strict
        assert "xxx查询" in strict
        assert "payload_json.agent_review.type_judgement.judgements" in strict
        assert "judgement_kind=external_data_function" in strict
        assert "suggested_type=EIF" in strict
        assert "同时输出 EIF 数据功能行和 EI 事务功能行" in strict
        assert "judgement_kind=ordinary_external_service" in strict
        assert "payload_json.merge_review.groups" in strict
        assert "agent_review.type_judgement" in strict_system
        assert "不得用 EI 替代 EIF" in strict_system
        for prompt in (unified_system, multi_uis_system, unified, multi_uis):
            assert "payload_json.agent_review.workload_judgement.judgements" in prompt
            assert "recommended_categories" in prompt
        assert "不要因为已有查询处理开发行就省略界面开发行" in unified
        assert "不要只输出界面开发行替代这些处理开发行" in unified
        assert "独立页面、独立业务对象、独立业务流程或独立用户端" in multi_uis
        assert "不要只输出界面开发行替代这些处理开发行" in multi_uis
        assert "payload_json.agent_review.mapping_judgement.judgements" in mapping_system
        assert "expected_default_rows" in mapping_system
        assert "explicit_backend_rows" in mapping_system
        assert "逐个 source_process_id 覆盖 expected_default_rows" in mapping
        assert "不要因为存在明确接口/后端调用行就省略默认界面开发行或默认接口开发行" in mapping
        assert "explicit_backend_rows 为空时，不得额外编造接口/后端调用行" in mapping

    def test_calculation_explanation_rules_profile_override(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content += """
prompt_fragments:
  calculation_explanation_rules:
    default: DEFAULT RULES
    strict_fpa: STRICT OVERRIDE RULES
"""
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            strict = load_fpa_calculation_explanation_rules("strict_fpa")
            unified = load_fpa_calculation_explanation_rules("unified_ui")

        assert strict.text == "STRICT OVERRIDE RULES"
        assert strict.source_label == (
            "用户配置（配置目录/fpa_config.yaml: prompt_fragments.calculation_explanation_rules.strict_fpa）"
        )
        assert unified.text == "DEFAULT RULES"

    def test_prompt_using_calculation_explanation_rules_requires_fragment(self, tmp_path):
        _write_fpa_config(tmp_path)
        content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
        content = content.replace(
            "STRICT ${core_rules} ${judgement_rules} ${payload_json}",
            "STRICT ${core_rules} ${judgement_rules} ${calculation_explanation_rules} ${payload_json}",
        )
        (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")

        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            with pytest.raises(FpaConfigError, match=r"prompt_fragments"):
                load_fpa_user_prompt_template("strict_fpa")

    def test_fpa_system_prompt_exposes_safe_source_label(self, tmp_path):
        _write_fpa_config(tmp_path)
        with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
            result = load_fpa_system_prompt_config("strict_fpa")

        assert result.text == "STRICT SYSTEM"
        assert result.source_label == "用户配置（配置目录/fpa_config.yaml: system_prompt_sets.strict_fpa_sp）"


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
