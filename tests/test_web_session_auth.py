import threading

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import server
from web_app import dependencies
from web_app.services import session_access


def _client_as_user(monkeypatch, user: str, *, local_mode: bool = False):
    monkeypatch.setattr(session_access, "is_local_mode", lambda request: local_mode)
    server.app.dependency_overrides[dependencies.require_auth] = lambda: user
    return TestClient(server.app)


def _cleanup_overrides():
    server.app.dependency_overrides.clear()


def test_remote_user_cannot_read_other_users_ai_log(monkeypatch, tmp_path):
    client = _client_as_user(monkeypatch, "bob")
    session_id = "auth_ai_log"
    work_dir = tmp_path / "work"
    log_dir = work_dir / "output" / "日志"
    log_dir.mkdir(parents=True)
    (log_dir / "ai_对话日志.md").write_text("secret", encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=work_dir)

    denied = client.get(f"/api/ai-log/{session_id}")

    _cleanup_overrides()
    client = _client_as_user(monkeypatch, "alice")
    allowed = client.get(f"/api/ai-log/{session_id}")

    assert denied.status_code == 404
    assert allowed.status_code == 200
    assert allowed.json()["content"] == "secret"
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()


def test_remote_user_cannot_cancel_or_continue_other_users_session(monkeypatch):
    client = _client_as_user(monkeypatch, "bob")
    session_id = "auth_cancel"
    event = threading.Event()
    server.session_manager.create(session_id, mode="remote", owner="alice")
    server.session_manager.set_input_waiter(session_id, event)

    cancel_resp = client.post(f"/api/cancel/{session_id}")
    continue_resp = client.post(f"/api/continue/{session_id}", json={"fpa_reduced": 1})

    assert cancel_resp.status_code == 404
    assert continue_resp.status_code == 404
    assert event.is_set() is False
    assert server.session_manager.pop_input_result(session_id) == {}
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()


def test_remote_user_cannot_download_or_stream_other_users_session(monkeypatch, tmp_path):
    client = _client_as_user(monkeypatch, "bob")
    session_id = "auth_download"
    zip_path = tmp_path / "out.zip"
    zip_path.write_bytes(b"zip")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.set_zip(session_id, zip_path)

    download_resp = client.get(f"/api/download/{session_id}")
    stream_resp = client.get(f"/api/log-stream?session={session_id}")

    assert download_resp.status_code == 404
    assert stream_resp.status_code == 404
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()


def test_download_running_remote_session_returns_conflict(monkeypatch, tmp_path):
    client = _client_as_user(monkeypatch, "alice")
    session_id = "running_download"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/download/{session_id}")

    assert resp.status_code == 409
    assert resp.json()["detail"] == "任务仍在运行，交付物尚未生成"
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()


def test_local_mode_allows_existing_remote_session(monkeypatch, tmp_path):
    client = _client_as_user(monkeypatch, "", local_mode=True)
    session_id = "auth_local"
    work_dir = tmp_path / "work"
    log_dir = work_dir / "output" / "日志"
    log_dir.mkdir(parents=True)
    (log_dir / "ai_对话日志.md").write_text("local", encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=work_dir)

    resp = client.get(f"/api/ai-log/{session_id}")

    assert resp.status_code == 200
    assert resp.json()["content"] == "local"
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()


def test_remote_request_cannot_read_local_session(monkeypatch, tmp_path):
    client = _client_as_user(monkeypatch, "alice", local_mode=False)
    session_id = "auth_local_denied"
    out_dir = tmp_path / "output"
    log_dir = out_dir / "日志"
    log_dir.mkdir(parents=True)
    (log_dir / "ai_对话日志.md").write_text("local secret", encoding="utf-8")
    server.session_manager.create(session_id, mode="local", output_dir=out_dir)

    resp = client.get(f"/api/ai-log/{session_id}")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)
    _cleanup_overrides()
