import logging
import json

import openpyxl
import pytest

from ai_gen_reimbursement_docs.config_utils import FpaConfigError, FpaPromptConfigError
from ai_gen_reimbursement_docs.gen_fpa import (
    _extract_json_obj,
    _fpa_ai_cache_key,
    _group_rows_for_audit,
    _group_rows_by_l3,
    _normalize_ai_fpa_rows_for_l3,
    _plan_fpa_rows_with_execution,
    _plan_fpa_rows_with_ai,
    _rules_first_ai_reasons,
    _supplement_ai_rows_with_rules,
    generate_fpa_check_xlsx_from_md,
    preview_fpa_module,
)
from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    STRICT_FPA_PROFILE,
    CustomRulesProfile,
    ExternalDataGroupRule,
    FpaCoverageRules,
    FpaProcessRowsPlanningRule,
    FpaRowPlanningRules,
    FpaRuleSetConfig,
    FpaUiRowPlanningRule,
    KeywordTypeRule,
    TypeMappingRule,
    reset_current_fpa_rule_set_config,
    set_current_fpa_rule_set_config,
)


def _meta():
    return {"子系统（模块）": "测试系统", "资产标识": "TEST-001"}


def _rows():
    return [
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "维护垂直行业基础信息和管理员。",
            "功能过程": "添加垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "输入垂直行业名称并保存。",
        },
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "维护垂直行业基础信息和管理员。",
            "功能过程": "查询垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "按行业名称查询垂直行业列表。",
        },
    ]


def _custom_default_rule_set() -> FpaRuleSetConfig:
    return FpaRuleSetConfig(
        name="custom_rules_default",
        row_planning_rules=FpaRowPlanningRules(
            ui_row=FpaUiRowPlanningRule(
                enabled=True,
                scope="l3",
                merge="single_row",
                name_suffix="界面开发",
                fpa_type="EI",
                reason="三级模块兜底合并界面能力。",
                empty_process_text="完成三级模块页面交互能力",
                explanation_template="{name}，具体为以下：\n{items}",
            ),
            process_rows=FpaProcessRowsPlanningRule(
                enabled=True,
                one_row_per_process=True,
                default_name_suffix="逻辑处理开发",
                type_suffixes={"EQ": "查询处理开发", "EO": "导出处理开发", "EI": "导入处理开发"},
                explanation_template="{name}，具体为以下：\n1、{description}",
            ),
        ),
        type_mapping_rules=(
            TypeMappingRule("EI", ("界面开发", "页面")),
            TypeMappingRule("EIF", ("外部应用维护", "外部系统维护", "引用外部数据组", "统一用户中心", "外部主数据")),
            TypeMappingRule("ILF", ("添加", "新增", "编辑", "修改", "删除", "维护", "保存", "启用", "停用", "更新")),
            TypeMappingRule("ILF", ("外部接口", "外部数据")),
        ),
        keyword_rules=(
            KeywordTypeRule("EO", ("导出", "报表输出", "生成文件", "下载", "下载模板", "下载文件")),
            KeywordTypeRule("EQ", ("查询", "查看", "详情", "列表检索", "检索")),
            KeywordTypeRule("EI", ("导入",)),
        ),
    )


def _strict_default_rule_set() -> FpaRuleSetConfig:
    return FpaRuleSetConfig(
        name="strict_fpa_default",
        keyword_rules=(
            KeywordTypeRule("EO", ("导出", "报表", "下载", "生成文件"), "事务功能产生派生或格式化输出，按 EO。"),
            KeywordTypeRule("EQ", ("查询", "查看", "详情", "检索", "列表"), "事务功能读取数据且无派生输出，按 EQ。"),
            KeywordTypeRule(
                "EI",
                ("新增", "添加", "修改", "编辑", "删除", "保存", "提交", "审批", "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联"),
                "事务功能进入或改变系统边界内数据，按 EI。",
            ),
        ),
        external_data_rules=(
            ExternalDataGroupRule(("统一用户中心", "用户中心"), "统一用户中心账号", ("账号", "账户", "人员", "组织", "机构", "信息")),
        ),
    )


def _structured_explanation(process: str = "添加垂直行业", fpa_type: str = "EI") -> str:
    return (
        f"来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-{process}”，"
        "后台用户输入垂直行业名称并保存。"
        "\n业务数据：涉及垂直行业数据，输入字段为垂直行业名称。"
        "\n业务规则：系统根据用户提交动作创建或处理对应垂直行业记录。"
        f"\n计算说明：该功能过程体现后台用户维护垂直行业业务数据，可支撑 FPA 功能点计量，并按 {fpa_type} 识别。"
    )


