import asyncio
import json
import time

from web_app.services import config_service
from web_app.services import secret_service


def test_remote_session_retention_seconds_reads_retention_days(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "config_dir", lambda: tmp_path)
    (tmp_path / "system_config.yaml").write_text(
        "remote_session_retention_days: 2\n",
        encoding="utf-8",
    )

    assert config_service.remote_session_retention_seconds() == 2 * 24 * 3600


def test_remote_session_retention_seconds_falls_back_for_invalid_days(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "config_dir", lambda: tmp_path)
    (tmp_path / "system_config.yaml").write_text(
        "remote_session_retention_days: invalid\n",
        encoding="utf-8",
    )

    assert config_service.remote_session_retention_seconds(default=60) == 60


def test_mask_env_content_hides_sensitive_values_without_fragments(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=sk-secret-value\n"
        "ANTHROPIC_BASE_URL=https://api.example.test\n",
        encoding="utf-8",
    )

    masked = config_service.mask_env_content(env_path)

    assert "ANTHROPIC_API_KEY=***" in masked
    assert "sk-" not in masked
    assert "value" not in masked
    assert "ANTHROPIC_BASE_URL=https://api.example.test" in masked


def test_save_config_to_dir_preserves_existing_sensitive_env_when_omitted(tmp_path):
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-existing\n"
        "ANTHROPIC_BASE_URL=https://old.example.test\n",
        encoding="utf-8",
    )

    asyncio.run(config_service.save_config_to_dir(
        {
            "_env": {
                "ANTHROPIC_BASE_URL": "https://new.example.test",
                "ANTHROPIC_MODEL": "deepseek-v4-flash",
            }
        },
        tmp_path,
    ))

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-existing" in env_text
    assert "ANTHROPIC_BASE_URL=https://new.example.test" in env_text
    assert "ANTHROPIC_MODEL=deepseek-v4-flash" in env_text


def test_redact_env_dict_hides_sensitive_values_without_fragments():
    redacted = config_service.redact_env_dict({
        "ANTHROPIC_API_KEY": "sk-secret-value",
        "ANTHROPIC_BASE_URL": "https://api.example.test",
    })

    assert redacted["ANTHROPIC_API_KEY"] == "***"
    assert redacted["ANTHROPIC_BASE_URL"] == "https://api.example.test"


def test_build_web_config_view_redacts_api_key_and_marks_global_sources():
    view = config_service.build_web_config_view(
        global_config={
            "_env": {
                "ANTHROPIC_API_KEY": "sk-global-secret",
                "ANTHROPIC_BASE_URL": "https://global.example.test",
                "ANTHROPIC_MODEL": "global-model",
            },
            "_system": {
                "max_tokens": "8K",
                "allow_shared_ai_credentials": True,
                "out_templates": {"fpa": "data/out_templates/fpa.xlsx"},
            },
        },
        local_mode=True,
    )

    assert view["ai"]["api_key_configured"] is True
    assert view["ai"]["api_key_source"] == "global"
    assert "sk-global-secret" not in str(view)
    assert view["ai"]["base_url"] == {
        "value": "https://global.example.test",
        "source": "global",
    }
    assert view["ai"]["model"] == {"value": "global-model", "source": "global"}
    assert view["ai"]["max_tokens"] == {"value": "8K", "source": "global"}
    assert view["ai"]["allow_shared_ai_credentials"] == {"value": True, "source": "global"}
    assert view["templates"]["out_templates"]["source"] == "global"


def test_build_web_config_view_uses_personal_overrides_for_remote_user():
    view = config_service.build_web_config_view(
        global_config={
            "_env": {
                "ANTHROPIC_API_KEY": "sk-global-secret",
                "ANTHROPIC_BASE_URL": "https://global.example.test",
                "ANTHROPIC_MODEL": "global-model",
            },
            "_system": {
                "max_tokens": "8K",
                "fpa_profile": "strict_fpa",
                "allow_shared_ai_credentials": False,
            },
        },
        user_config={
            "_env": {
                "ANTHROPIC_BASE_URL": "https://personal.example.test",
            },
            "_system": {
                "fpa_profile": "custom_rules",
            },
        },
        username="alice",
        local_mode=False,
    )

    assert view["scope"] == {"mode": "remote", "username": "alice"}
    assert view["ai"]["api_key_configured"] is False
    assert view["ai"]["api_key_source"] == "default"
    assert "sk-global-secret" not in str(view)
    assert view["ai"]["base_url"] == {
        "value": "https://personal.example.test",
        "source": "personal",
    }
    assert view["ai"]["model"] == {"value": "global-model", "source": "global"}
    assert view["run_defaults"]["fpa_profile"] == {
        "value": "custom_rules",
        "source": "personal",
    }


