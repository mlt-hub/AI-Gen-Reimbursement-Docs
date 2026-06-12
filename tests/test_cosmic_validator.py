"""COSMIC deterministic validation tests."""

import json
from pathlib import Path

from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.cosmic_validator import (
    global_cosmic_issue,
    validate_cosmic_item,
    validate_cosmic_items,
    write_cosmic_validation_json,
    write_cosmic_validation_report_md,
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


def _item_from_fixture(raw):
    return CosmicItem(
        project=raw["project"],
        module_l1=raw["module_l1"],
        module_l2=raw["module_l2"],
        module_l3=raw["module_l3"],
        user=raw["user"],
        trigger=raw["trigger"],
        process=raw["process"],
        movements=[
            DataMovement(
                order=movement["order"],
                sub_process=movement["sub_process"],
                move_type=movement["move_type"],
                data_group=movement["data_group"],
                data_attrs=movement["data_attrs"],
                reuse=movement.get("reuse", "新增"),
            )
            for movement in raw.get("movements", [])
        ],
    )


def _codes(result):
    return [issue.code for issue in result.issues]


def test_passed_item_has_no_issues():
    result = validate_cosmic_item(_item())

    assert result.status == "passed"
    assert result.issues == []
    assert result.basis["function_user"]["matched"] is True
    assert result.basis["function_user"]["match_source"] == "module_l3"


def test_cosmic_regression_fixtures_cover_core_governance_paths():
    fixture_path = Path(__file__).parent / "fixtures" / "cosmic_regression_cases.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert {case["name"] for case in cases} == {
        "passed_all_clear",
        "warning_only_draft_review",
        "blocked_missing_formal_trigger",
        "ai_empty_result",
        "missing_cfp_formula",
        "generic_function_user",
        "control_command_movement",
        "internal_technical_boundary",
        "complex_non_functional_scope",
    }

    for case in cases:
        report = validate_cosmic_items(
            [_item_from_fixture(item) for item in case["items"]],
            project_name="样例项目",
            cfp_formula=case.get("cfp_formula", ""),
        )
        assert report.status == case["expected_status"], case["name"]
        assert report.issue_codes == case["expected_issue_codes"], case["name"]


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
    issue = next(issue for issue in result.issues if issue.code == "CONTROL_COMMAND_MOVEMENT")
    assert issue.details["governance_category"] == "control_command"
    assert [action["action"] for action in issue.details["suggested_actions"]] == [
        "exclude_movement",
        "merge_movement",
    ]


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


def test_error_confirmation_message_requires_review():
    message = _movement(2, "X", data_group="错误提示", data_attrs="确认消息")
    message.sub_process = "输出保存失败错误提示和确认消息"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="保存请求", data_attrs="业务数据"),
            message,
        ])
    )

    assert "ERROR_CONFIRMATION_MESSAGE" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["movement_semantics"][0]["code"] == "ERROR_CONFIRMATION_MESSAGE"
    issue = next(issue for issue in result.issues if issue.code == "ERROR_CONFIRMATION_MESSAGE")
    assert "错误提示" in issue.details["matched_terms"]
    assert issue.details["scope_policy"] == "manual_merge_or_exclude"
    assert [action["action"] for action in issue.details["suggested_actions"]] == [
        "exclude_movement",
        "merge_movement",
    ]


def test_internal_technical_boundary_requires_review():
    internal = _movement(2, "X", data_group="接口响应", data_attrs="状态码")
    internal.sub_process = "后端调用内部接口并返回微服务响应"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="查询请求", data_attrs="业务编号"),
            internal,
        ])
    )

    assert "INTERNAL_TECHNICAL_BOUNDARY" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["movement_semantics"][0]["code"] == "INTERNAL_TECHNICAL_BOUNDARY"


