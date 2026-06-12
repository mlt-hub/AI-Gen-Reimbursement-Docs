import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from web_app.services import task_assets_service


def test_snapshot_input_file_writes_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(task_assets_service, "task_assets_retention_seconds", lambda: 86400)
    source = tmp_path / "功能清单.xlsx"
    source.write_bytes(b"input")

    snapshot = task_assets_service.snapshot_input_file(
        base_dir=tmp_path,
        session_id="session1",
        source=source,
        mode="remote",
        owner_id="alice",
        source_run_id="original1",
    )

    assert snapshot.read_bytes() == b"input"
    metadata = json.loads((tmp_path / "products" / "task_assets" / "session1" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["session_id"] == "session1"
    assert metadata["source_run_id"] == "original1"
    assert metadata["mode"] == "remote"
    assert metadata["owner_id"] == "alice"
    assert metadata["input_path"] == str(snapshot)
    assert metadata["retention_expires_at"]


def test_cleanup_expired_task_assets_removes_old_dirs_and_writes_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(task_assets_service, "task_assets_retention_seconds", lambda: 60)
    root = tmp_path / "products" / "task_assets"
    old_dir = root / "old_session"
    fresh_dir = root / "fresh_session"
    old_dir.mkdir(parents=True)
    fresh_dir.mkdir(parents=True)
    old_created = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    fresh_created = datetime.now(UTC).isoformat()
    (old_dir / "metadata.json").write_text(json.dumps({"created_at": old_created}), encoding="utf-8")
    (fresh_dir / "metadata.json").write_text(json.dumps({"created_at": fresh_created}), encoding="utf-8")

    removed = task_assets_service.cleanup_expired_task_assets(base_dir=tmp_path)

    assert removed == 1
    assert not old_dir.exists()
    assert fresh_dir.exists()
    audit = (tmp_path / "products" / "task_assets_cleanup.jsonl").read_text(encoding="utf-8")
    assert "old_session" in audit
    assert "retention_expired" in audit


def test_cleanup_expired_task_assets_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(task_assets_service, "task_assets_retention_seconds", lambda: 0)
    old_dir = tmp_path / "products" / "task_assets" / "old_session"
    old_dir.mkdir(parents=True)
    (old_dir / "metadata.json").write_text(
        json.dumps({"created_at": (datetime.now(UTC) - timedelta(days=10)).isoformat()}),
        encoding="utf-8",
    )

    assert task_assets_service.cleanup_expired_task_assets(base_dir=tmp_path) == 0
    assert old_dir.exists()