def test_build_web_config_view_allows_shared_global_api_key_only_when_enabled():
    view = config_service.build_web_config_view(
        global_config={
            "_env": {
                "ANTHROPIC_API_KEY": "sk-global-secret",
            },
            "_system": {
                "allow_shared_ai_credentials": True,
            },
        },
        user_config={"_env": {}, "_system": {}},
        username="alice",
        local_mode=False,
    )

    assert view["ai"]["api_key_configured"] is True
    assert view["ai"]["api_key_source"] == "global"
    assert "sk-global-secret" not in str(view)


def test_resolve_task_start_config_prefers_explicit_then_personal_then_global(monkeypatch, tmp_path):
    user_root = tmp_path / "user"
    global_root = tmp_path / "global"
    user_root.mkdir()
    global_root.mkdir()
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))
    personal_key = secret_service.encrypt_secret("sk-personal", config_root=user_root)
    global_key = secret_service.encrypt_secret("sk-global", config_root=global_root)

    resolved = config_service.resolve_task_start_config(
        explicit={
            "model": "explicit-model",
            "fpa_strategy": "rules_only",
        },
        user_config={
            "_env": {
                "ANTHROPIC_API_KEY_ENC": personal_key,
                "ANTHROPIC_MODEL": "personal-model",
            },
            "_system": {
                "fpa_profile": "personal_profile",
            },
        },
        global_config={
            "_env": {
                "ANTHROPIC_API_KEY_ENC": global_key,
                "ANTHROPIC_BASE_URL": "https://global.example.test",
            },
            "_system": {
                "fpa_profile": "global_profile",
                "fpa_strategy": "ai_first",
            },
        },
        local_mode=False,
        global_config_root=global_root,
        user_config_root=user_root,
    )

    assert resolved["api_key"] == "sk-personal"
    assert resolved["api_key_source"] == "personal"
    assert resolved["model"] == "explicit-model"
    assert resolved["base_url"] == "https://global.example.test"
    assert resolved["fpa_profile"] == "personal_profile"
    assert resolved["fpa_strategy"] == "rules_only"


def test_resolve_task_start_config_uses_shared_global_key_only_when_enabled(monkeypatch, tmp_path):
    global_root = tmp_path / "global"
    global_root.mkdir()
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))
    global_key = secret_service.encrypt_secret("sk-global", config_root=global_root)

    disabled = config_service.resolve_task_start_config(
        explicit={},
        user_config={"_env": {}, "_system": {}},
        global_config={
            "_env": {"ANTHROPIC_API_KEY_ENC": global_key},
            "_system": {"allow_shared_ai_credentials": False},
        },
        local_mode=False,
        global_config_root=global_root,
        user_config_root=tmp_path / "user",
    )
    enabled = config_service.resolve_task_start_config(
        explicit={},
        user_config={"_env": {}, "_system": {}},
        global_config={
            "_env": {"ANTHROPIC_API_KEY_ENC": global_key},
            "_system": {"allow_shared_ai_credentials": True},
        },
        local_mode=False,
        global_config_root=global_root,
        user_config_root=tmp_path / "user",
    )

    assert disabled["api_key"] == ""
    assert disabled["api_key_source"] == "missing"
    assert enabled["api_key"] == "sk-global"
    assert enabled["api_key_source"] == "global"
    assert enabled["uses_shared_api_key"] is True


def test_mode_requires_ai_skips_basedata_and_rules_only_fpa():
    assert config_service.mode_requires_ai("from-excel-gen-basedata") is False
    assert config_service.mode_requires_ai("from-excel-gen-fpa", "rules_only") is False
    assert config_service.mode_requires_ai("from-excel-gen-fpa", "ai_first") is True


