from pathlib import Path

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
FastAPI = pytest.importorskip("fastapi").FastAPI

from web_app.routes import config as config_routes


def test_legacy_config_endpoints_require_auth_in_remote_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_web_work_mode",
        lambda: "remote",
    )
    app = FastAPI()
    app.include_router(config_routes.router)
    client = TestClient(app)

    assert client.get("/api/config").status_code == 401
    assert client.get("/api/config-read").status_code == 401


def test_remote_config_read_is_limited_to_current_user_scope(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)
    user_dir = tmp_path / "users" / "alice"
    user_dir.mkdir(parents=True)
    (user_dir / ".env").write_text("ANTHROPIC_API_KEY=sk-user\n", encoding="utf-8")
    (user_dir / "system_config.yaml").write_text("max_tokens: 16K\n", encoding="utf-8")
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "business_rules.yaml").write_text("secret-rule: true\n", encoding="utf-8")

    monkeypatch.setattr(config_routes, "is_local_ip", lambda request: False)
    monkeypatch.setattr(config_routes, "user_config_dir", lambda username: user_dir)
    monkeypatch.setattr(config_routes, "config_dir", lambda: global_dir)

    resp = client.get("/api/config-read")

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert "sk-user" not in data["env"]
    assert data["system_config"] == "max_tokens: 16K\n"
    assert data["business_rules"] == ""
    assert data["global_system"] == ""
    assert data["global_env"] == ""
