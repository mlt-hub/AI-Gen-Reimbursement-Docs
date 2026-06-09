from ai_gen_reimbursement_docs.fpa_profiles import CustomRulesProfile
from ai_gen_reimbursement_docs.gen_fpa import _normalize_ai_fpa_rows_for_l3


def _group():
    return {
        "client_type": "地市后台",
        "l1": "客户管理",
        "l2": "客户中心",
        "l3": "客户档案",
        "processes": [
            {"name": "维护客户档案", "type": "新增", "desc": "维护客户档案基础信息。"},
            {"name": "维护联系人", "type": "新增", "desc": "维护客户联系人。"},
        ],
    }


def _meta():
    return {"子系统（模块）": "测试系统", "资产标识": "TEST-001"}


def _explanation(source: str, fpa_type: str = "EI") -> str:
    return (
        f"来源场景：{source}。\n"
        "业务数据：客户档案。\n"
        "业务规则：按独立界面维护不同业务对象。\n"
        f"计算说明：按 {fpa_type} 计量。"
    )


def test_multi_uis_harness_keeps_multiple_ui_rows_with_split_reason_metadata():
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=_group(),
        meta=_meta(),
        ai_rows=[
            {
                "name": "客户档案-界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": _explanation("维护客户档案"),
                "source_processes": ["维护客户档案"],
                "split_reason": "独立页面：客户基础信息维护页。",
            },
            {
                "name": "客户联系人-界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": _explanation("维护联系人"),
                "source_processes": ["维护联系人"],
                "split_reason": "独立业务对象：客户联系人维护区。",
            },
        ],
        judgement_rules=["规则一"],
        profile=CustomRulesProfile(name="multi_uis"),
    )

    ui_rows = [row for row in rows if "界面开发" in str(row["新增/修改功能点"])]
    assert len(ui_rows) == 2
    assert all("拆分理由" in str(row["后处理警告"]) for row in ui_rows)
    assert any("独立页面" in str(row["后处理警告"]) for row in ui_rows)
    assert any("独立业务对象" in str(row["后处理警告"]) for row in ui_rows)
    assert not any("同名多界面开发行" in warning for warning in warnings)


def test_multi_uis_harness_keeps_duplicate_ui_names_and_warns_for_review():
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=_group(),
        meta=_meta(),
        ai_rows=[
            {
                "name": "客户档案-界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": _explanation("维护客户档案"),
                "source_processes": ["维护客户档案"],
                "split_reason": "独立页面：基础信息维护页。",
            },
            {
                "name": "客户档案-界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": _explanation("维护联系人"),
                "source_processes": ["维护联系人"],
                "split_reason": "独立业务对象：联系人维护区。",
            },
        ],
        judgement_rules=["规则一"],
        profile=CustomRulesProfile(name="multi_uis"),
    )

    ui_rows = [row for row in rows if "界面开发" in str(row["新增/修改功能点"])]
    assert len(ui_rows) == 2
    assert "同名多界面开发行" in str(ui_rows[1]["后处理警告"])
    assert any("同名多界面开发行" in warning for warning in warnings)
