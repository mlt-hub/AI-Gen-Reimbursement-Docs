from pathlib import Path

from ai_gen_reimbursement_docs import auth
from ai_gen_reimbursement_docs.auth import (
    ADMIN_INITIAL_PASSWORD,
    ADMIN_USERNAME,
    create_invite,
    create_token,
    get_username_by_token,
    init_user_dir,
    verify_user,
)


def test_init_user_dir_copies_all_default_config_files(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    init_user_dir("alice")

    user_dir = tmp_path / ".ai-gen-reimbursement-docs" / "users" / "alice"
    assert (user_dir / ".env").exists()
    assert (user_dir / "system_config.yaml").exists()
    assert (user_dir / "fpa_config.yaml").exists()
    assert (user_dir / "domain_context.json").exists()
    assert (user_dir / "templates").is_dir()
    assert (user_dir / "tasks").is_dir()


def test_init_db_creates_builtin_admin(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert verify_user(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD) is True

    user_dir = tmp_path / ".ai-gen-reimbursement-docs" / "users" / ADMIN_USERNAME
    assert user_dir.is_dir()


def test_remember_me_token_survives_memory_clear(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    token = create_token(ADMIN_USERNAME, remember_me=True)
    auth._tokens.clear()

    assert get_username_by_token(token) == ADMIN_USERNAME


def test_create_invite_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    invite = create_invite(ADMIN_USERNAME)

    assert len(invite["code"]) == 16
    assert invite["max_uses"] == 1
    assert invite["used_count"] == 0
    assert invite["status"] == "active"