def test_external_interface_boundary_requires_context_review():
    external = _movement(2, "X", data_group="外部系统响应", data_attrs="回执状态")
    external.sub_process = "调用第三方平台外部接口返回回执"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="业务请求", data_attrs="业务编号"),
            external,
        ])
    )

    assert "EXTERNAL_INTERFACE_BOUNDARY_REVIEW" in _codes(result)
    issue = next(issue for issue in result.issues if issue.code == "EXTERNAL_INTERFACE_BOUNDARY_REVIEW")
    assert issue.details["governance_category"] == "external_interface_boundary"
    assert "接口清单" in issue.details["review_required_reason"]
    assert [action["action"] for action in issue.details["suggested_actions"]] == [
        "exclude_movement",
        "merge_movement",
    ]


def test_boundary_context_extends_governance_rule_terms():
    movement = _movement(2, "X", data_group="统一支付回执", data_attrs="支付状态")
    movement.sub_process = "调用统一支付平台返回支付回执"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="支付请求", data_attrs="订单号"),
            movement,
        ]),
        governance_config={
            "boundary_context": {
                "external_systems": ["统一支付平台"],
            },
        },
    )

    issue = next(issue for issue in result.issues if issue.code == "EXTERNAL_INTERFACE_BOUNDARY_REVIEW")
    assert "统一支付平台" in issue.details["matched_terms"]
    assert issue.details["context_source"] == "gen_cosmic.governance.boundary_context.external_systems"


def test_configured_rule_matrix_adds_custom_movement_rule():
    movement = _movement(2, "X", data_group="专线响应", data_attrs="状态")
    movement.sub_process = "通过外部专线返回处理结果"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="处理请求", data_attrs="业务编号"),
            movement,
        ]),
        governance_config={
            "rule_matrix": [{
                "code": "CUSTOM_EXTERNAL_LINK",
                "target": "movement",
                "severity": "warning",
                "message": "外部专线边界需确认",
                "scope_policy": "manual_exclude_or_merge",
                "governance_category": "external_link_boundary",
                "description": "子过程命中外部专线",
                "terms": ["外部专线"],
                "suggested_actions": [{"action": "exclude_movement", "label": "排除计数"}],
            }],
        },
    )

    issue = next(issue for issue in result.issues if issue.code == "CUSTOM_EXTERNAL_LINK")
    assert issue.message == "外部专线边界需确认"
    assert issue.details["governance_category"] == "external_link_boundary"
    assert issue.details["suggested_actions"][0]["movement_order"] == 2


def test_configured_rule_matrix_overrides_default_terms():
    control = _movement(2, "X", data_group="页面状态", data_attrs="排序状态")
    control.sub_process = "点击下一页并排序列表"
    result = validate_cosmic_item(
        _item(movements=[
            _movement(1, "E", data_group="查询参数", data_attrs="页码"),
            control,
        ]),
        governance_config={
            "rule_matrix": [{
                "code": "CONTROL_COMMAND_MOVEMENT",
                "target": "movement",
                "terms": ["不会命中"],
            }],
        },
    )

    assert "CONTROL_COMMAND_MOVEMENT" not in _codes(result)


def test_non_functional_scope_requires_review():
    result = validate_cosmic_item(_item(
        module_l3="服务器扩容",
        process="完成系统迁移和架构改造",
        user="发起者：服务器扩容|接收者：系统管理",
    ))

    assert "NON_FUNCTIONAL_SCOPE" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["process_semantics"][0]["code"] == "NON_FUNCTIONAL_SCOPE"
    assert "系统迁移" in result.basis["process_semantics"][0]["matched_terms"]
    issue = next(issue for issue in result.issues if issue.code == "NON_FUNCTIONAL_SCOPE")
    assert issue.details["governance_category"] == "non_functional_scope"
    assert issue.details["suggested_actions"][0]["action"] == "exclude_process"


