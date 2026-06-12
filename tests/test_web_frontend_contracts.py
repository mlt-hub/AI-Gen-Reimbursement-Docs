from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_view_exposes_restore_and_asset_retention_contracts():
    source = (ROOT / "web_app" / "src" / "views" / "History.vue").read_text(encoding="utf-8")

    assert "重跑输入和模板快照保留策略" in source
    assert "task_assets_retention_label" in source
    assert "local_input_snapshot_enabled" in source
    assert "/api/tasks/${item.run_id}/restore" in source
    assert "canRestore(item)" in source


def test_task_detail_view_exposes_closed_restore_action():
    source = (ROOT / "web_app" / "src" / "views" / "TaskDetail.vue").read_text(encoding="utf-8")

    assert "恢复任务" in source
    assert "/api/tasks/${historyItem.value.run_id}/restore" in source
    assert "canRestore" in source


def test_config_view_exposes_cosmic_governance_editor_contract():
    source = (ROOT / "web_app" / "src" / "views" / "Config.vue").read_text(encoding="utf-8")

    assert "COSMIC 治理" in source
    assert "/api/web-config/cosmic-governance" in source
    assert "auto_apply_review_actions" in source
    assert "auto_apply_issue_codes" in source
    assert "function_user_role_map" in source
    assert "boundary_context" in source
    assert "rule_matrix" in source
    assert "audit_ledger_path_env" in source
