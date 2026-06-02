from pathlib import Path

from ai_gen_reimbursement_docs.auth import init_user_dir


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