def _write_fpa_prompt_config(tmp_path, monkeypatch):
    (tmp_path / "fpa_config.yaml").write_text(
        """
profile: custom_rules
profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    core_rules: custom_rules
    system_prompt: custom_rules
    user_prompt: custom_rules
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    core_rules: strict_fpa
    system_prompt: strict_fpa
    user_prompt: strict_fpa
core_rules:
  custom_rules: CUSTOM CORE RULES
  strict_fpa: STRICT CORE RULES
system_prompt_sets:
  custom_rules: 系统提示词
  strict_fpa: 严格系统提示词
user_prompt_sets:
  custom_rules: |-
    ${core_rules}
    模块输入 JSON：
    ${payload_json}
    判定原则：
    ${judgement_rules}
  strict_fpa: |-
    ${core_rules}
    模块输入 JSON：
    ${payload_json}
    判定原则：
    ${judgement_rules}
rule_sets:
  custom_rules_default:
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
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_default:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
""",
        encoding="utf-8",
    )
    (tmp_path / "fpa_judgement_rules.yaml").write_text(
        "judgement_rules:\n  - 规则一\n  - 规则二\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)


def test_fpa_audit_grouping_prefers_source_process_over_l3_substring():
    tree_rows = [
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "",
            "功能过程": "添加垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "",
        },
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "合伙商管理",
            "三级模块整体功能描述": "",
            "功能过程": "搜索合作商",
            "功能过程类型": "查询",
            "功能过程描述": "",
        },
    ]
    groups = _group_rows_by_l3(tree_rows)
    fpa_rows = [
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-合伙商管理-搜索合作商",
            "计算依据说明": "",
            "源功能过程": "搜索合作商",
        }
    ]

    grouped = _group_rows_for_audit(fpa_rows, groups)

    assert grouped[1] == []
    assert grouped[2] == fpa_rows


def test_markdown_code_block_json_is_parsed():
    data = _extract_json_obj("""```json
{"rows":[{"name":"垂直行业管理界面开发"}]}
```""")
    assert data["rows"][0]["name"] == "垂直行业管理界面开发"


def test_normalize_ai_rows_maps_basis_and_types():
    group = _group_rows_by_l3(_rows())[0]
    token = set_current_fpa_rule_set_config(_custom_default_rule_set())
    try:
        rows, warnings = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=_meta(),
            judgement_rules=["规则一", "规则二"],
            start_seq=1,
            ai_rows=[
                {
                    "name": "垂直行业管理界面开发",
                    "type": "EI",
                    "type_reason": "页面交互能力",
                    "classification_basis_index": 1,
                    "explanation": "垂直行业管理界面开发，具体为以下：1、新增列表和查询条件。",
                },
                {
                    "name": "添加垂直行业-逻辑处理开发",
                    "type": "ILF",
                    "classification_basis_index": 2,
                    "explanation": "保存垂直行业基础信息。",
                    "source_processes": ["添加垂直行业"],
                },
            ],
        )
    finally:
        reset_current_fpa_rule_set_config(token)
    assert any("AI 行名称前缀已按源功能清单规范化" in w for w in warnings)
    assert [r["类型"] for r in rows] == ["EI", "ILF"]
    assert rows[0]["新增/修改功能点"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业管理界面开发"
    assert rows[1]["新增/修改功能点"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-添加垂直行业-逻辑处理开发"
    assert rows[0]["计算依据归类"] == "规则一"
    assert rows[1]["计算依据归类"] == "规则二"


def test_invalid_index_warns_and_leaves_basis_empty():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        ai_rows=[{
            "name": "查询垂直行业-查询处理开发",
            "type": "EQ",
            "classification_basis_index": 99,
            "explanation": "查询垂直行业列表。",
        }],
    )
    assert rows[0]["计算依据归类"] == ""
    assert any("越界" in w for w in warnings)
    rule_hits = rows[0]["_规则命中详情"]
    assert any(hit["rule_id"] == "postprocess.classification_basis_index" for hit in rule_hits)
    assert any("越界" in warning for hit in rule_hits for warning in hit["warnings"])


def test_structured_explanation_passes_quality_check():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[{
            "name": "添加垂直行业",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": _structured_explanation("添加垂直行业", "EI"),
        }],
    )

    assert not any("计算依据说明" in warning for warning in warnings)
    assert not any(
        hit["rule_id"] == "postprocess.explanation_quality"
        for hit in rows[0]["_规则命中详情"]
    )


def test_data_function_explanation_accepts_data_group_source_path():
    group = _group_rows_by_l3(_rows())[0]
    explanation = (
        "来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组”，"
        "本系统维护垂直行业基础信息。"
        "\n业务数据：涉及垂直行业数据，字段包括行业名称。"
        "\n业务规则：系统保存并持续维护垂直行业逻辑数据组。"
        "\n计算说明：该数据组由本系统维护，可支撑 FPA 功能点计量，并按 ILF 识别。"
    )

    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[{
            "name": "垂直行业数据组",
            "type": "ILF",
            "classification_basis_index": 1,
            "explanation": explanation,
        }],
    )

    assert not any("来源场景未使用完整路径格式" in warning for warning in warnings)
    assert not any(
        hit["rule_id"] == "postprocess.explanation_quality"
        for hit in rows[0]["_规则命中详情"]
    )


def test_data_function_source_path_warning_mentions_data_group_name():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[{
            "name": "垂直行业数据组",
            "type": "ILF",
            "classification_basis_index": 1,
            "explanation": (
                "来源场景：来自“垂直行业管理”，本系统维护垂直行业基础信息。"
                "\n业务数据：涉及垂直行业数据，字段包括行业名称。"
                "\n业务规则：系统保存并持续维护垂直行业逻辑数据组。"
                "\n计算说明：该数据组由本系统维护，可支撑 FPA 功能点计量，并按 ILF 识别。"
            ),
        }],
    )

    assert any("<数据组名称>" in warning for warning in warnings)
    assert not any("<功能过程>" in warning for warning in warnings)
    quality_hit = next(
        hit for hit in rows[0]["_规则命中详情"]
        if hit["rule_id"] == "postprocess.explanation_quality"
    )
    assert any("<数据组名称>" in warning for warning in quality_hit["warnings"])


