from ai_gen_reimbursement_docs.cosmic_confirmation import (
    apply_cosmic_confirmation_export_policy,
)


def _payload(*, status: str, severity: str = "warning", confirmation_status: str = "unconfirmed"):
    return {
        "project": "测试项目",
        "status": status,
        "review_items": [
            {
                "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
                "severity": severity,
                "confirmation": {
                    "status": confirmation_status,
                    "decision": confirmation_status if confirmation_status != "unconfirmed" else "",
                    "note": "",
                    "confirmed_by": "",
                    "confirmed_at": "",
                },
            }
        ],
    }


def test_confirmation_policy_blocks_unconfirmed_review_items():
    payload = apply_cosmic_confirmation_export_policy(_payload(status="review_required"))

    assert payload["confirmation_summary"]["unconfirmed_review_item_count"] == 1
    assert payload["export_policy"]["formal_excel"]["status"] == "blocked"
    assert "未确认" in payload["export_policy"]["formal_excel"]["reason"]
    assert payload["export_policy"]["draft_excel"]["status"] == "eligible"


def test_confirmation_policy_allows_formal_after_warning_is_resolved():
    payload = apply_cosmic_confirmation_export_policy(
        _payload(status="review_required", confirmation_status="confirmed")
    )

    assert payload["confirmation_summary"]["unconfirmed_review_item_count"] == 0
    assert payload["confirmation_summary"]["resolved_review_item_count"] == 1
    assert payload["export_policy"]["formal_excel"]["status"] == "allowed_after_confirmation"
    assert payload["export_policy"]["draft_excel"]["status"] == "not_needed"


def test_confirmation_policy_keeps_error_items_blocked_after_confirmation():
    payload = apply_cosmic_confirmation_export_policy(
        _payload(status="blocked", severity="error", confirmation_status="waived")
    )

    assert payload["confirmation_summary"]["error_review_item_count"] == 1
    assert payload["confirmation_summary"]["unconfirmed_review_item_count"] == 0
    assert payload["export_policy"]["formal_excel"]["status"] == "blocked"
    assert "error" in payload["export_policy"]["formal_excel"]["reason"]
    assert payload["export_policy"]["draft_excel"]["status"] == "blocked"
