import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
FastAPI = pytest.importorskip("fastapi").FastAPI

from web_app import server
from web_app.routes.system import create_router


def test_health_endpoint_returns_core_status():
    client = TestClient(server.app)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["version"], str)
    assert data["work_mode"] in {"local", "remote"}
    assert data["api"] == {
        "version": True,
        "modes": True,
        "config": True,
        "license": True,
    }
    assert data["paths"]["templates_readable"] is True
    assert data["paths"]["output_writable"] is None
    assert isinstance(data["paths"]["fpa_runtime_config_present"], bool)
    assert data["features"]["prompt_debug"] is True
    assert data["features"]["ai_interactions"] is True
    assert data["config"]["fpa_runtime"]["present"] == data["paths"]["fpa_runtime_config_present"]
    assert isinstance(data["config"]["fpa_runtime"]["missing"], list)


def test_health_endpoint_reports_missing_fpa_runtime_config(monkeypatch, tmp_path):
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: tmp_path)
    app = FastAPI()
    app.include_router(create_router(base_dir=tmp_path, mode_info=server.MODE_INFO))
    client = TestClient(app)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["paths"]["fpa_runtime_config_present"] is False
    assert data["config"]["fpa_runtime"]["missing"] == [
        "fpa_config.yaml",
        "fpa_judgement_rules.yaml",
        "domain_context.json",
    ]


def test_license_status_endpoint_is_available_without_data_package(tmp_path):
    app = FastAPI()
    app.include_router(create_router(base_dir=tmp_path, mode_info=server.MODE_INFO))
    client = TestClient(app)

    resp = client.get("/api/license/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["activated"] is False
    assert isinstance(data["crypto_available"], bool)
    assert data["data_package_present"] is False
    assert "data_enc" in data["paths"]


def test_license_activate_requires_license_material():
    client = TestClient(server.app)

    resp = client.post(
        "/api/license/activate",
        json={"license_path": "", "license_secret": "secret"},
    )

    assert resp.status_code == 400
    assert "缺少 license 文件或 license 内容" in resp.text


def test_license_page_returns_spa_entry():
    client = TestClient(server.app)

    resp = client.get("/license")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
