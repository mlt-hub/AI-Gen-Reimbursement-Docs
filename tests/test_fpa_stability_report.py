import json

from ai_gen_reimbursement_docs.fpa_stability_report import (
    build_fpa_stability_comparison,
    build_fpa_stability_report,
    evaluate_fpa_stability_comparison,
    render_fpa_stability_comparison_markdown,
)


def test_stability_report_summarizes_module_quality_signals():
    report = build_fpa_stability_report({
        "modules": [
            {
                "module": "客户管理",
                "l3": "客户档案",
                "source": "ai",
                "warnings": ["客户档案 AI 输出稳定性校验触发一次重试", "普通 warning"],
                "quality_review": {
                    "issues": [
                        {"code": "validator.query_as_ei", "retryable": True},
                        {"code": "quality.merge_review_not_applied", "retryable": True},
                    ],
                    "summary": {
                        "issue_count": 2,
                        "retryable_count": 2,
                        "confirmed_decision_count": 1,
                    },
                },
                "agent_review": {
                    "roles": [
                        {"name": "business_fact_extractor", "status": "completed"},
                        {"name": "fpa_type_judge", "status": "pending_agent"},
                        {"name": "merge_boundary_reviewer", "status": "completed"},
                    ],
                },
            },
            {
                "module": "订单管理",
                "l3": "订单查询",
                "source": "rules_fallback",
                "warnings": [],
                "quality_review": {"issues": [], "summary": {"issue_count": 0}},
                "agent_review": {
                    "roles": [
                        {"name": "business_fact_extractor", "status": "completed"},
                        {"name": "fpa_type_judge", "status": "pending_agent"},
                    ],
                },
            },
        ]
    })

    summary = report["summary"]
    assert summary["module_count"] == 2
    assert summary["warning_count"] == 2
    assert summary["quality_issue_count"] == 2
    assert summary["retryable_quality_issue_count"] == 2
    assert summary["confirmed_decision_count"] == 1
    assert summary["retry_count"] == 1
    assert summary["source_counts"] == {"ai": 1, "rules_fallback": 1}
    assert summary["issue_code_counts"]["validator.query_as_ei"] == 1
    assert summary["agent_role_counts"]["business_fact_extractor"] == 2
    assert summary["pending_agent_role_counts"]["fpa_type_judge"] == 2
    assert report["modules"][0]["retry_count"] == 1
    assert report["modules"][0]["pending_agent_roles"] == ["fpa_type_judge"]


def test_stability_comparison_loads_traces_and_renders_markdown(tmp_path):
    trace_a = tmp_path / "model-a.json"
    trace_b = tmp_path / "model-b.json"
    trace_a.write_text(json.dumps({
        "case_id": "customer_query",
        "run_id": "customer_query__strict_fpa__ai_first__strict_fpa_rs",
        "profile": "strict_fpa",
        "strategy": "ai_first",
        "rule_set": "strict_fpa_rs",
        "modules": [{
            "module": "客户管理",
            "l3": "客户档案",
            "source": "ai",
            "warnings": ["客户档案 AI 输出稳定性校验触发一次重试"],
            "quality_review": {
                "issues": [{
                    "code": "validator.query_as_ei",
                    "retryable": True,
                    "message": "查询流程不应判为 EI",
                }],
                "summary": {"issue_count": 1, "retryable_count": 1},
            },
        }],
    }, ensure_ascii=False), encoding="utf-8")
    trace_b.write_text(json.dumps({
        "profile": "strict_fpa",
        "strategy": "ai_first",
        "rule_set": "strict_fpa_rs",
        "stability_report": {
            "summary": {
                "module_count": 2,
                "warning_count": 0,
                "quality_issue_count": 0,
                "retryable_quality_issue_count": 0,
                "confirmed_decision_count": 0,
                "retry_count": 0,
                "source_counts": {"ai_cache": 2},
                "issue_code_counts": {},
            },
            "modules": [],
        },
    }, ensure_ascii=False), encoding="utf-8")

    comparison = build_fpa_stability_comparison([str(trace_a), str(trace_b)])
    markdown = render_fpa_stability_comparison_markdown(comparison)

    assert comparison["summary"]["run_count"] == 2
    assert comparison["summary"]["module_count"] == 3
    assert comparison["summary"]["warning_count"] == 1
    assert comparison["summary"]["retry_count"] == 1
    assert comparison["summary"]["source_counts"] == {"ai": 1, "ai_cache": 2}
    assert comparison["runs"][0]["case_id"] == "customer_query"
    assert comparison["runs"][0]["run_id"] == "customer_query__strict_fpa__ai_first__strict_fpa_rs"
    assert comparison["issue_details"][0]["case_id"] == "customer_query"
    assert comparison["issue_details"][0]["message"] == "查询流程不应判为 EI"
    assert "validator.query_as_ei" in markdown
    assert "| customer_query | customer_query__strict_fpa__ai_first__strict_fpa_rs | model-a.json |" in markdown
    assert "## Issue Details" in markdown
    assert "| 1 | customer_query | 客户管理 | validator.query_as_ei | yes | 查询流程不应判为 EI |" in markdown


def test_stability_comparison_quality_gate_renders_failure():
    comparison = {
        "summary": {
            "run_count": 1,
            "module_count": 1,
            "warning_count": 2,
            "quality_issue_count": 1,
            "retryable_quality_issue_count": 1,
            "confirmed_decision_count": 0,
            "retry_count": 0,
            "source_counts": {},
            "issue_code_counts": {},
        },
        "runs": [],
    }

    comparison["evaluation"] = evaluate_fpa_stability_comparison(
        comparison,
        {"warning_count": 1, "retry_count": 0},
    )
    markdown = render_fpa_stability_comparison_markdown(comparison)

    assert comparison["evaluation"]["status"] == "fail"
    assert "Status: **FAIL**" in markdown
    assert "| warning_count | 2 | 1 | no |" in markdown
