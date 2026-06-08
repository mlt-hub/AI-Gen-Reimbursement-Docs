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


def test_admin_can_create_list_and_disable_invite(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "admin"

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
    client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )
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
    client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )
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
    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_INITIAL_PASSWORD, "remember_me": True},
    )
    assert login.status_code == 200

    auth._tokens.clear()
    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["username"] == ADMIN_USERNAME
    assert me.json()["role"] == "admin"

    client.post("/api/auth/logout")
    auth._tokens.clear()

    logged_out = client.get("/api/auth/me")
    assert logged_out.json()["username"] is None