def test_save_web_config_to_dir_encrypts_api_key_and_saves_editable_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))

    asyncio.run(config_service.save_web_config_to_dir(
        {
            "ai": {
                "api_key": "sk-new-secret",
                "base_url": {"value": "https://api.example.test"},
                "model": {"value": "deepseek-v4-flash"},
                "max_tokens": {"value": "32K"},
                "allow_shared_ai_credentials": {"value": True},
            },
            "templates": {
                "out_templates": {
                    "value": {"fpa_out_template": "data/out_templates/fpa.xlsx"},
                },
            },
            "run_defaults": {
                "project_name": {"value": "测试项目"},
                "fpa_profile": {"value": "strict_fpa"},
            },
        },
        tmp_path,
        allow_shared_credentials_write=True,
    ))

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    system_text = (tmp_path / "system_config.yaml").read_text(encoding="utf-8")
    saved = config_service.read_config_from_dir(tmp_path)

    assert "ANTHROPIC_API_KEY=" not in env_text
    assert "ANTHROPIC_API_KEY_ENC=fernet:" in env_text
    assert "sk-new-secret" not in env_text
    assert secret_service.decrypt_secret(saved["_env"]["ANTHROPIC_API_KEY_ENC"], config_root=tmp_path) == "sk-new-secret"
    assert saved["_env"]["ANTHROPIC_BASE_URL"] == "https://api.example.test"
    assert saved["_env"]["ANTHROPIC_MODEL"] == "deepseek-v4-flash"
    assert saved["_system"]["max_tokens"] == "32K"
    assert saved["_system"]["allow_shared_ai_credentials"] is True
    assert saved["_system"]["out_templates"] == {"fpa_out_template": "data/out_templates/fpa.xlsx"}
    assert saved["_system"]["project_name"] == "测试项目"
    assert "sk-new-secret" not in system_text


def test_save_web_config_to_dir_preserves_encrypted_key_when_omitted(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))
    asyncio.run(config_service.save_web_config_to_dir({"ai": {"api_key": "sk-existing"}}, tmp_path))
    saved_before = config_service.read_config_from_dir(tmp_path)["_env"]["ANTHROPIC_API_KEY_ENC"]

    asyncio.run(config_service.save_web_config_to_dir(
        {"ai": {"base_url": {"value": "https://new.example.test"}}},
        tmp_path,
    ))

    saved_after = config_service.read_config_from_dir(tmp_path)
    assert saved_after["_env"]["ANTHROPIC_API_KEY_ENC"] == saved_before
    assert saved_after["_env"]["ANTHROPIC_BASE_URL"] == "https://new.example.test"


def test_save_web_config_to_dir_can_clear_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))
    asyncio.run(config_service.save_web_config_to_dir({"ai": {"api_key": "sk-existing"}}, tmp_path))

    asyncio.run(config_service.save_web_config_to_dir({"ai": {"clear_api_key": True}}, tmp_path))

    saved = config_service.read_config_from_dir(tmp_path)
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in saved["_env"]
    assert "ANTHROPIC_API_KEY_ENC" not in saved["_env"]
    assert "sk-existing" not in env_text


def test_save_web_config_to_dir_backs_up_existing_files_and_writes_redacted_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY_ENC=fernet:old-ciphertext\n"
        "ANTHROPIC_BASE_URL=https://old.example.test\n",
        encoding="utf-8",
    )
    (tmp_path / "system_config.yaml").write_text(
        "max_tokens: 8K\n",
        encoding="utf-8",
    )

    asyncio.run(config_service.save_web_config_to_dir(
        {
            "ai": {
                "api_key": "sk-new-secret",
                "base_url": {"value": "https://new.example.test"},
            },
        },
        tmp_path,
        actor="alice",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    ))

    backup_dir = tmp_path / "backups" / "config" / "unit"
    env_backups = list(backup_dir.glob(".env.*.bak"))
    system_backups = list(backup_dir.glob("system_config.yaml.*.bak"))
    assert len(env_backups) == 1
    assert len(system_backups) == 1
    assert "fernet:old-ciphertext" in env_backups[0].read_text(encoding="utf-8")

    audit_path = tmp_path / "audit" / "config_changes.jsonl"
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["actor"] == "alice"
    assert records[0]["files"] == [".env", "system_config.yaml"]
    assert "ai.api_key" in records[0]["changed_fields"]
    assert "ai.base_url" in records[0]["changed_fields"]
    assert "sk-new-secret" not in audit_path.read_text(encoding="utf-8")
    assert "fernet:" not in audit_path.read_text(encoding="utf-8")