def test_explanation_warns_when_table_count_basis_is_used_as_detail():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["按后台数据库变更的表个数计量"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[{
            "name": "垂直行业数据组",
            "type": "ILF",
            "classification_basis_index": 1,
            "explanation": (
                "来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组”，"
                "本系统维护垂直行业基础信息。"
                "\n业务数据：涉及垂直行业数据，字段包括行业名称。"
                "\n业务规则：系统保存并持续维护垂直行业逻辑数据组。"
                "\n计算说明：该数据组由本系统维护，符合 ILF 定义，按后台数据库变更的表个数计量。"
            ),
        }],
    )

    assert rows[0]["计算依据归类"] == "按后台数据库变更的表个数计量"
    assert any("应保留在计算依据归类而非计算依据说明" in warning for warning in warnings)
    quality_hit = next(
        hit for hit in rows[0]["_规则命中详情"]
        if hit["rule_id"] == "postprocess.explanation_quality"
    )
    assert any("数据库表个数" in warning for warning in quality_hit["warnings"])


def test_unstructured_explanation_records_quality_warning():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        ai_rows=[{
            "name": "添加垂直行业-逻辑处理开发",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": "保存垂直行业基础信息。",
        }],
    )

    assert any("计算依据说明格式不完整" in warning for warning in warnings)
    assert any("未使用完整路径格式" in warning for warning in warnings)
    assert any("未明确当前 FPA 类型: ILF" in warning for warning in warnings)
    rule_hits = rows[0]["_规则命中详情"]
    quality_hit = next(hit for hit in rule_hits if hit["rule_id"] == "postprocess.explanation_quality")
    assert "结构化证据说明规则" in quality_hit["rule_desc"]
    assert "计算依据说明格式不完整" in "；".join(quality_hit["warnings"])


def test_multiple_ui_rows_without_split_reason_are_merged():
    group = _group_rows_by_l3(_rows())[0]
    token = set_current_fpa_rule_set_config(_custom_default_rule_set())
    try:
        rows, warnings = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=_meta(),
            judgement_rules=[],
            start_seq=1,
            ai_rows=[
                {"name": "垂直行业列表界面开发", "type": "EI", "explanation": "列表。"},
                {"name": "垂直行业查询界面开发", "type": "EI", "explanation": "查询。"},
                {"name": "添加垂直行业-逻辑处理开发", "type": "ILF", "explanation": "保存。"},
            ],
        )
    finally:
        reset_current_fpa_rule_set_config(token)
    assert sum(1 for r in rows if "界面开发" in r["新增/修改功能点"]) == 1
    assert any("split_reason" in w for w in warnings)


def test_strict_profile_normalizes_ai_development_work_item_names():
    group = _group_rows_by_l3(_rows())[0]
    token = set_current_fpa_rule_set_config(_strict_default_rule_set())
    try:
        rows, warnings = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=_meta(),
            judgement_rules=[],
            start_seq=1,
            profile=STRICT_FPA_PROFILE,
            ai_rows=[
                {
                    "name": "添加垂直行业-逻辑处理开发",
                    "type": "ILF",
                    "explanation": "输入垂直行业名称并保存。",
                },
            ],
        )
    finally:
        reset_current_fpa_rule_set_config(token)

    assert rows[0]["新增/修改功能点"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-添加垂直行业"
    assert rows[0]["类型"] == "EI"
    assert any("已规范化" in w for w in warnings)


def test_ai_name_prefix_is_forced_from_source_module_path():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        ai_rows=[
            {
                "name": "和乐业-垂直行业营销-垂直行业管理-垂直行业管理-查询垂直行业",
                "type": "EQ",
                "explanation": "查询垂直行业。",
            },
            {
                "name": "地市后台-垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组",
                "type": "ILF",
                "explanation": "垂直行业数据组。",
            },
            {
                "name": "自定义页面列表查询",
                "type": "EQ",
                "explanation": "查询自定义页面。",
            },
            {
                "name": "【地市后台】垂直行业营销-装修管理-首页装修-行业首页装修数据",
                "type": "ILF",
                "explanation": "行业首页装修数据。",
            },
            {
                "name": "地市后台-垂直行业营销-装修管理-自定义装修-自定义页面信息",
                "type": "ILF",
                "explanation": "自定义页面信息。",
            },
        ],
    )

    assert [row["新增/修改功能点"] for row in rows] == [
        "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-查询垂直行业",
        "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组",
        "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-自定义页面列表查询",
        "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-行业首页装修数据",
        "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-自定义页面信息",
    ]
    assert len([w for w in warnings if "AI 行名称前缀已按源功能清单规范化" in w]) == 5
    assert all(
        any(hit["rule_id"] == "postprocess.ai_name_prefix" for hit in row["_规则命中详情"])
        for row in rows
    )


def test_strict_profile_corrects_external_service_eif_misclassification():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "消息管理",
            "二级模块": "通知发送",
            "三级模块": "短信通知",
            "三级模块整体功能描述": "系统调用短信平台发送通知短信。",
            "功能过程": "发送测试短信",
            "功能过程类型": "新增",
            "功能过程描述": "调用短信平台发送测试短信。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[
            {
                "name": "发送测试短信",
                "type": "EIF",
                "explanation": "调用短信平台发送测试短信。",
            },
        ],
    )

    assert rows[0]["类型"] == "EI"
    conflict_warning = next(w for w in warnings if "明显冲突" in w)
    assert "规则建议 type=EI" in conflict_warning
    assert "普通外部服务调用按触发事务处理，不能直接判 EIF" in conflict_warning
    hit = next(hit for hit in rows[0]["_规则命中详情"] if hit["rule_id"] == "postprocess.keyword_type_conflict")
    assert hit["suggested_type"] == "EI"
    assert "规则建议 type=EI" in hit["rule_desc"]
    assert "普通外部服务调用按触发事务处理，不能直接判 EIF" in hit["rule_desc"]


