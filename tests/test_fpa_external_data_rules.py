import pytest
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import STRICT_FPA_PROFILE


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "统一用户中心账号"),
        ("系统引用 CRM 系统维护的客户档案，本系统不维护客户主数据。", "CRM客户档案"),
        ("本模块读取客户中心提供的客户基础信息。", "客户中心客户档案"),
        ("本模块引用财务核算系统维护的报账单据，本系统不维护单据主数据。", "财务核算单据"),
        ("系统引用 ERP 系统维护的采购订单，本系统不维护订单主数据。", "ERP业务单据"),
        ("系统引用 OA 系统维护的审批流程记录。", "OA流程单据"),
        ("系统引用主数据平台维护的组织主数据。", "外部主数据"),
    ],
)
def test_strict_fpa_external_data_rule_table_matches_known_sources(text, expected_name):
    assert STRICT_FPA_PROFILE._is_external_data_group(text)
    assert STRICT_FPA_PROFILE._external_data_name(text, "外部引用") == expected_name


@pytest.mark.parametrize(
    "text",
    [
        "系统调用短信平台发送通知短信。",
        "系统调用支付网关完成支付扣款。",
        "系统调用文件存储服务上传附件。",
        "系统调用地图服务查询经纬度。",
        "系统调用 OCR 服务识别发票图片。",
    ],
)
def test_strict_fpa_external_service_calls_are_not_data_groups(text):
    assert not STRICT_FPA_PROFILE._is_external_data_group(text)


def test_strict_fpa_external_data_rules_can_be_extended_from_config(tmp_path):
    yaml_file = tmp_path / "system_config.yaml"
    yaml_file.write_text(
        """
fpa_external_data_rules:
  - source_aliases: ["统一认证平台", "统一认证"]
    data_name: "统一认证账号"
    data_nouns: ["账号", "账户", "人员"]
""",
        encoding="utf-8",
    )

    text = "系统引用统一认证平台维护的人员账号，本系统不维护账号主数据。"
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        assert STRICT_FPA_PROFILE._is_external_data_group(text)
        assert STRICT_FPA_PROFILE._external_data_name(text, "认证引用") == "统一认证账号"
