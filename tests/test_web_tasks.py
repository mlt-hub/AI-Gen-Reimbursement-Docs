import json
import threading
import shutil
import zipfile
from pathlib import Path

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from web_app import dependencies
from web_app import server
from web_app.routes import tasks
from web_app.services import run_history_service
from web_app.services import session_access


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    server.app.dependency_overrides.clear()
    yield
    server.app.dependency_overrides.clear()


def _client(monkeypatch, user: str = "alice", *, local_mode: bool = False):
    monkeypatch.setattr(session_access, "is_local_mode", lambda request: local_mode)
    monkeypatch.setattr(tasks, "is_local_mode", lambda request: local_mode)
    monkeypatch.setattr("web_app.routes.history.is_local_mode", lambda request: local_mode)
    server.app.dependency_overrides[dependencies.require_auth] = lambda: user
    server.app.dependency_overrides[dependencies.require_local] = lambda: None
    return TestClient(server.app)


def test_task_list_excludes_closed_items(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)

    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="visible1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="visible1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="closed1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="closed1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )
    resp_close = client.post("/api/tasks/closed1/close")
    assert resp_close.status_code == 200

    resp = client.get("/api/tasks")

    assert resp.status_code == 200
    ids = [item["run_id"] for item in resp.json()["items"]]
    assert ids == ["visible1"]


def test_task_list_marks_running_session_availability(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    server.session_manager.create("recoverable1", mode="local", output_dir=tmp_path)
    server.session_manager.mark_task_started("recoverable1")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="recoverable1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="orphan_running1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    resp = client.get("/api/tasks")

    assert resp.status_code == 200
    by_id = {item["run_id"]: item for item in resp.json()["items"]}
    assert by_id["recoverable1"]["session_available"] is True
    assert by_id["orphan_running1"]["session_available"] is False
    server.session_manager.cleanup_download("recoverable1")


def test_mark_unrecoverable_running_task_cancels_history(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="orphan_mark1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    resp = client.post("/api/tasks/orphan_mark1/mark-unrecoverable")

    assert resp.status_code == 200
    item = resp.json()["item"]
    assert item["run_state"] == "cancelled"
    assert item["finished_at"]
    assert "会话已结束" in item["error"]


def test_mark_unrecoverable_running_task_rejects_recoverable_session(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    server.session_manager.create("recoverable_mark1", mode="local", output_dir=tmp_path)
    server.session_manager.mark_task_started("recoverable_mark1")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="recoverable_mark1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    resp = client.post("/api/tasks/recoverable_mark1/mark-unrecoverable")

    assert resp.status_code == 400
    assert "仍可继续执行" in resp.json()["detail"]
    server.session_manager.cleanup_download("recoverable_mark1")


def test_mark_unrecoverable_task_can_be_rerun(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="orphan_rerun1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    mark_resp = client.post("/api/tasks/orphan_rerun1/mark-unrecoverable")
    assert mark_resp.status_code == 200

    def fake_start_background_task(session_manager, session_id, target):
        session_manager.mark_task_started(session_id)
        target()
        session_manager.mark_task_finished(session_id)
        return None

    def fake_execute_in_session(*args, **kwargs):
        kwargs["on_finish"](args[1], [], None)

    monkeypatch.setattr(tasks, "start_background_task", fake_start_background_task)
    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)

    resp = client.post("/api/tasks/orphan_rerun1/rerun")

    assert resp.status_code == 200
    assert resp.json()["session_id"] != "orphan_rerun1"


def test_close_running_task_returns_400(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="running1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "功能清单.xlsx"),
        output_dir=str(tmp_path),
    )

    resp = client.post("/api/tasks/running1/close")

    assert resp.status_code == 400
    assert "运行中任务不能关闭" in resp.json()["detail"]


def test_close_done_task_keeps_it_in_history_as_closed(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="done1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="done1",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    resp = client.post("/api/tasks/done1/close")

    assert resp.status_code == 200
    assert resp.json()["item"]["run_state"] == "closed"
    history = client.get("/api/history?state=closed")
    assert history.status_code == 200
    assert [item["run_id"] for item in history.json()["items"]] == ["done1"]


def test_task_list_remote_filters_by_owner(monkeypatch, tmp_path):
    db = tmp_path / "service_history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.service_history_path", lambda base_dir: db)
    client = _client(monkeypatch, user="alice", local_mode=False)

    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="alice_task",
        mode="remote",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "alice.xlsx"),
        owner_id="alice",
        owner_label="alice",
    )
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="bob_task",
        mode="remote",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "bob.xlsx"),
        owner_id="bob",
        owner_label="bob",
    )

    resp = client.get("/api/tasks")

    assert resp.status_code == 200
    assert [item["run_id"] for item in resp.json()["items"]] == ["alice_task"]


def test_remote_user_cannot_close_other_users_task(monkeypatch, tmp_path):
    db = tmp_path / "service_history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.service_history_path", lambda base_dir: db)
    client = _client(monkeypatch, user="bob", local_mode=False)
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="alice_done",
        mode="remote",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "alice.xlsx"),
        owner_id="alice",
        owner_label="alice",
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="alice_done",
        mode="remote",
        task_mode="from-excel-gen-fpa",
        input_path=str(tmp_path / "alice.xlsx"),
        owner_id="alice",
        owner_label="alice",
    )

    resp = client.post("/api/tasks/alice_done/close")

    assert resp.status_code == 404