def test_ai_first_keeps_valid_ai_type_without_keyword_override():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "消息管理",
            "二级模块": "通知发送",
            "三级模块": "短信通知",
            "三级模块整体功能描述": "系统调用短信平台发送通知短信。",
            "功能过程": "发送测试短信",
            "功能过程类型": "新增",
            "功能过程描述": "调用短信平台发送测试短信。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "发送测试短信",
                "type": "EIF",
                "explanation": "调用短信平台发送测试短信。",
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    conflict_warning = next(w for w in warnings if "AI 优先策略下保留 AI type" in w)
    assert "规则建议 type=EI" in conflict_warning
    assert "普通外部服务调用按触发事务处理，不能直接判 EIF" in conflict_warning
    hit = next(hit for hit in rows[0]["_规则命中详情"] if hit["rule_id"] == "postprocess.ai_first_type_conflict")
    assert hit["suggested_type"] == "EI"
    assert "规则建议 type=EI" in hit["rule_desc"]
    assert "普通外部服务调用按触发事务处理，不能直接判 EIF" in hit["rule_desc"]


def test_ai_first_does_not_warn_type_conflict_when_rule_type_matches_ai_type():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "维护垂直行业基础信息和管理员。",
            "功能过程": "添加垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "点击添加按钮，在弹窗输入垂直行业名称并保存。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "添加垂直行业",
                "type": "EI",
                "explanation": "点击添加按钮，在弹窗输入垂直行业名称并保存。",
            },
        ],
    )

    assert rows[0]["类型"] == "EI"
    assert not any("AI type=EI 与规则存在冲突" in warning for warning in warnings)
    assert not any(hit["rule_id"] == "postprocess.ai_first_type_conflict" for hit in rows[0]["_规则命中详情"])


def test_ai_first_data_function_supplement_warning_does_not_report_zero_missing_processes():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "客户管理",
            "二级模块": "客户档案",
            "三级模块": "客户档案",
            "三级模块整体功能描述": "维护客户档案。",
            "功能过程": "添加客户档案",
            "功能过程类型": "新增",
            "功能过程描述": "保存客户档案。",
        },
    ])[0]
    ai_rows, _ = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "添加客户档案",
                "type": "EI",
                "explanation": "保存客户档案。",
                "source_processes": ["添加客户档案"],
            },
        ],
    )

    combined, warnings = _supplement_ai_rows_with_rules(
        group=group,
        meta=_meta(),
        ai_rows=ai_rows,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
    )

    assert len(combined) == 2
    assert any(row["生成方式"] == "rules_fallback" and row["类型"] == "ILF" for row in combined)
    assert any("AI 结果未包含数据功能行" in warning for warning in warnings)
    assert not any("未覆盖 0 个功能过程" in warning for warning in warnings)


def test_coverage_rules_can_disable_data_function_supplement():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "客户管理",
            "二级模块": "客户档案",
            "三级模块": "客户档案",
            "三级模块整体功能描述": "维护客户档案。",
            "功能过程": "添加客户档案",
            "功能过程类型": "新增",
            "功能过程描述": "保存客户档案。",
        },
    ])[0]
    ai_rows, _ = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[{
            "name": "添加客户档案",
            "type": "EI",
            "explanation": "保存客户档案。",
            "source_processes": ["添加客户档案"],
        }],
    )

    combined, warnings = _supplement_ai_rows_with_rules(
        group=group,
        meta=_meta(),
        ai_rows=ai_rows,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        rule_set_config=FpaRuleSetConfig(
            name="no_data_supplement",
            coverage_rules=FpaCoverageRules(require_data_function=False),
        ),
    )

    assert combined == ai_rows
    assert warnings == []


def test_coverage_rules_can_disable_missing_process_supplement():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "客户管理",
            "二级模块": "客户查询",
            "三级模块": "客户查询",
            "三级模块整体功能描述": "查询和导出客户。",
            "功能过程": "查询客户",
            "功能过程类型": "新增",
            "功能过程描述": "按客户名称查询客户列表。",
        },
        {
            "客户端类型": "地市后台",
            "一级模块": "客户管理",
            "二级模块": "客户查询",
            "三级模块": "客户查询",
            "三级模块整体功能描述": "查询和导出客户。",
            "功能过程": "导出客户",
            "功能过程类型": "新增",
            "功能过程描述": "导出客户列表。",
        },
    ])[0]
    token = set_current_fpa_rule_set_config(_custom_default_rule_set())
    try:
        ai_rows, _ = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=_meta(),
            judgement_rules=[],
            start_seq=1,
            profile=CUSTOM_RULES_PROFILE,
            strategy="ai_first",
            ai_rows=[{
                "name": "查询客户-查询处理开发",
                "type": "EQ",
                "explanation": "按客户名称查询客户列表。",
                "source_processes": ["查询客户"],
            }],
        )
    finally:
        reset_current_fpa_rule_set_config(token)

    combined, warnings = _supplement_ai_rows_with_rules(
        group=group,
        meta=_meta(),
        ai_rows=ai_rows,
        profile=CUSTOM_RULES_PROFILE,
        strategy="ai_first",
        rule_set_config=FpaRuleSetConfig(
            name="no_process_supplement",
            coverage_rules=FpaCoverageRules(require_process_coverage=False, require_data_function=False),
        ),
    )

    assert combined == ai_rows
    assert warnings == []


