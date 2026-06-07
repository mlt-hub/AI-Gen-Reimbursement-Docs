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


def test_web_config_files_endpoint_lists_local_advanced_configs(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    (tmp_path / "business_rules.yaml").write_text("cfp:\n  enabled: true\n", encoding="utf-8")

    resp = client.get("/api/web-config/files")

    assert resp.status_code == 200
    assert resp.json()["scope"] == {"mode": "local", "username": ""}
    items = {item["id"]: item for item in resp.json()["items"]}
    assert items["business_rules"]["exists"] is True
    assert items["fpa_config"]["file"] == "fpa_config.yaml"


def test_web_config_file_validate_returns_400_without_saving(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)

    resp = client.post(
        "/api/web-config/files/fpa_judgement_rules/validate",
        json={"content": "judgement_rules: []\n"},
    )

    assert resp.status_code == 400
    assert "judgement_rules 必须是非空字符串列表" in resp.json()["detail"]
    assert not (tmp_path / "fpa_judgement_rules.yaml").exists()


def test_web_config_file_put_saves_valid_content_and_redacts_no_values(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    (tmp_path / "business_rules.yaml").write_text("cfp:\n  enabled: false\n", encoding="utf-8")

    resp = client.put(
        "/api/web-config/files/business_rules",
        json={"content": "cfp:\n  enabled: true\n"},
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == "business_rules"
    assert resp.json()["backed_up"] == ["business_rules.yaml"]
    assert (tmp_path / "business_rules.yaml").read_text(encoding="utf-8") == "cfp:\n  enabled: true\n"
    assert "enabled: false" not in (tmp_path / "audit" / "config_changes.jsonl").read_text(encoding="utf-8")


def test_web_config_files_reject_remote_user(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)

    resp = client.get("/api/web-config/files")

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]


def test_web_config_fpa_strategy_endpoint_reads_local_settings(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "build_fpa_strategy_settings_view", lambda *, target_dir: {
        "default_profile": "strict_fpa",
        "profiles": [{"name": "strict_fpa", "strategy": "ai_first", "rule_set": "strict_fpa_rs"}],
        "rule_sets": [{"name": "strict_fpa_rs", "extends": ""}],
    })

    resp = client.get("/api/web-config/fpa-strategy")

    assert resp.status_code == 200
    assert resp.json()["default_profile"] == "strict_fpa"
    assert resp.json()["profiles"][0]["rule_set"] == "strict_fpa_rs"


def test_web_config_fpa_strategy_put_saves_local_settings(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    calls = []

    def fake_save_fpa_strategy_settings(**kwargs):
        calls.append(kwargs)
        return {"default_profile": "unified_ui", "profiles": [], "rule_sets": [], "backed_up": ["fpa_config.yaml"]}

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "save_fpa_strategy_settings", fake_save_fpa_strategy_settings)

    payload = {
        "default_profile": "unified_ui",
        "profiles": [{"name": "strict_fpa", "strategy": "rules_only", "rule_set": "strict_fpa_rs"}],
    }
    resp = client.put("/api/web-config/fpa-strategy", json=payload)

    assert resp.status_code == 200
    assert resp.json()["backed_up"] == ["fpa_config.yaml"]
    assert calls == [{
        "payload": payload,
        "target_dir": tmp_path,
        "actor": "local-admin",
        "audit_root": tmp_path,
        "backup_root": tmp_path,
        "backup_scope": "global",
    }]


def test_web_config_fpa_strategy_rejects_remote_user(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)

    resp = client.put("/api/web-config/fpa-strategy", json={"profiles": []})

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]


def test_web_config_fpa_judgement_rules_endpoint_reads_local_rules(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "build_fpa_judgement_rules_view", lambda *, target_dir: {
        "rules": ["规则一", "规则二"],
        "exists": True,
    })

    resp = client.get("/api/web-config/fpa-judgement-rules")

    assert resp.status_code == 200
    assert resp.json()["rules"] == ["规则一", "规则二"]


def test_web_config_fpa_judgement_rules_put_saves_local_rules(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    calls = []

    def fake_save_fpa_judgement_rules(**kwargs):
        calls.append(kwargs)
        return {"rules": ["规则一"], "exists": True, "backed_up": ["fpa_judgement_rules.yaml"]}

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "save_fpa_judgement_rules", fake_save_fpa_judgement_rules)

    resp = client.put("/api/web-config/fpa-judgement-rules", json={"rules": ["规则一"]})

    assert resp.status_code == 200
    assert resp.json()["backed_up"] == ["fpa_judgement_rules.yaml"]
    assert calls == [{
        "rules": ["规则一"],
        "target_dir": tmp_path,
        "actor": "local-admin",
        "audit_root": tmp_path,
        "backup_root": tmp_path,
        "backup_scope": "global",
    }]


def test_web_config_fpa_judgement_rules_rejects_remote_user(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)

    resp = client.put("/api/web-config/fpa-judgement-rules", json={"rules": ["规则一"]})

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]