def test_complex_non_functional_scope_requires_review():
    result = validate_cosmic_item(_item(
        module_l3="国产化适配",
        process="完成中间件升级和上线切换",
        user="发起者：国产化适配|接收者：国产化适配",
    ))

    assert "COMPLEX_NON_FUNCTIONAL_SCOPE" in _codes(result)
    issue = next(issue for issue in result.issues if issue.code == "COMPLEX_NON_FUNCTIONAL_SCOPE")
    assert issue.details["governance_category"] == "complex_non_functional_scope"
    assert issue.details["suggested_actions"][0]["action"] == "exclude_process"


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
    assert report.issue_codes == {
        "EMPTY_DATA_ATTRS": 1,
        "MISSING_TRIGGER": 1,
    }


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
    assert payload["issue_codes"] == {}
    assert payload["cfp_basis"]["source"] == "template_formula"
    assert payload["cfp_basis"]["formula_configured"] is True
    assert payload["export_policy"]["manual_confirmation_required"] is False
    assert payload["export_policy"]["unconfirmed_review_item_count"] == 0
    assert payload["export_policy"]["formal_excel"]["status"] == "allowed"
    assert payload["export_policy"]["draft_excel"]["status"] == "not_needed"
    assert payload["preview_rows"] == [
        {
            "item_index": 0,
            "module_path": "系统管理 > 用户管理 > 用户注册",
            "module_l1": "系统管理",
            "module_l2": "用户管理",
            "module_l3": "用户注册",
            "process": "注册用户",
            "user": "发起者：用户注册|接收者：系统管理",
            "trigger": "用户触发",
            "movement_count": 2,
            "movement_types": ["E", "X"],
            "status": "passed",
            "issue_count": 0,
            "review_item_ids": [],
        }
    ]
    assert payload["items"][0]["basis"]["function_user"]["matched_term"] == "用户注册"