def test_strict_profile_keeps_real_external_data_group_eif():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "权限管理",
            "二级模块": "账号权限",
            "三级模块": "用户中心账号引用",
            "三级模块整体功能描述": "系统引用统一用户中心维护的人员账号。",
            "功能过程": "同步账号",
            "功能过程类型": "新增",
            "功能过程描述": "统一用户中心维护的人员账号，本系统只引用。",
        },
    ])[0]
    token = set_current_fpa_rule_set_config(_strict_default_rule_set())
    try:
        rows, warnings = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=_meta(),
            judgement_rules=[],
            start_seq=1,
            profile=STRICT_FPA_PROFILE,
            ai_rows=[
                {
                    "name": "统一用户中心账号",
                    "type": "EIF",
                    "explanation": "统一用户中心维护的人员账号，本系统只引用。",
                },
            ],
        )
    finally:
        reset_current_fpa_rule_set_config(token)

    assert rows[0]["类型"] == "EIF"
    assert not any("明显冲突" in w for w in warnings)


def test_strict_profile_warns_when_ai_complex_eif_needs_manual_review():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "风控管理",
            "二级模块": "风险画像",
            "三级模块": "风险画像",
            "三级模块整体功能描述": "结合多源业务信息生成风险画像。",
            "功能过程": "查看画像",
            "功能过程类型": "查询",
            "功能过程描述": "查看企业风险画像详情。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "跨域企业风险画像",
                "type": "EIF",
                "explanation": "AI 判断该风险画像由外部风控平台维护，本系统只引用。",
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)
    review_hits = [
        hit
        for hit in rows[0]["_规则命中详情"]
        if hit["rule_id"] == "postprocess.ai_data_group_review"
    ]
    assert review_hits
    assert review_hits[0]["suggested_type"] == "EIF"


def test_strict_profile_warns_when_ai_complex_ilf_needs_manual_review():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "营销管理",
            "二级模块": "客群洞察",
            "三级模块": "客群洞察",
            "三级模块整体功能描述": "生成客户洞察结果。",
            "功能过程": "刷新洞察",
            "功能过程类型": "新增",
            "功能过程描述": "刷新客户洞察。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "客户生命周期洞察",
                "type": "ILF",
                "explanation": "AI 判断本系统保存并持续维护客户生命周期洞察结果。",
            },
        ],
    )

    assert rows[0]["类型"] == "ILF"
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)
    assert any(
        hit["rule_id"] == "postprocess.ai_data_group_review"
        for hit in rows[0]["_规则命中详情"]
    )


def test_strict_profile_data_group_review_survives_unrelated_ai_warning():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "风控管理",
            "二级模块": "风险画像",
            "三级模块": "风险画像",
            "三级模块整体功能描述": "结合多源业务信息生成风险画像。",
            "功能过程": "查看画像",
            "功能过程类型": "查询",
            "功能过程描述": "查看企业风险画像详情。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["有效规则"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "跨域企业风险画像",
                "type": "EIF",
                "explanation": "AI 判断该风险画像由外部风控平台维护，本系统只引用。",
                "classification_basis_index": 99,
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert any("classification_basis_index 越界" in warning for warning in warnings)
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)


def test_keyword_type_fallbacks():
    token = set_current_fpa_rule_set_config(_custom_default_rule_set())
    try:
        assert CUSTOM_RULES_PROFILE.infer_type("客户界面开发")[0] == "EI"
        assert CUSTOM_RULES_PROFILE.infer_type("添加客户-逻辑处理开发")[0] == "ILF"
        assert CUSTOM_RULES_PROFILE.infer_type("查询客户-查询处理开发")[0] == "EQ"
        assert CUSTOM_RULES_PROFILE.infer_type("导出客户-导出处理开发")[0] == "EO"
        assert CUSTOM_RULES_PROFILE.infer_type("导入客户-导入处理开发")[0] == "EI"
        assert CUSTOM_RULES_PROFILE.infer_type("同步外部接口数据-逻辑处理开发")[0] == "ILF"
        assert CUSTOM_RULES_PROFILE.infer_type("引用统一用户中心账号-外部接口处理开发")[0] == "EIF"
    finally:
        reset_current_fpa_rule_set_config(token)


class LowConfidenceRulesProfile(CustomRulesProfile):
    def fallback_rows_for_l3(self, group, meta, start_seq=1):
        return [{
            "序号": start_seq,
            "子系统(模块)": meta.get("子系统（模块）", ""),
            "资产标识": meta.get("资产标识", ""),
            "新增/修改功能点": "低置信度规则行",
            "类型": "",
            "计算依据归类": "",
            "计算依据说明": "低置信度规则行。",
            "变更状态": "新增",
            "调整值": 1,
            "要素数量": 1,
            "生成方式": "fallback",
            "类型理由": "",
            "源功能过程": "",
            "后处理警告": "",
        }]


def test_rules_first_keeps_rules_when_rule_rows_are_usable(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: pytest.fail("rules_first should not call AI when rules are usable"),
    )

    result = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        strategy="rules_first",
    )

    assert result
    assert {row["生成方式"] for row in result} == {"fallback"}
    assert _rules_first_ai_reasons(_group_rows_by_l3(_rows())[0], result) == []