def test_web_config_business_rules_endpoint_reads_local_rules(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "build_business_rules_view", lambda *, target_dir: {
        "cfp_formula": "FORMULA",
        "exists": True,
    })

    resp = client.get("/api/web-config/business-rules")

    assert resp.status_code == 200
    assert resp.json()["cfp_formula"] == "FORMULA"


def test_web_config_business_rules_put_saves_local_rules(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    calls = []

    def fake_save_business_rules(**kwargs):
        calls.append(kwargs)
        return {"cfp_formula": "FORMULA", "exists": True, "backed_up": ["business_rules.yaml"]}

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "save_business_rules", fake_save_business_rules)

    resp = client.put("/api/web-config/business-rules", json={"cfp_formula": "FORMULA"})

    assert resp.status_code == 200
    assert resp.json()["backed_up"] == ["business_rules.yaml"]
    assert calls == [{
        "cfp_formula": "FORMULA",
        "target_dir": tmp_path,
        "actor": "local-admin",
        "audit_root": tmp_path,
        "backup_root": tmp_path,
        "backup_scope": "global",
    }]


def test_web_config_business_rules_rejects_remote_user(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)

    resp = client.put("/api/web-config/business-rules", json={"cfp_formula": "FORMULA"})

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]


def test_web_config_ai_prompts_endpoint_reads_local_prompts(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "build_ai_prompt_settings_view", lambda *, target_dir: {
        "prompts": [{
            "name": "metadata_gen",
            "scene": "元数据生成",
            "system": "SYSTEM",
            "examples": "EXAMPLES",
        }],
        "exists": True,
    })

    resp = client.get("/api/web-config/ai-prompts")

    assert resp.status_code == 200
    assert resp.json()["prompts"][0]["name"] == "metadata_gen"
    assert resp.json()["prompts"][0]["system"] == "SYSTEM"


def test_web_config_ai_prompts_put_saves_local_prompts(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: ""
    client = TestClient(app)

    calls = []

    def fake_save_ai_prompt_settings(**kwargs):
        calls.append(kwargs)
        return {"prompts": kwargs["prompts"], "exists": True, "backed_up": ["ai_system_prompts_config.yaml"]}

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: True)
    monkeypatch.setattr(config_routes, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_routes, "save_ai_prompt_settings", fake_save_ai_prompt_settings)

    prompts = [{
        "name": "metadata_gen",
        "scene": "元数据生成",
        "system": "SYSTEM",
        "examples": "EXAMPLES",
    }]
    resp = client.put("/api/web-config/ai-prompts", json={"prompts": prompts})

    assert resp.status_code == 200
    assert resp.json()["backed_up"] == ["ai_system_prompts_config.yaml"]
    assert calls == [{
        "prompts": prompts,
        "target_dir": tmp_path,
        "actor": "local-admin",
        "audit_root": tmp_path,
        "backup_root": tmp_path,
        "backup_scope": "global",
    }]


def test_web_config_ai_prompts_rejects_remote_user(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    app.dependency_overrides[config_routes.require_auth] = lambda: "alice"
    client = TestClient(app)

    monkeypatch.setattr(config_routes, "is_local_mode", lambda request: False)

    resp = client.put("/api/web-config/ai-prompts", json={"prompts": []})

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]
