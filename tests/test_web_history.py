import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import dependencies
from web_app import server
from web_app.services import run_history_service


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    server.app.dependency_overrides.clear()
    yield
    server.app.dependency_overrides.clear()


def _client(monkeypatch, *, local_mode: bool, user: str = "alice"):
    monkeypatch.setattr("web_app.routes.history.is_local_mode", lambda request: local_mode)
    server.app.dependency_overrides[dependencies.require_auth] = lambda: "" if local_mode else user
    server.app.dependency_overrides[dependencies.require_local] = lambda: None
    return TestClient(server.app)


def test_history_local_lists_user_history(monkeypatch, tmp_path):
    db = tmp_path / "user_history.sqlite3"
    monkeypatch.setattr(run_history_service, "user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)

    run_history_service.start_web_run(
        base_dir=tmp_path,
        session_id="local1",
        mode="local",
        task_mode="gen-all",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )

    resp = client.get("/api/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["run_id"] == "local1"
    assert data["items"][0]["open_folder_available"] is True


def test_history_remote_filters_by_owner(monkeypatch, tmp_path):
    db = tmp_path / "service_history.sqlite3"
    monkeypatch.setattr(run_history_service, "service_history_path", lambda base_dir: db)
    client = _client(monkeypatch, local_mode=False, user="alice")

    run_history_service.start_web_run(
        base_dir=tmp_path,
        session_id="alice1",
        mode="remote",
        task_mode="gen-all",
        input_path=str(tmp_path / "alice.xlsx"),
        owner_id="alice",
        owner_label="alice",
    )
    run_history_service.start_web_run(
        base_dir=tmp_path,
        session_id="bob1",
        mode="remote",
        task_mode="gen-all",
        input_path=str(tmp_path / "bob.xlsx"),
        owner_id="bob",
        owner_label="bob",
    )

    resp = client.get("/api/history")

    assert resp.status_code == 200
    ids = [item["run_id"] for item in resp.json()["items"]]
    assert ids == ["alice1"]
