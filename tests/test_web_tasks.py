import json
import threading
from pathlib import Path

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
    ["/login", "/preview/fpa", "/sessions/demo-session/fpa/debug"],
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