def test_report_json_includes_issue_details(tmp_path):
    message = _movement(2, "X", data_group="错误提示", data_attrs="确认消息")
    message.sub_process = "输出保存失败错误提示和确认消息"
    report = validate_cosmic_items(
        [_item(movements=[
            _movement(1, "E", data_group="保存请求", data_attrs="业务数据"),
            message,
        ])],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
    )
    output = tmp_path / "cosmic.json"

    write_cosmic_validation_json(report, str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    issue = payload["items"][0]["issues"][0]
    assert issue["code"] == "ERROR_CONFIRMATION_MESSAGE"
    assert "错误提示" in issue["details"]["matched_terms"]


def test_report_json_includes_flat_review_items(tmp_path):
    report = validate_cosmic_items(
        [_item(user="发起者：操作员|接收者：系统")],
        project_name="测试项目",
        cfp_formula="",
    )
    output = tmp_path / "cosmic.json"

    write_cosmic_validation_json(report, str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    review_items = payload["review_items"]
    assert [item["code"] for item in review_items] == [
        "MISSING_CFP_FORMULA",
        "GENERIC_FUNCTION_USER",
    ]
    assert review_items[0]["scope"] == "global"
    assert review_items[0]["item_index"] is None
    assert review_items[0]["review_id"] == "global::global::MISSING_CFP_FORMULA::cfp_formula::"
    assert review_items[1]["scope"] == "item"
    assert review_items[1]["item_index"] == 0
    assert review_items[1]["review_id"] == "item::0::GENERIC_FUNCTION_USER::user::"
    assert review_items[1]["details"]["match_source"] == "generic_only"
    assert review_items[1]["confirmation"] == {
        "status": "unconfirmed",
        "decision": "",
        "note": "",
        "confirmed_by": "",
        "confirmed_at": "",
    }
    assert payload["export_policy"]["manual_confirmation_required"] is True
    assert payload["export_policy"]["unconfirmed_review_item_count"] == 2
    assert payload["export_policy"]["formal_excel"]["status"] == "blocked"
    assert payload["export_policy"]["draft_excel"]["status"] == "blocked"
    assert payload["preview_rows"][0]["status"] == "review_required"
    assert payload["preview_rows"][0]["issue_count"] == 1
    assert payload["preview_rows"][0]["review_item_ids"] == [
        "item::0::GENERIC_FUNCTION_USER::user::"
    ]


def test_review_required_export_policy_allows_configured_draft(tmp_path):
    report = validate_cosmic_items(
        [_item(movements=[_movement(1, "E", data_attrs=""), _movement(2, "X")])],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
    )
    output = tmp_path / "cosmic.json"

    write_cosmic_validation_json(report, str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "review_required"
    assert payload["export_policy"]["manual_confirmation_required"] is True
    assert payload["export_policy"]["formal_excel"]["status"] == "blocked"
    assert "人工确认" in payload["export_policy"]["formal_excel"]["reason"]
    assert payload["export_policy"]["draft_excel"] == {
        "status": "eligible",
        "reason": "存在待审问题，可在配置开启后写草稿 Excel",
        "requires_config": True,
        "config_key": "gen_cosmic.allow_draft_excel_output",
    }


def test_review_id_escapes_separator_characters(tmp_path):
    report = validate_cosmic_items(
        [_item()],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
        global_issues=[
            global_cosmic_issue(
                "warning",
                "CUSTOM_WARNING",
                "自定义警告",
                "field:with\\separator",
            )
        ],
    )
    output = tmp_path / "cosmic.json"

    write_cosmic_validation_json(report, str(output))

    payload = json.loads(output.read_text(encoding="utf-8"))
    review_item = payload["review_items"][0]
    assert review_item["review_id"] == "global::global::CUSTOM_WARNING::field\\:with\\\\separator::"


def test_report_md_includes_issue_details(tmp_path):
    message = _movement(2, "X", data_group="错误提示", data_attrs="确认消息")
    message.sub_process = "输出保存失败错误提示和确认消息"
    report = validate_cosmic_items(
        [_item(movements=[
            _movement(1, "E", data_group="保存请求", data_attrs="业务数据"),
            message,
        ])],
        project_name="测试项目",
        cfp_formula="IF(L{row}=\"新增\",1,0)",
    )
    output = tmp_path / "cosmic.md"

    write_cosmic_validation_report_md(
        report,
        str(output),
        formal_excel_written=False,
        draft_excel_written=True,
        excel_reason="待审",
    )

    content = output.read_text(encoding="utf-8")
    assert "- issue code：ERROR_CONFIRMATION_MESSAGE=1" in content
    assert "| 级别 | code | 字段 | 数据移动序号 | 说明 | 依据 |" in content
    assert "命中：" in content
    assert "确认消息" in content
    assert "错误提示" in content


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
    issue = next(issue for issue in result.issues if issue.code == "GENERIC_FUNCTION_USER")
    assert issue.details["function_user_parts"] == ["操作员", "系统"]
    assert issue.details["match_source"] == "generic_only"


def test_module_context_without_l3_user_requires_review():
    result = validate_cosmic_item(_item(user="发起者：系统管理|接收者：用户管理"))

    assert "GENERIC_FUNCTION_USER" in _codes(result)
    assert result.status == "review_required"
    assert result.basis["function_user"]["matched"] is False
    assert result.basis["function_user"]["match_source"] == "module_context_only"
    assert result.basis["function_user"]["matched_term"] == "用户管理"


def test_unique_function_user_governance_flags_conflicting_roles():
    result = validate_cosmic_item(
        _item(
            module_l3="客户资料",
            user="发起者：客户资料|接收者：订单管理",
        ),
        governance_config={"require_unique_function_user": True},
    )

    assert "FUNCTION_USER_ROLE_CONFLICT" in _codes(result)
    assert result.status == "review_required"
    issue = next(issue for issue in result.issues if issue.code == "FUNCTION_USER_ROLE_CONFLICT")
    assert issue.details["matched_part"] == "客户资料"
    assert issue.details["function_user_parts"] == ["客户资料", "订单管理"]
    assert issue.details["approval_required"] is True
    assert issue.details["suggested_actions"][0]["action"] == "apply_function_user"
    assert issue.details["suggested_actions"][0]["suggested_user"] == "发起者：客户资料|接收者：客户资料"
