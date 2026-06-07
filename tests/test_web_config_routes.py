import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
FastAPI = pytest.importorskip("fastapi").FastAPI

from web_app.routes import config as config_routes


def test_web_config_endpoint_returns_redacted_business_view(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "read_config", lambda: {
        "_env": {
            "ANTHROPIC_API_KEY": "sk-route-secret",
            "ANTHROPIC_BASE_URL": "https://route.example.test",
            "ANTHROPIC_MODEL": "route-model",
        },
        "_system": {
            "max_tokens": "16K",
            "allow_shared_ai_credentials": False,
        },
    })

    resp = client.get("/api/web-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai"]["api_key_configured"] is True
    assert data["ai"]["api_key_source"] == "global"
    assert "sk-route-secret" not in resp.text
    assert data["ai"]["base_url"] == {
        "value": "https://route.example.test",
        "source": "global",
    }
    assert data["ai"]["model"] == {"value": "route-model", "source": "global"}
    assert data["ai"]["max_tokens"] == {"value": "16K", "source": "global"}


def test_web_config_put_saves_and_returns_redacted_view(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    saved_payloads = []

    async def fake_save_web_config_to_dir(
        payload,
        target_dir,
        *,
        allow_shared_credentials_write=False,
        actor="",
        audit_root=None,
        backup_root=None,
        backup_scope="",
    ):
        saved_payloads.append({
            "payload": payload,
            "target_dir": target_dir,
            "allow_shared_credentials_write": allow_shared_credentials_write,
            "actor": actor,
            "audit_root": audit_root,
            "backup_root": backup_root,
            "backup_scope": backup_scope,
        })

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "save_web_config_to_dir", fake_save_web_config_to_dir)
    monkeypatch.setattr(config_routes, "read_config", lambda: {
        "_env": {
            "ANTHROPIC_API_KEY_ENC": "fernet:ciphertext",
            "ANTHROPIC_BASE_URL": "https://saved.example.test",
        },
        "_system": {
            "allow_shared_ai_credentials": True,
        },
    })

    resp = client.put("/api/web-config", json={
        "ai": {
            "api_key": "sk-new-secret",
            "base_url": {"value": "https://saved.example.test"},
            "allow_shared_ai_credentials": {"value": True},
        },
    })

    assert resp.status_code == 200
    assert saved_payloads == [{
        "payload": {
            "ai": {
                "api_key": "sk-new-secret",
                "base_url": {"value": "https://saved.example.test"},
                "allow_shared_ai_credentials": {"value": True},
            },
        },
        "target_dir": tmp_path,
        "allow_shared_credentials_write": True,
        "actor": "local-admin",
        "audit_root": tmp_path,
        "backup_root": tmp_path,
        "backup_scope": "global",
    }]
    assert "sk-new-secret" not in resp.text
    assert resp.json()["ai"]["api_key_configured"] is True


def test_web_config_backups_endpoint_uses_current_scope(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    calls = []

    def fake_list_config_backups(*, backup_root, scope):
        calls.append({"backup_root": backup_root, "scope": scope})
        return [{"id": ".env.20260607_120000_000001.bak", "file": ".env", "created_at": "2026-06-07T12:00:00", "size_bytes": 32}]

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "list_config_backups", fake_list_config_backups)

    resp = client.get("/api/web-config/backups")

    assert resp.status_code == 200
    assert calls == [{"backup_root": tmp_path, "scope": "user-alice"}]
    assert resp.json()["scope"] == {"mode": "remote", "username": "alice"}
    assert resp.json()["items"][0]["file"] == ".env"


def test_web_config_restore_restores_scope_and_returns_redacted_view(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    calls = []

    def fake_restore_config_backup(**kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "restore_config_backup", fake_restore_config_backup)
    monkeypatch.setattr(config_routes, "read_config", lambda: {
        "_env": {
            "ANTHROPIC_API_KEY": "sk-route-secret",
            "ANTHROPIC_MODEL": "restored-model",
        },
        "_system": {},
    })

    resp = client.post(
        "/api/web-config/backups/restore",
        json={"backup_id": ".env.20260607_120000_000001.bak"},
    )

    assert resp.status_code == 200
    assert calls == [{
        "target_dir": tmp_path,
        "backup_root": tmp_path,
        "scope": "global",
        "backup_id": ".env.20260607_120000_000001.bak",
        "actor": "local-admin",
        "audit_root": tmp_path,
    }]
    assert resp.json()["ai"]["model"] == {"value": "restored-model", "source": "global"}
    assert "sk-route-secret" not in resp.text


def test_web_config_restore_requires_backup_id(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)

    resp = client.post("/api/web-config/backups/restore", json={})

    assert resp.status_code == 400
    assert "backup_id" in resp.json()["detail"]
