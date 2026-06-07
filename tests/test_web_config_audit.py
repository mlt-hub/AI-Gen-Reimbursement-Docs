import json

from web_app.services.config_audit_service import (
    append_config_audit_record,
    redact_changed_fields,
)


def test_redact_changed_fields_collapses_sensitive_names():
    redacted = redact_changed_fields([
        "ai.api_key",
        "_env.ANTHROPIC_API_KEY",
        "_env.ANTHROPIC_API_KEY_ENC",
        "ai.base_url",
    ])

    assert redacted == ["ai.api_key", "ai.base_url"]


def test_append_config_audit_record_writes_redacted_jsonl(tmp_path):
    audit_path = append_config_audit_record(
        audit_root=tmp_path,
        actor="alice",
        target_dir=tmp_path / "config",
        files=["system_config.yaml", ".env", ".env"],
        changed_fields=[
            "ai.api_key",
            "_env.ANTHROPIC_API_KEY_ENC",
            "templates.out_templates",
        ],
        result="success",
    )

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["actor"] == "alice"
    assert record["files"] == [".env", "system_config.yaml"]
    assert record["changed_fields"] == ["ai.api_key", "templates.out_templates"]
    assert record["result"] == "success"
    assert "timestamp" in record
    assert "ANTHROPIC_API_KEY" not in lines[0]
    assert "ANTHROPIC_API_KEY_ENC" not in lines[0]
