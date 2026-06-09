"""COSMIC deterministic validation tests."""

import json

from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.cosmic_validator import (
    global_cosmic_issue,
    validate_cosmic_item,
    validate_cosmic_items,
    write_cosmic_validation_json,
)


def _movement(order=1, move_type="E", data_group="用户数据", data_attrs="姓名,手机号"):
    return DataMovement(
        order=order,
        sub_process=f"步骤{order}",
        move_type=move_type,
        data_group=data_group,
        data_attrs=data_attrs,
    )


def _item(**overrides):
    data = {
        "project": "测试项目",
        "module_l1": "系统管理",
        "module_l2": "用户管理",
        "module_l3": "用户注册",
        "user": "发起者：用户注册|接收者：系统管理",
        "trigger": "用户触发",
        "process": "注册用户",
        "movements": [_movement(1, "E"), _movement(2, "X")],
    }
    data.update(overrides)
    return CosmicItem(**data)


def _codes(result):
    return [issue.code for issue in result.issues]


def test_passed_item_has_no_issues():
    result = validate_cosmic_item(_item())

    assert result.status == "passed"
    assert result.issues == []
    assert result.basis["function_user"]["matched"] is True
    assert result.basis["function_user"]["match_source"] == "module_l3"


def test_missing_trigger_is_error():
    result = validate_cosmic_item(_item(trigger=""))

    assert "MISSING_TRIGGER" in _codes(result)
    assert result.status == "blocked"


def test_first_move_must_be_entry():
    result = validate_cosmic_item(
        _item(movements=[_movement(1, "R"), _movement(2, "X")])
    )

    issue = next(issue for issue in result.issues if issue.code == "FIRST_MOVE_NOT_ENTRY")
    assert issue.field == "movements[0].move_type"


def test_last_move_must_be_write_or_exit():
    result = validate_cosmic_item(
        _item(movements=[_movement(1, "E"), _movement(2, "R")])
    )

    assert "LAST_MOVE_NOT_WRITE_OR_EXIT" in _codes(result)
    assert result.status == "blocked"


def test_too_few_movements_is_error():
    result = validate_cosmic_item(_item(movements=[_movement(1, "E")]))

    assert "TOO_FEW_MOVEMENTS" in _codes(result)
    assert result.status == "blocked"


def test_missing_module_path_is_error():
    result = validate_cosmic_item(_item(module_l3=""))

    assert "MISSING_MODULE_PATH" in _codes(result)
    assert result.status == "blocked"


def test_missing_process_name_is_error():
    result = validate_cosmic_item(_item(process=""))

    assert "MISSING_PROCESS_NAME" in _codes(result)
    assert result.status == "blocked"


def test_empty_data_group_is_warning():
    result = validate_cosmic_item(
        _item(movements=[_movement(1, "E", data_group=""), _movement(2, "X")])
    )

    assert "EMPTY_DATA_GROUP" in _codes(result)
    assert result.status == "review_required"


def test_empty_data_attrs_is_warning():
    result = validate_cosmic_item(
        _item(movements=[_movement(1, "E", data_attrs=""), _movement(2, "X")])
    )

    assert "EMPTY_DATA_ATTRS" in _codes(result)
    assert result.status == "review_required"


def test_non_standard_move_type_is_warning():
    result = validate_cosmic_item(
        _item(movements=[_movement(1, "E"), _movement(2, "输入")])
    )

    assert "NON_STANDARD_MOVE_TYPE" in _codes(result)


def test_control_command_movement_requires_review():
    control = _movement(3, "X", data_group="页面状态", data_attrs="排序状态")
    control.sub_process = "点击下一页并排序列表"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="查询参数", data_attrs="页码"),
            _movement(2, "X", data_group="查询结果", data_attrs="列表"),
            control,
        ])
    )

    assert "CONTROL_COMMAND_MOVEMENT" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["movement_semantics"][0]["code"] == "CONTROL_COMMAND_MOVEMENT"
    assert result.basis["movement_semantics"][0]["movement_order"] == 3


