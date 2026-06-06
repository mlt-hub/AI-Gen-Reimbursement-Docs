from ai_gen_reimbursement_docs.fpa_profiles import STRICT_FPA_PROFILE
from ai_gen_reimbursement_docs.gen_fpa import _build_fpa_rule_rows, _normalize_ai_fpa_rows_for_l3


def _meta():
    return {"子系统（模块）": "测试系统", "资产标识": "TEST-001"}


def _row(client_type, l1, l2, l3, l3_desc, proc, proc_desc, proc_type="新增"):
    return {
        "客户端类型": client_type,
        "一级模块": l1,
        "二级模块": l2,
        "三级模块": l3,
        "三级模块整体功能描述": l3_desc,
        "功能过程": proc,
        "功能过程类型": proc_type,
        "功能过程描述": proc_desc,
    }


def _names(rows):
    names = []
    for row in rows:
        name = row["新增/修改功能点"]
        names.append(name)
        short = _short_name(name)
        if short != name:
            names.append(short)
    return names


def _types_by_name(rows):
    result = {}
    for row in rows:
        name = row["新增/修改功能点"]
        result[name] = row["类型"]
        result[_short_name(name)] = row["类型"]
    return result


def _short_name(name):
    text = str(name)
    if not text.startswith("【"):
        return text
    parts = text.split("-", 3)
    return parts[3] if len(parts) == 4 else text


