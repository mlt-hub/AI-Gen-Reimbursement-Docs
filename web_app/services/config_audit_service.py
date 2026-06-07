import json
from datetime import datetime, timezone
from pathlib import Path


SENSITIVE_FIELD_NAMES = {
    "api_key",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY_ENC",
}


def redact_changed_fields(fields: list[str]) -> list[str]:
    redacted: list[str] = []
    for field in fields:
        parts = field.split(".")
        if any(part in SENSITIVE_FIELD_NAMES for part in parts):
            redacted.append("ai.api_key")
        else:
            redacted.append(field)
    return sorted(set(redacted))


def append_config_audit_record(
    *,
    audit_root: Path,
    actor: str,
    target_dir: Path,
    files: list[str],
    changed_fields: list[str],
    result: str,
) -> Path:
    audit_dir = audit_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "config_changes.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "target_dir": str(target_dir),
        "files": sorted(set(files)),
        "changed_fields": redact_changed_fields(changed_fields),
        "result": result,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