def test_data_operation_only_movement_requires_review():
    operation = _movement(2, "X", data_group="校验结果", data_attrs="提示")
    operation.sub_process = "格式化手机号并校验输入格式"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="用户数据", data_attrs="手机号"),
            operation,
        ])
    )

    assert "DATA_OPERATION_ONLY_MOVEMENT" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["movement_semantics"][0]["code"] == "DATA_OPERATION_ONLY_MOVEMENT"


def test_error_wins_over_warning():
    result = validate_cosmic_item(
        _item(trigger="", movements=[_movement(1, "E", data_attrs=""), _movement(2, "X")])
    )

    assert "MISSING_TRIGGER" in _codes(result)
    assert "EMPTY_DATA_ATTRS" in _codes(result)
    assert result.status == "blocked"


def test_report_summary_counts_status_and_severity():
    report = validate_cosmic_items(
        [
            _item(process="通过"),
            _item(process="待审", movements=[_movement(1, "E", data_attrs=""), _movement(2, "X")]),
            _item(process="阻断", trigger=""),
        ],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
    )

    assert report.summary["passed"] == 1
    assert report.summary["review_required"] == 1
    assert report.summary["blocked"] == 1
    assert report.summary["errors"] == 1
    assert report.summary["warnings"] == 1
    assert report.status == "blocked"


def test_report_json_is_stable_and_chinese_readable(tmp_path):
    report = validate_cosmic_items(
        [_item()],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
    )
    output = tmp_path / "cosmic.json"

    write_cosmic_validation_json(report, str(output))

    content = output.read_text(encoding="utf-8")
    assert "测试项目" in content
    assert "\\u6d4b" not in content
    payload = json.loads(content)
    assert payload["summary"]["passed"] == 1
    assert payload["cfp_basis"]["source"] == "template_formula"
    assert payload["cfp_basis"]["formula_configured"] is True
    assert payload["items"][0]["basis"]["function_user"]["matched_term"] == "用户注册"


def test_empty_items_is_global_error():
    report = validate_cosmic_items([], project_name="测试项目", cfp_formula="x")

    assert report.status == "blocked"
    assert [issue.code for issue in report.issues] == ["NO_COSMIC_ITEMS"]


def test_generation_global_issue_is_preserved():
    report = validate_cosmic_items(
        [],
        project_name="测试项目",
        cfp_formula="x",
        global_issues=[
            global_cosmic_issue(
                "error", "NO_API_KEY",
                "未设置 API Key，未调用 AI 生成 COSMIC 拆分数据",
                "api_key",
            )
        ],
    )

    assert report.status == "blocked"
    assert [issue.code for issue in report.issues] == [
        "NO_API_KEY",
        "NO_COSMIC_ITEMS",
    ]
    assert report.summary["global_errors"] == 2


def test_missing_cfp_formula_is_global_error():
    report = validate_cosmic_items([_item()], project_name="测试项目", cfp_formula="")

    assert report.status == "blocked"
    assert [issue.code for issue in report.issues] == ["MISSING_CFP_FORMULA"]
    assert report.cfp_basis["source"] == "unconfirmed"
    assert report.cfp_basis["formula_configured"] is False


def test_generic_function_user_is_warning():
    result = validate_cosmic_item(_item(user="发起者：操作员|接收者：系统"))

    assert "GENERIC_FUNCTION_USER" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["function_user"]["match_source"] == "generic_only"
    assert result.basis["function_user"]["requires_review"] is True


def test_module_context_without_l3_user_requires_review():
    result = validate_cosmic_item(_item(user="发起者：系统管理|接收者：用户管理"))

    assert "GENERIC_FUNCTION_USER" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["function_user"]["matched"] is False
    assert result.basis["function_user"]["match_source"] == "module_context_only"
    assert result.basis["function_user"]["matched_term"] == "用户管理"
