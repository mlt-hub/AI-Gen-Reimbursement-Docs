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


def test_golden_vertical_industry_management_fallback_shape():
    rows = [
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "查询垂直行业", "按行业名称查询垂直行业列表，支持分页。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "添加垂直行业", "输入垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "编辑垂直行业", "修改垂直行业名称并保存。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "删除垂直行业", "删除指定垂直行业。"),
        _row("地市后台", "垂直行业营销", "垂直行业管理", "垂直行业管理", "维护垂直行业基础信息、状态和管理员。", "新增垂直行业管理员", "为垂直行业添加管理员账号。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta())
    names = _names(result)
    types = _types_by_name(result)

    assert sum(1 for name in names if "界面开发" in name) == 1
    assert types["查询垂直行业-查询处理开发"] == "EQ"
    assert types["添加垂直行业-逻辑处理开发"] == "ILF"
    assert types["编辑垂直行业-逻辑处理开发"] == "ILF"
    assert types["删除垂直行业-逻辑处理开发"] == "ILF"
    assert types["新增垂直行业管理员-逻辑处理开发"] == "ILF"
    assert not any("按钮界面开发" in name or "弹窗界面开发" in name for name in names)


def test_golden_import_module_type_fallbacks():
    rows = [
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "下载导入模板", "下载客户名单导入模板文件。"),
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "导入客户名单", "上传 Excel 文件，校验手机号、客户类型和归属地，保存有效记录。"),
        _row("地市后台", "客户运营", "客户数据管理", "客户名单导入", "运营人员导入客户名单文件，系统校验数据格式并保存有效客户名单。", "查看导入结果", "查看成功数量、失败数量和失败原因。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta())
    types = _types_by_name(result)

    assert types["下载导入模板-导出处理开发"] == "EO"
    assert types["导入客户名单-导入处理开发"] == "EI"
    assert types["查看导入结果-查询处理开发"] == "EQ"
    assert not any("校验手机号" in row["新增/修改功能点"] for row in result)


def test_golden_external_user_center_allows_eif_without_forcing_service_calls():
    user_center_rows = [
        _row("地市后台", "权限管理", "账号权限", "用户中心账号引用", "系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "引用统一用户中心账号", "引用统一用户中心账号基础信息和所属组织。"),
        _row("地市后台", "权限管理", "账号权限", "用户中心账号引用", "系统引用统一用户中心维护的人员账号，本系统不维护账号主数据。", "选择业务负责人", "从用户中心账号中选择负责人并保存到本系统业务对象。"),
    ]
    sms_rows = [
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "编辑短信模板", "维护短信标题、正文和变量。"),
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "发送测试短信", "调用短信平台发送测试短信。"),
        _row("地市后台", "消息管理", "通知发送", "短信通知", "运营人员配置短信内容并触发短信发送，系统调用短信平台完成发送。", "查看发送记录", "查询短信发送状态和失败原因。"),
    ]

    user_center = _build_fpa_rule_rows(user_center_rows, _meta())
    sms = _build_fpa_rule_rows(sms_rows, _meta())
    user_center_types = _types_by_name(user_center)
    sms_types = _types_by_name(sms)

    assert user_center_types["引用统一用户中心账号-逻辑处理开发"] == "EIF"
    assert user_center_types["选择业务负责人-逻辑处理开发"] == "ILF"
    assert sms_types["编辑短信模板-逻辑处理开发"] == "ILF"
    assert sms_types["发送测试短信-逻辑处理开发"] != "EIF"
    assert sms_types["查看发送记录-查询处理开发"] == "EQ"


def test_golden_complex_multi_page_fallback_stays_conservative():
    rows = [
        _row("地市后台", "审批管理", "客户审批", "客户准入审批", "包含客户准入申请列表、详情页和审批页，审批页有独立入口和状态流转。", "查询申请列表", "按客户名称、申请状态查询准入申请。"),
        _row("地市后台", "审批管理", "客户审批", "客户准入审批", "包含客户准入申请列表、详情页和审批页，审批页有独立入口和状态流转。", "查看申请详情", "进入详情页查看客户资料、附件和历史记录。"),
        _row("地市后台", "审批管理", "客户审批", "客户准入审批", "包含客户准入申请列表、详情页和审批页，审批页有独立入口和状态流转。", "审批客户准入", "进入审批页填写审批意见并通过或驳回。"),
        _row("地市后台", "审批管理", "客户审批", "客户准入审批", "包含客户准入申请列表、详情页和审批页，审批页有独立入口和状态流转。", "导出申请列表", "导出当前筛选条件下的申请列表。"),
    ]

    result = _build_fpa_rule_rows(rows, _meta())
    names = _names(result)
    types = _types_by_name(result)

    assert sum(1 for name in names if "界面开发" in name) == 1
    assert types["查询申请列表-查询处理开发"] == "EQ"
    assert types["查看申请详情-查询处理开发"] == "EQ"
    assert types["审批客户准入-逻辑处理开发"] == "ILF"
    assert types["导出申请列表-导出处理开发"] == "EO"
