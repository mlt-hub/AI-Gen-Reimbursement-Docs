from pathlib import Path
import sqlite3

from ai_gen_reimbursement_docs import auth
from ai_gen_reimbursement_docs.auth import (
    ADMIN_INITIAL_PASSWORD,
    ADMIN_USERNAME,
    change_password,
    create_invite,
    create_token,
    get_username_by_token,
    init_user_dir,
    user_must_change_password,
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
    assert user_must_change_password(ADMIN_USERNAME) is True

    user_dir = tmp_path / ".ai-gen-reimbursement-docs" / "users" / ADMIN_USERNAME
    assert user_dir.is_dir()


def test_admin_password_change_clears_initial_password_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert verify_user(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD) is True
    assert change_password(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD, "changed-secret") is True

    assert verify_user(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD) is False
    assert verify_user(ADMIN_USERNAME, "changed-secret") is True
    assert user_must_change_password(ADMIN_USERNAME) is False


def test_init_db_backfills_development_user_schema(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db = tmp_path / ".ai-gen-reimbursement-docs" / "users.db"
    db.parent.mkdir(parents=True)
    pw_hash, salt = auth._hash_password(ADMIN_INITIAL_PASSWORD)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO users (username, password, salt) VALUES (?, ?, ?)",
            (ADMIN_USERNAME, pw_hash, salt),
        )
        conn.commit()

    assert verify_user(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD) is True
    assert user_must_change_password(ADMIN_USERNAME) is True

    with sqlite3.connect(str(db)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        role = conn.execute("SELECT role FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()[0]

    assert {"role", "disabled", "must_change_password"} <= columns
    assert role == "admin"


def test_remember_me_token_survives_memory_clear(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    token = create_token(ADMIN_USERNAME, remember_me=True)
    auth._tokens.clear()

    assert get_username_by_token(token) == ADMIN_USERNAME


def test_change_password_revokes_existing_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    token = create_token(ADMIN_USERNAME, remember_me=True)
    assert get_username_by_token(token) == ADMIN_USERNAME

    assert change_password(ADMIN_USERNAME, ADMIN_INITIAL_PASSWORD, "changed-secret") is True

    auth._tokens.clear()
    assert get_username_by_token(token) is None


def test_disabled_user_token_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    token = create_token(ADMIN_USERNAME, remember_me=True)
    db = tmp_path / ".ai-gen-reimbursement-docs" / "users.db"
    with sqlite3.connect(str(db)) as conn:
        conn.execute("UPDATE users SET disabled = 1 WHERE username = ?", (ADMIN_USERNAME,))
        conn.commit()

    auth._tokens.clear()
    assert get_username_by_token(token) is None


def test_create_invite_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    invite = create_invite(ADMIN_USERNAME)

    assert len(invite["code"]) == 16
    assert invite["max_uses"] == 1
    assert invite["used_count"] == 0
    assert invite["status"] == "active"
