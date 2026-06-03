import pytest
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import (
    ExternalDataGroupRule,
    FpaRuleSetConfig,
    STRICT_FPA_PROFILE,
    resolve_fpa_execution_config,
    reset_current_fpa_rule_set_config,
    set_current_fpa_rule_set_config,
)


@pytest.fixture
def strict_default_rule_context():
    config = FpaRuleSetConfig(
        name="strict_fpa_default",
        external_data_rules=(
            ExternalDataGroupRule(("统一用户中心", "用户中心"), "统一用户中心账号", ("账号", "账户", "人员", "组织", "机构", "信息")),
            ExternalDataGroupRule(("CRM", "客户关系管理系统"), "CRM客户档案", ("客户", "档案", "信息", "记录", "主数据")),
            ExternalDataGroupRule(("客户中心", "客户主数据平台"), "客户中心客户档案", ("客户", "档案", "信息", "记录", "主数据")),
            ExternalDataGroupRule(("财务核算系统",), "财务核算单据", ("单据", "报账", "凭证", "记录", "信息")),
            ExternalDataGroupRule(("财务系统",), "财务系统单据", ("单据", "报账", "凭证", "记录", "信息")),
            ExternalDataGroupRule(("ERP", "ERP系统"), "ERP业务单据", ("单据", "订单", "物料", "供应商", "记录", "信息")),
            ExternalDataGroupRule(("OA", "OA系统"), "OA流程单据", ("单据", "流程", "审批", "记录", "信息")),
            ExternalDataGroupRule(("主数据平台", "外部主数据"), "组织主数据", ("组织", "机构")),
            ExternalDataGroupRule(("主数据平台", "外部主数据"), "外部主数据", ("主数据", "基础数据", "数据组", "信息")),
        ),
    )
    token = set_current_fpa_rule_set_config(config)
    try:
        yield
    finally:
        reset_current_fpa_rule_set_config(token)


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "统一用户中心账号"),
        ("系统引用 CRM 系统维护的客户档案，本系统不维护客户主数据。", "CRM客户档案"),
        ("本模块读取客户中心提供的客户基础信息。", "客户中心客户档案"),
        ("本模块引用财务核算系统维护的报账单据，本系统不维护单据主数据。", "财务核算单据"),
        ("系统引用 ERP 系统维护的采购订单，本系统不维护订单主数据。", "ERP业务单据"),
        ("系统引用 OA 系统维护的审批流程记录。", "OA流程单据"),
        ("系统引用主数据平台维护的组织主数据。", "组织主数据"),
    ],
)
def test_strict_fpa_external_data_rule_table_matches_known_sources(strict_default_rule_context, text, expected_name):
    assert STRICT_FPA_PROFILE._is_external_data_group(text)
    assert STRICT_FPA_PROFILE._external_data_name(text, "外部引用") == expected_name


@pytest.mark.parametrize(
    "text",
    [
        "系统调用短信平台发送通知短信。",
        "系统调用支付网关完成支付扣款。",
        "系统调用支付网关发起退款，支付网关为普通外部服务，不作为外部维护数据组计量。",
        "系统调用文件存储服务上传附件。",
        "系统调用地图服务查询经纬度。",
        "系统调用 OCR 服务识别发票图片。",
    ],
)
def test_strict_fpa_external_service_calls_are_not_data_groups(strict_default_rule_context, text):
    assert not STRICT_FPA_PROFILE._is_external_data_group(text)


def test_strict_fpa_extracts_multiple_generic_external_data_names(strict_default_rule_context):
    text = (
        "系统引用外部征信平台维护的企业信用记录，"
        "并引用外部合同平台维护的合同档案，本系统只保存业务关联关系。"
    )

    assert STRICT_FPA_PROFILE._external_data_names(text, "外部引用") == [
        "企业信用记录",
        "合同档案",
    ]


def test_strict_fpa_external_data_rules_can_be_extended_from_config(tmp_path):
    yaml_file = tmp_path / "fpa_config.yaml"
    yaml_file.write_text(
        """
default-profile: strict_fpa
profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    core_rules: custom_rules
    system_prompt: custom_rules
    user_prompt: custom_rules
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_auth
    core_rules: strict_fpa
    system_prompt: strict_fpa
    user_prompt: strict_fpa
core_rules:
  custom_rules: CUSTOM CORE RULES
  strict_fpa: STRICT CORE RULES
system_prompt_sets:
  custom_rules: "CUSTOM SYSTEM"
  strict_fpa: "STRICT SYSTEM"
user_prompt_sets:
  custom_rules: "${core_rules} ${judgement_rules} ${payload_json}"
  strict_fpa: "${core_rules} ${judgement_rules} ${payload_json}"
rule_sets:
  custom_rules_default:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_default:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_auth:
    extends: strict_fpa_default
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["统一认证平台", "统一认证"]
          data_name: "统一认证账号"
          data_nouns: ["账号", "账户", "人员"]
""",
        encoding="utf-8",
    )

    text = "系统引用统一认证平台维护的人员账号，本系统不维护账号主数据。"
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        execution = resolve_fpa_execution_config("strict_fpa")
        token = set_current_fpa_rule_set_config(execution.rule_set_config)
        try:
            assert STRICT_FPA_PROFILE._is_external_data_group(text)
            assert STRICT_FPA_PROFILE._external_data_name(text, "认证引用") == "统一认证账号"
        finally:
            reset_current_fpa_rule_set_config(token)


def test_rule_set_warns_when_external_data_rule_looks_like_ordinary_service(tmp_path):
    yaml_file = tmp_path / "fpa_config.yaml"
    yaml_file.write_text(
        """
default-profile: strict_fpa
profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    core_rules: custom_rules
    system_prompt: custom_rules
    user_prompt: custom_rules
  strict_fpa:
    strategy: rules_only
    rule_set: strict_fpa_sms
    core_rules: strict_fpa
    system_prompt: strict_fpa
    user_prompt: strict_fpa
core_rules:
  custom_rules: CUSTOM CORE RULES
  strict_fpa: STRICT CORE RULES
system_prompt_sets:
  custom_rules: "CUSTOM SYSTEM"
  strict_fpa: "STRICT SYSTEM"
user_prompt_sets:
  custom_rules: "${core_rules} ${judgement_rules} ${payload_json}"
  strict_fpa: "${core_rules} ${judgement_rules} ${payload_json}"
rule_sets:
  custom_rules_default:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_default:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_sms:
    extends: strict_fpa_default
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["短信平台"]
          data_name: "短信平台消息记录"
          data_nouns: ["短信", "记录"]
""",
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        execution = resolve_fpa_execution_config("strict_fpa")

    assert execution.rule_set_config.config_warnings
    assert "FPA 配置 warning" in execution.rule_set_config.config_warnings[0]
    assert "短信平台" in execution.rule_set_config.config_warnings[0]
    assert "普通外部服务" in execution.rule_set_config.config_warnings[0]
