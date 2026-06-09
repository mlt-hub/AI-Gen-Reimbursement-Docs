from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    FpaProcessRowsPlanningRule,
    FpaRowPlanningRules,
    FpaRuleSetConfig,
    FpaUiRowPlanningRule,
    KeywordTypeRule,
    reset_current_fpa_rule_set_config,
    set_current_fpa_rule_set_config,
)
from ai_gen_reimbursement_docs.fpa_validator import validate_fpa_rows


def _group():
    return {
        "client_type": "业务端",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户档案",
        "processes": [
            {"name": "查询客户", "type": "新增", "desc": "按客户名称查询客户列表。"},
            {"name": "查询客户", "type": "新增", "desc": "按手机号查询客户列表。"},
            {"name": "导出客户清单", "type": "新增", "desc": "按查询条件导出客户清单文件。"},
            {"name": "导入客户名单", "type": "新增", "desc": "上传客户名单并导入。"},
        ],
    }


def _rule_set():
    return FpaRuleSetConfig(
        name="unified_ui_rs",
        keyword_rules=(
            KeywordTypeRule("EO", ("导出", "下载", "生成文件"), "导出类处理按 EO。"),
            KeywordTypeRule("EQ", ("查询", "查看", "列表"), "查询类处理按 EQ。"),
            KeywordTypeRule("EI", ("导入", "保存", "新增", "修改", "删除"), "维护类处理按 EI。"),
        ),
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
    )


def _point(group: dict[str, object], name: str) -> str:
    return f"【{group['client_type']}】{group['l1']}-{group['l2']}-{group['l3']}-{name}"


def test_unified_ui_harness_merges_l3_ui_and_process_rows_by_business_action():
    group = _group()
    token = set_current_fpa_rule_set_config(_rule_set())
    try:
        rows = CUSTOM_RULES_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    finally:
        reset_current_fpa_rule_set_config(token)

    names = [str(row["新增/修改功能点"]) for row in rows]
    assert names.count(_point(group, "界面开发")) == 1
    assert names.count(_point(group, "查询客户-查询处理开发")) == 1
    assert _point(group, "导出客户清单-导出处理开发") in names
    assert _point(group, "导入客户名单-导入处理开发") in names

    query_row = next(row for row in rows if row["新增/修改功能点"] == _point(group, "查询客户-查询处理开发"))
    assert query_row["源功能过程"] == "查询客户"
    assert not any("按钮" in name or "查询条件" in name for name in names)
    assert not any(issue.code == "validator.explanation_structure" for issue in validate_fpa_rows(group=group, rows=rows))


def test_unified_ui_harness_can_disable_l3_ui_row_without_disabling_process_rows():
    group = _group()
    rule_set = _rule_set()
    disabled_rule_set = FpaRuleSetConfig(
        name=rule_set.name,
        keyword_rules=rule_set.keyword_rules,
        row_planning_rules=FpaRowPlanningRules(
            ui_row=FpaUiRowPlanningRule(
                enabled=False,
                scope="l3",
                merge="single_row",
                name_suffix="界面开发",
                fpa_type="EI",
            ),
            process_rows=rule_set.row_planning_rules.process_rows,
        ),
    )
    token = set_current_fpa_rule_set_config(disabled_rule_set)
    try:
        rows = CUSTOM_RULES_PROFILE.fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    finally:
        reset_current_fpa_rule_set_config(token)

    names = [str(row["新增/修改功能点"]) for row in rows]
    assert _point(group, "界面开发") not in names
    assert _point(group, "查询客户-查询处理开发") in names
