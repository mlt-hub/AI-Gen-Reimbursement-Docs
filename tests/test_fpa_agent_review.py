from ai_gen_reimbursement_docs.fpa_agent_review import build_fpa_agent_review


def _group():
    return {
        "client_type": "地市后台",
        "l1": "垂直行业营销",
        "l2": "垂直行业管理",
        "l3": "垂直行业管理",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "添加垂直行业",
                "description": "输入垂直行业名称并保存。",
                "type": "新增",
            },
            {
                "process_id": "m1_p2",
                "process_name": "编辑垂直行业",
                "description": "修改垂直行业名称并保存。",
                "type": "新增",
            },
        ],
    }


def test_agent_review_exposes_role_contract_before_rows_exist():
    review = build_fpa_agent_review(group=_group())

    roles = {role["name"]: role for role in review["roles"]}
    assert set(roles) == {
        "business_fact_extractor",
        "fpa_type_judge",
        "merge_boundary_reviewer",
        "quality_reviewer",
    }
    assert roles["business_fact_extractor"]["status"] == "completed"
    assert roles["merge_boundary_reviewer"]["status"] == "completed"
    assert roles["quality_reviewer"]["status"] == "awaiting_rows"
    assert roles["fpa_type_judge"]["status"] == "completed"
    assert roles["fpa_type_judge"]["output_key"] == "type_judgement"
    assert review["summary"]["pending_agent_roles"] == []
    assert review["summary"]["type_judgement_count"] == 1
    assert review["type_judgement"]["judgements"][0]["suggested_type"] == "EI"
    assert review["merge_review"]["groups"][0]["recommendation"] == "merge"


def test_agent_review_runs_quality_role_after_rows_exist():
    rows = [
        {
            "新增/修改功能点": "添加垂直行业",
            "类型": "EI",
            "计算依据说明": "来源场景：添加垂直行业。\n业务数据：垂直行业。\n业务规则：新增。\n计算说明：EI。",
            "source_process_ids": ["m1_p1"],
        },
        {
            "新增/修改功能点": "编辑垂直行业",
            "类型": "EI",
            "计算依据说明": "来源场景：编辑垂直行业。\n业务数据：垂直行业。\n业务规则：修改。\n计算说明：EI。",
            "source_process_ids": ["m1_p2"],
        },
    ]

    review = build_fpa_agent_review(group=_group(), rows=rows)

    roles = {role["name"]: role for role in review["roles"]}
    assert roles["quality_reviewer"]["status"] == "completed"
    assert review["quality_review"]["summary"]["retryable_count"] >= 1
    assert review["summary"]["quality_issue_count"] >= 1


def test_multi_uis_quality_accepts_ui_row_name_without_development_suffix():
    rows = [
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业管理界面",
            "类型": "EI",
            "计算依据说明": "来源场景：垂直行业管理界面。\n业务数据：垂直行业。\n业务规则：展示并维护。\n计算说明：EI。",
            "源功能过程": "添加垂直行业、编辑垂直行业",
        },
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-添加垂直行业-逻辑处理开发",
            "类型": "EI",
            "计算依据说明": "来源场景：添加垂直行业。\n业务数据：垂直行业。\n业务规则：新增。\n计算说明：EI。",
            "源功能过程": "添加垂直行业",
        },
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-编辑垂直行业-逻辑处理开发",
            "类型": "EI",
            "计算依据说明": "来源场景：编辑垂直行业。\n业务数据：垂直行业。\n业务规则：修改。\n计算说明：EI。",
            "源功能过程": "编辑垂直行业",
        },
    ]

    review = build_fpa_agent_review(group=_group(), rows=rows, profile_name="multi_uis", profile_kind="unified_ui")

    codes = {issue["code"] for issue in review["unified_quality_review"]["issues"]}
    assert "unified_ui.missing_ui_row" not in codes


def test_ui_api_mapping_default_api_row_is_not_unexpected_explicit_backend_row():
    group = {
        "client_type": "地市后台",
        "l1": "组织管理",
        "l2": "归属组织",
        "l3": "归属组织选择",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "选择归属组织",
                "description": "从主数据平台组织主数据中选择归属组织并保存到当前业务对象。",
                "type": "新增",
            },
        ],
    }
    rows = [
        {
            "新增/修改功能点": "【地市后台】组织管理-归属组织-归属组织选择-选择归属组织-界面开发",
            "类型": "EI",
            "计算依据说明": "来源场景：选择归属组织。\n业务数据：组织。\n业务规则：选择。\n计算说明：EI。",
            "源功能过程": "选择归属组织",
        },
        {
            "新增/修改功能点": "【地市后台】组织管理-归属组织-归属组织选择-选择归属组织-接口开发",
            "类型": "ILF",
            "计算依据说明": "来源场景：选择归属组织。\n业务数据：组织。\n业务规则：保存。\n计算说明：ILF。",
            "源功能过程": "选择归属组织",
        },
    ]

    review = build_fpa_agent_review(group=group, rows=rows, profile_name="ui_api_mapping", profile_kind="ui_api_mapping")

    codes = {issue["code"] for issue in review["mapping_quality_review"]["issues"]}
    assert "ui_api_mapping.unexpected_explicit_backend_row" not in codes


def test_ui_api_mapping_still_flags_unexpected_backend_row():
    group = {
        "client_type": "地市后台",
        "l1": "组织管理",
        "l2": "归属组织",
        "l3": "归属组织选择",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "选择归属组织",
                "description": "从主数据平台组织主数据中选择归属组织并保存到当前业务对象。",
                "type": "新增",
            },
        ],
    }
    rows = [
        {
            "新增/修改功能点": "【地市后台】组织管理-归属组织-归属组织选择-选择归属组织-界面开发",
            "类型": "EI",
            "计算依据说明": "来源场景：选择归属组织。\n业务数据：组织。\n业务规则：选择。\n计算说明：EI。",
            "源功能过程": "选择归属组织",
        },
        {
            "新增/修改功能点": "【地市后台】组织管理-归属组织-归属组织选择-组织主数据服务",
            "类型": "ILF",
            "计算依据说明": "来源场景：选择归属组织。\n业务数据：组织。\n业务规则：调用组织主数据服务。\n计算说明：ILF。",
            "源功能过程": "选择归属组织",
        },
    ]

    review = build_fpa_agent_review(group=group, rows=rows, profile_name="ui_api_mapping", profile_kind="ui_api_mapping")

    issues = review["mapping_quality_review"]["issues"]
    assert any(issue["code"] == "ui_api_mapping.unexpected_explicit_backend_row" for issue in issues)
