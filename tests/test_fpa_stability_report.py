from ai_gen_reimbursement_docs.fpa_stability_report import build_fpa_stability_report


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
            },
            {
                "module": "订单管理",
                "l3": "订单查询",
                "source": "rules_fallback",
                "warnings": [],
                "quality_review": {"issues": [], "summary": {"issue_count": 0}},
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
    assert report["modules"][0]["retry_count"] == 1
