"""Persistence for FPA project-profile confirmation decisions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ai_gen_reimbursement_docs.fpa_confirmation import (
    FpaConfirmationDecision,
    normalize_confirmed_decisions,
)


PROFILE_FILE_NAME = "fpa_project_profile.json"
PROFILE_SCOPE = "project_profile"


def profile_path(config_root: Path) -> Path:
    return config_root / PROFILE_FILE_NAME


def load_project_profile_decisions(config_root: Path | None) -> dict[str, FpaConfirmationDecision]:
    if config_root is None:
        return {}
    path = profile_path(config_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_decisions = payload.get("confirmed_decisions")
    decisions = normalize_confirmed_decisions(raw_decisions if isinstance(raw_decisions, dict) else {})
    return {
        key: FpaConfirmationDecision(value=decision.value, scope=PROFILE_SCOPE)
        for key, decision in decisions.items()
        if decision.scope == PROFILE_SCOPE
    }


def merge_decision_payloads(
    persisted: object | None,
    current: object | None,
) -> dict[str, FpaConfirmationDecision]:
    merged = dict(normalize_confirmed_decisions(persisted or {}))
    merged.update(normalize_confirmed_decisions(current or {}))
    return merged


def persist_project_profile_decisions(
    *,
    config_root: Path | None,
    confirmed_decisions: object | None,
) -> dict[str, FpaConfirmationDecision]:
    """Persist only explicitly project-profile scoped decisions."""
    if config_root is None:
        return {}
    incoming = {
        key: decision
        for key, decision in normalize_confirmed_decisions(confirmed_decisions or {}).items()
        if decision.scope == PROFILE_SCOPE
    }
    if not incoming:
        return load_project_profile_decisions(config_root)

    existing = load_project_profile_decisions(config_root)
    existing.update(incoming)
    config_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "confirmed_decisions": _serialize_decisions(existing),
    }
    _atomic_write_text(profile_path(config_root), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return existing


def serialize_decisions(decisions: object | None) -> dict[str, dict[str, str]]:
    return _serialize_decisions(normalize_confirmed_decisions(decisions or {}))


def _serialize_decisions(
    decisions: dict[str, FpaConfirmationDecision],
) -> dict[str, dict[str, str]]:
    return {
        str(key): {"value": decision.value, "scope": decision.scope}
        for key, decision in sorted(decisions.items())
    }


def _atomic_write_text(path: Path, text: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
