import json
import threading

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import dependencies
from web_app import server
from web_app.routes import tasks
from web_app.services import session_access


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    server.app.dependency_overrides.clear()
    yield
    server.app.dependency_overrides.clear()


def _client(monkeypatch, user: str = "alice", *, local_mode: bool = False):
    monkeypatch.setattr(session_access, "is_local_mode", lambda request: local_mode)
    server.app.dependency_overrides[dependencies.require_auth] = lambda: user
    server.app.dependency_overrides[dependencies.require_local] = lambda: None
    return TestClient(server.app)


def test_run_local_smoke_creates_local_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, local_mode=True)
    xlsx_path = tmp_path / "功能清单.xlsx"
    output_dir = tmp_path / "out"
    xlsx_path.write_bytes(b"placeholder")
    calls: list[dict] = []

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)

    resp = client.post(
        "/api/run-local",
        data={
            "xlsx_path": str(xlsx_path),
            "output_dir": str(output_dir),
            "mode": "from-excel-gen-fpa",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    state = server.session_manager.get(data["session_id"])
    assert data["output_dir"] == str(output_dir)
    assert state is not None
    assert state.mode == "local"
    assert state.output_dir == output_dir
    assert state.task_created_at is not None
    server.session_manager.cleanup_download(data["session_id"])


def test_run_upload_smoke_creates_remote_session(monkeypatch):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)
    monkeypatch.setattr(tasks, "cleanup_expired_sessions", lambda *args, **kwargs: 0)

    resp = client.post(
        "/api/run-upload",
        data={"mode": "from-excel-gen-fpa"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    data = resp.json()
    state = server.session_manager.get(data["session_id"])
    assert data["has_download"] is True
    assert state is not None
    assert state.mode == "remote"
    assert state.owner == "alice"
    assert state.work_dir is not None
    assert state.work_dir.exists()
    assert state.task_created_at is not None
    server.session_manager.cleanup_download(data["session_id"])


def test_log_stream_returns_existing_events_and_removes_queue(monkeypatch):
    client = _client(monkeypatch, user="alice")
    session_id = "task_stream"
    state = server.session_manager.create(session_id, mode="remote", owner="alice")
    assert state.queue is not None
    state.queue.put(json.dumps({"type": "log", "level": "INFO", "msg": "hello"}))
    state.queue.put(json.dumps({"type": "done", "files": []}))

    resp = client.get(f"/api/log-stream?session={session_id}")

    assert resp.status_code == 200
    assert 'data: {"type": "log"' in resp.text
    assert 'data: {"type": "done"' in resp.text
    assert server.session_manager.get_queue(session_id) is None
    server.session_manager.cleanup_download(session_id)


def test_continue_wakes_waiting_input_session(monkeypatch):
    client = _client(monkeypatch, user="alice")
    session_id = "task_continue"
    event = threading.Event()
    server.session_manager.create(session_id, mode="remote", owner="alice")
    server.session_manager.set_input_waiter(session_id, event)

    resp = client.post(
        f"/api/continue/{session_id}",
        json={"fpa_reduced": 12.5, "cfp_total": 7},
    )

    assert resp.status_code == 200
    assert event.is_set() is True
    assert server.session_manager.pop_input_result(session_id) == {
        "fpa_reduced": 12.5,
        "cfp_total": 7,
    }
    server.session_manager.cleanup_download(session_id)


def test_session_status_returns_running_remote_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "task_status_running"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.mark_task_started(session_id)

    resp = client.get(f"/api/sessions/{session_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["mode"] == "remote"
    assert data["run_state"] == "running"
    assert data["output_dir"] == ""
    assert data["has_zip"] is False
    server.session_manager.cleanup_download(session_id)


def test_session_status_returns_done_files_and_zip(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "task_status_done"
    zip_path = tmp_path / "out.zip"
    zip_path.write_bytes(b"zip")
    files = [{"label": "FPA", "path": "fpa.xlsx", "size_kb": 1, "is_temp": False}]
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.set_zip(session_id, zip_path)
    server.session_manager.set_done_files(session_id, files)
    server.session_manager.mark_task_finished(session_id)

    resp = client.get(f"/api/sessions/{session_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_state"] == "done"
    assert data["has_zip"] is True
    assert data["done_files"] == files
    server.session_manager.cleanup_download(session_id)


def test_session_status_hides_other_users_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = "task_status_other_user"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/sessions/{session_id}")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)
