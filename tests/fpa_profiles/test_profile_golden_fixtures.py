import json
from pathlib import Path

import pytest

from ai_gen_reimbursement_docs.fpa_agent_review import build_fpa_agent_review
from ai_gen_reimbursement_docs.fpa_profiles import (
    FpaProcessRowsPlanningRule,
    FpaRowPlanningRules,
    FpaRuleSetConfig,
    FpaUiRowPlanningRule,
    KeywordTypeRule,
    get_fpa_profile,
    reset_current_fpa_rule_set_config,
    set_current_fpa_rule_set_config,
)
from ai_gen_reimbursement_docs.gen_fpa import _normalize_ai_fpa_rows_for_l3


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "fpa_profile_golden_cases"
    / "profile_agent_review_contract_cases.json"
)


def _profile_golden_cases():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _summary(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {
            "name": str(row.get("新增/修改功能点", "") or ""),
            "type": str(row.get("类型", "") or ""),
        }
        for row in rows
    ]


def _unified_rule_set(name: str = "unified_ui_rs") -> FpaRuleSetConfig:
    return FpaRuleSetConfig(
        name=name,
        keyword_rules=(
            KeywordTypeRule("EO", ("导出", "下载", "生成文件"), "导出类处理按 EO。"),
            KeywordTypeRule("EQ", ("导入",), "导入类处理按 EQ。"),
            KeywordTypeRule("EIF", ("外部接口联调", "外部系统调用"), "外部边界能力按 EIF。"),
            KeywordTypeRule("ILF", ("查询", "查看", "列表", "保存", "新增", "修改", "维护", "删除"), "逻辑接口/表能力按 ILF。"),
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
                explanation_template=(
                    "来源场景：{name}\n"
                    "业务数据：当前三级模块业务数据。\n"
                    "业务规则：覆盖以下功能过程：\n{items}\n"
                    "计算说明：按 EI 识别。"
                ),
            ),
            process_rows=FpaProcessRowsPlanningRule(
                enabled=True,
                one_row_per_process=True,
                default_name_suffix="逻辑接口开发",
                type_suffixes={
                    "ILF": "逻辑接口开发",
                    "EQ": "导入处理开发",
                    "EO": "导出处理开发",
                    "EIF": "外部接口联调调用",
                },
                explanation_template=(
                    "来源场景：{name}\n"
                    "业务数据：当前功能过程业务数据。\n"
                    "业务规则：{description}\n"
                    "计算说明：按 EI/ILF/EQ/EO/EIF 之一识别并计量。"
                ),
            ),
        ),
    )


def _ui_api_mapping_rule_set() -> FpaRuleSetConfig:
    return FpaRuleSetConfig(
        name="ui_api_mapping_rs",
        row_planning_rules=FpaRowPlanningRules(
            process_rows=FpaProcessRowsPlanningRule(
                enabled=True,
                one_row_per_process=True,
                explanation_template="{name}，具体为以下：\n1、{description}",
            ),
        ),
    )


def _rows_for_case(case: dict[str, object]) -> list[dict[str, object]]:
    profile_name = str(case["profile"])
    profile = get_fpa_profile(profile_name)
    group = case["group"]
    meta = case["meta"]
    mode = str(case["mode"])
    if mode == "ai_normalized":
        rows, warnings = _normalize_ai_fpa_rows_for_l3(
            group=group,
            meta=meta,
            ai_rows=list(case.get("ai_rows", [])),
            judgement_rules=["规则一"],
            profile=profile,
        )
        assert not any("类型不合法" in warning for warning in warnings)
        return rows

    rule_set = _ui_api_mapping_rule_set() if profile_name == "ui_api_mapping" else _unified_rule_set()
    token = set_current_fpa_rule_set_config(rule_set)
    try:
        return profile.fallback_rows_for_l3(group, meta, judgement_rules=["规则一"])
    finally:
        reset_current_fpa_rule_set_config(token)


@pytest.mark.parametrize("case", _profile_golden_cases(), ids=lambda item: item["case_id"])
def test_profile_golden_fixture_outputs_match_contract(case):
    rows = _rows_for_case(case)
    assert _summary(rows) == case["expected"]

    profile = get_fpa_profile(str(case["profile"]))
    review = build_fpa_agent_review(
        group=case["group"],
        rows=rows,
        profile_name=profile.name,
        profile_kind=profile.agent_review_profile_kind(),
    )

    assert review["applicability"] == "debug_only"
    assert review["summary"]["profile_quality_issue_count"] == 0
