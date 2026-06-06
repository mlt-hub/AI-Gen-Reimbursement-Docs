from ai_gen_reimbursement_docs.fpa_quality_review import build_fpa_quality_review


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
