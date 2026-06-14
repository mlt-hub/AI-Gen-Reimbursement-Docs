import pytest
import json

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import dependencies, server
from web_app.services import session_access


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    server.app.dependency_overrides.clear()
    yield
    server.app.dependency_overrides.clear()


def _client(monkeypatch, user: str = "alice", *, local_mode: bool = False):
    monkeypatch.setattr(session_access, "is_local_mode", lambda request: local_mode)
    server.app.dependency_overrides[dependencies.require_auth] = lambda: user
    return TestClient(server.app)


def _create_debug_session(tmp_path, *, session_id: str = "fpa_debug_session", owner: str = "alice"):
    work_dir = tmp_path / session_id
    log_dir = work_dir / "output" / "日志"
    prompts_dir = log_dir / "ai_prompts"
    responses_dir = log_dir / "ai_responses"
    thinking_dir = log_dir / "ai_thinking"
    records_dir = log_dir / "debug_records"
    prompts_dir.mkdir(parents=True)
    responses_dir.mkdir(parents=True)
    thinking_dir.mkdir(parents=True)
    records_dir.mkdir(parents=True)
    (prompts_dir / "fpa_preview_prompt.md").write_text("SYSTEM\nUSER", encoding="utf-8")
    (responses_dir / "fpa_preview_response.md").write_text("RAW RESPONSE", encoding="utf-8")
    (thinking_dir / "fpa_preview_thinking.md").write_text("AI THINKING", encoding="utf-8")
    (records_dir / "fpa_preview.json").write_text(
        json.dumps({
            "id": "fpa_preview",
            "source": "fpa_preview",
            "module": "三级模块A",
            "model": "test-model",
            "reason": "rules_first_needs_ai",
            "ai_called": True,
            "prompt_file": "fpa_preview_prompt.md",
            "response_file": "fpa_preview_response.md",
            "thinking_file": "fpa_preview_thinking.md",
            "parsed_rows": [{"name": "新增/修改功能点A", "type": "EI"}],
            "final_rows": [{"name": "新增/修改功能点A", "type": "EI"}],
            "quality_review": {"summary": {"issue_count": 0}},
            "error": "",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "ai_对话日志.md").write_text("# FPA 预览调试\nRAW RESPONSE", encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner=owner, work_dir=work_dir)
    server.session_manager.mark_task_started(session_id)
    server.session_manager.mark_task_finished(session_id)
    return session_id


def test_fpa_debug_page_data_endpoints_return_session_and_ai_logs(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = _create_debug_session(tmp_path)

    status_resp = client.get(f"/api/sessions/{session_id}")
    interactions_resp = client.get(f"/api/ai-interactions/{session_id}")
    structured_resp = client.get(f"/api/sessions/{session_id}/fpa/debug-records")
    log_resp = client.get(f"/api/ai-log/{session_id}")

    assert status_resp.status_code == 200
    assert status_resp.json()["session_id"] == session_id
    assert status_resp.json()["run_state"] == "done"

    assert interactions_resp.status_code == 200
    interactions = interactions_resp.json()["interactions"]
    assert interactions == [
        {
            "name": "fpa_preview_prompt.md",
            "type": "prompt",
            "content": "SYSTEM\nUSER",
        },
        {
            "name": "fpa_preview_response.md",
            "type": "response",
            "content": "RAW RESPONSE",
        },
        {
            "name": "fpa_preview_thinking.md",
            "type": "thinking",
            "content": "AI THINKING",
        },
    ]

    assert structured_resp.status_code == 200
    structured = structured_resp.json()
    assert structured["count"] == 1
    assert structured["filters"]["models"] == ["test-model"]
    assert structured["filters"]["modules"] == ["三级模块A"]
    assert structured["filters"]["function_points"] == ["新增/修改功能点A"]
    record = structured["records"][0]
    assert record["id"] == "fpa_preview"
    assert record["module"] == "三级模块A"
    assert record["model"] == "test-model"
    assert record["prompt"] == "SYSTEM\nUSER"
    assert record["response"] == "RAW RESPONSE"
    assert record["thinking"] == "AI THINKING"
    assert record["parsed_rows"][0]["name"] == "新增/修改功能点A"

    assert log_resp.status_code == 200
    assert "FPA 预览调试" in log_resp.json()["content"]
    assert "RAW RESPONSE" in log_resp.json()["content"]
    server.session_manager.cleanup_download(session_id)


def test_fpa_debug_page_spa_route_survives_refresh(monkeypatch):
    client = _client(monkeypatch, user="alice")

    resp = client.get("/sessions/fpa_debug_session/fpa/debug")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "id=\"app\"" in resp.text or "前端未构建" in resp.text


def test_fpa_debug_page_data_endpoints_hide_other_users_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = _create_debug_session(tmp_path, owner="alice")

    status_resp = client.get(f"/api/sessions/{session_id}")
    interactions_resp = client.get(f"/api/ai-interactions/{session_id}")
    structured_resp = client.get(f"/api/sessions/{session_id}/fpa/debug-records")
    log_resp = client.get(f"/api/ai-log/{session_id}")

    assert status_resp.status_code == 404
    assert interactions_resp.status_code == 404
    assert structured_resp.status_code == 404
    assert log_resp.status_code == 404
    server.session_manager.cleanup_download(session_id)
