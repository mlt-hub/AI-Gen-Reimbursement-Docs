import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import server


def test_prompt_debug_requires_login_in_remote_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_web_work_mode",
        lambda: "remote",
    )
    client = TestClient(server.app)

    resp = client.post(
        "/api/test-prompt",
        json={"system_prompt": "s", "user_prompt": "u"},
    )

    assert resp.status_code == 401


def test_prompt_debug_file_path_helpers_require_local_client(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    client = TestClient(server.app, client=("203.0.113.10", 50000))

    reliability = client.post(
        "/api/test-ai-reliability-desc",
        data={"xlsx_path": str(tmp_path / "secret.xlsx")},
    )
    metadata = client.post(
        "/api/test-ai-metadata",
        data={"xlsx_path": str(tmp_path / "secret.xlsx"), "field_key": "工单内容"},
    )

    assert reliability.status_code == 403
    assert metadata.status_code == 403
