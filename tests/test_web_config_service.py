import asyncio

from web_app.services import config_service


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