def test_rerun_closed_task_returns_400(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="closed_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="closed_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    client.post("/api/tasks/closed_rerun/close")

    resp = client.post("/api/tasks/closed_rerun/rerun")

    assert resp.status_code == 400
    assert "关闭任务不能重跑" in resp.json()["detail"]


def test_rerun_done_local_task_creates_new_history(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="done_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="done_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    def fake_start_background_task(session_manager, session_id, target):
        session_manager.mark_task_started(session_id)
        target()
        session_manager.mark_task_finished(session_id)
        return None

    def fake_execute_in_session(*args, **kwargs):
        kwargs["on_finish"](args[1], [], None)

    monkeypatch.setattr(tasks, "start_background_task", fake_start_background_task)
    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)

    resp = client.post("/api/tasks/done_rerun/rerun")

    assert resp.status_code == 200
    new_id = resp.json()["session_id"]
    assert new_id != "done_rerun"
    history = client.get("/api/history")
    ids = [item["run_id"] for item in history.json()["items"]]
    assert new_id in ids
    assert "done_rerun" in ids


def test_rerun_uses_original_run_config_snapshot(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    client = _client(monkeypatch, local_mode=True)
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")
    tasks.start_web_run(
        base_dir=tmp_path,
        session_id="snapshot_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
        run_config={
            "model": "original-model",
            "base_url": "https://original.example.test",
            "max_tokens": "8K",
            "project_name": "Original Project",
            "fpa_profile": "strict_fpa",
            "fpa_strategy": "ai_first",
            "fpa_rule_set": "strict_fpa_rs",
            "fpa_confirmation_mode": "strict",
            "clean": True,
        },
    )
    tasks.finish_web_run(
        base_dir=tmp_path,
        session_id="snapshot_rerun",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )
    calls: list[dict] = []

    def fake_start_background_task(session_manager, session_id, target):
        session_manager.mark_task_started(session_id)
        target()
        session_manager.mark_task_finished(session_id)
        return None

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        kwargs["on_finish"](args[1], [], None)

    monkeypatch.setattr(tasks, "start_background_task", fake_start_background_task)
    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)

    resp = client.post("/api/tasks/snapshot_rerun/rerun")

    assert resp.status_code == 200
    assert calls
    args = calls[0]["args"]
    assert args[6] == "original-model"
    assert args[7] == "https://original.example.test"
    assert args[8] == "Original Project"
    assert args[9] == "8K"
    assert args[10] == "strict_fpa"
    assert args[11] == "ai_first"
    assert args[12] == "strict_fpa_rs"
    assert args[13] == "strict"
    assert args[15] is True


def test_finish_backfills_missing_project_name_into_history(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    monkeypatch.setattr(
        "web_app.services.run_history_service._infer_project_name",
        lambda path: "完成后项目名",
    )
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")

    run_history_service.start_web_run(
        base_dir=tmp_path,
        session_id="finish_project_name",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
        run_config={
            "model": "original-model",
            "project_name": "",
            "fpa_profile": "strict_fpa",
        },
    )
    started = run_history_service.get_history_item(
        base_dir=tmp_path,
        run_id="finish_project_name",
        local_mode=True,
        owner_id="",
    )
    assert started["run_config"]["project_name"] == ""

    run_history_service.finish_web_run(
        base_dir=tmp_path,
        session_id="finish_project_name",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    finished = run_history_service.get_history_item(
        base_dir=tmp_path,
        run_id="finish_project_name",
        local_mode=True,
        owner_id="",
    )
    assert finished["run_state"] == "done"
    assert finished["run_config"]["project_name"] == "完成后项目名"
    assert finished["run_config"]["model"] == "original-model"
    assert finished["run_config"]["fpa_profile"] == "strict_fpa"


def test_finish_keeps_explicit_project_name(monkeypatch, tmp_path):
    db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.user_history_path", lambda: db)
    monkeypatch.setattr(
        "web_app.services.run_history_service._infer_project_name",
        lambda path: "完成后项目名",
    )
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"placeholder")

    run_history_service.start_web_run(
        base_dir=tmp_path,
        session_id="explicit_project_name",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
        run_config={"project_name": "显式项目名"},
    )
    run_history_service.finish_web_run(
        base_dir=tmp_path,
        session_id="explicit_project_name",
        mode="local",
        task_mode="from-excel-gen-fpa",
        input_path=str(input_path),
        output_dir=str(tmp_path),
    )

    finished = run_history_service.get_history_item(
        base_dir=tmp_path,
        run_id="explicit_project_name",
        local_mode=True,
        owner_id="",
    )
    assert finished["run_config"]["project_name"] == "显式项目名"


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
            "fpa_profile": "strict_fpa",
            "fpa_strategy": "ai_first",
            "fpa_rule_set": "strict_fpa_rs",
            "fpa_confirmation_mode": "strict",
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
    assert calls
    assert calls[0]["args"][10] == "strict_fpa"
    assert calls[0]["args"][11] == "ai_first"
    assert calls[0]["args"][12] == "strict_fpa_rs"
    assert calls[0]["args"][13] == "strict"
    server.session_manager.cleanup_download(data["session_id"])


def test_local_user_config_redacts_api_key(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="", local_mode=True)
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-local-secret\n"
        "ANTHROPIC_BASE_URL=https://api.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "web_app.services.config_service.config_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "web_app.routes.config.config_dir",
        lambda: tmp_path,
    )

    resp = client.get("/api/user/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["_env"]["ANTHROPIC_API_KEY"] == "***"
    assert "sk-local-secret" not in resp.text
    assert data["_env"]["ANTHROPIC_BASE_URL"] == "https://api.example.test"


def test_fpa_options_returns_config_metadata(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: strict_fpa
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
profiles:
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
core_rules:
  unified_ui_cr: CUSTOM CORE RULES
  strict_fpa_cr: STRICT CORE RULES
system_prompt_sets:
  unified_ui_sp: CUSTOM SYSTEM secret
  strict_fpa_sp: STRICT SYSTEM secret
user_prompt_sets:
  unified_ui_up: custom user secret ${core_rules} ${judgement_rules} ${payload_json}
  strict_fpa_up: strict user secret ${core_rules} ${judgement_rules} ${payload_json}
rule_sets:
  unified_ui_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  client_a_rules:
    extends: strict_fpa_rs
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["供应商平台"]
          data_name: "供应商平台供应商档案"
          data_nouns: ["供应商"]
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.config_dir",
        lambda: tmp_path,
    )

    resp = client.get("/api/fpa/options")

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_profile"] == "strict_fpa"
    assert data["profiles"] == [
        {
            "name": "unified_ui",
            "label": "统一界面口径",
            "kind": "unified_ui",
            "strategy": "rules_first",
            "rule_set": "unified_ui_rs",
        },
        {
            "name": "strict_fpa",
            "label": "严格 FPA 口径",
            "kind": "strict_fpa",
            "strategy": "ai_first",
            "rule_set": "strict_fpa_rs",
        },
    ]
    assert {item["name"] for item in data["rule_sets"]} == {
        "unified_ui_rs",
        "strict_fpa_rs",
        "client_a_rules",
    }
    assert data["confirmation_modes"] == [
        {"name": "auto", "label": "自动模式"},
        {"name": "cautious", "label": "审慎模式"},
        {"name": "strict", "label": "严格确认模式"},
    ]
    assert data["rule_sets"][2]["extends"] == "strict_fpa_rs"
    assert "secret" not in resp.text


def test_fpa_options_preserves_custom_profile_order_and_label_fallback(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: client_api
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
profiles:
  client_api:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: shared_rs
    core_rules: shared_cr
    system_prompt: shared_sp
    user_prompt: shared_up
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: shared_rs
    core_rules: shared_cr
    system_prompt: shared_sp
    user_prompt: shared_up
core_rules:
  shared_cr: SHARED CORE RULES
system_prompt_sets:
  shared_sp: SHARED SYSTEM
user_prompt_sets:
  shared_up: ${core_rules} ${judgement_rules} ${payload_json}
rule_sets:
  shared_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.config_dir",
        lambda: tmp_path,
    )

    resp = client.get("/api/fpa/options")

    assert resp.status_code == 200
    data = resp.json()
    assert [profile["name"] for profile in data["profiles"]] == ["client_api", "strict_fpa"]
    assert data["profiles"][0]["label"] == "client_api"
    assert data["profiles"][0]["kind"] == "ui_api_mapping"
    assert {kind["name"] for kind in data["kinds"]} == {"strict_fpa", "unified_ui", "ui_api_mapping"}
    assert "core_rules" not in resp.text
    assert "system_prompt" not in resp.text
    assert "user_prompt" not in resp.text


def test_fpa_options_returns_400_for_invalid_prompt_placeholder(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    (tmp_path / "fpa_config.yaml").write_text(
        """
default-profile: strict_fpa
adjustment_value_method_default: legacy_workload
adjustment_value_methods:
  legacy_workload:
    type_weights:
      EI: 2
      default: 1
profiles:
  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
core_rules:
  unified_ui_cr: CUSTOM CORE RULES
  strict_fpa_cr: STRICT CORE RULES
system_prompt_sets:
  unified_ui_sp: CUSTOM SYSTEM
  strict_fpa_sp: STRICT SYSTEM
user_prompt_sets:
  unified_ui_up: ${core_rules} ${judgement_rules} ${payload_json}
  strict_fpa_up: ${core_rules} ${judgement_rules} ${payload_json} ${unknown_placeholder}
rule_sets:
  unified_ui_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
  strict_fpa_rs:
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.config_dir",
        lambda: tmp_path,
    )

    resp = client.get("/api/fpa/options")

    assert resp.status_code == 400
    assert "user_prompt_sets.strict_fpa_up 包含未知占位符" in resp.json()["detail"]
    assert "${unknown_placeholder}" in resp.json()["detail"]


def test_run_upload_smoke_creates_remote_session(monkeypatch):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)
    monkeypatch.setattr(tasks, "cleanup_expired_sessions", lambda *args, **kwargs: 0)

    resp = client.post(
        "/api/run-upload",
        data={
            "mode": "from-excel-gen-fpa",
            "api_key": "sk-explicit",
            "fpa_profile": "strict_fpa",
            "fpa_strategy": "ai_first",
            "fpa_rule_set": "strict_fpa_rs",
            "fpa_confirmation_mode": "cautious",
        },
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
    assert calls
    assert calls[0]["args"][5] == "sk-explicit"
    assert calls[0]["args"][10] == "strict_fpa"
    assert calls[0]["args"][11] == "ai_first"
    assert calls[0]["args"][12] == "strict_fpa_rs"
    assert calls[0]["args"][13] == "cautious"
    server.session_manager.cleanup_download(data["session_id"])


def test_run_upload_blocks_ai_task_without_personal_or_shared_api_key(monkeypatch):
    client = _client(monkeypatch, user="alice")
    monkeypatch.setattr(tasks, "cleanup_expired_sessions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(tasks, "read_config", lambda: {
        "_env": {"ANTHROPIC_API_KEY_ENC": "fernet:global-ciphertext"},
        "_system": {"allow_shared_ai_credentials": False},
    })
    monkeypatch.setattr(tasks, "read_config_from_dir", lambda path: {"_env": {}, "_system": {}})

    resp = client.post(
        "/api/run-upload",
        data={"mode": "from-excel-gen-fpa"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 400
    assert "配置个人 API Key" in resp.json()["detail"]


def test_run_upload_uses_config_defaults_snapshot(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []
    user_dir = tmp_path / "users" / "alice"
    user_dir.mkdir(parents=True)

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)
    monkeypatch.setattr(tasks, "cleanup_expired_sessions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(tasks, "user_config_dir", lambda user: user_dir)
    monkeypatch.setattr(tasks, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(tasks, "read_config", lambda: {
        "_env": {
            "ANTHROPIC_API_KEY": "sk-global",
            "ANTHROPIC_BASE_URL": "https://global.example.test",
            "ANTHROPIC_MODEL": "global-model",
        },
        "_system": {
            "allow_shared_ai_credentials": True,
            "max_tokens": "16K",
            "fpa_profile": "strict_fpa",
            "fpa_strategy": "ai_first",
            "fpa_rule_set": "strict_fpa_rs",
        },
    })
    monkeypatch.setattr(tasks, "read_config_from_dir", lambda path: {
        "_env": {
            "ANTHROPIC_MODEL": "personal-model",
        },
        "_system": {
            "fpa_strategy": "rules_first",
        },
    })

    resp = client.post(
        "/api/run-upload",
        data={"mode": "from-excel-gen-fpa"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    assert calls
    assert calls[0]["args"][5] == "sk-global"
    assert calls[0]["args"][6] == "personal-model"
    assert calls[0]["args"][7] == "https://global.example.test"
    assert calls[0]["args"][9] == "16K"
    assert calls[0]["args"][10] == "strict_fpa"
    assert calls[0]["args"][11] == "rules_first"
    assert calls[0]["args"][12] == "strict_fpa_rs"
    server.session_manager.cleanup_download(resp.json()["session_id"])


def test_run_upload_loads_project_profile_decisions(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []
    user_dir = tmp_path / "users" / "alice"
    user_dir.mkdir(parents=True)
    (user_dir / "fpa_project_profile.json").write_text(
        json.dumps({
            "version": 1,
            "confirmed_decisions": {
                "merge_query_demo": {"value": "yes", "scope": "project_profile"},
            },
        }),
        encoding="utf-8",
    )

    def fake_execute_in_session(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(tasks, "execute_in_session", fake_execute_in_session)
    monkeypatch.setattr(tasks, "cleanup_expired_sessions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(tasks, "user_config_dir", lambda user: user_dir)

    resp = client.post(
        "/api/run-upload",
        data={
            "mode": "from-excel-gen-fpa",
            "api_key": "sk-explicit",
        },
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    assert calls
    assert calls[0]["args"][14] == {
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }
    state = server.session_manager.get(resp.json()["session_id"])
    assert state is not None
    assert state.config_root == user_dir
    server.session_manager.cleanup_download(resp.json()["session_id"])


def test_fpa_preview_upload_returns_preview(monkeypatch):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []

    def fake_preview_fpa_module(**kwargs):
        calls.append(kwargs)
        return {
            "module": {
                "index": 1,
                "client_type": "地市后台",
                "l1": "一级",
                "l2": "二级",
                "l3": "垂直行业管理",
                "process_count": 2,
            },
            "rows": [
                {
                    "name": "垂直行业管理界面开发",
                    "type": "EI",
                    "type_reason": "界面能力",
                    "classification_basis": "规则一",
                    "classification_basis_index": 1,
                    "explanation": "说明",
                    "source_processes": [],
                    "generation": "ai",
                }
            ],
            "warnings": [],
            "status": "ok",
            "confirmation_questions": [],
            "used_ai": True,
        }

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)

    resp = client.post(
        "/api/fpa/preview-module",
        data={
            "module_name": "垂直行业管理",
            "api_key": "sk-test",
            "fpa_profile": "unified_ui",
            "fpa_strategy": "rules_first",
            "fpa_rule_set": "unified_ui_rs",
            "fpa_confirmation_mode": "cautious",
            "confirmed_decisions": json.dumps({"merge_crud_demo": {"value": "yes", "scope": "current_run"}}),
        },
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["module"]["l3"] == "垂直行业管理"
    assert data["rows"][0]["type"] == "EI"
    assert calls
    assert calls[0]["module_name"] == "垂直行业管理"
    assert calls[0]["api_key"] == "sk-test"
    assert calls[0]["profile_name"] == "unified_ui"
    assert calls[0]["strategy"] == "rules_first"
    assert calls[0]["rule_set"] == "unified_ui_rs"
    assert calls[0]["fpa_confirmation_mode"] == "cautious"
    assert calls[0]["confirmed_decisions"] == {"merge_crud_demo": {"value": "yes", "scope": "current_run"}}


def test_fpa_preview_merges_and_persists_project_profile_decisions(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []
    user_dir = tmp_path / "users" / "alice"
    user_dir.mkdir(parents=True)
    (user_dir / "fpa_project_profile.json").write_text(
        json.dumps({
            "version": 1,
            "confirmed_decisions": {
                "merge_query_demo": {"value": "yes", "scope": "project_profile"},
            },
        }),
        encoding="utf-8",
    )

    def fake_preview_fpa_module(**kwargs):
        calls.append(kwargs)
        return {"module": {"l3": "垂直行业管理"}, "rows": [], "warnings": [], "status": "ok"}

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)
    monkeypatch.setattr(tasks, "user_config_dir", lambda user: user_dir)

    resp = client.post(
        "/api/fpa/preview-module",
        data={
            "module_name": "垂直行业管理",
            "api_key": "sk-test",
            "confirmed_decisions": json.dumps({
                "merge_crud_demo": {"value": "yes", "scope": "project_profile"},
                "current_only_demo": {"value": "no", "scope": "current_run"},
            }),
        },
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    assert calls[0]["confirmed_decisions"] == {
        "current_only_demo": {"value": "no", "scope": "current_run"},
        "merge_crud_demo": {"value": "yes", "scope": "project_profile"},
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }
    saved = json.loads((user_dir / "fpa_project_profile.json").read_text(encoding="utf-8"))
    assert saved["confirmed_decisions"] == {
        "merge_crud_demo": {"value": "yes", "scope": "project_profile"},
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }


def test_fpa_preview_upload_uses_config_defaults(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []
    user_dir = tmp_path / "users" / "alice"
    user_dir.mkdir(parents=True)

    def fake_preview_fpa_module(**kwargs):
        calls.append(kwargs)
        return {"module": {"l3": "垂直行业管理"}, "rows": [], "warnings": [], "status": "ok"}

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)
    monkeypatch.setattr(tasks, "user_config_dir", lambda user: user_dir)
    monkeypatch.setattr(tasks, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(tasks, "read_config", lambda: {
        "_env": {
            "ANTHROPIC_API_KEY": "sk-global",
            "ANTHROPIC_BASE_URL": "https://global.example.test",
            "ANTHROPIC_MODEL": "global-model",
        },
        "_system": {
            "allow_shared_ai_credentials": True,
            "fpa_profile": "strict_fpa",
            "fpa_strategy": "ai_first",
            "fpa_rule_set": "strict_fpa_rs",
            "fpa_confirmation_mode": "strict",
        },
    })
    monkeypatch.setattr(tasks, "read_config_from_dir", lambda path: {
        "_env": {
            "ANTHROPIC_MODEL": "personal-model",
        },
        "_system": {
            "fpa_strategy": "rules_first",
        },
    })

    resp = client.post(
        "/api/fpa/preview-module",
        data={"module_name": "垂直行业管理"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    assert calls
    assert calls[0]["api_key"] == "sk-global"
    assert calls[0]["model"] == "personal-model"
    assert calls[0]["base_url"] == "https://global.example.test"
    assert calls[0]["profile_name"] == "strict_fpa"
    assert calls[0]["strategy"] == "rules_first"
    assert calls[0]["rule_set"] == "strict_fpa_rs"
    assert calls[0]["fpa_confirmation_mode"] == "strict"


def test_fpa_preview_upload_blocks_without_available_ai_key(monkeypatch):
    client = _client(monkeypatch, user="alice")
    monkeypatch.setattr(tasks, "read_config", lambda: {
        "_env": {"ANTHROPIC_API_KEY": "sk-global"},
        "_system": {"allow_shared_ai_credentials": False},
    })
    monkeypatch.setattr(tasks, "read_config_from_dir", lambda path: {"_env": {}, "_system": {}})

    resp = client.post(
        "/api/fpa/preview-module",
        data={"module_name": "垂直行业管理"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 400
    assert "配置个人 API Key" in resp.json()["detail"]


def test_fpa_preview_rules_only_allows_missing_ai_key(monkeypatch):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []

    def fake_preview_fpa_module(**kwargs):
        calls.append(kwargs)
        return {"module": {"l3": "垂直行业管理"}, "rows": [], "warnings": [], "status": "ok"}

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)
    monkeypatch.setattr(tasks, "read_config", lambda: {
        "_env": {},
        "_system": {"allow_shared_ai_credentials": False},
    })
    monkeypatch.setattr(tasks, "read_config_from_dir", lambda path: {"_env": {}, "_system": {}})

    resp = client.post(
        "/api/fpa/preview-module",
        data={"module_name": "垂直行业管理", "fpa_strategy": "rules_only"},
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    assert calls
    assert calls[0]["api_key"] == ""
    assert calls[0]["strategy"] == "rules_only"


def test_fpa_preview_appends_debug_to_accessible_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "fpa_preview_debug"
    work_dir = tmp_path / "work"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=work_dir)

    def fake_preview_fpa_module(**kwargs):
        return {
            "module": {"index": 1, "l3": "垂直行业管理"},
            "rows": [],
            "warnings": [],
            "status": "ok",
            "debug": {
                "ai_called": True,
                "system_prompt": "SYSTEM PROMPT",
                "user_prompt": "USER PROMPT",
                "ai_prompt": "AI PROMPT",
                "raw_response": "RAW RESPONSE",
                "thinking": "THINKING",
                "parsed_rows": [{"name": "功能点"}],
                "quality_review": {"ok": True},
            },
        }

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)

    resp = client.post(
        "/api/fpa/preview-module",
        data={
            "module_name": "垂直行业管理",
            "api_key": "sk-test",
            "session_id": session_id,
        },
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    log_dir = work_dir / "output" / "日志"
    prompt_text = next((log_dir / "ai_prompts").glob("fpa_preview_*_prompt.txt")).read_text(encoding="utf-8")
    response_text = next((log_dir / "ai_responses").glob("fpa_preview_*_response.txt")).read_text(encoding="utf-8")
    combined_text = (log_dir / "ai_对话日志.md").read_text(encoding="utf-8")
    assert "SYSTEM PROMPT" in prompt_text
    assert "USER PROMPT" in prompt_text
    assert "RAW RESPONSE" in response_text
    assert "垂直行业管理" in combined_text
    server.session_manager.cleanup_download(session_id)


def test_fpa_preview_rejects_debug_session_without_access(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = "fpa_preview_debug_forbidden"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path / "work")

    def fake_preview_fpa_module(**kwargs):
        return {
            "module": {"index": 1, "l3": "垂直行业管理"},
            "rows": [],
            "warnings": [],
            "status": "ok",
            "debug": {"ai_called": True, "system_prompt": "secret"},
        }

    monkeypatch.setattr(tasks, "preview_fpa_module", fake_preview_fpa_module)

    resp = client.post(
        "/api/fpa/preview-module",
        data={
            "module_name": "垂直行业管理",
            "api_key": "sk-test",
            "session_id": session_id,
        },
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 404
    assert not (tmp_path / "work" / "output" / "日志").exists()
    server.session_manager.cleanup_download(session_id)


def test_fpa_preview_modules_upload_returns_selectable_modules(monkeypatch):
    client = _client(monkeypatch, user="alice")
    calls: list[dict] = []

    def fake_preview_fpa_modules(**kwargs):
        calls.append(kwargs)
        return {
            "modules": [
                {
                    "index": 1,
                    "client_type": "地市后台",
                    "l1": "一级",
                    "l2": "二级",
                    "l3": "垂直行业管理",
                    "l3_desc": "描述",
                    "process_count": 2,
                    "label": "1. 地市后台 / 一级 / 二级 / 垂直行业管理",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(tasks, "preview_fpa_modules", fake_preview_fpa_modules)

    resp = client.post(
        "/api/fpa/preview-modules",
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["modules"][0]["index"] == 1
    assert data["modules"][0]["l3"] == "垂直行业管理"
    assert calls
    assert Path(calls[0]["file_path"]).name == "功能清单.xlsx"


def test_fpa_preview_requires_module_target(monkeypatch):
    client = _client(monkeypatch, user="alice")

    resp = client.post(
        "/api/fpa/preview-module",
        files={"file": ("功能清单.xlsx", b"placeholder", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 400
    assert "三级模块" in resp.json()["detail"]


@pytest.mark.parametrize(
    "path",
    [
        "/static/dist",
        "/static/dist/",
        "/static/dist/login",
        "/static/dist/config",
        "/static/dist/license",
        "/static/dist/tasks",
        "/static/dist/history",
        "/static/dist/prompt-debug",
        "/static/dist/preview/fpa",
        "/static/dist/sessions/demo-session/fpa/debug",
    ],
)
def test_static_dist_spa_routes_return_spa_index(monkeypatch, path):
    client = _client(monkeypatch, user="alice")

    resp = client.get(path)

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "id=\"app\"" in resp.text or "前端未构建" in resp.text


@pytest.mark.parametrize(
    "path",
    ["/login", "/tasks", "/preview/fpa", "/sessions/demo-session/fpa/debug"],
)
def test_top_level_spa_routes_return_spa_index(monkeypatch, path):
    client = _client(monkeypatch, user="alice")

    resp = client.get(path)

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "id=\"app\"" in resp.text or "前端未构建" in resp.text


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


def test_continue_persists_project_profile_fpa_confirmation(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "task_continue_profile"
    event = threading.Event()
    server.session_manager.create(
        session_id,
        mode="remote",
        owner="alice",
        config_root=tmp_path,
    )
    server.session_manager.set_input_waiter(session_id, event)

    resp = client.post(
        f"/api/continue/{session_id}",
        json={
            "kind": "fpa_confirmation",
            "confirmed_decisions": {
                "merge_query_demo": {"value": "yes", "scope": "project_profile"},
                "current_only_demo": {"value": "no", "scope": "current_run"},
            },
        },
    )

    assert resp.status_code == 200
    assert event.is_set() is True
    submitted = server.session_manager.pop_input_result(session_id)
    assert submitted["confirmed_decisions"] == {
        "current_only_demo": {"value": "no", "scope": "current_run"},
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }
    saved = json.loads((tmp_path / "fpa_project_profile.json").read_text(encoding="utf-8"))
    assert saved["confirmed_decisions"] == {
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
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
    assert data["progress_steps"] == {}
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


def test_session_status_returns_cancelled_run_state(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "task_status_cancelled"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.mark_task_started(session_id)
    server.session_manager.mark_task_finished(session_id, last_error="cancelled")

    resp = client.get(f"/api/sessions/{session_id}")

    assert resp.status_code == 200
    assert resp.json()["run_state"] == "cancelled"
    server.session_manager.cleanup_download(session_id)


def test_session_status_hides_other_users_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = "task_status_other_user"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/sessions/{session_id}")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmation_can_be_saved_and_loaded(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_confirmation"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    payload = {
        "project": "测试项目",
        "status": "review_required",
        "review_items": [
            {
                "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
                "severity": "warning",
                "confirmation": {
                    "status": "confirmed",
                    "decision": "confirmed",
                    "note": "已确认功能用户",
                    "confirmed_by": "",
                    "confirmed_at": "2026-06-09T00:00:00Z",
                },
            }
        ],
    }

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)
    load_resp = client.get(f"/api/sessions/{session_id}/cosmic/confirmation")

    assert save_resp.status_code == 200
    assert save_resp.json()["filename"] == "cosmic-confirmation.json"
    assert save_resp.json()["payload"]["export_policy"]["formal_excel"]["status"] == "allowed_after_confirmation"
    assert load_resp.status_code == 200
    saved_payload = load_resp.json()["payload"]
    assert saved_payload["project"] == payload["project"]
    assert saved_payload["review_items"] == payload["review_items"]
    assert saved_payload["confirmation_summary"]["unconfirmed_review_item_count"] == 0
    assert saved_payload["export_policy"]["formal_excel"]["status"] == "allowed_after_confirmation"
    saved = json.loads((tmp_path / "cosmic-confirmation.json").read_text(encoding="utf-8"))
    assert saved == saved_payload
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmation_persists_edited_items(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_confirmation_edited_items"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    payload = _cosmic_export_payload()
    payload["items"][0]["process"] = "维护客户资料"
    payload["items"][0]["user"] = "发起者：客户|接收者：客户资料"
    payload["items"][0]["movements"].append({
        "order": 3,
        "sub_process": "输出客户维护结果",
        "move_type": "X",
        "data_group": "客户维护结果",
        "data_attrs": "处理状态",
        "reuse": "新增",
    })

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)
    load_resp = client.get(f"/api/sessions/{session_id}/cosmic/confirmation")

    assert save_resp.status_code == 200
    saved_payload = load_resp.json()["payload"]
    assert saved_payload["items"][0]["process"] == "维护客户资料"
    assert saved_payload["items"][0]["user"] == "发起者：客户|接收者：客户资料"
    assert len(saved_payload["items"][0]["movements"]) == 3
    assert saved_payload["items"][0]["movements"][2]["sub_process"] == "输出客户维护结果"
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmation_requires_session_access(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = "cosmic_confirmation_other_user"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json={"project": "测试项目"})

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmation_get_missing_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_confirmation_missing"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/sessions/{session_id}/cosmic/confirmation")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)


def _cosmic_export_payload(*, confirmation_status: str = "confirmed") -> dict:
    return {
        "project": "测试项目",
        "status": "review_required",
        "summary": {},
        "issue_codes": {},
        "items": [
            {
                "project": "测试项目",
                "module_l1": "业务",
                "module_l2": "管理",
                "module_l3": "客户",
                "user": "发起者：客户|接收者：客户",
                "trigger": "用户触发",
                "process": "维护客户",
                "status": "review_required",
                "movements": [
                    {
                        "order": 1,
                        "sub_process": "提交客户信息",
                        "move_type": "E",
                        "data_group": "客户信息",
                        "data_attrs": "客户名称",
                        "reuse": "新增",
                    },
                    {
                        "order": 2,
                        "sub_process": "保存客户信息",
                        "move_type": "W",
                        "data_group": "客户信息",
                        "data_attrs": "客户名称",
                        "reuse": "新增",
                    },
                ],
            }
        ],
        "review_items": [
            {
                "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
                "scope": "item",
                "item_index": 0,
                "severity": "warning",
                "code": "GENERIC_FUNCTION_USER",
                "message": "功能用户待确认",
                "field": "user",
                "confirmation": {
                    "status": confirmation_status,
                    "decision": confirmation_status if confirmation_status != "unconfirmed" else "",
                    "note": "",
                    "confirmed_by": "",
                    "confirmed_at": "2026-06-09T00:00:00Z" if confirmation_status != "unconfirmed" else "",
                },
            }
        ],
    }


def test_cosmic_confirmed_export_writes_formal_excel(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_confirmed"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text(json.dumps(_cosmic_export_payload(), ensure_ascii=False), encoding="utf-8")
    confirmation_path = tmp_path / "cosmic-confirmation.json"
    confirmation_path.write_text(json.dumps(_cosmic_export_payload(), ensure_ascii=False), encoding="utf-8")
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    def fake_write_cosmic_xlsx(template, output, report, *, meta=None, cfp_formula=""):
        assert template == str(template_path)
        assert report.project == "测试项目"
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)
    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "项目功能点拆分表-确认后.xlsx"
    assert Path(data["path"]).exists()
    assert data["cfp_total"] == 2.0
    assert data["cfp_summary_file"]["label"] == "COSMIC CFP 总和（确认后）"
    assert Path(data["cfp_summary_file"]["path"]).read_text(encoding="utf-8").strip().endswith("CFP 总和: 2.0")
    assert data["export_policy"]["formal_excel"]["status"] == "allowed_after_confirmation"
    state = server.session_manager.get(session_id)
    assert state is not None
    assert any(item["label"] == "项目功能点拆分表（确认后）" for item in state.done_files)
    assert any(item["label"] == "COSMIC CFP 总和（确认后）" for item in state.done_files)
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmed_export_uses_saved_edited_items(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_edited_items"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    draft_payload = _cosmic_export_payload()
    edited_payload = json.loads(json.dumps(draft_payload, ensure_ascii=False))
    edited_payload["items"][0]["process"] = "维护客户资料"
    edited_payload["items"][0]["movements"].append({
        "order": 3,
        "sub_process": "输出客户维护结果",
        "move_type": "X",
        "data_group": "客户维护结果",
        "data_attrs": "处理状态",
        "reuse": "新增",
    })
    draft_path.write_text(json.dumps(draft_payload, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cosmic-confirmation.json").write_text(
        json.dumps(edited_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    def fake_write_cosmic_xlsx(template, output, report, *, meta=None, cfp_formula=""):
        assert template == str(template_path)
        assert report.results[0].item.process == "维护客户资料"
        assert len(report.results[0].item.movements) == 3
        assert report.results[0].item.movements[2].sub_process == "输出客户维护结果"
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)
    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 200
    assert resp.json()["cfp_total"] == 3.0
    server.session_manager.cleanup_download(session_id)


def test_cosmic_review_action_excludes_movement_and_revalidates(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_review_exclude"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    payload["items"][0]["movements"].append({
        "order": 3,
        "sub_process": "点击下一页并排序列表",
        "move_type": "X",
        "data_group": "页面状态",
        "data_attrs": "排序状态",
        "reuse": "新增",
    })
    payload["review_actions"] = [{
        "action": "exclude_movement",
        "item_index": 0,
        "movement_order": 3,
        "review_id": "item::0::CONTROL_COMMAND_MOVEMENT::movements[2].sub_process::3",
        "reason": "控制命令不计数",
    }]
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)

    def fake_write_cosmic_xlsx(template, output, report, **kwargs):
        assert len(report.results[0].item.movements) == 2
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)
    export_resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][0]["movements"][2]["excluded_from_cfp"] is True
    assert saved_payload["status"] == "passed"
    assert saved_payload["review_items"] == []
    assert saved_payload["export_policy"]["formal_excel"]["status"] == "allowed"
    assert export_resp.status_code == 200
    assert export_resp.json()["cfp_total"] == 2.0
    server.session_manager.cleanup_download(session_id)


def test_cosmic_review_action_applies_function_user_and_revalidates(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_review_function_user"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    payload["items"][0]["module_l3"] = "客户资料"
    payload["items"][0]["user"] = "发起者：操作员|接收者：系统"
    payload["review_actions"] = [{
        "action": "apply_function_user",
        "item_index": 0,
        "suggested_user": "发起者：客户资料|接收者：客户资料",
        "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
    }]
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][0]["user"] == "发起者：客户资料|接收者：客户资料"
    assert saved_payload["status"] == "passed"
    assert "GENERIC_FUNCTION_USER" not in saved_payload["issue_codes"]
    server.session_manager.cleanup_download(session_id)


def test_cosmic_review_action_applies_function_user_role_map(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_review_function_user_role_map"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    payload["items"][0]["module_l3"] = "客户资料"
    payload["items"][0]["user"] = "发起者：操作员|接收者：系统"
    payload["function_user_role_map"] = {
        "客户资料": "发起者：客户资料经办|接收者：客户资料经办",
    }
    payload["review_actions"] = [{
        "action": "apply_function_user",
        "item_index": 0,
        "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
    }]
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][0]["user"] == "发起者：客户资料经办|接收者：客户资料经办"
    assert saved_payload["status"] == "passed"
    assert "GENERIC_FUNCTION_USER" not in saved_payload["issue_codes"]
    server.session_manager.cleanup_download(session_id)


def test_cosmic_review_action_uses_configured_function_user_role_map(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_review_configured_function_user_role_map"
    payload = _cosmic_export_payload()
    payload["items"][0]["module_l3"] = "客户资料"
    payload["items"][0]["user"] = "发起者：操作员|接收者：系统"
    payload["review_actions"] = [{
        "action": "apply_function_user",
        "item_index": 0,
        "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
    }]
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_governance_config",
        lambda: {
            "auto_apply_review_actions": False,
            "auto_apply_issue_codes": [],
            "function_user_role_map": {
                "客户资料": "发起者：客户资料经办|接收者：客户资料经办",
            },
            "require_unique_function_user": False,
            "cfp_formula_consistency_check": False,
            "audit_hash_chain": True,
        },
    )

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][0]["user"] == "发起者：客户资料经办|接收者：客户资料经办"
    assert "audit_hash" in saved_payload["review_audit"][0]
    assert len(saved_payload["review_audit"][0]["audit_hash"]) == 64
    server.session_manager.cleanup_download(session_id)


def test_cosmic_governance_auto_applies_allowed_review_action(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_auto_apply_review_action"
    payload = _cosmic_export_payload()
    payload["items"][0]["movements"].append({
        "order": 3,
        "sub_process": "点击下一页并排序列表",
        "move_type": "X",
        "data_group": "页面状态",
        "data_attrs": "排序状态",
        "reuse": "新增",
    })
    payload["review_items"] = [{
        "review_id": "item::0::CONTROL_COMMAND_MOVEMENT::movements[2].sub_process::3",
        "scope": "item",
        "item_index": 0,
        "movement_order": 3,
        "severity": "warning",
        "code": "CONTROL_COMMAND_MOVEMENT",
        "message": "控制命令待确认",
        "field": "movements[2].sub_process",
        "details": {
            "basis_description": "控制命令不计数",
            "suggested_actions": [{
                "action": "exclude_movement",
                "movement_order": 3,
                "reason": "控制命令不计数",
            }],
        },
        "confirmation": {"status": "unconfirmed"},
    }]
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_governance_config",
        lambda: {
            "auto_apply_review_actions": True,
            "auto_apply_issue_codes": ["CONTROL_COMMAND_MOVEMENT"],
            "function_user_role_map": {},
            "require_unique_function_user": False,
            "cfp_formula_consistency_check": False,
            "audit_hash_chain": True,
        },
    )

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][0]["movements"][2]["excluded_from_cfp"] is True
    assert saved_payload["review_actions"][0]["source"] == "auto_governance"
    assert saved_payload["review_audit"][0]["source"] == "auto_governance"
    assert saved_payload["status"] == "passed"
    server.session_manager.cleanup_download(session_id)


def test_cosmic_cfp_formula_consistency_warning(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_cfp_formula_consistency"
    payload = _cosmic_export_payload()
    payload["cfp_policy"] = {"复用": 0.5}
    payload["review_items"] = []
    payload["items"][0]["status"] = "passed"
    payload["items"][0]["movements"][1]["reuse"] = "复用"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_governance_config",
        lambda: {
            "auto_apply_review_actions": False,
            "auto_apply_issue_codes": [],
            "function_user_role_map": {},
            "require_unique_function_user": False,
            "cfp_formula_consistency_check": True,
            "audit_hash_chain": True,
        },
    )
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_cfp_formula",
        lambda: 'IF(L{row}="复用",0.333333333333,1)',
    )

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["status"] == "review_required"
    assert saved_payload["issue_codes"]["CFP_POLICY_FORMULA_MISMATCH"] == 1
    issue = next(item for item in saved_payload["review_items"] if item["code"] == "CFP_POLICY_FORMULA_MISMATCH")
    assert issue["scope"] == "global"
    assert "复用=0.5" in issue["details"]["missing_policy_terms"]
    assert saved_payload["cfp_basis"]["formula"] == 'IF(L{row}="复用",0.333333333333,1)'
    server.session_manager.cleanup_download(session_id)


def test_cosmic_unique_function_user_governance_revalidates_payload(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_unique_function_user_governance"
    payload = _cosmic_export_payload()
    payload["review_items"] = []
    payload["items"][0]["module_l3"] = "客户资料"
    payload["items"][0]["user"] = "发起者：客户资料|接收者：订单管理"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_governance_config",
        lambda: {
            "auto_apply_review_actions": False,
            "auto_apply_issue_codes": [],
            "function_user_role_map": {},
            "require_unique_function_user": True,
            "cfp_formula_consistency_check": False,
            "audit_hash_chain": True,
        },
    )

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["status"] == "review_required"
    assert saved_payload["issue_codes"]["FUNCTION_USER_ROLE_CONFLICT"] == 1
    assert saved_payload["governance_effective"]["require_unique_function_user"] is True
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmed_export_uses_cfp_policy(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_cfp_policy"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    payload["status"] = "passed"
    payload["review_items"] = []
    payload["items"][0]["status"] = "passed"
    payload["items"][0]["movements"] = [
        {**payload["items"][0]["movements"][0], "reuse": "新增"},
        {**payload["items"][0]["movements"][1], "reuse": "复用"},
        {
            "order": 3,
            "sub_process": "归档历史数据",
            "move_type": "W",
            "data_group": "历史数据",
            "data_attrs": "归档状态",
            "reuse": "利旧",
        },
    ]
    payload["cfp_policy"] = {"新增": 1, "复用": 0.5, "利旧": 0}
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cosmic-confirmation.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)

    def fake_write_cosmic_xlsx(template, output, report, **kwargs):
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 200
    assert resp.json()["cfp_total"] == 1.5
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmed_export_uses_configured_cfp_policy(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_configured_cfp_policy"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    payload["status"] = "passed"
    payload["review_items"] = []
    payload["items"][0]["status"] = "passed"
    payload["items"][0]["movements"] = [
        {**payload["items"][0]["movements"][0], "reuse": "新增"},
        {**payload["items"][0]["movements"][1], "reuse": "复用"},
    ]
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cosmic-confirmation.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_cfp_policy",
        lambda: {"复用": 0.5},
    )

    def fake_write_cosmic_xlsx(template, output, report, **kwargs):
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)
    export_resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert save_resp.status_code == 200
    assert save_resp.json()["payload"]["cfp_policy_effective"]["复用"] == 0.5
    assert export_resp.status_code == 200
    assert export_resp.json()["cfp_total"] == 1.5
    server.session_manager.cleanup_download(session_id)


def test_cosmic_payload_cfp_policy_overrides_configured_policy(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_payload_cfp_policy_override"
    payload = _cosmic_export_payload()
    payload["cfp_policy"] = {"复用": 0.25}
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr(
        "web_app.routes.artifacts.load_gen_cosmic_cfp_policy",
        lambda: {"复用": 0.5},
    )

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)

    assert save_resp.status_code == 200
    assert save_resp.json()["payload"]["cfp_policy_effective"]["复用"] == 0.25
    server.session_manager.cleanup_download(session_id)


def test_cosmic_review_action_excludes_non_functional_process_and_stamps_audit(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_review_exclude_process"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = _cosmic_export_payload()
    non_functional = json.loads(json.dumps(payload["items"][0], ensure_ascii=False))
    non_functional["module_l3"] = "服务器扩容"
    non_functional["process"] = "完成系统迁移和架构改造"
    non_functional["user"] = "发起者：服务器扩容|接收者：服务器扩容"
    payload["items"].append(non_functional)
    payload["review_actions"] = [{
        "action": "exclude_process",
        "item_index": 1,
        "review_id": "item::1::NON_FUNCTIONAL_SCOPE::process::",
        "reason": "非功能事项不进入 COSMIC 功能规模",
    }]
    payload["cfp_policy"] = {"新增": 1, "复用": "bad", "利旧": -1}
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    template_path = tmp_path / "项目功能点拆分表-输出模板.xlsx"
    template_path.write_bytes(b"template")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    monkeypatch.setattr("web_app.routes.artifacts._cosmic_template_path", lambda *_: template_path)

    def fake_write_cosmic_xlsx(template, output, report, **kwargs):
        assert len(report.results) == 1
        assert report.results[0].item.process == payload["items"][0]["process"]
        Path(output).write_bytes(b"xlsx")
        return output

    monkeypatch.setattr("web_app.routes.artifacts.write_cosmic_xlsx", fake_write_cosmic_xlsx)

    save_resp = client.put(f"/api/sessions/{session_id}/cosmic/confirmation", json=payload)
    export_resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert save_resp.status_code == 200
    saved_payload = save_resp.json()["payload"]
    assert saved_payload["items"][1]["excluded_from_cfp"] is True
    assert saved_payload["items"][1]["movements"][0]["excluded_from_cfp"] is True
    assert saved_payload["review_audit"][0]["confirmed_by"] == "alice"
    assert saved_payload["review_audit"][0]["applied_by"] == "alice"
    assert "applied_at" in saved_payload["review_audit"][0]
    assert saved_payload["cfp_policy_effective"]["新增"] == 1.0
    assert saved_payload["cfp_policy_effective"]["复用"] == 1.0 / 3.0
    assert saved_payload["cfp_policy_effective"]["利旧"] == 0.0
    assert export_resp.status_code == 200
    assert export_resp.json()["cfp_total"] == 2.0
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmed_export_blocks_unconfirmed_items(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_unconfirmed"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text(json.dumps(_cosmic_export_payload(confirmation_status="unconfirmed"), ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cosmic-confirmation.json").write_text(
        json.dumps(_cosmic_export_payload(confirmation_status="unconfirmed"), ensure_ascii=False),
        encoding="utf-8",
    )
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 409
    assert "未确认" in resp.json()["detail"]
    server.session_manager.cleanup_download(session_id)


def test_cosmic_draft_can_be_loaded_from_session_artifact(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_draft_artifact"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "项目" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = {
        "project": "测试项目",
        "status": "review_required",
        "preview_rows": [],
        "review_items": [],
        "items": [],
    }
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.record_pipeline_event(session_id, {
        "type": "artifact",
        "step": "cosmic",
        "payload": {
            "label": "COSMIC JSON 草稿",
            "name": draft_path.name,
            "path": str(draft_path),
            "is_temp": True,
        },
    })

    resp = client.get(f"/api/sessions/{session_id}/cosmic/draft")

    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "3.3.gen-cosmic-AI填充-COSMIC.json"
    assert data["payload"] == payload
    server.session_manager.cleanup_download(session_id)


def test_cosmic_draft_falls_back_to_output_search(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_draft_search"
    output_dir = tmp_path / "output"
    draft_path = output_dir / "nested" / "md" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    draft_path.parent.mkdir(parents=True)
    payload = {
        "project": "搜索回退",
        "status": "blocked",
        "preview_rows": [],
        "review_items": [],
        "items": [],
    }
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/sessions/{session_id}/cosmic/draft")

    assert resp.status_code == 200
    assert resp.json()["payload"] == payload
    server.session_manager.cleanup_download(session_id)


def test_cosmic_draft_rejects_artifact_outside_output_dir(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_draft_unsafe_artifact"
    unsafe_path = tmp_path / "scratch" / "3.3.gen-cosmic-AI填充-COSMIC.json"
    unsafe_path.parent.mkdir(parents=True)
    unsafe_path.write_text(
        json.dumps({
            "project": "越界草稿",
            "status": "passed",
            "preview_rows": [],
            "review_items": [],
            "items": [],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)
    server.session_manager.record_pipeline_event(session_id, {
        "type": "artifact",
        "step": "cosmic",
        "payload": {
            "label": "COSMIC JSON 草稿",
            "name": unsafe_path.name,
            "path": str(unsafe_path),
            "is_temp": True,
        },
    })

    resp = client.get(f"/api/sessions/{session_id}/cosmic/draft")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)


def test_cosmic_draft_requires_session_access(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="bob")
    session_id = "cosmic_draft_other_user"
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=tmp_path)

    resp = client.get(f"/api/sessions/{session_id}/cosmic/draft")

    assert resp.status_code == 404
    server.session_manager.cleanup_download(session_id)


def _cosmic_preview_payload(*, confirmation_status: str) -> dict:
    return {
        "project": "测试项目",
        "status": "review_required",
        "summary": {"review_required": 1},
        "issue_codes": {"GENERIC_FUNCTION_USER": 1},
        "review_items": [
            {
                "review_id": "item::0::GENERIC_FUNCTION_USER::user::",
                "scope": "item",
                "item_index": 0,
                "severity": "warning",
                "code": "GENERIC_FUNCTION_USER",
                "message": "功能用户待确认",
                "field": "user",
                "confirmation": {
                    "status": confirmation_status,
                    "decision": confirmation_status if confirmation_status != "unconfirmed" else "",
                    "note": "",
                    "confirmed_by": "",
                    "confirmed_at": "",
                },
            }
        ],
        "preview_rows": [],
        "items": [
            {
                "project": "测试项目",
                "module_l1": "业务",
                "module_l2": "管理",
                "module_l3": "客户管理",
                "user": "发起者：操作员|接收者：客户管理",
                "trigger": "用户提交",
                "process": "维护客户",
                "status": "review_required",
                "movements": [
                    {
                        "order": 1,
                        "sub_process": "提交客户信息",
                        "move_type": "E",
                        "data_group": "客户信息",
                        "data_attrs": "客户名称",
                        "reuse": "新增",
                    },
                    {
                        "order": 2,
                        "sub_process": "保存客户信息",
                        "move_type": "W",
                        "data_group": "客户信息",
                        "data_attrs": "客户名称",
                        "reuse": "新增",
                    },
                ],
            }
        ],
    }


def test_cosmic_confirmed_export_writes_excel_and_done_file(monkeypatch, tmp_path):
    history_db = tmp_path / "history.sqlite3"
    monkeypatch.setattr("web_app.services.run_history_service.service_history_path", lambda base_dir: history_db)
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_confirmed"
    work_dir = tmp_path
    md_dir = work_dir / "output" / "md"
    md_dir.mkdir(parents=True)
    draft_path = md_dir / "3.3.gen-cosmic-AI填充-COSMIC.json"
    payload = _cosmic_preview_payload(confirmation_status="confirmed")
    draft_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (work_dir / "cosmic-confirmation.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=work_dir)
    zip_path = work_dir / f"交付物_{session_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(work_dir / "output"))
    server.session_manager.set_zip(session_id, zip_path)
    run_history_service.finish_web_run(
        base_dir=tmp_path,
        session_id=session_id,
        mode="remote",
        task_mode="from-excel-gen-cosmic",
        input_path=str(work_dir / "input.xlsx"),
        owner_id="alice",
        owner_label="alice",
        zip_path=str(zip_path),
        done_files=[],
    )

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 200
    data = resp.json()
    output_path = Path(data["path"])
    assert output_path.name == "项目功能点拆分表-确认后.xlsx"
    assert output_path.exists()
    assert data["file"]["label"] == "项目功能点拆分表（确认后）"
    assert data["cfp_total"] == 2.0
    cfp_summary_path = work_dir / "output" / "md" / "3.5.gen-cosmic-CFP-总和.md"
    assert Path(data["cfp_summary_file"]["path"]) == cfp_summary_path
    assert cfp_summary_path.read_text(encoding="utf-8").strip().endswith("CFP 总和: 2.0")
    state = server.session_manager.get(session_id)
    assert state is not None
    assert any(item["path"] == str(output_path) for item in state.done_files)
    assert any(item["path"] == str(cfp_summary_path) for item in state.done_files)
    with zipfile.ZipFile(zip_path) as archive:
        assert "cosmic文档/项目功能点拆分表-确认后.xlsx" in archive.namelist()
        assert "md/3.5.gen-cosmic-CFP-总和.md" in archive.namelist()
    history = run_history_service.get_history_item(
        base_dir=tmp_path,
        run_id=session_id,
        local_mode=False,
        owner_id="alice",
    )
    assert history is not None
    assert history["zip_path"] == str(zip_path)
    assert history["done_files"][0]["label"] == "项目功能点拆分表（确认后）"
    assert history["done_files"][0]["relative_path"] == "项目功能点拆分表-确认后.xlsx"
    assert history["done_files"][1]["label"] == "COSMIC CFP 总和（确认后）"
    assert history["done_files"][1]["relative_path"] == "3.5.gen-cosmic-CFP-总和.md"
    server.session_manager.cleanup_download(session_id)


def test_cosmic_confirmed_export_blocks_unconfirmed_payload(monkeypatch, tmp_path):
    client = _client(monkeypatch, user="alice")
    session_id = "cosmic_export_unconfirmed"
    work_dir = tmp_path
    md_dir = work_dir / "output" / "md"
    md_dir.mkdir(parents=True)
    payload = _cosmic_preview_payload(confirmation_status="unconfirmed")
    (md_dir / "3.3.gen-cosmic-AI填充-COSMIC.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (work_dir / "cosmic-confirmation.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    server.session_manager.create(session_id, mode="remote", owner="alice", work_dir=work_dir)

    resp = client.post(f"/api/sessions/{session_id}/cosmic/export-confirmed")

    assert resp.status_code == 409
    assert not (work_dir / "output" / "cosmic文档" / "项目功能点拆分表-确认后.xlsx").exists()
    server.session_manager.cleanup_download(session_id)
