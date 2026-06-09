from ai_gen_reimbursement_docs.fpa_facts import extract_fpa_process_facts


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
                "process_name": "删除垂直行业",
                "description": "删除指定垂直行业。",
                "type": "新增",
            },
        ],
    }


def _by_id(facts):
    return {fact["process_id"]: fact for fact in facts}


def test_extract_process_facts_uses_name_and_description_before_input_type():
    facts = _by_id(extract_fpa_process_facts(_group()))

    query = facts["m1_p1"]
    assert query["operation"] == "query"
    assert query["query_only"] is True
    assert query["changes_internal_data"] is False
    assert query["input_type"] == "新增"

    create = facts["m1_p2"]
    assert create["operation"] == "create"
    assert create["changes_internal_data"] is True

    delete = facts["m1_p3"]
    assert delete["operation"] == "delete"
    assert delete["changes_internal_data"] is True


def test_extract_process_facts_marks_import_operation_as_internal_change():
    facts = extract_fpa_process_facts({
        "l3": "客户名单导入",
        "processes": [{
            "process_id": "p1",
            "process_name": "导入客户名单",
            "description": "上传 Excel 文件，校验手机号并保存有效记录。",
            "type": "新增",
        }],
    })

    assert facts[0]["operation"] == "import"
    assert facts[0]["changes_internal_data"] is True


def test_extract_process_facts_marks_ordinary_external_service_without_eif_evidence():
    facts = extract_fpa_process_facts({
        "l3": "短信通知",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "发送测试短信",
            "description": "调用短信平台发送测试短信。",
            "type": "新增",
        }],
    })

    assert facts[0]["ordinary_external_service"] is True
    assert facts[0]["external_data_group_evidence"] == ""


def test_extract_process_facts_treats_payment_gateway_result_as_service_not_eif():
    facts = _by_id(extract_fpa_process_facts({
        "l3": "退款处理",
        "l3_desc": "系统调用支付网关发起退款并查询退款结果，支付网关为普通外部服务，不作为外部维护数据组计量。",
        "processes": [
            {
                "process_id": "m1_p1",
                "process_name": "发起退款",
                "description": "调用支付网关提交退款请求，并记录本系统退款申请状态。",
                "type": "新增",
            },
            {
                "process_id": "m1_p2",
                "process_name": "查看退款结果",
                "description": "查询支付网关返回的退款状态、失败原因和处理时间。",
                "type": "查询",
            },
        ],
    }))

    assert facts["m1_p1"]["ordinary_external_service"] is True
    assert facts["m1_p1"]["external_data_group_evidence"] == ""
    assert facts["m1_p2"]["ordinary_external_service"] is True
    assert facts["m1_p2"]["external_data_group_evidence"] == ""
    assert facts["m1_p2"]["operation"] == "query"
    assert facts["m1_p2"]["query_only"] is True


def test_extract_process_facts_keeps_external_data_group_evidence():
    facts = extract_fpa_process_facts({
        "l3": "用户中心账号引用",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "引用统一用户中心账号",
            "description": "读取统一用户中心维护的人员账号，本系统不维护账号主数据。",
            "type": "新增",
        }],
    })

    assert facts[0]["operation"] == "query"
    assert facts[0]["query_only"] is True
    assert facts[0]["target_data_group"] == "统一用户中心账号"
    assert "本系统不维护" in facts[0]["external_data_group_evidence"]
    assert facts[0]["changes_internal_data"] is False


def test_extract_process_facts_uses_module_description_for_external_data_evidence():
    facts = extract_fpa_process_facts({
        "l3": "归属组织选择",
        "l3_desc": "系统引用主数据平台维护的组织主数据，本系统不维护组织主数据。",
        "processes": [{
            "process_id": "m1_p1",
            "process_name": "选择归属组织",
            "description": "从主数据平台组织主数据中选择归属组织并保存到当前业务对象。",
            "type": "新增",
        }],
    })

    assert facts[0]["target_data_group"] == "组织主数据"
    assert "本系统不维护" in facts[0]["external_data_group_evidence"]
    assert facts[0]["changes_internal_data"] is True
