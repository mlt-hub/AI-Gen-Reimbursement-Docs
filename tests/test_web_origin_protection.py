import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import server


def test_cross_origin_api_write_is_rejected():
    client = TestClient(server.app, base_url="http://testserver")

    resp = client.post(
        "/api/auth/logout",
        headers={"Origin": "https://evil.example"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "跨站请求被拒绝"


def test_same_origin_api_write_is_allowed():
    client = TestClient(server.app, base_url="http://testserver")

    resp = client.post(
        "/api/auth/logout",
        headers={"Origin": "http://testserver"},
    )

    assert resp.status_code == 200
