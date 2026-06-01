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