def test_rules_first_calls_ai_when_rule_rows_are_low_confidence(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    response = {
        "rows": [{
            "name": "AI 复核功能点",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": "AI 复核功能点，具体为以下：1、覆盖低置信度规则无法覆盖的功能过程。",
            "source_processes": ["添加垂直行业", "查询垂直行业"],
        }]
    }
    calls = {"count": 0}

    def fake_call_llm(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = _plan_fpa_rows_with_execution(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        profile=LowConfidenceRulesProfile(),
        strategy="rules_first",
        rule_set="custom_rules_default",
    )

    assert calls["count"] == 1
    assert result[0]["生成方式"] == "ai"
    assert result[0]["新增/修改功能点"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-AI 复核功能点"


def test_rules_first_without_api_keeps_low_confidence_rules_and_audit_warning(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    audit_trace = tmp_path / "audit.json"

    result = _plan_fpa_rows_with_execution(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="",
        model="test",
        base_url="",
        profile=LowConfidenceRulesProfile(),
        strategy="rules_first",
        rule_set="custom_rules_default",
        audit_trace_path=str(audit_trace),
    )

    assert result[0]["生成方式"] == "fallback"
    trace = json.loads(audit_trace.read_text(encoding="utf-8"))
    warnings = trace["modules"][0]["warnings"]
    assert any("规则结果需要 AI 复核但未配置 API Key" in warning for warning in warnings)
    assert any("类型无效" in warning for warning in warnings)


def test_ai_parse_failure_falls_back(monkeypatch, tmp_path, caplog):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: "这里不是 JSON",
    )
    caplog.set_level(logging.WARNING)
    result = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        strategy="ai_first",
    )
    assert result[0]["生成方式"] == "fallback"
    assert any("FPA AI 响应解析失败" in r.message for r in caplog.records)


def test_missing_fpa_config_does_not_fall_back(monkeypatch, tmp_path):
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: pytest.fail("missing prompt config must stop before LLM call"),
    )

    with pytest.raises(FpaConfigError, match="未找到 FPA 配置文件"):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="sk-test",
            model="test",
            base_url="",
            strategy="ai_first",
        )


def test_ai_first_requires_api_key():
    with pytest.raises(ValueError, match="需要 API Key"):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="",
            model="test",
            base_url="",
            profile=STRICT_FPA_PROFILE,
            strategy="ai_first",
        )


def test_fpa_preview_returns_ai_debug(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    response = {
        "rows": [
            {
                "name": "垂直行业数据维护",
                "type": "ILF",
                "type_reason": "内部逻辑文件",
                "classification_basis_index": 1,
                "explanation": "垂直行业数据维护，具体如下：触发事件：管理员维护数据；事件流：系统保存数据。",
            }
        ]
    }

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )
    def fake_call_llm(*args, **kwargs):
        assert kwargs.get("return_thinking") is True
        return json.dumps(response, ensure_ascii=False), "思考过程"

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        base_url="",
        strategy="ai_only",
    )

    debug = result["debug"]
    assert debug["ai_called"] is True
    assert debug["model"] == "test-model"
    assert debug["system_prompt"] == "系统提示词"
    assert debug["core_rules_source"] == "用户配置（配置目录/fpa_config.yaml: core_rules.custom_rules）"
    assert debug["system_prompt_source"] == "用户配置（配置目录/fpa_config.yaml: system_prompt_sets.custom_rules）"
    assert debug["user_prompt_source"] == "用户配置（配置目录/fpa_config.yaml: user_prompt_sets.custom_rules）"
    assert "垂直行业管理" in debug["user_prompt"]
    assert "1) 规则一" in debug["user_prompt"]
    assert "2) 规则二" in debug["user_prompt"]
    assert "[system]" in debug["ai_prompt"]
    assert "垂直行业数据维护" in debug["raw_response"]
    assert debug["thinking"] == "思考过程"
    assert debug["parsed_rows"] == response["rows"]
    assert result["rows"][0]["classification_basis"] == "规则一"
    assert debug["final_rows"][0]["name"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据维护"
    assert result["audit"]["raw_ai"]["source"] == "ai"
    assert result["audit"]["raw_ai"]["raw_rows"] == response["rows"]


def test_ai_only_preview_empty_rows_does_not_fallback(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: (json.dumps({"rows": []}), "") if kwargs.get("return_thinking") else json.dumps({"rows": []}),
    )

    def fail_if_fallback(*args, **kwargs):
        pytest.fail("ai_only 失败时不应使用 rules_fallback")

    monkeypatch.setattr(CustomRulesProfile, "fallback_rows_for_l3", fail_if_fallback)

    with pytest.raises(ValueError, match="AI 规划未生成有效 FPA 行"):
        preview_fpa_module(
            file_path=str(xlsx),
            module_name="垂直行业管理",
            api_key="sk-test",
            model="test-model",
            base_url="",
            strategy="ai_only",
        )


def test_fpa_preview_prompt_includes_project_domain_context(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    (tmp_path / "domain_context.json").write_text(
        """
{
  "system_boundary": "本系统维护供应商协同关系，不维护供应商主档。",
  "internal_data_groups": [{"name": "供应商协同关系"}],
  "external_data_groups": [{"name": "供应商档案", "source": "供应商平台"}],
  "external_services": [{"name": "短信平台"}]
}
""",
        encoding="utf-8",
    )
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: (
            json.dumps(
                {
                    "rows": [{
                        "name": "领域上下文验证功能点",
                        "type": "EI",
                        "classification_basis_index": 1,
                        "explanation": "领域上下文验证功能点，具体为以下：1、覆盖上下文传入。",
                    }]
                },
                ensure_ascii=False,
            ),
            "",
        ),
    )

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        base_url="",
        strategy="ai_only",
    )

    prompt = result["debug"]["user_prompt"]
    assert '"子系统（模块）": "测试系统"' in prompt
    assert '"system_boundary": "本系统维护供应商协同关系，不维护供应商主档。"' in prompt
    assert '"name": "供应商协同关系"' in prompt
    assert '"name": "供应商档案"' in prompt
    assert '"source": "供应商平台"' in prompt
    assert '"name": "短信平台"' in prompt


