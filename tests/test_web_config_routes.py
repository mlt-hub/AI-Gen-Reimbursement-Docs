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

    async def fake_save_web_config_to_dir(payload, target_dir, *, allow_shared_credentials_write=False):
        saved_payloads.append({
            "payload": payload,
            "target_dir": target_dir,
            "allow_shared_credentials_write": allow_shared_credentials_write,
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
    }]
    assert "sk-new-secret" not in resp.text
    assert resp.json()["ai"]["api_key_configured"] is True
