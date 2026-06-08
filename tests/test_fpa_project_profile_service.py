import json

from web_app.services.fpa_project_profile_service import (
    load_project_profile_decisions,
    merge_decision_payloads,
    persist_project_profile_decisions,
    profile_path,
    serialize_decisions,
)


def test_persist_project_profile_decisions_only_saves_explicit_scope(tmp_path):
    saved = persist_project_profile_decisions(
        config_root=tmp_path,
        confirmed_decisions={
            "merge_query_demo": {"value": "yes", "scope": "project_profile"},
            "merge_crud_demo": {"value": "no", "scope": "current_run"},
        },
    )

    assert serialize_decisions(saved) == {
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }
    payload = json.loads(profile_path(tmp_path).read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["confirmed_decisions"] == {
        "merge_query_demo": {"value": "yes", "scope": "project_profile"},
    }


def test_load_and_merge_project_profile_decisions(tmp_path):
    profile_path(tmp_path).write_text(
        json.dumps({
            "version": 1,
            "confirmed_decisions": {
                "query_type_demo": {"value": "eq", "scope": "project_profile"},
                "ignored": {"value": "yes", "scope": "current_run"},
            },
        }),
        encoding="utf-8",
    )

    persisted = load_project_profile_decisions(tmp_path)
    merged = merge_decision_payloads(
        persisted,
        {
            "query_type_demo": {"value": "ei", "scope": "current_run"},
            "eif_boundary_demo": {"value": "no", "scope": "current_run"},
        },
    )

    assert serialize_decisions(merged) == {
        "eif_boundary_demo": {"value": "no", "scope": "current_run"},
        "query_type_demo": {"value": "ei", "scope": "current_run"},
    }
