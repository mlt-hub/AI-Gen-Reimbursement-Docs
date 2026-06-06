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
    assert roles["fpa_type_judge"]["status"] == "pending_agent"
    assert review["summary"]["pending_agent_roles"] == ["fpa_type_judge"]
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
