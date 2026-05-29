import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import server


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
    }
    assert data["paths"]["templates_readable"] is True
    assert data["paths"]["output_writable"] is None
    assert data["features"]["prompt_debug"] is True
    assert data["features"]["ai_interactions"] is True
