from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ai_gen_reimbursement_docs.run_history import (
    get_run,
    list_runs,
    now_iso,
    upsert_run,
)


def test_run_history_upserts_and_computes_local_status(tmp_path):
    db = tmp_path / "run_history.sqlite3"
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    upsert_run(
        {
            "run_id": "r1",
            "source": "cli",
            "mode": "local",
            "task_mode": "gen-all",
            "run_state": "running",
            "output_dir": str(output_dir),
            "artifact_kind": "local_dir",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        db,
    )
    upsert_run(
        {
            "run_id": "r1",
            "source": "cli",
            "mode": "local",
            "task_mode": "gen-all",
            "run_state": "done",
            "output_dir": str(output_dir),
            "artifact_kind": "local_dir",
            "done_files": [{"label": "FPA", "path": str(output_dir / "fpa.xlsx")}],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        db,
    )

    record = get_run("r1", db)

    assert record is not None
    assert record["run_state"] == "done"
    assert record["open_folder_available"] is True
    assert record["done_files"][0]["path"].endswith("fpa.xlsx")


def test_run_history_sanitizes_remote_file_paths(tmp_path):
    db = tmp_path / "run_history.sqlite3"
    zip_path = tmp_path / "result.zip"
    zip_path.write_bytes(b"zip")

    upsert_run(
        {
            "run_id": "r2",
            "source": "web",
            "mode": "remote",
            "owner_id": "alice",
            "task_mode": "gen-all",
            "run_state": "done",
            "artifact_kind": "remote_zip",
            "zip_path": str(zip_path),
            "download_expires_at": "2999-01-01T00:00:00+00:00",
            "done_files": [{"label": "SPEC", "path": str(tmp_path / "secret" / "spec.docx")}],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        db,
    )

    record = get_run("r2", db)

    assert record is not None
    assert record["download_available"] is True
    assert "path" not in record["done_files"][0]
    assert record["done_files"][0]["relative_path"] == "spec.docx"


def test_run_history_persists_run_config_without_api_key(tmp_path):
    db = tmp_path / "run_history.sqlite3"

    upsert_run(
        {
            "run_id": "r_config",
            "source": "web",
            "mode": "local",
            "task_mode": "gen-fpa",
            "run_state": "done",
            "artifact_kind": "local_dir",
            "run_config": {
                "model": "original-model",
                "base_url": "https://api.example.test",
                "api_key": "sk-should-not-be-used",
                "fpa_profile": "strict_fpa",
            },
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        db,
    )

    record = get_run("r_config", db)

    assert record is not None
    assert record["run_config"]["model"] == "original-model"
    assert record["run_config"]["base_url"] == "https://api.example.test"
    assert "api_key" not in record["run_config"]


def test_run_history_concurrent_writes_do_not_drop_records(tmp_path):
    db = tmp_path / "run_history.sqlite3"

    def write(index: int) -> None:
        upsert_run(
            {
                "run_id": f"r{index}",
                "source": "web",
                "mode": "remote",
                "owner_id": "alice",
                "task_mode": "gen-fpa",
                "run_state": "done",
                "artifact_kind": "remote_zip",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
            db,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(20)))

    records = list_runs(db, filters={"owner_id": "alice"}, limit=50)

    assert len(records) == 20
