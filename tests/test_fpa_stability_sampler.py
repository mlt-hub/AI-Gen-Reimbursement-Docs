import json

from ai_gen_reimbursement_docs.fpa_stability_sampler import (
    parse_fpa_stability_sample_configs,
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
    )

    assert len(manifest["runs"]) == 1
    trace_path = manifest["runs"][0]["audit_trace"]
    trace = json.loads(open(trace_path, encoding="utf-8").read())
    assert trace["stability_report"]["summary"]["module_count"] == 1
    assert (output_dir / "fpa-stability-sampling-report.md").exists()
    assert (output_dir / "fpa-stability-sampling-manifest.json").exists()
