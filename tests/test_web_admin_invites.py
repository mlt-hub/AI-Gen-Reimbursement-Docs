from pathlib import Path

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from ai_gen_reimbursement_docs import auth
from ai_gen_reimbursement_docs.auth import ADMIN_INITIAL_PASSWORD, ADMIN_USERNAME
from web_app import server


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_web_work_mode",
        lambda: "remote",
    )
    auth._tokens.clear()
    return TestClient(server.app)


def _login_admin(client):
    return client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )


def _change_admin_password(client, new_password="changed-secret"):
    return client.post(
        "/api/auth/change-password",
        json={"current_password": ADMIN_INITIAL_PASSWORD, "new_password": new_password},
    )


def test_admin_must_change_initial_password_before_managing_invites(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    login = _login_admin(client)

    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    assert login.json()["must_change_password"] is True

    denied = client.post("/api/admin/invites", json={})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "请先修改初始密码"

    changed = _change_admin_password(client)
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False


def test_admin_can_create_list_and_disable_invite(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    login = _login_admin(client)
    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    assert _change_admin_password(client).status_code == 200

    created = client.post("/api/admin/invites", json={})
    assert created.status_code == 200
    invite = created.json()
    assert len(invite["code"]) == 16
    assert invite["max_uses"] == 1

    listed = client.get("/api/admin/invites")
    assert listed.status_code == 200
    listed_invite = listed.json()["invites"][0]
    assert listed_invite["id"] == invite["id"]
    assert "code" not in listed_invite

    disabled = client.post(f"/api/admin/invites/{invite['id']}/disable")
    assert disabled.status_code == 200

    listed_again = client.get("/api/admin/invites")
    assert listed_again.json()["invites"][0]["status"] == "disabled"


def test_invite_register_consumes_single_use_code(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _login_admin(client)
    _change_admin_password(client)
    invite = client.post("/api/admin/invites", json={}).json()

    registered = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret1", "invite_code": invite["code"]},
    )
    assert registered.status_code == 200

    reused = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "secret1", "invite_code": invite["code"]},
    )
    assert reused.status_code == 400
    assert reused.json()["detail"] == "邀请码使用次数已耗尽"


def test_non_admin_cannot_manage_invites(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _login_admin(client)
    _change_admin_password(client)
    invite = client.post("/api/admin/invites", json={}).json()
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret1", "invite_code": invite["code"]},
    )
    client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "secret1"},
    )

    denied = client.post("/api/admin/invites", json={})

    assert denied.status_code == 403


def test_remember_me_cookie_restores_after_memory_clear(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    login = _login_admin(client)
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    auth._tokens.clear()
    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["username"] == ADMIN_USERNAME
    assert me.json()["role"] == "admin"
    assert me.json()["must_change_password"] is True

    client.post("/api/auth/logout")
    auth._tokens.clear()

    logged_out = client.get("/api/auth/me")
    assert logged_out.json()["username"] is None


def test_change_password_rejects_initial_admin_password(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _login_admin(client)

    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": ADMIN_INITIAL_PASSWORD, "new_password": ADMIN_INITIAL_PASSWORD},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "新密码不能继续使用初始密码"


def test_register_failure_does_not_consume_invite(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _login_admin(client)
    _change_admin_password(client)
    invite = client.post("/api/admin/invites", json={}).json()

    failed = client.post(
        "/api/auth/register",
        json={"username": ADMIN_USERNAME, "password": "secret1", "invite_code": invite["code"]},
    )

    assert failed.status_code == 409
    listed = client.get("/api/admin/invites")
    assert listed.json()["invites"][0]["used_count"] == 0


def test_https_login_cookie_is_secure(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_web_work_mode",
        lambda: "remote",
    )
    auth._tokens.clear()
    client = TestClient(server.app, base_url="https://testserver")

    resp = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )

    assert resp.status_code == 200
    assert "secure" in resp.headers["set-cookie"].lower()
