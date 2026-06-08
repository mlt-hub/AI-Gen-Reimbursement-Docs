import json
import pytest
from unittest.mock import patch

from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    STRICT_FPA_PROFILE,
    ExternalDataGroupRule,
    FpaRuleSetConfig,
    KeywordTypeRule,
    UiApiMappingProfile,
    get_fpa_profile,
    resolve_fpa_execution_config,
    set_current_fpa_rule_set_config,
    reset_current_fpa_rule_set_config,
)
from ai_gen_reimbursement_docs.fpa_validator import validate_fpa_rows


def _fp_name(group: dict[str, str], name: str) -> str:
    return f"【{group['client_type']}】{group['l1']}-{group['l2']}-{group['l3']}-{name}"


def _assert_structured_explanations(group, rows):
    labels = ("来源场景：", "业务数据：", "业务规则：", "计算说明：")
    assert rows
    assert all(all(label in str(row["计算依据说明"]) for label in labels) for row in rows)
    assert not any(issue.code == "validator.explanation_structure" for issue in validate_fpa_rows(group=group, rows=rows))


@pytest.fixture(autouse=True)
def strict_default_rule_context():
    config = FpaRuleSetConfig(
        name="strict_fpa_rs",
        keyword_rules=(
            KeywordTypeRule("EO", ("导出", "报表", "下载", "生成文件"), "事务功能产生派生或格式化输出，按 EO。"),
            KeywordTypeRule("EQ", ("查询", "查看", "详情", "检索", "列表"), "事务功能读取数据且无派生输出，按 EQ。"),
            KeywordTypeRule(
                "EI",
                ("新增", "添加", "修改", "编辑", "删除", "维护", "保存", "提交", "审批", "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联"),
                "事务功能进入或改变系统边界内数据，按 EI。",
            ),
        ),
        external_data_rules=(
            ExternalDataGroupRule(("统一用户中心", "用户中心"), "统一用户中心账号", ("账号", "账户", "人员", "组织", "机构", "信息")),
            ExternalDataGroupRule(("主数据平台", "外部主数据"), "组织主数据", ("组织", "机构")),
        ),
    )
    token = set_current_fpa_rule_set_config(config)
    try:
        yield
    finally:
        reset_current_fpa_rule_set_config(token)


def _write_fpa_config(tmp_path):
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: unified_ui
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
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
  unified_ui_up: |-
    自定义 custom 模板
    ${core_rules}
    CUSTOM_RULES:
    ${judgement_rules}
    PAYLOAD:
    ${payload_json}
  strict_fpa_up: |-
    自定义 strict 模板
    ${core_rules}
    RULES:
    ${judgement_rules}
    PAYLOAD:
    ${payload_json}
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
    type_mapping_rules:
      merge: append
      items:
        - type: EI
          keywords: ["界面开发", "页面"]
        - type: ILF
          keywords: ["添加", "新增", "编辑", "修改", "删除", "维护", "保存", "启用", "停用", "更新"]
    keyword_rules:
      merge: append
      items:
        - type: EO
          keywords: ["导出", "报表输出", "生成文件", "下载", "下载模板", "下载文件"]
        - type: EQ
          keywords: ["查询", "查看", "详情", "列表检索", "检索"]
        - type: EI
          keywords: ["导入"]
  strict_fpa_rs:
    keyword_rules:
      merge: append
      items:
        - type: EO
          keywords: ["导出", "报表", "下载", "生成文件"]
          reason: "事务功能产生派生或格式化输出，按 EO。"
        - type: EQ
          keywords: ["查询", "查看", "详情", "检索", "列表"]
          reason: "事务功能读取数据且无派生输出，按 EQ。"
        - type: EI
          keywords: ["新增", "添加", "修改", "编辑", "删除", "维护", "保存", "提交", "审批", "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联"]
          reason: "事务功能进入或改变系统边界内数据，按 EI。"
  telecom_rules:
    extends: strict_fpa_rs
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
    ai_type_conflict_rules:
      merge: append
      items:
        - expected_type: ILF
          ai_type: EO
          keywords: ["本地报表快照"]
          conflict: false
          reason: "本地报表快照允许 AI 按格式化输出复核，不提示类型冲突。"
        - expected_type: EO
          ai_type: EO
          keywords: ["监管报表导出"]
          conflict: true
          reason: "监管报表导出即使 AI 返回 EO 也要求人工复核。"
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
    coverage_rules:
      require_process_coverage: false
      require_data_function: true
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
    ai_type_conflict_rules:
      merge: replace
      items:
        - expected_type: EIF
          ai_type: ILF
          keywords: ["标签平台客户标签"]
          conflict: true
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
    coverage_rules:
      require_data_function: false
