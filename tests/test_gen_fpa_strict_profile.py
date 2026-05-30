from ai_gen_reimbursement_docs.fpa_profiles import STRICT_FPA_PROFILE
from ai_gen_reimbursement_docs.gen_fpa import _build_fpa_rule_rows


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
    return [row["新增/修改功能点"] for row in rows]


def _types_by_name(rows):
    return {row["新增/修改功能点"]: row["类型"] for row in rows}


def test_strict_fpa_vertical_industry_uses_data_and_transaction_functions():
    rows = [
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "查询垂直行业", "按行业名称查询垂直行业列表，支持分页。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "添加垂直行业", "输入垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "编辑垂直行业", "修改垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "删除垂直行业", "删除指定垂直行业。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "新增垂直行业管理员", "为垂直行业添加管理员账号。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "删除垂直行业管理员", "移除垂直行业管理员账号。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta(), profile=STRICT_FPA_PROFILE)
    names = _names(result)
    types = _types_by_name(result)

    assert "垂直行业信息" in names
    assert "垂直行业管理员关系" in names
    assert types["垂直行业信息"] == "ILF"
    assert types["垂直行业管理员关系"] == "ILF"
    assert types["查询垂直行业"] == "EQ"
    assert types["添加垂直行业"] == "EI"
    assert types["编辑垂直行业"] == "EI"
    assert types["删除垂直行业"] == "EI"
    assert types["新增垂直行业管理员"] == "EI"
    assert types["删除垂直行业管理员"] == "EI"
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