def test_rules_first_preview_calls_ai_when_rule_rows_are_low_confidence(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )

    def fake_fallback(self, group, meta, start_seq=1):
        return [{
            "序号": start_seq,
            "子系统(模块)": meta.get("子系统（模块）", ""),
            "资产标识": meta.get("资产标识", ""),
            "新增/修改功能点": "低置信度规则行",
            "类型": "",
            "计算依据归类": "",
            "计算依据说明": "低置信度规则行。",
            "变更状态": "新增",
            "调整值": 1,
            "要素数量": 1,
            "生成方式": "fallback",
            "类型理由": "",
            "源功能过程": "",
            "后处理警告": "",
        }]

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.fpa_profiles.CustomRulesProfile.fallback_rows_for_l3",
        fake_fallback,
    )
    response = {
        "rows": [{
            "name": "AI 预览复核功能点",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": "AI 预览复核功能点，具体为以下：1、覆盖低置信度规则输出。",
            "source_processes": ["添加垂直行业", "查询垂直行业"],
        }]
    }

    def fake_call_llm(*args, **kwargs):
        assert kwargs.get("return_thinking") is True
        return json.dumps(response, ensure_ascii=False), "思考过程"

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        strategy="rules_first",
    )

    assert result["used_ai"] is True
    assert result["debug"]["reason"] == "rules_first_needs_ai"
    assert result["rows"][0]["name"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-AI 预览复核功能点"
    assert any("规则结果触发 AI 复核" in warning for warning in result["warnings"])


def test_ai_cache_hit_skips_llm(monkeypatch, tmp_path, caplog):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    cache_path = tmp_path / "fpa_ai_cache.json"
    audit_trace_path = tmp_path / "fpa_audit_trace.json"
    response = {
        "rows": [
            {
                "name": "垂直行业管理界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": "垂直行业管理界面开发，具体为以下：1、新增列表和查询条件。",
            }
        ]
    }
    calls = {"count": 0}

    def first_call(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", first_call)
    first = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
        audit_trace_path=str(audit_trace_path),
    )
    assert calls["count"] == 1
    assert cache_path.exists()
    assert first[0]["生成方式"] == "ai"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = next(iter(cache["entries"].values()))
    assert entry["profile"] == "custom_rules"
    assert entry["profile_version"] == "1"
    assert entry["strategy"] == "ai_first"
    assert entry["rule_set"] == "custom_rules_default"
    trace = json.loads(audit_trace_path.read_text(encoding="utf-8"))
    assert trace["modules"][0]["source"] == "ai"
    assert trace["modules"][0]["raw_rows"] == response["rows"]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM should not be called on cache hit")

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fail_if_called)
    caplog.set_level(logging.INFO)
    second = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
        audit_trace_path=str(audit_trace_path),
    )

    assert second[0]["新增/修改功能点"] == "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业管理界面开发"
    trace = json.loads(audit_trace_path.read_text(encoding="utf-8"))
    assert trace["modules"][0]["source"] == "ai_cache"
    assert any("缓存命中" in r.message for r in caplog.records)


def test_ai_cache_is_invalidated_when_project_domain_context_changes(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    domain_context_path = tmp_path / "domain_context.json"
    domain_context_path.write_text(
        """
{
  "system_boundary": "本系统维护供应商关系。",
  "internal_data_groups": [{"name": "供应商关系"}],
  "external_data_groups": [],
  "external_services": []
}
""",
        encoding="utf-8",
    )
    cache_path = tmp_path / "fpa_ai_cache.json"
    response = {
        "rows": [{
            "name": "供应商关系维护",
            "type": "ILF",
            "classification_basis_index": 1,
            "explanation": "供应商关系维护，具体为以下：1、保存供应商关系。",
        }]
    }
    calls = {"count": 0}

    def fake_call(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call)
    for _ in range(2):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="sk-test",
            model="test-model",
            base_url="",
            cache_path=str(cache_path),
            strategy="ai_first",
        )
    assert calls["count"] == 1

    domain_context_path.write_text(
        domain_context_path.read_text(encoding="utf-8").replace("供应商关系。", "供应商协同关系。"),
        encoding="utf-8",
    )
    _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
    )

    assert calls["count"] == 2


def test_ai_cache_key_includes_configured_core_rules():
    base_kwargs = {
        "group": _group_rows_by_l3(_rows())[0],
        "judgement_rules": ["规则一"],
        "domain_context": {},
        "model": "test-model",
        "profile": CUSTOM_RULES_PROFILE,
        "strategy": "ai_first",
        "rule_set": "custom_rules_default",
        "rule_set_config": {},
        "system_prompt": "system",
        "user_prompt": "user",
    }

    first = _fpa_ai_cache_key(core_rules="custom core v1", **base_kwargs)
    second = _fpa_ai_cache_key(core_rules="custom core v2", **base_kwargs)

    assert first != second


