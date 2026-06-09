from ai_gen_reimbursement_docs.fpa_profiles import UiApiMappingProfile
from ai_gen_reimbursement_docs.fpa_validator import validate_fpa_rows


def _group():
    return {
        "client_type": "业务端",
        "l1": "销售管理",
        "l2": "合同中心",
        "l3": "合同管理",
        "processes": [
            {"name": "查询合同列表", "type": "新增", "desc": "查询合同列表。"},
            {"name": "提交合同审批", "type": "新增", "desc": "提交合同审批，调用 OA 审批接口。"},
            {"name": "再次提交合同审批", "type": "新增", "desc": "再次提交合同审批，调用 OA 审批接口。"},
            {"name": "保存合同草稿", "type": "新增", "desc": "保存合同草稿。"},
        ],
    }


def _point(group: dict[str, object], name: str) -> str:
    return f"【{group['client_type']}】{group['l1']}-{group['l2']}-{group['l3']}-{name}"


def test_ui_api_mapping_harness_generates_default_ui_and_api_rows_per_process():
    group = _group()
    rows = UiApiMappingProfile().fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    types = {str(row["新增/修改功能点"]): str(row["类型"]) for row in rows}

    for process in group["processes"]:
        process_name = process["name"]
        assert types[_point(group, f"{process_name}-界面开发")] == "EI"
        assert types[_point(group, f"{process_name}-接口开发")] == "ILF"

    assert not any(issue.code == "validator.explanation_structure" for issue in validate_fpa_rows(group=group, rows=rows))


def test_ui_api_mapping_harness_keeps_explicit_backend_rows_and_merges_sources():
    group = _group()
    rows = UiApiMappingProfile().fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    names = [str(row["新增/修改功能点"]) for row in rows]
    explicit_name = _point(group, "OA 审批接口")

    assert names.count(explicit_name) == 1
    explicit_row = next(row for row in rows if row["新增/修改功能点"] == explicit_name)
    assert explicit_row["类型"] == "ILF"
    assert explicit_row["源功能过程"] == "提交合同审批、再次提交合同审批"
    assert _point(group, "提交合同审批-接口开发") in names


def test_ui_api_mapping_harness_does_not_create_explicit_backend_row_for_plain_actions():
    group = _group()
    rows = UiApiMappingProfile().fallback_rows_for_l3(group, {"子系统（模块）": "测试", "资产标识": "T"})
    names = [str(row["新增/修改功能点"]) for row in rows]

    assert _point(group, "保存合同草稿-界面开发") in names
    assert _point(group, "保存合同草稿-接口开发") in names
    assert _point(group, "保存合同草稿") not in names
