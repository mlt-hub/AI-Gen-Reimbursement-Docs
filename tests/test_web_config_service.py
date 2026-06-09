import asyncio
import json
import time
from pathlib import Path

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


def test_atomic_write_text_replaces_existing_file(tmp_path):
    target = tmp_path / ".env"
    target.write_text("ANTHROPIC_MODEL=old\n", encoding="utf-8")

    config_service._atomic_write_text(target, "ANTHROPIC_MODEL=new\n")

    assert target.read_text(encoding="utf-8") == "ANTHROPIC_MODEL=new\n"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_text_keeps_existing_file_when_temp_write_fails(monkeypatch, tmp_path):
    target = tmp_path / ".env"
    target.write_text("ANTHROPIC_MODEL=old\n", encoding="utf-8")

    class FailingHandle:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, text):
            raise OSError("disk full")

        def flush(self):
            pass

        def fileno(self):
            return 0

    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: FailingHandle())

    try:
        config_service._atomic_write_text(target, "ANTHROPIC_MODEL=new\n")
    except OSError as exc:
        assert "disk full" in str(exc)
    else:
        raise AssertionError("_atomic_write_text should propagate write failure")

    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "ANTHROPIC_MODEL=old\n"


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
    (backup_dir / "business_rules.yaml.20260607_120000_000001.bak").write_text("cfp_formula: old\n", encoding="utf-8")

    items = config_service.list_config_backups(backup_root=tmp_path, scope="unit")

    assert {item["file"] for item in items} == {".env", "system_config.yaml", "business_rules.yaml"}
    assert {item["id"] for item in items} == {
        ".env.20260607_120000_000001.bak",
        "system_config.yaml.20260607_120000_000001.bak",
        "business_rules.yaml.20260607_120000_000001.bak",
    }
    assert all("size_bytes" in item for item in items)


def test_build_config_backup_diff_masks_env_secrets(tmp_path):
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-current-secret\nANTHROPIC_MODEL=current\n",
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups" / "config" / "unit"
    backup_dir.mkdir(parents=True)
    backup = backup_dir / ".env.20260607_120000_000001.bak"
    backup.write_text(
        "ANTHROPIC_API_KEY=sk-backup-secret\nANTHROPIC_MODEL=old\n",
        encoding="utf-8",
    )

    diff = config_service.build_config_backup_diff(
        target_dir=tmp_path,
        backup_root=tmp_path,
        scope="unit",
        backup_id=backup.name,
    )

    assert diff["file"] == ".env"
    assert diff["has_changes"] is True
    assert "sk-current-secret" not in diff["diff"]
    assert "sk-backup-secret" not in diff["diff"]
    assert "ANTHROPIC_API_KEY=***" in diff["diff"]
    assert "-ANTHROPIC_MODEL=old" in diff["diff"]
    assert "+ANTHROPIC_MODEL=current" in diff["diff"]


def test_restore_config_backup_supports_advanced_config_files(tmp_path):
    target = tmp_path / "fpa_config.yaml"
    target.write_text("default-profile: current\n", encoding="utf-8")
    backup_dir = tmp_path / "backups" / "config" / "unit"
    backup_dir.mkdir(parents=True)
    backup = backup_dir / "fpa_config.yaml.20260607_120000_000001.bak"
    backup.write_text("default-profile: restored\n", encoding="utf-8")

    config_service.restore_config_backup(
        target_dir=tmp_path,
        backup_root=tmp_path,
        scope="unit",
        backup_id=backup.name,
        actor="local-admin",
        audit_root=tmp_path,
    )

    assert target.read_text(encoding="utf-8") == "default-profile: restored\n"
    current_backups = list(backup_dir.glob("fpa_config.yaml.*.bak"))
    assert len(current_backups) == 2
    assert any("default-profile: current" in path.read_text(encoding="utf-8") for path in current_backups)


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


