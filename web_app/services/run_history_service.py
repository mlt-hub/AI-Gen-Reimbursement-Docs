from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_gen_reimbursement_docs.run_history import (
    get_run,
    list_runs,
    now_iso,
    service_history_path,
    upsert_run,
    user_history_path,
)
from web_app.services.config_service import remote_session_retention_seconds


logger = logging.getLogger("ai_gen_reimbursement_docs")


def _history_path(*, base_dir: Path, mode: str) -> Path:
    if mode == "remote":
        return service_history_path(base_dir)
    return user_history_path()


def _display_mode(mode_info: dict[str, dict[str, str]], task_mode: str) -> str:
    item = mode_info.get(task_mode, {})
    return item.get("label") or task_mode


def start_web_run(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    task_mode: str,
    input_path: str,
    owner_id: str = "",
    owner_label: str = "",
    output_dir: str = "",
) -> None:
    now = now_iso()
    path = _history_path(base_dir=base_dir, mode=mode)
    input_name = Path(input_path).name
    try:
        upsert_run(
            {
                "run_id": session_id,
                "session_id": session_id,
                "source": "web",
                "mode": mode,
                "owner_id": owner_id if mode == "remote" else "",
                "owner_label": owner_label if mode == "remote" else "",
                "task_mode": task_mode,
                "run_state": "running",
                "input_name": input_name,
                "input_path": "" if mode == "remote" else input_path,
                "output_dir": output_dir if mode == "local" else "",
                "artifact_kind": "remote_zip" if mode == "remote" else "local_dir",
                "created_at": now,
                "started_at": now,
                "updated_at": now,
            },
            path,
        )
    except Exception as exc:
        logger.warning("运行历史写入失败: %s", exc)


def finish_web_run(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    task_mode: str,
    input_path: str = "",
    owner_id: str = "",
    owner_label: str = "",
    output_dir: str = "",
    zip_path: str = "",
    done_files: list[dict[str, Any]] | None = None,
    error: str = "",
) -> None:
    now = now_iso()
    state = "cancelled" if error == "cancelled" else ("error" if error else "done")
    expires_at = ""
    if mode == "remote" and zip_path:
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=remote_session_retention_seconds())
        ).isoformat()
    path = _history_path(base_dir=base_dir, mode=mode)
    try:
        upsert_run(
            {
                "run_id": session_id,
                "session_id": session_id,
                "source": "web",
                "mode": mode,
                "owner_id": owner_id if mode == "remote" else "",
                "owner_label": owner_label if mode == "remote" else "",
                "task_mode": task_mode,
                "run_state": state,
                "input_name": Path(input_path).name if input_path else "",
                "input_path": "" if mode == "remote" else input_path,
                "output_dir": output_dir if mode == "local" else "",
                "artifact_kind": "remote_zip" if mode == "remote" else "local_dir",
                "zip_path": zip_path if mode == "remote" else "",
                "download_expires_at": expires_at,
                "done_files": done_files or [],
                "error": "" if state == "done" else error,
                "finished_at": now,
                "updated_at": now,
            },
            path,
        )
    except Exception as exc:
        logger.warning("运行历史写入失败: %s", exc)


def list_history(
    *,
    base_dir: Path,
    local_mode: bool,
    owner_id: str,
    source: str = "all",
    mode: str = "all",
    state: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    filters = {
        "source": source,
        "mode": mode,
        "run_state": state,
    }
    if local_mode:
        path = user_history_path()
    else:
        path = service_history_path(base_dir)
        filters["owner_id"] = owner_id
    items = list_runs(path, filters=filters, limit=limit, offset=offset)
    return {
        "retention": {
            "remote_download_retention_days": round(remote_session_retention_seconds() / 86400, 2),
            "local_retention_label": "本机与 CLI 文件不由 Web UI 自动清理",
        },
        "items": items,
    }


def get_history_item(
    *,
    base_dir: Path,
    run_id: str,
    local_mode: bool,
    owner_id: str,
) -> dict[str, Any] | None:
    path = user_history_path() if local_mode else service_history_path(base_dir)
    record = get_run(run_id, path)
    if record is None:
        return None
    if not local_mode and record.get("owner_id") != owner_id:
        return None
    return record