""",
        encoding="utf-8",
    )


def test_default_profile_is_unified_ui():
    assert get_fpa_profile() is CUSTOM_RULES_PROFILE
    assert get_fpa_profile("unified_ui") is CUSTOM_RULES_PROFILE
    assert get_fpa_profile("strict_fpa") is STRICT_FPA_PROFILE


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="未知 FPA profile"):
        get_fpa_profile("unknown_profile")


def test_execution_config_uses_profile_defaults(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        custom = resolve_fpa_execution_config("unified_ui")
        assert custom.profile is CUSTOM_RULES_PROFILE
        assert custom.strategy == "rules_first"
        assert custom.rule_set == "unified_ui_rs"

        strict = resolve_fpa_execution_config("strict_fpa")
        assert strict.profile is STRICT_FPA_PROFILE
        assert strict.strategy == "ai_first"
        assert strict.rule_set == "strict_fpa_rs"


def test_execution_config_accepts_explicit_strategy_and_rule_set(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_only", "strict_fpa_rs")
        assert config.strategy == "ai_only"
        assert config.rule_set == "strict_fpa_rs"


def test_custom_profile_can_reuse_supported_kind(tmp_path):
    _write_fpa_config(tmp_path)
    path = tmp_path / "fpa_config.yaml"
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        "  strict_fpa:\n    kind: strict_fpa",
        "  contract_api:\n    kind: ui_api_mapping\n    strategy: rules_first\n    rule_set: unified_ui_rs\n    core_rules: unified_ui_cr\n    system_prompt: unified_ui_sp\n    user_prompt: unified_ui_up\n  strict_fpa:\n    kind: strict_fpa",
    )
    path.write_text(content, encoding="utf-8")

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("contract_api")

    assert isinstance(config.profile, UiApiMappingProfile)
    assert config.profile.name == "contract_api"
    assert config.strategy == "rules_first"
    assert config.rule_set == "unified_ui_rs"


def test_ui_api_mapping_fallback_generates_default_and_explicit_backend_rows():
    profile = UiApiMappingProfile()
    group = {
        "client_type": "业务端",
        "l1": "销售管理",
        "l2": "合同中心",
        "l3": "合同管理",
        "processes": [
            {"name": "查询合同列表", "type": "新增", "desc": "查询合同列表。"},
            {"name": "提交合同审批", "type": "新增", "desc": "提交合同审批，调用 OA 审批接口。"},
            {"name": "再次提交合同审批", "type": "新增", "desc": "再次提交合同审批，调用 OA 审批接口。"},
            {"name": "同步客户信息", "type": "新增", "desc": "同步客户信息，调用 CRM 客户查询服务。"},
        ],
    }

    rows = profile.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    names = [str(row["新增/修改功能点"]) for row in rows]
    types = {str(row["新增/修改功能点"]): str(row["类型"]) for row in rows}

    _assert_structured_explanations(group, rows)
    assert "【业务端】销售管理-合同中心-合同管理-查询合同列表-界面开发" in names
    assert "【业务端】销售管理-合同中心-合同管理-查询合同列表-接口开发" in names
    assert "【业务端】销售管理-合同中心-合同管理-OA 审批接口" in names
    assert names.count("【业务端】销售管理-合同中心-合同管理-OA 审批接口") == 1
    assert "提交合同审批、再次提交合同审批" == next(
        str(row["源功能过程"])
        for row in rows
        if row["新增/修改功能点"] == "【业务端】销售管理-合同中心-合同管理-OA 审批接口"
    )
    assert "【业务端】销售管理-合同中心-合同管理-CRM 客户查询服务" in names
    assert "【业务端】销售管理-合同中心-合同管理-客户信息" not in names
    assert types["【业务端】销售管理-合同中心-合同管理-查询合同列表-界面开发"] == "EI"
    assert types["【业务端】销售管理-合同中心-合同管理-查询合同列表-接口开发"] == "ILF"
    assert types["【业务端】销售管理-合同中心-合同管理-OA 审批接口"] == "ILF"


def test_ui_api_mapping_keeps_multiple_explicit_backend_rows_and_duplicate_default_rows():
    profile = UiApiMappingProfile()
    group = {
        "client_type": "业务端",
        "l1": "销售管理",
        "l2": "合同中心",
        "l3": "合同管理",
        "processes": [
            {"name": "提交合同审批", "type": "新增", "desc": "调用 OA 审批接口，请求 风控校验服务。"},
            {"name": "提交合同审批", "type": "新增", "desc": "再次提交合同审批。"},
        ],
    }

    rows = profile.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    names = [str(row["新增/修改功能点"]) for row in rows]

    assert names.count("【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发") == 2
    assert names.count("【业务端】销售管理-合同中心-合同管理-提交合同审批-接口开发") == 2
    assert "【业务端】销售管理-合同中心-合同管理-OA 审批接口" in names
    assert "【业务端】销售管理-合同中心-合同管理-风控校验服务" in names
    duplicate_rows = [
        row
        for row in rows
        if row["新增/修改功能点"] == "【业务端】销售管理-合同中心-合同管理-提交合同审批-界面开发"
    ]
    assert duplicate_rows[0]["后处理警告"] == ""
    assert "功能过程默认行同名" in str(duplicate_rows[1]["后处理警告"])


def test_strict_profile_merges_same_name_same_type_and_keeps_type_conflict():
    group = {
        "client_type": "业务端",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户查询",
        "processes": [
            {"name": "查询客户", "type": "新增", "desc": "按客户名称查询客户列表。"},
            {"name": "查询客户", "type": "新增", "desc": "按手机号查询客户列表。"},
            {"name": "客户处理", "type": "新增", "desc": "导出客户报表。"},
            {"name": "客户处理", "type": "新增", "desc": "查询客户列表。"},
        ],
    }

    rows = STRICT_FPA_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    query_rows = [row for row in rows if row["新增/修改功能点"] == _fp_name(group, "客户查询")]
    report_rows = [row for row in rows if row["新增/修改功能点"] == _fp_name(group, "客户处理")]

    _assert_structured_explanations(group, rows)
    assert len(query_rows) == 1
    assert query_rows[0]["类型"] == "EQ"
    assert query_rows[0]["源功能过程"] == "查询客户、查询客户"
    assert len(report_rows) == 2
    assert {str(row["类型"]) for row in report_rows} == {"EO", "EQ"}
    assert all("同名不同类型结果行" in str(row["后处理警告"]) for row in report_rows)


def test_unified_ui_fallback_merges_duplicate_non_ui_process_rows(tmp_path):
    _write_fpa_config(tmp_path)
    group = {
        "client_type": "业务端",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户档案",
        "processes": [
            {"name": "查询客户", "type": "新增", "desc": "按客户名称查询客户列表。"},
            {"name": "查询客户", "type": "新增", "desc": "按手机号查询客户列表。"},
        ],
    }

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("unified_ui")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = config.profile.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)
    _assert_structured_explanations(group, rows)

    process_rows = [row for row in rows if row["新增/修改功能点"] == _fp_name(group, "查询客户-查询处理开发")]
    assert len(process_rows) == 1
    assert process_rows[0]["源功能过程"] == "查询客户"


def test_rule_set_extends_are_loaded(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("strict_fpa", "ai_first", "telecom_rules")

    assert config.rule_set == "telecom_rules"
    assert config.rule_set_config.extends == "strict_fpa_rs"
    assert config.rule_set_config.keyword_rules[0].fpa_type == "EO"
    assert config.rule_set_config.type_mapping_rules[0].fpa_type == "ILF"
    assert config.rule_set_config.ai_type_conflict_rules[0].expected_type == "ILF"
    assert config.rule_set_config.internal_data_rules[0].data_name == "认证授权关系"
    assert config.rule_set_config.external_data_rules[0].data_name == "行业平台客户档案"
    assert config.rule_set_config.coverage_rules.require_process_coverage is False
    assert config.rule_set_config.coverage_rules.require_data_function is True


def test_custom_rule_set_row_planning_rules_are_loaded(tmp_path):
    _write_fpa_config(tmp_path)
    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("unified_ui")

    row_planning = config.rule_set_config.row_planning_rules
    assert row_planning.ui_row is not None
    assert row_planning.ui_row.name_suffix == "界面开发"
    assert row_planning.ui_row.fpa_type == "EI"
    assert row_planning.process_rows is not None
    assert row_planning.process_rows.type_suffixes["EQ"] == "查询处理开发"


def test_custom_rule_set_row_planning_rules_affect_fallback_rows(tmp_path):
    _write_fpa_config(tmp_path)
    content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
    content = content.replace('name_suffix: "界面开发"', 'name_suffix: "页面交互开发"')
    content = content.replace('EQ: "查询处理开发"', 'EQ: "读取处理开发"')
    (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
    group = {
        "client_type": "后台",
        "l1": "业务",
        "l2": "管理",
        "l3": "客户管理",
        "processes": [
            {"name": "查询客户", "type": "新增", "desc": "按客户名称查询客户列表。"},
        ],
    }

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("unified_ui")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = CUSTOM_RULES_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)

    names = [str(row["新增/修改功能点"]) for row in rows]
    assert names[0].endswith("-页面交互开发")
    assert names[1] == _fp_name(group, "查询客户-读取处理开发")


def test_custom_rule_set_can_disable_ui_fallback_row(tmp_path):
    _write_fpa_config(tmp_path)
    content = (tmp_path / "fpa_config.yaml").read_text(encoding="utf-8")
    content = content.replace("        enabled: true\n        scope: l3", "        enabled: false\n        scope: l3")
    (tmp_path / "fpa_config.yaml").write_text(content, encoding="utf-8")
    group = {
        "client_type": "后台",
        "l1": "业务",
        "l2": "管理",
        "l3": "客户管理",
        "processes": [
            {"name": "查询客户", "type": "新增", "desc": "按客户名称查询客户列表。"},
        ],
    }

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        config = resolve_fpa_execution_config("unified_ui")
        token = set_current_fpa_rule_set_config(config.rule_set_config)
        try:
            rows = CUSTOM_RULES_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
        finally:
            reset_current_fpa_rule_set_config(token)

    assert [str(row["新增/修改功能点"]) for row in rows] == [_fp_name(group, "查询客户-查询处理开发")]


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
    assert [rule.keywords for rule in config.rule_set_config.ai_type_conflict_rules] == [("标签平台客户标签",)]
    assert [rule.data_name for rule in config.rule_set_config.internal_data_rules] == ["客户标签关系"]
    assert [rule.data_name for rule in config.rule_set_config.external_data_rules] == ["标签平台客户标签"]
    assert config.rule_set_config.coverage_rules.require_process_coverage is False
    assert config.rule_set_config.coverage_rules.require_data_function is False


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
            forced_conflict = STRICT_FPA_PROFILE.has_obvious_conflict(
                "监管报表导出",
                "导出监管报表文件。",
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
    assert not has_conflict
    assert forced_conflict
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
    assert types[_fp_name(group, "认证授权关系")] == "ILF"


def test_unified_ui_prompt_is_rendered_from_config(tmp_path):
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

    assert "CUSTOM CORE RULES" in prompt
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
    assert "STRICT CORE RULES" in prompt
    assert "1) 规则一" in prompt
    assert '"l3": "客户管理"' in prompt
    assert "${" not in prompt


def test_prompt_payload_includes_extracted_process_facts(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        prompt = STRICT_FPA_PROFILE.build_prompt(
            {
                "client_type": "后台",
                "l1": "业务",
                "l2": "管理",
                "l3": "客户管理",
                "l3_desc": "维护客户信息。",
                "processes": [
                    {
                        "process_id": "m1_p1",
                        "process_name": "查询客户",
                        "description": "按客户名称查询客户列表。",
                        "type": "新增",
                    }
                ],
            },
            ["规则一"],
        )

    payload = json.loads(prompt.split("PAYLOAD:", 1)[1])
    fact = payload["process_facts"][0]
    assert fact["process_id"] == "m1_p1"
    assert fact["operation"] == "query"
    assert fact["query_only"] is True
    assert fact["changes_internal_data"] is False
    assert fact["input_type"] == "新增"
    assert payload["merge_review"]["groups"] == []
    assert payload["type_judgement"]["judgements"][0]["suggested_type"] == "EQ"


def test_prompt_payload_includes_merge_review(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        prompt = STRICT_FPA_PROFILE.build_prompt(
            {
                "client_type": "后台",
                "l1": "业务",
                "l2": "管理",
                "l3": "客户管理",
                "l3_desc": "维护客户信息。",
                "processes": [
                    {
                        "process_id": "m1_p1",
                        "process_name": "添加客户",
                        "description": "输入客户名称并保存。",
                        "type": "新增",
                    },
                    {
                        "process_id": "m1_p2",
                        "process_name": "编辑客户",
                        "description": "修改客户名称并保存。",
                        "type": "新增",
                    },
                ],
            },
            ["规则一"],
        )

    payload = json.loads(prompt.split("PAYLOAD:", 1)[1])
    group = payload["merge_review"]["groups"][0]
    assert group["kind"] == "maintenance_ei"
    assert group["recommendation"] == "merge"
    assert group["process_ids"] == ["m1_p1", "m1_p2"]


def test_prompt_payload_includes_agent_review_contract(tmp_path):
    _write_fpa_config(tmp_path)

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        prompt = STRICT_FPA_PROFILE.build_prompt(
            {
                "client_type": "后台",
                "l1": "业务",
                "l2": "管理",
                "l3": "客户管理",
                "l3_desc": "维护客户信息。",
                "processes": [
                    {
                        "process_id": "m1_p1",
                        "process_name": "添加客户",
                        "description": "输入客户名称并保存。",
                        "type": "新增",
                    },
                    {
                        "process_id": "m1_p2",
                        "process_name": "编辑客户",
                        "description": "修改客户名称并保存。",
                        "type": "新增",
                    },
                ],
            },
            ["规则一"],
        )

    payload = json.loads(prompt.split("PAYLOAD:", 1)[1])
    roles = {role["name"]: role for role in payload["agent_review"]["roles"]}
    assert roles["business_fact_extractor"]["output_key"] == "process_facts"
    assert roles["merge_boundary_reviewer"]["output_key"] == "merge_review"
    assert roles["quality_reviewer"]["status"] == "awaiting_rows"
    assert roles["fpa_type_judge"]["status"] == "completed"
    assert roles["fpa_type_judge"]["output_key"] == "type_judgement"
    assert payload["agent_review"]["type_judgement"]["judgements"][0]["suggested_type"] == "EI"


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
