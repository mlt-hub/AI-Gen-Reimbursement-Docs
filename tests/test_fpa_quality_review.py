from ai_gen_reimbursement_docs.fpa_quality_review import (
    build_fpa_quality_review,
    quality_feedback,
    retryable_quality_issues,
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
            {
                "process_id": "m1_p3",
                "process_name": "查询垂直行业",
                "description": "按行业名称查询垂直行业列表。",
                "type": "新增",
            },
        ],
    }


def _issue_codes(review):
    return {issue["code"] for issue in review["issues"]}


def test_quality_review_flags_rows_that_ignore_merge_review():
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

    review = build_fpa_quality_review(group=_group(), rows=rows)

    assert "quality.merge_review_not_applied" in _issue_codes(review)
    assert review["summary"]["retryable_count"] >= 1


def test_quality_review_accepts_rows_that_apply_merge_review():
    rows = [{
        "新增/修改功能点": "垂直行业维护",
        "类型": "EI",
        "计算依据说明": "来源场景：垂直行业维护。\n业务数据：垂直行业。\n业务规则：新增和修改。\n计算说明：EI。",
        "source_process_ids": ["m1_p1", "m1_p2"],
    }]

    review = build_fpa_quality_review(group=_group(), rows=rows)

    assert "quality.merge_review_not_applied" not in _issue_codes(review)
    assert review["summary"]["issue_count"] == 0


def test_quality_review_includes_validator_issues():
    rows = [{
        "新增/修改功能点": "查询垂直行业",
        "类型": "EI",
        "计算依据说明": "来源场景：查询垂直行业。\n业务数据：垂直行业列表。\n业务规则：只读取并展示列表。\n计算说明：误判为 EI。",
        "source_process_ids": ["m1_p3"],
    }]

    review = build_fpa_quality_review(group=_group(), rows=rows)

    assert "validator.query_as_ei" in _issue_codes(review)
    assert review["summary"]["retryable_count"] >= 1


def test_quality_review_flags_type_judgement_mismatch():
    rows = [{
        "新增/修改功能点": "查询垂直行业",
        "类型": "EI",
        "计算依据说明": "来源场景：查询垂直行业。\n业务数据：垂直行业列表。\n业务规则：只读取并展示列表。\n计算说明：误判为 EI。",
        "source_process_ids": ["m1_p3"],
    }]

    review = build_fpa_quality_review(group=_group(), rows=rows)

    assert "quality.type_judgement_mismatch" in _issue_codes(review)
    assert retryable_quality_issues(review)
    assert "type_judgement" in quality_feedback(review)


def test_quality_review_requires_external_data_function_row_without_rejecting_transaction():
    group = {
        "client_type": "地市后台",
        "l1": "权限管理",
        "l2": "账号权限",
        "l3": "用户中心账号引用",
        "l3_desc": "系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "选择业务负责人",
                "description": "从用户中心账号中选择负责人并保存到本系统业务对象。",
                "type": "新增",
            },
        ],
    }
    rows = [{
        "新增/修改功能点": "选择业务负责人",
        "类型": "EI",
        "计算依据说明": "来源场景：选择业务负责人。\n业务数据：业务负责人。\n业务规则：保存到业务对象。\n计算说明：EI。",
        "source_process_ids": ["m1_p1"],
    }]

    missing_review = build_fpa_quality_review(group=group, rows=rows)

    assert "quality.external_data_function_missing" in _issue_codes(missing_review)
    assert retryable_quality_issues(missing_review)

    rows.insert(0, {
        "新增/修改功能点": "人员账号数据组",
        "类型": "EIF",
        "计算依据说明": "来源场景：人员账号数据组。\n业务数据：人员账号。\n业务规则：统一用户中心维护。\n计算说明：EIF。",
        "source_process_ids": ["m1_p1"],
    })

    accepted_review = build_fpa_quality_review(group=group, rows=rows)

    assert "quality.external_data_function_missing" not in _issue_codes(accepted_review)
    assert "quality.type_judgement_mismatch" not in _issue_codes(accepted_review)


def test_quality_review_matches_rules_rows_by_source_process_name():
    group = {
        "client_type": "地市后台",
        "l1": "组织管理",
        "l2": "归属组织",
        "l3": "归属组织选择",
        "l3_desc": "系统引用主数据平台维护的组织主数据，本系统不维护组织主数据。",
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
            "新增/修改功能点": "组织主数据",
            "类型": "EIF",
            "计算依据说明": "来源场景：组织主数据。\n业务数据：组织主数据。\n业务规则：主数据平台维护，本系统引用。\n计算说明：EIF。",
            "源功能过程": "选择归属组织",
        },
        {
            "新增/修改功能点": "选择归属组织",
            "类型": "EI",
            "计算依据说明": "来源场景：选择归属组织。\n业务数据：归属组织。\n业务规则：保存到当前业务对象。\n计算说明：EI。",
            "源功能过程": "选择归属组织",
        },
    ]

    review = build_fpa_quality_review(group=group, rows=rows)

    assert review["summary"]["issue_count"] == 0
