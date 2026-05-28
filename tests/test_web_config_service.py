from web_app.services import config_service


def test_remote_session_ttl_seconds_reads_system_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "config_dir", lambda: tmp_path)
    (tmp_path / "system_config.yaml").write_text(
        "remote_session_ttl_seconds: 120\n",
        encoding="utf-8",
    )

    assert config_service.remote_session_ttl_seconds() == 120


def test_remote_session_ttl_seconds_falls_back_for_invalid_value(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "config_dir", lambda: tmp_path)
    (tmp_path / "system_config.yaml").write_text(
        "remote_session_ttl_seconds: invalid\n",
        encoding="utf-8",
    )

    assert config_service.remote_session_ttl_seconds(default=60) == 60