def test_build_config_export_package_excludes_secret_env_values(tmp_path):
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-secret\n"
        "ANTHROPIC_API_KEY_ENC=fernet:ciphertext\n"
        "ANTHROPIC_BASE_URL=https://example.test\n",
        encoding="utf-8",
    )
    (tmp_path / "system_config.yaml").write_text("max_tokens: 16K\n", encoding="utf-8")
    (tmp_path / "domain_context.json").write_text(
        json.dumps({
            "system_boundary": "",
            "internal_data_groups": [],
            "external_data_groups": [],
            "external_services": [],
        }),
        encoding="utf-8",
    )

    package = config_service.build_config_export_package(target_dir=tmp_path)

    assert package["version"] == 1
    assert "ANTHROPIC_BASE_URL=https://example.test" in package["files"][".env"]
    assert "ANTHROPIC_API_KEY" not in package["files"][".env"]
    assert "sk-secret" not in json.dumps(package, ensure_ascii=False)
    assert "fernet:ciphertext" not in json.dumps(package, ensure_ascii=False)
    assert "domain_context.json" in package["files"]


def test_import_config_package_validates_all_files_backs_up_and_audits(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_BASE_URL=https://old.example.test\n", encoding="utf-8")
    (tmp_path / "system_config.yaml").write_text("max_tokens: 8K\n", encoding="utf-8")

    imported = config_service.import_config_package(
        package={
            "version": 1,
            "files": {
                ".env": "ANTHROPIC_BASE_URL=https://new.example.test\n",
                "system_config.yaml": "max_tokens: 16K\n",
                "domain_context.json": json.dumps({
                    "system_boundary": "边界",
                    "internal_data_groups": [],
                    "external_data_groups": [],
                    "external_services": [],
                }, ensure_ascii=False),
            },
        },
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert imported["ok"] is True
    assert imported["imported"] == [".env", "domain_context.json", "system_config.yaml"]
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "ANTHROPIC_BASE_URL=https://new.example.test\n"
    assert (tmp_path / "system_config.yaml").read_text(encoding="utf-8") == "max_tokens: 16K\n"
    assert (tmp_path / "domain_context.json").exists()
    assert sorted(imported["backed_up"]) == [".env", "system_config.yaml"]
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == [".env", "domain_context.json", "system_config.yaml"]
    assert record["changed_fields"] == ["config_package"]
    assert record["result"] == "success"


def test_import_config_package_rejects_secret_env_without_overwrite(tmp_path):
    target = tmp_path / ".env"
    target.write_text("ANTHROPIC_BASE_URL=https://old.example.test\n", encoding="utf-8")

    try:
        config_service.import_config_package(
            package={
                "version": 1,
                "files": {
                    ".env": "ANTHROPIC_API_KEY=sk-secret\n",
                },
            },
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "不能包含 API Key" in str(exc)
    else:
        raise AssertionError("import_config_package should reject secret env values")

    assert target.read_text(encoding="utf-8") == "ANTHROPIC_BASE_URL=https://old.example.test\n"
    assert not (tmp_path / "backups" / "config" / "unit").exists()


def test_list_and_read_advanced_config_files(tmp_path):
    (tmp_path / "business_rules.yaml").write_text("cfp:\n  enabled: true\n", encoding="utf-8")

    items = config_service.list_advanced_config_files(target_dir=tmp_path)
    read = config_service.read_advanced_config_file(file_id="business_rules", target_dir=tmp_path)

    business_item = next(item for item in items if item["id"] == "business_rules")
    assert business_item["file"] == "business_rules.yaml"
    assert business_item["format"] == "yaml"
    assert business_item["exists"] is True
    assert read["content"] == "cfp:\n  enabled: true\n"


def test_validate_advanced_config_content_rejects_yaml_syntax_error():
    try:
        config_service.validate_advanced_config_content(
            file_id="business_rules",
            content="cfp:\n  - broken: [\n",
        )
    except config_service.AdvancedConfigError as exc:
        assert "YAML 语法错误" in str(exc)
    else:
        raise AssertionError("validate_advanced_config_content should reject invalid YAML")


def test_validate_advanced_fpa_judgement_rules_requires_non_empty_rules():
    try:
        config_service.validate_advanced_config_content(
            file_id="fpa_judgement_rules",
            content="judgement_rules: []\n",
        )
    except config_service.AdvancedConfigError as exc:
        assert "judgement_rules 必须是非空字符串列表" in str(exc)
    else:
        raise AssertionError("validate_advanced_config_content should reject empty judgement rules")


def test_save_advanced_config_file_backs_up_and_audits_success(tmp_path):
    target = tmp_path / "business_rules.yaml"
    target.write_text("cfp:\n  enabled: false\n", encoding="utf-8")

    saved = config_service.save_advanced_config_file(
        file_id="business_rules",
        content="cfp:\n  enabled: true\n",
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["id"] == "business_rules"
    assert saved["backed_up"] == ["business_rules.yaml"]
    assert target.read_text(encoding="utf-8") == "cfp:\n  enabled: true\n"
    backups = list((tmp_path / "backups" / "config" / "unit").glob("business_rules.yaml.*.bak"))
    assert len(backups) == 1
    assert "enabled: false" in backups[0].read_text(encoding="utf-8")
    audit_text = (tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8")
    record = json.loads(audit_text.splitlines()[-1])
    assert record["actor"] == "local-admin"
    assert record["files"] == ["business_rules.yaml"]
    assert record["changed_fields"] == ["advanced_config.business_rules"]
    assert record["result"] == "success"


def test_save_advanced_config_file_validation_failure_does_not_overwrite_or_backup(tmp_path):
    target = tmp_path / "fpa_judgement_rules.yaml"
    target.write_text("judgement_rules:\n  - 规则一\n", encoding="utf-8")

    try:
        config_service.save_advanced_config_file(
            file_id="fpa_judgement_rules",
            content="judgement_rules: []\n",
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "judgement_rules 必须是非空字符串列表" in str(exc)
    else:
        raise AssertionError("save_advanced_config_file should reject invalid content")

    assert target.read_text(encoding="utf-8") == "judgement_rules:\n  - 规则一\n"
    assert not (tmp_path / "backups" / "config" / "unit").exists()
    audit_text = (tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8")
    record = json.loads(audit_text.splitlines()[-1])
    assert record["files"] == ["fpa_judgement_rules.yaml"]
    assert record["changed_fields"] == ["advanced_config.fpa_judgement_rules"]
    assert record["result"] == "validation_failed"


def _write_minimal_fpa_config(path: Path) -> None:
    path.write_text(
        """
default-profile: strict_fpa
judgement_rules_source: config
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
profiles:
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_cr
    system_prompt: strict_sp
    user_prompt: strict_up
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_rs
    core_rules: unified_cr
    system_prompt: unified_sp
    user_prompt: unified_up
core_rules:
  strict_cr: strict core
  unified_cr: unified core
system_prompt_sets:
  strict_sp: strict system
  unified_sp: unified system
user_prompt_sets:
  strict_up: ${core_rules} ${judgement_rules} ${payload_json}
  unified_up: ${core_rules} ${judgement_rules} ${payload_json}
rule_sets:
  strict_fpa_rs: {}
  unified_rs:
    extends: strict_fpa_rs
""".lstrip(),
        encoding="utf-8",
    )


def test_build_fpa_strategy_settings_view_reads_profiles_and_rule_sets(tmp_path):
    _write_minimal_fpa_config(tmp_path / "fpa_config.yaml")

    view = config_service.build_fpa_strategy_settings_view(target_dir=tmp_path)

    assert view["default_profile"] == "strict_fpa"
    assert {item["name"] for item in view["profiles"]} == {"strict_fpa", "unified_ui"}
    strict = next(item for item in view["profiles"] if item["name"] == "strict_fpa")
    assert strict["strategy"] == "ai_first"
    assert strict["rule_set"] == "strict_fpa_rs"
    assert strict["prompt_diagnostics"]["profile"] == "strict_fpa"
    assert strict["prompt_diagnostics"]["ok"] is True
    assert strict["prompt_diagnostics"]["calculation_explanation_rules"]["referenced"] is False
    assert any("未引用 calculation_explanation_rules" in item for item in strict["prompt_diagnostics"]["warnings"])
    assert {item["name"] for item in view["rule_sets"]} == {"strict_fpa_rs", "unified_rs"}
    assert {item["profile"] for item in view["prompt_diagnostics"]} == {"strict_fpa", "unified_ui"}


def test_save_fpa_strategy_settings_validates_backs_up_and_audits(tmp_path):
    _write_minimal_fpa_config(tmp_path / "fpa_config.yaml")

    saved = config_service.save_fpa_strategy_settings(
        payload={
            "default_profile": "unified_ui",
            "profiles": [
                {"name": "strict_fpa", "strategy": "rules_only", "rule_set": "strict_fpa_rs"},
                {"name": "unified_ui", "strategy": "ai_first", "rule_set": "unified_rs"},
            ],
        },
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["default_profile"] == "unified_ui"
    strict = next(item for item in saved["profiles"] if item["name"] == "strict_fpa")
    assert strict["strategy"] == "rules_only"
    backups = list((tmp_path / "backups" / "config" / "unit").glob("fpa_config.yaml.*.bak"))
    assert len(backups) == 1
    assert "default-profile: strict_fpa" in backups[0].read_text(encoding="utf-8")
    audit_text = (tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8")
    record = json.loads(audit_text.splitlines()[-1])
    assert record["files"] == ["fpa_config.yaml"]
    assert record["result"] == "success"
    assert "fpa_strategy.default_profile" in record["changed_fields"]
    assert "fpa_strategy.profiles.strict_fpa.strategy" in record["changed_fields"]


def test_save_fpa_strategy_settings_validation_failure_does_not_overwrite(tmp_path):
    path = tmp_path / "fpa_config.yaml"
    _write_minimal_fpa_config(path)
    before = path.read_text(encoding="utf-8")

    try:
        config_service.save_fpa_strategy_settings(
            payload={
                "default_profile": "strict_fpa",
                "profiles": [
                    {"name": "strict_fpa", "strategy": "ai_first", "rule_set": "missing_rs"},
                ],
            },
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "rule_set 指向不存在" in str(exc)
    else:
        raise AssertionError("save_fpa_strategy_settings should reject missing rule_set")

    assert path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "backups" / "config" / "unit").exists()
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == ["fpa_config.yaml"]
    assert record["result"] == "validation_failed"


def test_run_fpa_prompt_sample_preview_skips_ai_when_prompt_has_error(monkeypatch, tmp_path):
    path = tmp_path / "fpa_config.yaml"
    _write_minimal_fpa_config(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("${payload_json}", ""), encoding="utf-8")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fail_if_called)

    result = config_service.run_fpa_prompt_sample_preview(
        profile_name="strict_fpa",
        target_dir=tmp_path,
    )

    assert result["ai_called"] is False
    assert result["parse_ok"] is False
    assert result["prompt_diagnostics"]["errors"]
    assert "prompt diagnostics" in result["warnings"][0]


def test_run_fpa_prompt_sample_preview_normalizes_mock_ai_rows(monkeypatch, tmp_path):
    _write_minimal_fpa_config(tmp_path / "fpa_config.yaml")
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-test\n"
        "ANTHROPIC_MODEL=test-model\n"
        "ANTHROPIC_BASE_URL=https://api.example.test\n",
        encoding="utf-8",
    )

    def fake_call_llm(*args, **kwargs):
        return (
            json.dumps({
                "rows": [{
                    "name": "新增客户",
                    "type": "EI",
                    "type_reason": "维护业务数据的外部输入。",
                    "classification_basis_index": 1,
                    "explanation": (
                        "来源场景：【后台】业务管理-客户管理-客户资料维护-新增客户\n"
                        "业务数据：客户名称、证件号码、联系电话。\n"
                        "业务规则：保存客户资料。\n"
                        "计算说明：作为 EI 纳入 FPA 功能点计量。"
                    ),
                    "source_process_ids": ["P1"],
                }]
            }, ensure_ascii=False),
            "",
        )

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = config_service.run_fpa_prompt_sample_preview(
        profile_name="strict_fpa",
        target_dir=tmp_path,
    )

    assert result["ai_called"] is True
    assert result["parse_ok"] is True
    assert result["model"] == "test-model"
    assert result["api_key_source"] == "global"
    assert result["parsed_rows"][0]["type"] == "EI"
    row = result["normalized_rows"][0]
    assert row["新增/修改功能点"] == "【后台】业务管理-客户管理-客户资料维护-新增客户"
    assert row["类型"] == "EI"
    assert row["计算依据归类"] == "维护业务数据的外部输入，按 EI 识别。"
    assert result["quality_warnings"] == []
    assert any(hit["rule_id"] == "postprocess.ai_type_validation" for hit in result["rule_hits"])


def test_run_fpa_prompt_sample_preview_returns_parse_error(monkeypatch, tmp_path):
    _write_minimal_fpa_config(tmp_path / "fpa_config.yaml")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")

    def fake_call_llm(*args, **kwargs):
        return "not json", ""

    monkeypatch.setattr("ai_gen_reimbursement_docs.gen_fpa._call_llm", fake_call_llm)

    result = config_service.run_fpa_prompt_sample_preview(
        profile_name="strict_fpa",
        target_dir=tmp_path,
    )

    assert result["ai_called"] is True
    assert result["parse_ok"] is False
    assert result["raw_response"] == "not json"
    assert "Expecting value" in result["error"]
    assert result["normalized_rows"] == []


def test_run_fpa_prompt_sample_preview_requires_api_key(tmp_path):
    _write_minimal_fpa_config(tmp_path / "fpa_config.yaml")

    try:
        config_service.run_fpa_prompt_sample_preview(
            profile_name="strict_fpa",
            target_dir=tmp_path,
        )
    except config_service.AdvancedConfigError as exc:
        assert "API Key" in str(exc)
    else:
        raise AssertionError("expected AdvancedConfigError")


def test_build_fpa_judgement_rules_view_reads_rules(tmp_path):
    (tmp_path / "fpa_judgement_rules.yaml").write_text(
        "judgement_rules:\n  - 规则一\n  - 规则二\n",
        encoding="utf-8",
    )

    view = config_service.build_fpa_judgement_rules_view(target_dir=tmp_path)

    assert view == {"rules": ["规则一", "规则二"], "exists": True}


def test_save_fpa_judgement_rules_backs_up_and_audits(tmp_path):
    target = tmp_path / "fpa_judgement_rules.yaml"
    target.write_text("judgement_rules:\n  - 旧规则\n", encoding="utf-8")

    saved = config_service.save_fpa_judgement_rules(
        rules=["新规则一", " 新规则二 "],
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["rules"] == ["新规则一", "新规则二"]
    assert saved["backed_up"] == ["fpa_judgement_rules.yaml"]
    assert "旧规则" not in target.read_text(encoding="utf-8")
    backups = list((tmp_path / "backups" / "config" / "unit").glob("fpa_judgement_rules.yaml.*.bak"))
    assert len(backups) == 1
    assert "旧规则" in backups[0].read_text(encoding="utf-8")
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == ["fpa_judgement_rules.yaml"]
    assert record["changed_fields"] == ["fpa_judgement_rules"]
    assert record["result"] == "success"


def test_save_fpa_judgement_rules_rejects_empty_rules_without_overwrite(tmp_path):
    target = tmp_path / "fpa_judgement_rules.yaml"
    target.write_text("judgement_rules:\n  - 原规则\n", encoding="utf-8")

    try:
        config_service.save_fpa_judgement_rules(
            rules=["  "],
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "judgement_rules 必须是非空字符串列表" in str(exc)
    else:
        raise AssertionError("save_fpa_judgement_rules should reject empty rules")

    assert target.read_text(encoding="utf-8") == "judgement_rules:\n  - 原规则\n"
    assert not (tmp_path / "backups" / "config" / "unit").exists()
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["result"] == "validation_failed"


def test_build_business_rules_view_reads_cfp_formula(tmp_path):
    (tmp_path / "business_rules.yaml").write_text(
        "cfp_formula: '=IF(L{row}=\"新增\",1,0)'\nother_rule: keep\n",
        encoding="utf-8",
    )

    view = config_service.build_business_rules_view(target_dir=tmp_path)

    assert view["exists"] is True
    assert view["cfp_formula"] == '=IF(L{row}="新增",1,0)'


def test_save_business_rules_preserves_unknown_keys_backs_up_and_audits(tmp_path):
    target = tmp_path / "business_rules.yaml"
    target.write_text(
        "cfp_formula: old\nother_rule: keep\n",
        encoding="utf-8",
    )

    saved = config_service.save_business_rules(
        cfp_formula='=IF(L{row}="复用",1/3,1)',
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["cfp_formula"] == '=IF(L{row}="复用",1/3,1)'
    assert saved["backed_up"] == ["business_rules.yaml"]
    text = target.read_text(encoding="utf-8")
    assert "other_rule: keep" in text
    assert "old" not in text
    backups = list((tmp_path / "backups" / "config" / "unit").glob("business_rules.yaml.*.bak"))
    assert len(backups) == 1
    assert "cfp_formula: old" in backups[0].read_text(encoding="utf-8")
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == ["business_rules.yaml"]
    assert record["changed_fields"] == ["business_rules.cfp_formula"]
    assert record["result"] == "success"


def test_save_business_rules_rejects_blank_formula_without_overwrite(tmp_path):
    target = tmp_path / "business_rules.yaml"
    target.write_text("cfp_formula: old\n", encoding="utf-8")

    try:
        config_service.save_business_rules(
            cfp_formula=" ",
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "CFP 计算公式不能为空" in str(exc)
    else:
        raise AssertionError("save_business_rules should reject blank cfp_formula")

    assert target.read_text(encoding="utf-8") == "cfp_formula: old\n"
    assert not (tmp_path / "backups" / "config" / "unit").exists()
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["result"] == "validation_failed"


def test_build_ai_prompt_settings_view_reads_prompt_scenes(tmp_path):
    (tmp_path / "ai_system_prompts_config.yaml").write_text(
        "ai_prompts:\n"
        "  metadata_gen:\n"
        "    scene: 元数据生成\n"
        "    system: 系统提示词\n"
        "    examples: 示例\n",
        encoding="utf-8",
    )

    view = config_service.build_ai_prompt_settings_view(target_dir=tmp_path)

    assert view["exists"] is True
    assert view["prompts"] == [{
        "name": "metadata_gen",
        "scene": "元数据生成",
        "system": "系统提示词",
        "examples": "示例",
    }]


def test_save_ai_prompt_settings_preserves_unknown_keys_backs_up_and_audits(tmp_path):
    target = tmp_path / "ai_system_prompts_config.yaml"
    target.write_text(
        "version: 1\n"
        "ai_prompts:\n"
        "  metadata_gen:\n"
        "    scene: old\n"
        "    system: old system\n",
        encoding="utf-8",
    )

    saved = config_service.save_ai_prompt_settings(
        prompts=[{
            "name": "metadata_gen",
            "scene": "元数据生成",
            "system": "new system",
            "examples": "new examples",
        }],
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["prompts"][0]["system"] == "new system"
    assert saved["backed_up"] == ["ai_system_prompts_config.yaml"]
    text = target.read_text(encoding="utf-8")
    assert "version: 1" in text
    assert "old system" not in text
    backups = list((tmp_path / "backups" / "config" / "unit").glob("ai_system_prompts_config.yaml.*.bak"))
    assert len(backups) == 1
    assert "old system" in backups[0].read_text(encoding="utf-8")
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == ["ai_system_prompts_config.yaml"]
    assert record["changed_fields"] == ["ai_prompts"]
    assert record["result"] == "success"


def test_save_ai_prompt_settings_rejects_blank_prompt_name_without_overwrite(tmp_path):
    target = tmp_path / "ai_system_prompts_config.yaml"
    target.write_text(
        "ai_prompts:\n  metadata_gen:\n    system: old\n",
        encoding="utf-8",
    )

    try:
        config_service.save_ai_prompt_settings(
            prompts=[{"name": " ", "system": "new"}],
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "Prompt 场景名称不能为空" in str(exc)
    else:
        raise AssertionError("save_ai_prompt_settings should reject blank prompt name")

    assert target.read_text(encoding="utf-8") == "ai_prompts:\n  metadata_gen:\n    system: old\n"
    assert not (tmp_path / "backups" / "config" / "unit").exists()


def test_build_domain_context_view_reads_structured_context(tmp_path):
    (tmp_path / "domain_context.json").write_text(
        json.dumps({
            "system_boundary": "只覆盖报账文档生成。",
            "internal_data_groups": [{"name": "报账单", "aliases": ["单据"], "description": "本系统维护"}],
            "external_data_groups": [{"name": "人员信息", "source": "人事系统"}],
            "external_services": [{"name": "审批平台"}],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    view = config_service.build_domain_context_view(target_dir=tmp_path)

    assert view["exists"] is True
    assert view["system_boundary"] == "只覆盖报账文档生成。"
    assert view["internal_data_groups"][0]["aliases"] == ["单据"]
    assert view["external_data_groups"][0]["source"] == "人事系统"


def test_save_domain_context_settings_preserves_unknown_keys_backs_up_and_audits(tmp_path):
    target = tmp_path / "domain_context.json"
    target.write_text(
        json.dumps({
            "version": 1,
            "system_boundary": "old",
            "internal_data_groups": [],
            "external_data_groups": [],
            "external_services": [],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    saved = config_service.save_domain_context_settings(
        payload={
            "system_boundary": "new boundary",
            "internal_data_groups": [{"name": "报账单", "aliases": ["单据"]}],
            "external_data_groups": [{"name": "人员信息", "source": "人事系统"}],
            "external_services": [{"name": "审批平台", "description": "外部审批"}],
        },
        target_dir=tmp_path,
        actor="local-admin",
        audit_root=tmp_path,
        backup_root=tmp_path,
        backup_scope="unit",
    )

    assert saved["system_boundary"] == "new boundary"
    assert saved["backed_up"] == ["domain_context.json"]
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["internal_data_groups"][0]["name"] == "报账单"
    backups = list((tmp_path / "backups" / "config" / "unit").glob("domain_context.json.*.bak"))
    assert len(backups) == 1
    assert "old" in backups[0].read_text(encoding="utf-8")
    record = json.loads((tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["files"] == ["domain_context.json"]
    assert record["changed_fields"] == ["domain_context"]
    assert record["result"] == "success"


def test_save_domain_context_settings_rejects_missing_external_source_without_overwrite(tmp_path):
    target = tmp_path / "domain_context.json"
    original = json.dumps({
        "system_boundary": "old",
        "internal_data_groups": [],
        "external_data_groups": [],
        "external_services": [],
    }, ensure_ascii=False)
    target.write_text(original, encoding="utf-8")

    try:
        config_service.save_domain_context_settings(
            payload={
                "system_boundary": "new",
                "internal_data_groups": [],
                "external_data_groups": [{"name": "人员信息"}],
                "external_services": [],
            },
            target_dir=tmp_path,
            actor="local-admin",
            audit_root=tmp_path,
            backup_root=tmp_path,
            backup_scope="unit",
        )
    except config_service.AdvancedConfigError as exc:
        assert "来源不能为空" in str(exc)
    else:
        raise AssertionError("save_domain_context_settings should reject missing external source")

    assert target.read_text(encoding="utf-8") == original
    assert not (tmp_path / "backups" / "config" / "unit").exists()