def test_fpa_check_xlsx_columns_can_be_configured(monkeypatch, tmp_path):
    (tmp_path / "system_config.yaml").write_text(
        """
fpa_check_columns:
  FPA结果: ["新增/修改功能点", "类型", "后处理警告"]
  Warnings: ["对象", "Warning", "来源规则ID"]
  规则命中详情: ["功能点名称", "规则ID", "是否采用"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)

    fpa_md = tmp_path / "fpa.md"
    fpa_md.write_text(
        """# FPA 工作量评估

**profile**: custom_rules
**strategy**: rules_first
**rule_set**: custom_rules_default

| 序号 | 子系统(模块) | 资产标识 | 新增/修改功能点 | 类型 | 计算依据归类 | 计算依据说明 | 变更状态 | 调整值 | 要素数量 | 生成方式 | 类型理由 | 源功能过程 | 后处理警告 |
|------|-------------|---------|----------------|------|-------------|-------------|---------|-------|---------|---------|---------|-----------|-----------|
| 1 | 测试系统 | TEST | 查询客户-查询处理开发 | EQ |  | 查询客户。 | 新增 | 2 | 1 | ai | AI 根据功能点名称和业务说明判定。 | 查询客户 | 查询客户 classification_basis_index 越界: 99 |
""",
        encoding="utf-8",
    )
    tree_md = tmp_path / "tree.md"
    tree_md.write_text(
        """| 入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述 |
|------|---------|---------|---------|----------|----------------------|----------|--------------|--------------|
| 后台 | 客户管理 | 客户查询 | 客户查询 | 地市后台 | 查询客户。 | 查询客户 | 查询 | 按条件查询客户。 |
""",
        encoding="utf-8",
    )
    audit_trace = tmp_path / "trace.json"
    audit_trace.write_text(
        json.dumps({
            "modules": [{
                "rule_hits": [{
                    "fpa_seq": 1,
                    "name": "查询客户-查询处理开发",
                    "generation": "ai",
                    "hit_object": "查询客户-查询处理开发",
                    "rule_id": "postprocess.classification_basis_index",
                    "rule_desc": "classification_basis_index 必须落在模板判定原则范围内。",
                    "suggested_type": "EQ",
                    "adopted": "是",
                    "warnings": ["查询客户 classification_basis_index 越界: 99"],
                }],
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    output = tmp_path / "check.xlsx"
    generate_fpa_check_xlsx_from_md(str(fpa_md), str(tree_md), str(output), str(audit_trace))

    wb = openpyxl.load_workbook(output, data_only=True)
    assert [cell.value for cell in wb["FPA结果"][1]] == ["新增/修改功能点", "类型", "后处理警告"]
    assert [cell.value for cell in wb["Warnings"][1]] == ["对象", "Warning", "来源规则ID"]
    assert [cell.value for cell in wb["规则命中详情"][1]] == ["功能点名称", "规则ID", "是否采用"]
    assert wb["Warnings"].cell(2, 3).value == "postprocess.classification_basis_index"
    wb.close()


def test_fpa_check_xlsx_includes_rule_set_config_warning(tmp_path):
    fpa_md = tmp_path / "fpa.md"
    fpa_md.write_text(
        """# FPA 工作量评估

**profile**: custom_rules
**strategy**: rules_first
**rule_set**: sms_service_rules

| 序号 | 子系统(模块) | 资产标识 | 新增/修改功能点 | 类型 | 计算依据归类 | 计算依据说明 | 变更状态 | 调整值 | 要素数量 | 生成方式 | 类型理由 | 源功能过程 | 后处理警告 |
|------|-------------|---------|----------------|------|-------------|-------------|---------|-------|---------|---------|---------|-----------|-----------|
| 1 | 测试系统 | TEST | 发送短信-逻辑处理开发 | EI |  | 调用短信平台发送通知。 | 新增 | 2 | 1 | fallback | 普通外部服务调用按事务处理。 | 发送短信 |  |
""",
        encoding="utf-8",
    )
    tree_md = tmp_path / "tree.md"
    tree_md.write_text(
        """| 入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述 |
|------|---------|---------|---------|----------|----------------------|----------|--------------|--------------|
| 后台 | 通知 | 短信通知 | 短信通知 | 地市后台 | 发送短信通知。 | 发送短信 | 新增 | 调用短信平台发送通知。 |
""",
        encoding="utf-8",
    )
    warning = (
        "FPA 配置 warning: rule_set sms_service_rules 的 external_data_rules "
        "将普通外部服务「短信平台」配置为外部数据组「短信平台消息记录」。"
    )
    audit_trace = tmp_path / "trace.json"
    audit_trace.write_text(
        json.dumps({
            "modules": [{
                "module": "【地市后台】通知-短信通知-短信通知",
                "l3": "短信通知",
                "source": "rules",
                "raw_rows": [],
                "warnings": [warning, "规则优先策略未调用 AI"],
                "rule_hits": [],
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    output = tmp_path / "check.xlsx"
    generate_fpa_check_xlsx_from_md(str(fpa_md), str(tree_md), str(output), str(audit_trace))

    wb = openpyxl.load_workbook(output, data_only=True)
    warning_rows = [
        [cell.value for cell in row]
        for row in wb["Warnings"].iter_rows(min_row=2)
    ]
    assert any(row[4] == warning for row in warning_rows)
    assert any(row[5] == "config.external_data_rules.external_service" for row in warning_rows)
    coverage_headers = [cell.value for cell in wb["覆盖审核"][1]]
    coverage_warning = wb["覆盖审核"].cell(2, coverage_headers.index("Warnings") + 1).value
    assert warning in coverage_warning
    raw_headers = [cell.value for cell in wb["AI原始返回"][1]]
    raw_warning = wb["AI原始返回"].cell(2, raw_headers.index("Warnings") + 1).value
    assert warning in raw_warning
    wb.close()