def test_strict_fpa_vertical_industry_uses_data_and_transaction_functions():
    rows = [
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "垂直行业列表数据查询", "默认展示存量垂直行业列表。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "查询垂直行业数据", "按行业名称查询垂直行业列表，支持分页。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "添加垂直行业", "输入垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "编辑垂直行业", "修改垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "删除垂直行业", "删除指定垂直行业。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "新增垂直行业管理员", "为垂直行业添加管理员账号。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "删除垂直行业管理员", "移除垂直行业管理员账号。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    names = _names(result)
    types = _types_by_name(result)

    assert all(
        str(row["新增/修改功能点"]).startswith("【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-")
        for row in result
    )
    assert "垂直行业信息" in names
    assert "垂直行业管理员关系" in names
    assert types["垂直行业信息"] == "ILF"
    assert types["垂直行业管理员关系"] == "ILF"
    assert types["垂直行业查询"] == "EQ"
    assert types["垂直行业维护"] == "EI"
    assert types["垂直行业管理员维护"] == "EI"
    assert "添加垂直行业" not in types
    assert "编辑垂直行业" not in types
    assert "删除垂直行业" not in types
    assert "新增垂直行业管理员" not in types
    assert "删除垂直行业管理员" not in types
    query_row = next(row for row in result if _short_name(row["新增/修改功能点"]) == "垂直行业查询")
    maintenance_row = next(row for row in result if _short_name(row["新增/修改功能点"]) == "垂直行业维护")
    admin_row = next(row for row in result if _short_name(row["新增/修改功能点"]) == "垂直行业管理员维护")
    assert query_row["源功能过程"] == "垂直行业列表数据查询、查询垂直行业数据"
    assert maintenance_row["源功能过程"] == "添加垂直行业、编辑垂直行业、删除垂直行业"
    assert admin_row["源功能过程"] == "新增垂直行业管理员、删除垂直行业管理员"
    assert not any("界面开发" in name or "接口开发" in name or "逻辑处理开发" in name for name in names)


def test_strict_fpa_import_export_and_external_data_group_types():
    rows = [
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "下载导入模板", "下载客户名单导入模板文件。"),
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "导入客户名单", "上传 Excel 文件，校验手机号、客户类型和归属地，保存有效记录。"),
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "查看导入结果", "查看成功数量、失败数量和失败原因。"),
    ]
    user_center_rows = [
        _row("地市后台", "权限管理", "账号权限", "用户中心账号引用", "系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "引用统一用户中心账号", "引用统一用户中心账号基础信息和所属组织。"),
        _row("地市后台", "权限管理", "账号权限", "用户中心账号引用", "系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "选择业务负责人", "从用户中心账号中选择负责人并保存到本系统业务对象。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    user_center = _build_fpa_rule_rows(user_center_rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)
    user_center_types = _types_by_name(user_center)

    assert types["客户名单导入"] == "ILF"
    assert types["下载导入模板"] == "EO"
    assert types["导入客户名单"] == "EI"
    assert types["查看导入结果"] == "EQ"
    assert user_center_types["统一用户中心账号"] == "EIF"
    assert user_center_types["选择业务负责人"] == "EI"


def test_strict_fpa_service_call_is_not_eif_without_external_data_group():
    rows = [
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "编辑短信模板", "维护短信标题、正文和变量。"),
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "发送测试短信", "调用短信平台发送测试短信。"),
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "查看发送记录", "查询短信发送状态和失败原因。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["短信通知信息"] == "ILF"
    assert types["发送测试短信"] != "EIF"
    assert types["查看发送记录"] == "EQ"


def test_strict_fpa_crm_customer_archive_reference_is_eif():
    rows = [
        _row("地市后台", "客户运营", "客户关系", "CRM客户档案引用", "系统引用 CRM 系统维护的客户档案，本系统不维护客户主数据。", "选择CRM客户", "从 CRM 客户档案中选择客户并保存到营销活动。"),
        _row("地市后台", "客户运营", "客户关系", "CRM客户档案引用", "系统引用 CRM 系统维护的客户档案，本系统不维护客户主数据。", "查看客户基础信息", "查看 CRM 客户档案中的客户名称、等级和归属地。", "查询"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["CRM客户档案"] == "EIF"
    assert types["选择CRM客户"] == "EI"
    assert types["查看客户基础信息"] == "EQ"


def test_strict_fpa_finance_document_reference_is_eif():
    rows = [
        _row("地市后台", "报账管理", "财务核算", "财务单据引用", "本模块引用财务核算系统维护的报账单据，本系统不维护单据主数据。", "选择报账单据", "从财务核算系统的报账单据中选择并关联到当前申请。"),
        _row("地市后台", "报账管理", "财务核算", "财务单据引用", "本模块引用财务核算系统维护的报账单据，本系统不维护单据主数据。", "查看单据详情", "查看财务核算系统返回的单据金额、状态和摘要。", "查询"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["财务核算单据"] == "EIF"
    assert types["选择报账单据"] == "EI"
    assert types["查看单据详情"] == "EQ"


def test_strict_fpa_erp_document_reference_uses_external_rule_table():
    rows = [
        _row("地市后台", "采购管理", "供应商协同", "ERP订单引用", "系统引用 ERP 系统维护的采购订单，本系统不维护订单主数据。", "关联ERP订单", "从 ERP 采购订单中选择并关联到当前报账申请。"),
        _row("地市后台", "采购管理", "供应商协同", "ERP订单引用", "系统引用 ERP 系统维护的采购订单，本系统不维护订单主数据。", "查看ERP订单信息", "查看 ERP 采购订单的供应商、金额和订单状态。", "查询"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["ERP业务单据"] == "EIF"
    assert types["关联ERP订单"] == "EI"
    assert types["查看ERP订单信息"] == "EQ"


def test_strict_fpa_detects_multiple_external_data_groups_from_separate_processes():
    rows = [
        _row(
            "地市后台",
            "协同管理",
            "业务关联",
            "跨系统业务关联",
            "维护跨系统业务关联关系。",
            "选择CRM客户",
            "从 CRM 系统维护的客户档案中选择客户并保存到本系统关联关系。",
        ),
        _row(
            "地市后台",
            "协同管理",
            "业务关联",
            "跨系统业务关联",
            "维护跨系统业务关联关系。",
            "关联ERP订单",
            "从 ERP 系统维护的采购订单中选择订单并保存到本系统关联关系。",
        ),
        _row(
            "地市后台",
            "协同管理",
            "业务关联",
            "跨系统业务关联",
            "维护跨系统业务关联关系。",
            "选择归属组织",
            "从主数据平台维护的组织主数据中选择组织并保存到本系统关联关系。",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["CRM客户档案"] == "EIF"
    assert types["ERP业务单据"] == "EIF"
    assert types["组织主数据"] == "EIF"
    assert types["选择CRM客户"] == "EI"
    assert types["关联ERP订单"] == "EI"
    assert types["选择归属组织"] == "EI"


def test_strict_fpa_keeps_internal_relation_data_with_external_references():
    rows = [
        _row(
            "地市后台",
            "营销活动",
            "活动配置",
            "客户订单关联",
            "系统引用 CRM 系统维护的客户档案和 ERP 系统维护的采购订单，本系统保存客户订单匹配关系、活动关联状态和生效时间。",
            "新增客户订单关联",
            "选择 CRM 客户档案和 ERP 采购订单，保存客户订单匹配关系。",
        ),
        _row(
            "地市后台",
            "营销活动",
            "活动配置",
            "客户订单关联",
            "系统引用 CRM 系统维护的客户档案和 ERP 系统维护的采购订单，本系统保存客户订单匹配关系、活动关联状态和生效时间。",
            "查看客户订单关联",
            "查看已保存的客户订单匹配关系及外部客户、订单摘要。",
            "查询",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["CRM客户档案"] == "EIF"
    assert types["ERP业务单据"] == "EIF"
    assert types["客户订单匹配关系"] == "ILF"
    assert types["新增客户订单关联"] == "EI"
    assert types["查看客户订单关联"] == "EQ"


def test_strict_fpa_uses_clear_description_when_process_name_is_vague_external_reference():
    rows = [
        _row(
            "地市后台",
            "风控管理",
            "风险校验",
            "风险校验",
            "配置业务风险校验能力。",
            "查看详情",
            "读取外部征信平台维护的企业信用记录，展示信用等级、风险标签和最近更新时间。",
            "查询",
        ),
        _row(
            "地市后台",
            "风控管理",
            "风险校验",
            "风险校验",
            "配置业务风险校验能力。",
            "选择对象",
            "从外部合同平台维护的合同档案中选择合同并关联到风险校验记录。",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["企业信用记录"] == "EIF"
    assert types["合同档案"] == "EIF"
    assert types["查看详情"] == "EQ"
    assert types["选择对象"] == "EI"
    assert "风险校验数据组" not in types


def test_strict_fpa_uses_clear_description_for_internal_relation_name():
    rows = [
        _row(
            "地市后台",
            "营销活动",
            "活动配置",
            "活动配置",
            "维护活动参与范围配置。",
            "保存设置",
            "本系统保存客户与活动的匹配关系、有效期和启停状态。",
        ),
        _row(
            "地市后台",
            "营销活动",
            "活动配置",
            "活动配置",
            "维护活动参与范围配置。",
            "查看详情",
            "查看已保存的客户活动匹配关系和当前生效状态。",
            "查询",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["客户活动匹配关系"] == "ILF"
    assert types["保存设置"] == "EI"
    assert types["查看详情"] == "EQ"


def test_strict_fpa_treats_external_reference_without_local_maintenance_as_eif():
    rows = [
        _row(
            "地市后台",
            "组织管理",
            "组织引用",
            "组织引用",
            "系统引用主数据平台维护的组织主数据，本系统不维护组织主数据。",
            "选择组织",
            "从主数据平台组织主数据中选择组织并关联到当前业务对象。",
        ),
        _row(
            "地市后台",
            "组织管理",
            "组织引用",
            "组织引用",
            "系统引用主数据平台维护的组织主数据，本系统不维护组织主数据。",
            "查看组织详情",
            "查看主数据平台组织主数据的组织名称、层级和状态。",
            "查询",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["组织主数据"] == "EIF"
    assert "组织本地档案" not in types
    assert types["选择组织"] == "EI"
    assert types["查看组织详情"] == "EQ"


def test_strict_fpa_treats_external_sync_then_local_maintenance_as_ilf():
    rows = [
        _row(
            "地市后台",
            "组织管理",
            "组织档案",
            "组织档案维护",
            "从主数据平台同步组织主数据后，本系统继续维护组织服务范围、启停状态和本地负责人。",
            "同步组织信息",
            "从主数据平台同步组织编码、组织名称和层级信息，写入本系统组织本地档案。",
        ),
        _row(
            "地市后台",
            "组织管理",
            "组织档案",
            "组织档案维护",
            "从主数据平台同步组织主数据后，本系统继续维护组织服务范围、启停状态和本地负责人。",
            "编辑组织扩展信息",
            "维护本系统组织本地档案中的服务范围、启停状态和本地负责人。",
        ),
        _row(
            "地市后台",
            "组织管理",
            "组织档案",
            "组织档案维护",
            "从主数据平台同步组织主数据后，本系统继续维护组织服务范围、启停状态和本地负责人。",
            "查看组织档案",
            "查看本系统保存的组织本地档案和同步来源信息。",
            "查询",
        ),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    types = _types_by_name(result)

    assert types["组织本地档案"] == "ILF"
    assert "组织主数据" not in types
    assert types["同步组织信息"] == "EI"
    assert types["编辑组织扩展信息"] == "EI"
    assert types["查看组织档案"] == "EQ"


def test_strict_fpa_keeps_valid_ai_ei_when_description_mentions_query_list():
    group = {
        "client_type": "地市后台",
        "l1": "垂直行业营销",
        "l2": "垂直行业管理",
        "l3": "垂直行业管理",
        "processes": [],
    }

    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        ai_rows=[
            {
                "name": "添加垂直行业",
                "type": "EI",
                "explanation": "保存垂直行业后刷新列表，并展示查询结果。",
                "source_processes": ["添加垂直行业"],
            }
        ],
        judgement_rules=[],
        profile=STRICT_FPA_PROFILE,
    )

    assert rows[0]["类型"] == "EI"
    assert not any("关键词规则明显冲突" in warning for warning in warnings)
