import logging
import json

import openpyxl
import pytest

from ai_gen_reimbursement_docs.gen_fpa import (
    _extract_json_obj,
    _group_rows_by_l3,
    _normalize_ai_fpa_rows_for_l3,
    _plan_fpa_rows_with_ai,
    generate_fpa_check_xlsx_from_md,
)
from ai_gen_reimbursement_docs.fpa_profiles import CUSTOM_RULES_PROFILE, STRICT_FPA_PROFILE


def _meta():
    return {"子系统（模块）": "测试系统", "资产标识": "TEST-001"}


def _rows():
    return [
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "维护垂直行业基础信息和管理员。",
            "功能过程": "添加垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "输入垂直行业名称并保存。",
        },
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "维护垂直行业基础信息和管理员。",
            "功能过程": "查询垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "按行业名称查询垂直行业列表。",
        },
    ]


def test_markdown_code_block_json_is_parsed():
    data = _extract_json_obj("""```json
{"rows":[{"name":"垂直行业管理界面开发"}]}
```""")
    assert data["rows"][0]["name"] == "垂直行业管理界面开发"


def test_normalize_ai_rows_maps_basis_and_types():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一", "规则二"],
        start_seq=1,
        ai_rows=[
            {
                "name": "垂直行业管理界面开发",
                "type": "EI",
                "type_reason": "页面交互能力",
                "classification_basis_index": 1,
                "explanation": "垂直行业管理界面开发，具体为以下：1、新增列表和查询条件。",
            },
            {
                "name": "添加垂直行业-逻辑处理开发",
                "type": "ILF",
                "classification_basis_index": 2,
                "explanation": "保存垂直行业基础信息。",
                "source_processes": ["添加垂直行业"],
            },
        ],
    )
    assert warnings == []
    assert [r["类型"] for r in rows] == ["EI", "ILF"]
    assert rows[0]["计算依据归类"] == "规则一"
    assert rows[1]["计算依据归类"] == "规则二"


def test_invalid_index_warns_and_leaves_basis_empty():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["规则一"],
        start_seq=1,
        ai_rows=[{
            "name": "查询垂直行业-查询处理开发",
            "type": "EQ",
            "classification_basis_index": 99,
            "explanation": "查询垂直行业列表。",
        }],
    )
    assert rows[0]["计算依据归类"] == ""
    assert any("越界" in w for w in warnings)
    rule_hits = rows[0]["_规则命中详情"]
    assert any(hit["rule_id"] == "postprocess.classification_basis_index" for hit in rule_hits)
    assert any("越界" in warning for hit in rule_hits for warning in hit["warnings"])


def test_multiple_ui_rows_without_split_reason_are_merged():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        ai_rows=[
            {"name": "垂直行业列表界面开发", "type": "EI", "explanation": "列表。"},
            {"name": "垂直行业查询界面开发", "type": "EI", "explanation": "查询。"},
            {"name": "添加垂直行业-逻辑处理开发", "type": "ILF", "explanation": "保存。"},
        ],
    )
    assert sum(1 for r in rows if "界面开发" in r["新增/修改功能点"]) == 1
    assert any("split_reason" in w for w in warnings)


def test_strict_profile_normalizes_ai_development_work_item_names():
    group = _group_rows_by_l3(_rows())[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[
            {
                "name": "添加垂直行业-逻辑处理开发",
                "type": "ILF",
                "explanation": "输入垂直行业名称并保存。",
            },
        ],
    )

    assert rows[0]["新增/修改功能点"] == "添加垂直行业"
    assert rows[0]["类型"] == "EI"
    assert any("已规范化" in w for w in warnings)


