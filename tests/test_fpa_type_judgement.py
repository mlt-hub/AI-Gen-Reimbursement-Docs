from ai_gen_reimbursement_docs.fpa_type_judgement import build_fpa_type_judgement


def _judgements_by_kind(review):
    result = {}
    for judgement in review["judgements"]:
        result.setdefault(judgement["judgement_kind"], []).append(judgement)
    return result


def test_type_judgement_suggests_merged_ei_and_eq():
    review = build_fpa_type_judgement({
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
                "description": "按行业名称查询垂直行业列表。",
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
        ],
    })

    by_kind = _judgements_by_kind(review)
    assert by_kind["query_eq"][0]["suggested_type"] == "EQ"
    assert by_kind["query_eq"][0]["source_process_ids"] == ["m1_p1", "m1_p2"]
    assert by_kind["maintenance_ei"][0]["suggested_type"] == "EI"
    assert by_kind["maintenance_ei"][0]["source_process_ids"] == ["m1_p3", "m1_p4"]


def test_type_judgement_distinguishes_services_external_data_and_output():
    review = build_fpa_type_judgement({
        "l3": "综合处理",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "发送测试短信",
                "description": "调用短信平台发送测试短信。",
                "type": "新增",
            },
            {
                "process_id": "m1_p2",
                "process_name": "引用组织主数据",
                "description": "读取主数据平台维护的组织主数据，本系统不维护组织主数据。",
                "type": "查询",
            },
            {
                "process_id": "m1_p3",
                "process_name": "导出客户报表",
                "description": "按筛选条件导出客户统计报表。",
                "type": "查询",
            },
        ],
    })

    by_kind = _judgements_by_kind(review)
    assert by_kind["ordinary_external_service"][0]["suggested_type"] == "NONE"
    assert by_kind["ordinary_external_service"][0]["applies_to_final_rows"] is False
    assert by_kind["external_data_function"][0]["suggested_type"] == "EIF"
    assert by_kind["output_eo"][0]["suggested_type"] == "EO"
