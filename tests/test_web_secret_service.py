from web_app.services import secret_service


def test_encrypt_secret_falls_back_to_local_master_key(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_service, "_encrypt_with_dpapi", lambda value: (_ for _ in ()).throw(secret_service.SecretServiceError("no dpapi")))

    encrypted = secret_service.encrypt_secret("sk-secret-value", config_root=tmp_path)
    decrypted = secret_service.decrypt_secret(encrypted, config_root=tmp_path)

    assert encrypted.startswith("fernet:")
    assert "sk-secret-value" not in encrypted
    assert decrypted == "sk-secret-value"
    assert (tmp_path / "secrets" / "master.key").exists()


def test_decrypt_secret_rejects_unknown_format(tmp_path):
    try:
        secret_service.decrypt_secret("plain:sk-secret-value", config_root=tmp_path)
    except secret_service.SecretServiceError as exc:
        assert "Unsupported secret format" in str(exc)
    else:
        raise AssertionError("SecretServiceError was not raised")