def test_strict_profile_corrects_external_service_eif_misclassification():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "消息管理",
            "二级模块": "通知发送",
            "三级模块": "短信通知",
            "三级模块整体功能描述": "系统调用短信平台发送通知短信。",
            "功能过程": "发送测试短信",
            "功能过程类型": "新增",
            "功能过程描述": "调用短信平台发送测试短信。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[
            {
                "name": "发送测试短信",
                "type": "EIF",
                "explanation": "调用短信平台发送测试短信。",
            },
        ],
    )

    assert rows[0]["类型"] == "EI"
    assert any("明显冲突" in w for w in warnings)


def test_ai_first_keeps_valid_ai_type_without_keyword_override():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "消息管理",
            "二级模块": "通知发送",
            "三级模块": "短信通知",
            "三级模块整体功能描述": "系统调用短信平台发送通知短信。",
            "功能过程": "发送测试短信",
            "功能过程类型": "新增",
            "功能过程描述": "调用短信平台发送测试短信。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "发送测试短信",
                "type": "EIF",
                "explanation": "调用短信平台发送测试短信。",
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert any("AI 优先策略下保留 AI type" in w for w in warnings)


def test_strict_profile_keeps_real_external_data_group_eif():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "权限管理",
            "二级模块": "账号权限",
            "三级模块": "用户中心账号引用",
            "三级模块整体功能描述": "系统引用统一用户中心维护的人员账号。",
            "功能过程": "同步账号",
            "功能过程类型": "新增",
            "功能过程描述": "统一用户中心维护的人员账号，本系统只引用。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=[],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        ai_rows=[
            {
                "name": "统一用户中心账号",
                "type": "EIF",
                "explanation": "统一用户中心维护的人员账号，本系统只引用。",
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert not any("明显冲突" in w for w in warnings)


def test_keyword_type_fallbacks():
    assert CUSTOM_RULES_PROFILE.infer_type("客户界面开发")[0] == "EI"
    assert CUSTOM_RULES_PROFILE.infer_type("添加客户-逻辑处理开发")[0] == "ILF"
    assert CUSTOM_RULES_PROFILE.infer_type("查询客户-查询处理开发")[0] == "EQ"
    assert CUSTOM_RULES_PROFILE.infer_type("导出客户-导出处理开发")[0] == "EO"
    assert CUSTOM_RULES_PROFILE.infer_type("导入客户-导入处理开发")[0] == "EI"
    assert CUSTOM_RULES_PROFILE.infer_type("同步外部接口数据-逻辑处理开发")[0] == "ILF"
    assert CUSTOM_RULES_PROFILE.infer_type("引用统一用户中心账号-外部接口处理开发")[0] == "EIF"


def test_ai_parse_failure_falls_back(monkeypatch, caplog):
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: "这里不是 JSON",
    )
    caplog.set_level(logging.WARNING)
    result = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        strategy="ai_first",
    )
    assert result[0]["生成方式"] == "fallback"
    assert any("FPA AI 响应解析失败" in r.message for r in caplog.records)


def test_ai_first_requires_api_key():
    with pytest.raises(ValueError, match="需要 API Key"):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="",
            model="test",
            base_url="",
            profile=STRICT_FPA_PROFILE,
            strategy="ai_first",
        )


def test_ai_cache_hit_skips_llm(monkeypatch, tmp_path, caplog):
    cache_path = tmp_path / "fpa_ai_cache.json"
    audit_trace_path = tmp_path / "fpa_audit_trace.json"
    response = {
        "rows": [
            {
                "name": "垂直行业管理界面开发",
                "type": "EI",
                "classification_basis_index": 1,
                "explanation": "垂直行业管理界面开发，具体为以下：1、新增列表和查询条件。",
            }
        ]
    }
    calls = {"count": 0}

    def first_call(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", first_call)
    first = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
        audit_trace_path=str(audit_trace_path),
    )
    assert calls["count"] == 1
    assert cache_path.exists()
    assert first[0]["生成方式"] == "ai"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = next(iter(cache["entries"].values()))
    assert entry["profile"] == "custom_rules"
    assert entry["profile_version"] == "1"
    assert entry["strategy"] == "ai_first"
    assert entry["rule_set"] == "custom_rules_default"
    assert entry["rule_set_version"] == "1"
    trace = json.loads(audit_trace_path.read_text(encoding="utf-8"))
    assert trace["modules"][0]["source"] == "ai"
    assert trace["modules"][0]["raw_rows"] == response["rows"]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM should not be called on cache hit")

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fail_if_called)
    caplog.set_level(logging.INFO)
    second = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
        audit_trace_path=str(audit_trace_path),
    )

    assert second[0]["新增/修改功能点"] == "垂直行业管理界面开发"
    trace = json.loads(audit_trace_path.read_text(encoding="utf-8"))
    assert trace["modules"][0]["source"] == "ai_cache"
    assert any("缓存命中" in r.message for r in caplog.records)


