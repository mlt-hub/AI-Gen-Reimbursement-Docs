from ai_gen_reimbursement_docs.fpa_validator import (
    retryable_validation_issues,
    validate_fpa_rows,
    validation_feedback,
)


def _group():
    return {
        "client_type": "地市后台",
        "l1": "垂直行业营销",
        "l2": "垂直行业管理",
        "l3": "垂直行业管理",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "查询垂直行业数据",
                "description": "按行业名称查询垂直行业列表，支持分页。",
                "type": "新增",
            },
            {
                "process_id": "m1_p2",
                "process_name": "添加垂直行业",
                "description": "输入垂直行业名称并保存。",
                "type": "新增",
            },
            {
                "process_id": "m1_p3",
                "process_name": "编辑垂直行业",
                "description": "修改垂直行业名称并保存。",
                "type": "新增",
            },
        ],
    }


def test_validator_flags_query_process_misclassified_as_ei():
    rows = [{
        "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-查询垂直行业数据",
        "类型": "EI",
        "计算依据说明": "来源场景：查询垂直行业数据。\n业务数据：垂直行业列表。\n业务规则：只读取并展示列表。\n计算说明：按查询展示。",
        "源功能过程": "查询垂直行业数据",
        "source_process_ids": ["m1_p1"],
    }]

    issues = validate_fpa_rows(group=_group(), rows=rows)

    assert any(issue.code == "validator.query_as_ei" for issue in issues)
    assert any(issue.code == "validator.query_as_ei" for issue in retryable_validation_issues(issues))
    assert "查询/列表/搜索/查看且不改变数据的流程不得判 EI" in validation_feedback(issues)


def test_validator_flags_ordinary_service_as_eif_without_external_data_evidence():
    group = {
        "client_type": "地市后台",
        "l1": "消息管理",
        "l2": "通知发送",
        "l3": "短信通知",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "发送测试短信",
            "description": "调用短信平台发送测试短信。",
            "type": "新增",
        }],
    }
    rows = [{
        "新增/修改功能点": "【地市后台】消息管理-通知发送-短信通知-短信平台",
        "类型": "EIF",
        "计算依据说明": "来源场景：发送测试短信。\n业务数据：短信内容。\n业务规则：调用短信平台发送。\n计算说明：误判为 EIF。",
        "源功能过程": "发送测试短信",
        "source_process_ids": ["m1_p1"],
    }]

    issues = validate_fpa_rows(group=group, rows=rows)

    assert any(issue.code == "validator.ordinary_service_as_eif" for issue in issues)


def test_validator_allows_eif_with_external_maintained_data_group_evidence():
    group = {
        "client_type": "地市后台",
        "l1": "权限管理",
        "l2": "账号权限",
        "l3": "用户中心账号引用",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "引用统一用户中心账号",
            "description": "读取统一用户中心维护的人员账号，本系统不维护账号主数据。",
            "type": "新增",
        }],
    }
    rows = [{
        "新增/修改功能点": "【地市后台】权限管理-账号权限-用户中心账号引用-统一用户中心账号",
        "类型": "EIF",
        "计算依据说明": "来源场景：引用统一用户中心账号。\n业务数据：统一用户中心维护的人员账号。\n业务规则：本系统不维护账号主数据。\n计算说明：外部系统维护数据组，按 EIF。",
        "源功能过程": "引用统一用户中心账号",
        "source_process_ids": ["m1_p1"],
    }]

    issues = validate_fpa_rows(group=group, rows=rows)

    assert not any(issue.code == "validator.ordinary_service_as_eif" for issue in issues)


def test_validator_flags_split_crud_ei_for_same_business_object():
    rows = [
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-添加垂直行业",
            "类型": "EI",
            "计算依据说明": "来源场景：添加垂直行业。\n业务数据：垂直行业。\n业务规则：新增。\n计算说明：EI。",
            "源功能过程": "添加垂直行业",
            "source_process_ids": ["m1_p2"],
        },
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-编辑垂直行业",
            "类型": "EI",
            "计算依据说明": "来源场景：编辑垂直行业。\n业务数据：垂直行业。\n业务规则：修改。\n计算说明：EI。",
            "源功能过程": "编辑垂直行业",
            "source_process_ids": ["m1_p3"],
        },
    ]

    issues = validate_fpa_rows(group=_group(), rows=rows)

    assert any(issue.code == "validator.split_crud_ei" for issue in issues)


def test_validator_allows_distinct_maintenance_objects_in_same_module():
    rows = [
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业维护",
            "类型": "EI",
            "计算依据说明": "来源场景：垂直行业维护。\n业务数据：垂直行业。\n业务规则：新增和修改。\n计算说明：EI。",
            "源功能过程": "添加垂直行业、编辑垂直行业",
            "source_process_ids": ["m1_p2", "m1_p3"],
        },
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业管理员维护",
            "类型": "EI",
            "计算依据说明": "来源场景：垂直行业管理员维护。\n业务数据：垂直行业管理员。\n业务规则：新增和删除管理员。\n计算说明：EI。",
            "源功能过程": "新增垂直行业管理员、删除垂直行业管理员",
            "source_process_ids": ["m1_p4", "m1_p5"],
        },
    ]

    issues = validate_fpa_rows(group=_group(), rows=rows)

    assert not any(issue.code == "validator.split_crud_ei" for issue in issues)
