"""Manual confirmation policy helpers for COSMIC preview payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_RESOLVED_CONFIRMATION_STATUSES = {"confirmed", "rejected", "waived"}


def apply_cosmic_confirmation_export_policy(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a COSMIC preview payload with confirmation-aware export policy."""
    data = deepcopy(payload)
    review_items = data.get("review_items")
    if not isinstance(review_items, list):
        review_items = []

    summary = _confirmation_summary(review_items)
    data["export_policy"] = _export_policy(data, summary)
    data["confirmation_summary"] = summary
    return data


def _confirmation_summary(review_items: list[Any]) -> dict[str, int]:
    total = 0
    unconfirmed = 0
    confirmed = 0
    rejected = 0
    waived = 0
    errors = 0
    warnings = 0
    infos = 0

    for raw_item in review_items:
        if not isinstance(raw_item, dict):
            continue
        total += 1
        severity = str(raw_item.get("severity") or "").strip().lower()
        if severity == "error":
            errors += 1
        elif severity == "warning":
            warnings += 1
        elif severity == "info":
            infos += 1

        confirmation = raw_item.get("confirmation")
        status = ""
        if isinstance(confirmation, dict):
            status = str(confirmation.get("status") or "").strip().lower()
        if status not in _RESOLVED_CONFIRMATION_STATUSES:
            unconfirmed += 1
        elif status == "confirmed":
            confirmed += 1
        elif status == "rejected":
            rejected += 1
        elif status == "waived":
            waived += 1

    return {
        "total_review_item_count": total,
        "unconfirmed_review_item_count": unconfirmed,
        "resolved_review_item_count": total - unconfirmed,
        "confirmed_review_item_count": confirmed,
        "rejected_review_item_count": rejected,
        "waived_review_item_count": waived,
        "error_review_item_count": errors,
        "warning_review_item_count": warnings,
        "info_review_item_count": infos,
    }


def _export_policy(payload: dict[str, Any], summary: dict[str, int]) -> dict[str, Any]:
    status = str(payload.get("status") or "").strip()
    total = summary["total_review_item_count"]
    unconfirmed = summary["unconfirmed_review_item_count"]
    error_count = summary["error_review_item_count"]

    manual_confirmation_required = total > 0
    if status == "passed":
        formal_excel = {
            "status": "allowed",
            "reason": "校验通过，可写正式 Excel",
        }
        draft_excel = {
            "status": "not_needed",
            "reason": "校验通过，不需要草稿 Excel",
            "requires_config": False,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }
    elif unconfirmed:
        formal_excel = {
            "status": "blocked",
            "reason": f"仍有 {unconfirmed} 个审阅项未确认，正式 Excel 需人工确认后再导出",
        }
        draft_excel = _draft_policy_for_unconfirmed(status)
    elif error_count:
        formal_excel = {
            "status": "blocked",
            "reason": "存在 error 级阻断项，即使已确认也不能写正式 Excel",
        }
        draft_excel = {
            "status": "blocked",
            "reason": "存在 error 级阻断项，不能写草稿 Excel",
            "requires_config": False,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }
    else:
        formal_excel = {
            "status": "allowed_after_confirmation",
            "reason": "待审项已人工处理，可写正式 Excel",
        }
        draft_excel = {
            "status": "not_needed",
            "reason": "待审项已人工处理，不需要草稿 Excel",
            "requires_config": False,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }

    return {
        "manual_confirmation_required": manual_confirmation_required,
        "unconfirmed_review_item_count": unconfirmed,
        "formal_excel": formal_excel,
        "draft_excel": draft_excel,
    }


def _draft_policy_for_unconfirmed(status: str) -> dict[str, Any]:
    if status == "review_required":
        return {
            "status": "eligible",
            "reason": "存在待审问题，可在配置开启后写草稿 Excel",
            "requires_config": True,
            "config_key": "gen_cosmic.allow_draft_excel_output",
        }
    return {
        "status": "blocked",
        "reason": "存在阻断问题，不能写草稿 Excel",
        "requires_config": False,
        "config_key": "gen_cosmic.allow_draft_excel_output",
    }