def test_fpa_check_xlsx_columns_can_be_configured(monkeypatch, tmp_path):
    (tmp_path / "system_config.yaml").write_text(
        """
fpa_check_columns:
  FPA结果: ["新增/修改功能点", "类型", "后处理警告"]
  Warnings: ["对象", "Warning", "来源规则ID"]
  规则命中详情: ["功能点名称", "规则ID", "是否采用"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)

    fpa_md = tmp_path / "fpa.md"
    fpa_md.write_text(
        """# FPA 工作量评估

**profile**: custom_rules
**strategy**: rules_first
**rule_set**: custom_rules_default
**rule_set_version**: 1

| 序号 | 子系统(模块) | 资产标识 | 新增/修改功能点 | 类型 | 计算依据归类 | 计算依据说明 | 变更状态 | 调整值 | 要素数量 | 生成方式 | 类型理由 | 源功能过程 | 后处理警告 |
|------|-------------|---------|----------------|------|-------------|-------------|---------|-------|---------|---------|---------|-----------|-----------|
| 1 | 测试系统 | TEST | 查询客户-查询处理开发 | EQ |  | 查询客户。 | 新增 | 2 | 1 | ai | AI 根据功能点名称和业务说明判定。 | 查询客户 | 查询客户 classification_basis_index 越界: 99 |
""",
        encoding="utf-8",
    )
    tree_md = tmp_path / "tree.md"
    tree_md.write_text(
        """| 入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述 |
|------|---------|---------|---------|----------|----------------------|----------|--------------|--------------|
| 后台 | 客户管理 | 客户查询 | 客户查询 | 地市后台 | 查询客户。 | 查询客户 | 查询 | 按条件查询客户。 |
""",
        encoding="utf-8",
    )
    audit_trace = tmp_path / "trace.json"
    audit_trace.write_text(
        json.dumps({
            "modules": [{
                "rule_hits": [{
                    "fpa_seq": 1,
                    "name": "查询客户-查询处理开发",
                    "generation": "ai",
                    "hit_object": "查询客户-查询处理开发",
                    "rule_id": "postprocess.classification_basis_index",
                    "rule_desc": "classification_basis_index 必须落在模板判定原则范围内。",
                    "suggested_type": "EQ",
                    "adopted": "是",
                    "warnings": ["查询客户 classification_basis_index 越界: 99"],
                }],
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    output = tmp_path / "check.xlsx"
    generate_fpa_check_xlsx_from_md(str(fpa_md), str(tree_md), str(output), str(audit_trace))

    wb = openpyxl.load_workbook(output, data_only=True)
    assert [cell.value for cell in wb["FPA结果"][1]] == ["新增/修改功能点", "类型", "后处理警告"]
    assert [cell.value for cell in wb["Warnings"][1]] == ["对象", "Warning", "来源规则ID"]
    assert [cell.value for cell in wb["规则命中详情"][1]] == ["功能点名称", "规则ID", "是否采用"]
    assert wb["Warnings"].cell(2, 3).value == "postprocess.classification_basis_index"
    wb.close()
