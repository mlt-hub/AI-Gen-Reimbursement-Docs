import logging
import json

import openpyxl
import pytest

from ai_gen_reimbursement_docs.config_utils import FpaConfigError, FpaPromptConfigError
from ai_gen_reimbursement_docs.gen_fpa import (
    _extract_json_obj,
    _group_rows_for_audit,
    _group_rows_by_l3,
    _normalize_ai_fpa_rows_for_l3,
    _plan_fpa_rows_with_execution,
    _plan_fpa_rows_with_ai,
    _rules_first_ai_reasons,
    generate_fpa_check_xlsx_from_md,
    preview_fpa_module,
)
from ai_gen_reimbursement_docs.fpa_profiles import CUSTOM_RULES_PROFILE, STRICT_FPA_PROFILE, CustomRulesProfile


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


def _write_fpa_prompt_config(tmp_path, monkeypatch):
    (tmp_path / "fpa_config.yaml").write_text(
        """
profile: custom_rules
profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    system_prompt: custom_rules
    user_prompt: custom_rules
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    system_prompt: strict_fpa
    user_prompt: strict_fpa
prompt_sets:
  custom_rules:
    system: 系统提示词
    user: |-
      ${core_rules}
      模块输入 JSON：
      ${payload_json}
      判定原则：
      ${judgement_rules}
  strict_fpa:
    system: 严格系统提示词
    user: |-
      ${core_rules}
      模块输入 JSON：
      ${payload_json}
      判定原则：
      ${judgement_rules}
rule_sets:
  custom_rules_default: {}
  strict_fpa_default: {}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)


def test_fpa_audit_grouping_prefers_source_process_over_l3_substring():
    tree_rows = [
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "垂直行业管理",
            "三级模块整体功能描述": "",
            "功能过程": "添加垂直行业",
            "功能过程类型": "新增",
            "功能过程描述": "",
        },
        {
            "客户端类型": "地市后台",
            "一级模块": "垂直行业营销",
            "二级模块": "垂直行业管理",
            "三级模块": "合伙商管理",
            "三级模块整体功能描述": "",
            "功能过程": "搜索合作商",
            "功能过程类型": "查询",
            "功能过程描述": "",
        },
    ]
    groups = _group_rows_by_l3(tree_rows)
    fpa_rows = [
        {
            "新增/修改功能点": "【地市后台】垂直行业营销-垂直行业管理-合伙商管理-搜索合作商",
            "计算依据说明": "",
            "源功能过程": "搜索合作商",
        }
    ]

    grouped = _group_rows_for_audit(fpa_rows, groups)

    assert grouped[1] == []
    assert grouped[2] == fpa_rows


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


def test_strict_profile_warns_when_ai_complex_eif_needs_manual_review():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "风控管理",
            "二级模块": "风险画像",
            "三级模块": "风险画像",
            "三级模块整体功能描述": "结合多源业务信息生成风险画像。",
            "功能过程": "查看画像",
            "功能过程类型": "查询",
            "功能过程描述": "查看企业风险画像详情。",
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
                "name": "跨域企业风险画像",
                "type": "EIF",
                "explanation": "AI 判断该风险画像由外部风控平台维护，本系统只引用。",
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)
    review_hits = [
        hit
        for hit in rows[0]["_规则命中详情"]
        if hit["rule_id"] == "postprocess.ai_data_group_review"
    ]
    assert review_hits
    assert review_hits[0]["suggested_type"] == "EIF"


def test_strict_profile_warns_when_ai_complex_ilf_needs_manual_review():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "营销管理",
            "二级模块": "客群洞察",
            "三级模块": "客群洞察",
            "三级模块整体功能描述": "生成客户洞察结果。",
            "功能过程": "刷新洞察",
            "功能过程类型": "新增",
            "功能过程描述": "刷新客户洞察。",
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
                "name": "客户生命周期洞察",
                "type": "ILF",
                "explanation": "AI 判断本系统保存并持续维护客户生命周期洞察结果。",
            },
        ],
    )

    assert rows[0]["类型"] == "ILF"
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)
    assert any(
        hit["rule_id"] == "postprocess.ai_data_group_review"
        for hit in rows[0]["_规则命中详情"]
    )


def test_strict_profile_data_group_review_survives_unrelated_ai_warning():
    group = _group_rows_by_l3([
        {
            "客户端类型": "地市后台",
            "一级模块": "风控管理",
            "二级模块": "风险画像",
            "三级模块": "风险画像",
            "三级模块整体功能描述": "结合多源业务信息生成风险画像。",
            "功能过程": "查看画像",
            "功能过程类型": "查询",
            "功能过程描述": "查看企业风险画像详情。",
        },
    ])[0]
    rows, warnings = _normalize_ai_fpa_rows_for_l3(
        group=group,
        meta=_meta(),
        judgement_rules=["有效规则"],
        start_seq=1,
        profile=STRICT_FPA_PROFILE,
        strategy="ai_first",
        ai_rows=[
            {
                "name": "跨域企业风险画像",
                "type": "EIF",
                "explanation": "AI 判断该风险画像由外部风控平台维护，本系统只引用。",
                "classification_basis_index": 99,
            },
        ],
    )

    assert rows[0]["类型"] == "EIF"
    assert any("classification_basis_index 越界" in warning for warning in warnings)
    assert any("AI 数据功能需人工复核" in warning for warning in warnings)


def test_keyword_type_fallbacks():
    assert CUSTOM_RULES_PROFILE.infer_type("客户界面开发")[0] == "EI"
    assert CUSTOM_RULES_PROFILE.infer_type("添加客户-逻辑处理开发")[0] == "ILF"
    assert CUSTOM_RULES_PROFILE.infer_type("查询客户-查询处理开发")[0] == "EQ"
    assert CUSTOM_RULES_PROFILE.infer_type("导出客户-导出处理开发")[0] == "EO"
    assert CUSTOM_RULES_PROFILE.infer_type("导入客户-导入处理开发")[0] == "EI"
    assert CUSTOM_RULES_PROFILE.infer_type("同步外部接口数据-逻辑处理开发")[0] == "ILF"
    assert CUSTOM_RULES_PROFILE.infer_type("引用统一用户中心账号-外部接口处理开发")[0] == "EIF"


class LowConfidenceRulesProfile(CustomRulesProfile):
    def fallback_rows_for_l3(self, group, meta, start_seq=1):
        return [{
            "序号": start_seq,
            "子系统(模块)": meta.get("子系统（模块）", ""),
            "资产标识": meta.get("资产标识", ""),
            "新增/修改功能点": "低置信度规则行",
            "类型": "",
            "计算依据归类": "",
            "计算依据说明": "低置信度规则行。",
            "变更状态": "新增",
            "调整值": 1,
            "要素数量": 1,
            "生成方式": "fallback",
            "类型理由": "",
            "源功能过程": "",
            "后处理警告": "",
        }]


def test_rules_first_keeps_rules_when_rule_rows_are_usable(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: pytest.fail("rules_first should not call AI when rules are usable"),
    )

    result = _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        strategy="rules_first",
    )

    assert result
    assert {row["生成方式"] for row in result} == {"fallback"}
    assert _rules_first_ai_reasons(_group_rows_by_l3(_rows())[0], result) == []


def test_rules_first_calls_ai_when_rule_rows_are_low_confidence(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    response = {
        "rows": [{
            "name": "AI 复核功能点",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": "AI 复核功能点，具体为以下：1、覆盖低置信度规则无法覆盖的功能过程。",
            "source_processes": ["添加垂直行业", "查询垂直行业"],
        }]
    }
    calls = {"count": 0}

    def fake_call_llm(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = _plan_fpa_rows_with_execution(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test",
        base_url="",
        profile=LowConfidenceRulesProfile(),
        strategy="rules_first",
        rule_set="custom_rules_default",
    )

    assert calls["count"] == 1
    assert result[0]["生成方式"] == "ai"
    assert result[0]["新增/修改功能点"] == "AI 复核功能点"


def test_rules_first_without_api_keeps_low_confidence_rules_and_audit_warning(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    audit_trace = tmp_path / "audit.json"

    result = _plan_fpa_rows_with_execution(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="",
        model="test",
        base_url="",
        profile=LowConfidenceRulesProfile(),
        strategy="rules_first",
        rule_set="custom_rules_default",
        audit_trace_path=str(audit_trace),
    )

    assert result[0]["生成方式"] == "fallback"
    trace = json.loads(audit_trace.read_text(encoding="utf-8"))
    warnings = trace["modules"][0]["warnings"]
    assert any("规则结果需要 AI 复核但未配置 API Key" in warning for warning in warnings)
    assert any("类型无效" in warning for warning in warnings)


def test_ai_parse_failure_falls_back(monkeypatch, tmp_path, caplog):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
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


def test_missing_fpa_config_does_not_fall_back(monkeypatch, tmp_path):
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: pytest.fail("missing prompt config must stop before LLM call"),
    )

    with pytest.raises(FpaConfigError, match="未找到 FPA 配置文件"):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="sk-test",
            model="test",
            base_url="",
            strategy="ai_first",
        )


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


def test_fpa_preview_returns_ai_debug(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    response = {
        "rows": [
            {
                "name": "垂直行业数据维护",
                "type": "ILF",
                "type_reason": "内部逻辑文件",
                "classification_basis_index": 1,
                "explanation": "垂直行业数据维护，具体如下：触发事件：管理员维护数据；事件流：系统保存数据。",
            }
        ]
    }

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )
    def fake_call_llm(*args, **kwargs):
        assert kwargs.get("return_thinking") is True
        return json.dumps(response, ensure_ascii=False), "思考过程"

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        base_url="",
        strategy="ai_only",
    )

    debug = result["debug"]
    assert debug["ai_called"] is True
    assert debug["model"] == "test-model"
    assert debug["system_prompt"] == "系统提示词"
    assert debug["system_prompt_source"] == "用户配置（配置目录/fpa_config.yaml: prompt_sets.custom_rules.system）"
    assert debug["user_prompt_source"] == "用户配置（配置目录/fpa_config.yaml: prompt_sets.custom_rules.user）"
    assert "垂直行业管理" in debug["user_prompt"]
    assert "[system]" in debug["ai_prompt"]
    assert "垂直行业数据维护" in debug["raw_response"]
    assert debug["thinking"] == "思考过程"
    assert debug["parsed_rows"] == response["rows"]
    assert debug["final_rows"][0]["name"] == "垂直行业数据维护"


def test_fpa_preview_prompt_includes_project_domain_context(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    (tmp_path / "domain_context.json").write_text(
        """
{
  "system_boundary": "本系统维护供应商协同关系，不维护供应商主档。",
  "internal_data_groups": [{"name": "供应商协同关系"}],
  "external_data_groups": [{"name": "供应商档案", "source": "供应商平台"}],
  "external_services": [{"name": "短信平台"}]
}
""",
        encoding="utf-8",
    )
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa._call_llm",
        lambda *args, **kwargs: (
            json.dumps(
                {
                    "rows": [{
                        "name": "领域上下文验证功能点",
                        "type": "EI",
                        "classification_basis_index": 1,
                        "explanation": "领域上下文验证功能点，具体为以下：1、覆盖上下文传入。",
                    }]
                },
                ensure_ascii=False,
            ),
            "",
        ),
    )

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        base_url="",
        strategy="ai_only",
    )

    prompt = result["debug"]["user_prompt"]
    assert '"子系统（模块）": "测试系统"' in prompt
    assert '"system_boundary": "本系统维护供应商协同关系，不维护供应商主档。"' in prompt
    assert '"name": "供应商协同关系"' in prompt
    assert '"name": "供应商档案"' in prompt
    assert '"source": "供应商平台"' in prompt
    assert '"name": "短信平台"' in prompt


def test_rules_first_preview_calls_ai_when_rule_rows_are_low_confidence(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    xlsx = tmp_path / "功能清单.xlsx"
    xlsx.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.gen_fpa.read_base_data_from_excel",
        lambda path: {"tree_rows": _rows(), "meta": _meta()},
    )

    def fake_fallback(self, group, meta, start_seq=1):
        return [{
            "序号": start_seq,
            "子系统(模块)": meta.get("子系统（模块）", ""),
            "资产标识": meta.get("资产标识", ""),
            "新增/修改功能点": "低置信度规则行",
            "类型": "",
            "计算依据归类": "",
            "计算依据说明": "低置信度规则行。",
            "变更状态": "新增",
            "调整值": 1,
            "要素数量": 1,
            "生成方式": "fallback",
            "类型理由": "",
            "源功能过程": "",
            "后处理警告": "",
        }]

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.fpa_profiles.CustomRulesProfile.fallback_rows_for_l3",
        fake_fallback,
    )
    response = {
        "rows": [{
            "name": "AI 预览复核功能点",
            "type": "EI",
            "classification_basis_index": 1,
            "explanation": "AI 预览复核功能点，具体为以下：1、覆盖低置信度规则输出。",
            "source_processes": ["添加垂直行业", "查询垂直行业"],
        }]
    }

    def fake_call_llm(*args, **kwargs):
        assert kwargs.get("return_thinking") is True
        return json.dumps(response, ensure_ascii=False), "思考过程"

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = preview_fpa_module(
        file_path=str(xlsx),
        module_name="垂直行业管理",
        api_key="sk-test",
        model="test-model",
        strategy="rules_first",
    )

    assert result["used_ai"] is True
    assert result["debug"]["reason"] == "rules_first_needs_ai"
    assert result["rows"][0]["name"] == "AI 预览复核功能点"
    assert any("规则结果触发 AI 复核" in warning for warning in result["warnings"])


def test_ai_cache_hit_skips_llm(monkeypatch, tmp_path, caplog):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
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


def test_ai_cache_is_invalidated_when_project_domain_context_changes(monkeypatch, tmp_path):
    _write_fpa_prompt_config(tmp_path, monkeypatch)
    domain_context_path = tmp_path / "domain_context.json"
    domain_context_path.write_text(
        """
{
  "system_boundary": "本系统维护供应商关系。",
  "internal_data_groups": [{"name": "供应商关系"}],
  "external_data_groups": [],
  "external_services": []
}
""",
        encoding="utf-8",
    )
    cache_path = tmp_path / "fpa_ai_cache.json"
    response = {
        "rows": [{
            "name": "供应商关系维护",
            "type": "ILF",
            "classification_basis_index": 1,
            "explanation": "供应商关系维护，具体为以下：1、保存供应商关系。",
        }]
    }
    calls = {"count": 0}

    def fake_call(*args, **kwargs):
        calls["count"] += 1
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call)
    for _ in range(2):
        _plan_fpa_rows_with_ai(
            _rows(),
            _meta(),
            ["规则一"],
            api_key="sk-test",
            model="test-model",
            base_url="",
            cache_path=str(cache_path),
            strategy="ai_first",
        )
    assert calls["count"] == 1

    domain_context_path.write_text(
        domain_context_path.read_text(encoding="utf-8").replace("供应商关系。", "供应商协同关系。"),
        encoding="utf-8",
    )
    _plan_fpa_rows_with_ai(
        _rows(),
        _meta(),
        ["规则一"],
        api_key="sk-test",
        model="test-model",
        base_url="",
        cache_path=str(cache_path),
        strategy="ai_first",
    )

    assert calls["count"] == 2


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


def test_fpa_check_xlsx_includes_rule_set_config_warning(tmp_path):
    fpa_md = tmp_path / "fpa.md"
    fpa_md.write_text(
        """# FPA 工作量评估

**profile**: custom_rules
**strategy**: rules_first
**rule_set**: sms_service_rules

| 序号 | 子系统(模块) | 资产标识 | 新增/修改功能点 | 类型 | 计算依据归类 | 计算依据说明 | 变更状态 | 调整值 | 要素数量 | 生成方式 | 类型理由 | 源功能过程 | 后处理警告 |
|------|-------------|---------|----------------|------|-------------|-------------|---------|-------|---------|---------|---------|-----------|-----------|
| 1 | 测试系统 | TEST | 发送短信-逻辑处理开发 | EI |  | 调用短信平台发送通知。 | 新增 | 2 | 1 | fallback | 普通外部服务调用按事务处理。 | 发送短信 |  |
""",
        encoding="utf-8",
    )
    tree_md = tmp_path / "tree.md"
    tree_md.write_text(
        """| 入口 | 一级模块 | 二级模块 | 三级模块 | 客户端类型 | 三级模块整体功能描述 | 功能过程 | 功能过程类型 | 功能过程描述 |
|------|---------|---------|---------|----------|----------------------|----------|--------------|--------------|
| 后台 | 通知 | 短信通知 | 短信通知 | 地市后台 | 发送短信通知。 | 发送短信 | 新增 | 调用短信平台发送通知。 |
""",
        encoding="utf-8",
    )
    warning = (
        "FPA 配置 warning: rule_set sms_service_rules 的 external_data_rules "
        "将普通外部服务「短信平台」配置为外部数据组「短信平台消息记录」。"
    )
    audit_trace = tmp_path / "trace.json"
    audit_trace.write_text(
        json.dumps({
            "modules": [{
                "module": "【地市后台】通知-短信通知-短信通知",
                "l3": "短信通知",
                "source": "rules",
                "raw_rows": [],
                "warnings": [warning, "规则优先策略未调用 AI"],
                "rule_hits": [],
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    output = tmp_path / "check.xlsx"
    generate_fpa_check_xlsx_from_md(str(fpa_md), str(tree_md), str(output), str(audit_trace))

    wb = openpyxl.load_workbook(output, data_only=True)
    warning_rows = [
        [cell.value for cell in row]
        for row in wb["Warnings"].iter_rows(min_row=2)
    ]
    assert any(row[4] == warning for row in warning_rows)
    assert any(row[5] == "config.external_data_rules.external_service" for row in warning_rows)
    coverage_headers = [cell.value for cell in wb["覆盖审核"][1]]
    coverage_warning = wb["覆盖审核"].cell(2, coverage_headers.index("Warnings") + 1).value
    assert warning in coverage_warning
    raw_headers = [cell.value for cell in wb["AI原始返回"][1]]
    raw_warning = wb["AI原始返回"].cell(2, raw_headers.index("Warnings") + 1).value
    assert warning in raw_warning
    wb.close()
