import json

from ai_gen_reimbursement_docs.fpa_stability_sampler import (
    parse_fpa_stability_sample_configs,
    resolve_fpa_stability_sample_preset,
    resolve_fpa_stability_suite_fixtures,
    run_fpa_stability_sampling,
)


def _fixture(path):
    path.write_text(json.dumps({
        "case_id": "customer_query",
        "meta": {
            "子系统（模块）": "测试系统",
            "资产标识": "TEST-001",
        },
        "rows": [
            {
                "客户端类型": "地市后台",
                "一级模块": "客户管理",
                "二级模块": "客户档案",
                "三级模块": "客户查询",
                "三级模块整体功能描述": "查询客户档案。",
                "功能过程": "查询客户",
                "功能过程类型": "查询",
                "功能过程描述": "按客户名称查询客户列表。",
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")


def test_parse_sample_configs_builds_matrix():
    configs = parse_fpa_stability_sample_configs(
        profiles="strict_fpa,unified_ui",
        strategies="rules_only,rules_first",
        rule_sets="strict_fpa_rs",
    )

    assert len(configs) == 4
    assert configs[0].profile == "strict_fpa"
    assert configs[0].strategy == "rules_only"
    assert configs[0].rule_set == "strict_fpa_rs"


def test_resolve_standard_suite_returns_existing_fixtures():
    paths = resolve_fpa_stability_suite_fixtures("standard")

    assert len(paths) >= 5
    assert any(path.endswith("vertical_industry_management.json") for path in paths)
    assert all(open(path, encoding="utf-8").read(1) == "{" for path in paths)


def test_resolve_recommended_suite_returns_extended_existing_fixtures():
    paths = resolve_fpa_stability_suite_fixtures("real-model-recommended")

    assert len(paths) == 10
    assert any(path.endswith("payment_gateway_refund.json") for path in paths)
    assert any(path.endswith("crm_customer_archive_reference.json") for path in paths)
    assert all(open(path, encoding="utf-8").read(1) == "{" for path in paths)


def test_resolve_strict_real_model_preset():
    preset = resolve_fpa_stability_sample_preset("strict-real-model")

    assert preset["suite"] == "standard"
    assert preset["profiles"] == "strict_fpa"
    assert preset["strategies"] == "ai_first"
    assert preset["rule_sets"] == "strict_fpa_rs"
    assert preset["thresholds"] == {
        "retryable_quality_issue_count": 0,
        "blocking_retry_count": 0,
    }


def test_resolve_strict_real_model_recommended_preset():
    preset = resolve_fpa_stability_sample_preset("strict-real-model-recommended")

    assert preset["suite"] == "real-model-recommended"
    assert preset["profiles"] == "strict_fpa"
    assert preset["strategies"] == "ai_first"
    assert preset["rule_sets"] == "strict_fpa_rs"
    assert preset["thresholds"] == {
        "retryable_quality_issue_count": 0,
        "blocking_retry_count": 0,
    }


def test_run_fpa_stability_sampling_writes_traces_manifest_and_report(tmp_path):
    fixture = tmp_path / "case.json"
    output_dir = tmp_path / "samples"
    _fixture(fixture)

    manifest = run_fpa_stability_sampling(
        fixture_paths=[str(fixture)],
        output_dir=str(output_dir),
        configs=parse_fpa_stability_sample_configs(
            profiles="strict_fpa",
            strategies="rules_only",
            rule_sets="strict_fpa_rs",
        ),
        thresholds={"retry_count": 0},
    )

    assert len(manifest["runs"]) == 1
    assert manifest["comparison"]["evaluation"]["status"] == "pass"
    trace_path = manifest["runs"][0]["audit_trace"]
    trace = json.loads(open(trace_path, encoding="utf-8").read())
    assert trace["case_id"] == "customer_query"
    assert trace["run_id"] == "customer_query__strict_fpa__rules_only__strict_fpa_rs"
    assert trace["run_dir"] == manifest["runs"][0]["run_dir"]
    assert trace["fixture_path"] == str(fixture)
    assert trace["stability_report"]["summary"]["module_count"] == 1
    report_text = (output_dir / "fpa-stability-sampling-report.md").read_text(encoding="utf-8")
    assert "Status: **PASS**" in report_text
    assert "customer_query__strict_fpa__rules_only__strict_fpa_rs" in report_text
    assert (output_dir / "fpa-stability-sampling-report.md").exists()
    assert (output_dir / "fpa-stability-sampling-manifest.json").exists()