def test_backup_config_files_keeps_recent_five_versions(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_BASE_URL=https://example.test\n", encoding="utf-8")

    for index in range(6):
        (tmp_path / ".env").write_text(f"ANTHROPIC_MODEL=model-{index}\n", encoding="utf-8")
        config_service.backup_config_files(
            target_dir=tmp_path,
            backup_root=tmp_path,
            scope="unit",
            keep=5,
        )
        time.sleep(0.01)

    backups = sorted((tmp_path / "backups" / "config" / "unit").glob(".env.*.bak"))
    assert len(backups) == 5
    combined = "\n".join(path.read_text(encoding="utf-8") for path in backups)
    assert "model-0" not in combined
    assert "model-5" in combined


def test_backup_config_files_redacts_plaintext_env_secrets(tmp_path):
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-plaintext-secret\n"
        "ANTHROPIC_API_KEY_ENC=fernet:ciphertext\n"
        "ANTHROPIC_BASE_URL=https://example.test\n",
        encoding="utf-8",
    )

    config_service.backup_config_files(
        target_dir=tmp_path,
        backup_root=tmp_path,
        scope="unit",
    )

    backup_text = next((tmp_path / "backups" / "config" / "unit").glob(".env.*.bak")).read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=***" in backup_text
    assert "sk-plaintext-secret" not in backup_text
    assert "ANTHROPIC_API_KEY_ENC=fernet:ciphertext" in backup_text


def test_list_config_backups_returns_restorable_items(tmp_path):
    backup_dir = tmp_path / "backups" / "config" / "unit"
    backup_dir.mkdir(parents=True)
    (backup_dir / ".env.20260607_120000_000001.bak").write_text("ANTHROPIC_MODEL=old\n", encoding="utf-8")
    (backup_dir / "system_config.yaml.20260607_120000_000001.bak").write_text("max_tokens: 8K\n", encoding="utf-8")
    (backup_dir / "business_rules.yaml.20260607_120000_000001.bak").write_text("ignored: true\n", encoding="utf-8")

    items = config_service.list_config_backups(backup_root=tmp_path, scope="unit")

    assert {item["file"] for item in items} == {".env", "system_config.yaml"}
    assert {item["id"] for item in items} == {
        ".env.20260607_120000_000001.bak",
        "system_config.yaml.20260607_120000_000001.bak",
    }
    assert all("size_bytes" in item for item in items)


def test_restore_config_backup_restores_file_and_writes_audit(tmp_path):
    (tmp_path / ".env").write_text(
        "ANTHROPIC_MODEL=current-model\n",
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups" / "config" / "unit"
    backup_dir.mkdir(parents=True)
    backup = backup_dir / ".env.20260607_120000_000001.bak"
    backup.write_text(
        "ANTHROPIC_MODEL=restored-model\n",
        encoding="utf-8",
    )

    restored = config_service.restore_config_backup(
        target_dir=tmp_path,
        backup_root=tmp_path,
        scope="unit",
        backup_id=backup.name,
        actor="alice",
        audit_root=tmp_path,
    )

    assert restored["_env"]["ANTHROPIC_MODEL"] == "restored-model"
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "ANTHROPIC_MODEL=restored-model\n"
    current_backups = list(backup_dir.glob(".env.*.bak"))
    assert len(current_backups) == 2
    assert any("current-model" in path.read_text(encoding="utf-8") for path in current_backups)

    audit_path = tmp_path / "audit" / "config_changes.jsonl"
    record = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["actor"] == "alice"
    assert record["files"] == [".env"]
    assert record["changed_fields"] == ["restore.env"]
    assert "restored-model" not in audit_path.read_text(encoding="utf-8")


def test_restore_config_backup_rejects_invalid_backup_id(tmp_path):
    try:
        config_service.restore_config_backup(
            target_dir=tmp_path,
            backup_root=tmp_path,
            scope="unit",
            backup_id="../.env.20260607.bak",
            actor="alice",
        )
    except ValueError as exc:
        assert "备份 ID 无效" in str(exc)
    else:
        raise AssertionError("restore_config_backup should reject path traversal")
