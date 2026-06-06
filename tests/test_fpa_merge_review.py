from ai_gen_reimbursement_docs.fpa_merge_review import build_fpa_merge_review


def _vertical_group():
    return {
        "client_type": "地市后台",
        "l1": "垂直行业营销",
        "l2": "垂直行业管理",
        "l3": "垂直行业管理",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "垂直行业列表数据查询",
                "description": "默认展示存量垂直行业列表。",
                "type": "新增",
            },
            {
                "process_id": "m1_p2",
                "process_name": "查询垂直行业数据",
                "description": "按行业名称查询垂直行业列表，支持分页。",
                "type": "新增",
            },
            {
                "process_id": "m1_p3",
                "process_name": "添加垂直行业",
                "description": "输入垂直行业名称并保存。",
                "type": "新增",
            },
            {
                "process_id": "m1_p4",
                "process_name": "编辑垂直行业",
                "description": "修改垂直行业名称并保存。",
                "type": "新增",
            },
            {
                "process_id": "m1_p5",
                "process_name": "删除垂直行业",
                "description": "删除指定垂直行业。",
                "type": "新增",
            },
            {
                "process_id": "m1_p6",
                "process_name": "新增垂直行业管理员",
                "description": "为垂直行业添加管理员账号。",
                "type": "新增",
            },
            {
                "process_id": "m1_p7",
                "process_name": "删除垂直行业管理员",
                "description": "移除垂直行业管理员账号。",
                "type": "新增",
            },
        ],
    }


def _groups_by_kind(review):
    result = {}
    for group in review["groups"]:
        result.setdefault(group["kind"], []).append(group)
    return result


def test_merge_review_recommends_query_and_maintenance_merges():
    review = build_fpa_merge_review(_vertical_group())
    by_kind = _groups_by_kind(review)

    query = by_kind["query_eq"][0]
    assert query["recommendation"] == "merge"
    assert query["process_ids"] == ["m1_p1", "m1_p2"]
    assert query["process_names"] == ["垂直行业列表数据查询", "查询垂直行业数据"]

    maintenance_groups = by_kind["maintenance_ei"]
    vertical = next(group for group in maintenance_groups if group["target_data_group"] == "垂直行业")
    admin = next(group for group in maintenance_groups if "管理员" in group["target_data_group"])
    assert vertical["process_ids"] == ["m1_p3", "m1_p4", "m1_p5"]
    assert admin["process_ids"] == ["m1_p6", "m1_p7"]


def test_merge_review_marks_ordinary_external_service_as_not_eif():
    review = build_fpa_merge_review({
        "l3": "短信通知",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "发送测试短信",
            "description": "调用短信平台发送测试短信。",
            "type": "新增",
        }],
    })

    group = review["groups"][0]
    assert group["kind"] == "ordinary_external_service"
    assert group["recommendation"] == "do_not_create_eif"
    assert group["process_ids"] == ["m1_p1"]
