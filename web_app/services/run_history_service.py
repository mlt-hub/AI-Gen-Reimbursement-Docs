from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_gen_reimbursement_docs.run_history import (
    connect,
    get_run,
    init_db,
    list_runs,
    now_iso,
    service_history_path,
    update_run_config,
    update_run_state,
    upsert_run,
    user_history_path,
)
from web_app.services.config_service import remote_session_retention_seconds


logger = logging.getLogger("ai_gen_reimbursement_docs")
UNRECOVERABLE_SESSION_ERROR = "服务已重启或会话已结束，无法继续当前执行"


def _history_path(*, base_dir: Path, mode: str) -> Path:
    if mode == "remote":
        return service_history_path(base_dir)
    return user_history_path()


def _display_mode(mode_info: dict[str, dict[str, str]], task_mode: str) -> str:
    item = mode_info.get(task_mode, {})
    return item.get("label") or task_mode


def _infer_project_name(input_path: str) -> str:
    if not input_path:
        return ""
    try:
        from ai_gen_reimbursement_docs.pipeline import _try_read_project_name

        return _try_read_project_name(input_path)
    except Exception as exc:
        logger.debug("完成时推断项目名失败: %s", exc)
        return ""


def _backfill_finished_project_name(
    *,
    session_id: str,
    history_path: Path,
    input_path: str,
    updated_at: str,
) -> None:
    record = get_run(session_id, history_path)
    if record is None:
        return
    run_config = record.get("run_config")
    if not isinstance(run_config, dict):
        run_config = {}
    else:
        run_config = dict(run_config)
    if str(run_config.get("project_name") or "").strip():
        return
    project_name = _infer_project_name(input_path)
    if not project_name:
        return
    run_config["project_name"] = project_name
    update_run_config(
        session_id,
        history_path,
        run_config=run_config,
        updated_at=updated_at,
    )


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
    run_config: dict[str, Any] | None = None,
    run_state: str = "running",
) -> None:
    now = now_iso()
    path = _history_path(base_dir=base_dir, mode=mode)
    input_name = Path(input_path).name
    state = run_state if run_state in {"queued", "running"} else "running"
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
                "input_name": input_name,
                "input_path": input_path,
                "output_dir": output_dir if mode == "local" else "",
                "artifact_kind": "remote_zip" if mode == "remote" else "local_dir",
                "created_at": now,
                "started_at": now if state == "running" else "",
                "updated_at": now,
                "run_config": run_config or {},
            },
            path,
        )
    except Exception as exc:
        logger.warning("运行历史写入失败: %s", exc)


def mark_web_run_started(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
) -> None:
    now = now_iso()
    path = _history_path(base_dir=base_dir, mode=mode)
    try:
        updated = update_run_state(
            session_id,
            path,
            run_state="running",
            error="",
            updated_at=now,
        )
        if updated is None:
            return
        init_db(path)
        with connect(path) as conn:
            conn.execute(
                "UPDATE run_history SET started_at = ? WHERE run_id = ?",
                (now, session_id),
            )
    except Exception as exc:
        logger.warning("运行历史启动状态更新失败: %s", exc)


def cancel_web_run(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    error: str = "cancelled",
) -> None:
    now = now_iso()
    path = _history_path(base_dir=base_dir, mode=mode)
    try:
        update_run_state(
            session_id,
            path,
            run_state="cancelled",
            error=error,
            finished_at=now,
            updated_at=now,
        )
    except Exception as exc:
        logger.warning("运行历史取消状态更新失败: %s", exc)


def fail_web_run(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    error: str,
) -> None:
    now = now_iso()
    path = _history_path(base_dir=base_dir, mode=mode)
    try:
        update_run_state(
            session_id,
            path,
            run_state="error",
            error=error,
            finished_at=now,
            updated_at=now,
        )
    except Exception as exc:
        logger.warning("运行历史失败状态更新失败: %s", exc)


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
                "input_path": input_path,
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
        _backfill_finished_project_name(
            session_id=session_id,
            history_path=path,
            input_path=input_path,
            updated_at=now,
        )
    except Exception as exc:
        logger.warning("运行历史写入失败: %s", exc)


def append_done_file_to_history(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    done_file: dict[str, Any],
    zip_path: str = "",
) -> None:
    path = _history_path(base_dir=base_dir, mode=mode)
    try:
        record = get_run(session_id, path)
        if record is None:
            return
        files = record.get("done_files")
        if not isinstance(files, list):
            files = []
        done_key = Path(str(done_file.get("path") or done_file.get("relative_path") or done_file.get("name") or "")).name
        merged = []
        for item in files:
            item_key = Path(str(item.get("path") or item.get("relative_path") or item.get("name") or "")).name
            if item_key != done_key:
                merged.append(item)
        merged.append(done_file)
        record = {
            **record,
            "done_files": merged,
            "updated_at": now_iso(),
        }
        if mode == "remote" and zip_path:
            record["zip_path"] = zip_path
        upsert_run(record, path)
    except Exception as exc:
        logger.warning("运行历史更新确认后产物失败: %s", exc)


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


def list_tasks(
    *,
    base_dir: Path,
    local_mode: bool,
    owner_id: str,
    mode: str = "all",
    state: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    filters = {
        "source": "web",
        "mode": mode,
        "run_state": state,
    }
    if local_mode:
        path = user_history_path()
    else:
        path = service_history_path(base_dir)
        filters["owner_id"] = owner_id
    items = list_runs(
        path,
        filters=filters,
        exclude_states=["closed"],
        limit=limit,
        offset=offset,
    )
    return {"items": items}


def cancel_stale_queued_web_runs(*, base_dir: Path) -> int:
    message = "服务重启，排队任务已取消"
    total = 0
    for path in (user_history_path(), service_history_path(base_dir)):
        try:
            while True:
                items = list_runs(
                    path,
                    filters={"source": "web", "run_state": "queued"},
                    limit=200,
                    offset=0,
                )
                if not items:
                    break
                for item in items:
                    now = now_iso()
                    if update_run_state(
                        str(item.get("run_id") or ""),
                        path,
                        run_state="cancelled",
                        error=message,
                        finished_at=now,
                        updated_at=now,
                    ) is not None:
                        total += 1
        except Exception as exc:
            logger.warning("清理遗留排队任务失败: %s", exc)
    return total


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


def close_history_item(
    *,
    base_dir: Path,
    run_id: str,
    local_mode: bool,
    owner_id: str,
) -> dict[str, Any]:
    path = user_history_path() if local_mode else service_history_path(base_dir)
    record = get_run(run_id, path)
    if record is None:
        raise ValueError("历史记录不存在")
    if not local_mode and record.get("owner_id") != owner_id:
        raise PermissionError("历史记录不存在")
    if record.get("run_state") == "running":
        raise RuntimeError("运行中任务不能关闭，请先取消任务")
    if record.get("run_state") == "closed":
        return record
    run_config = record.get("run_config")
    if not isinstance(run_config, dict):
        run_config = {}
    else:
        run_config = dict(run_config)
    run_config["closed_from_state"] = str(record.get("run_state") or "")
    update_run_config(
        run_id,
        path,
        run_config=run_config,
    )
    updated = update_run_state(run_id, path, run_state="closed")
    if updated is None:
        raise ValueError("历史记录不存在")
    return updated


def restore_closed_history_item(
    *,
    base_dir: Path,
    run_id: str,
    local_mode: bool,
    owner_id: str,
) -> dict[str, Any]:
    path = user_history_path() if local_mode else service_history_path(base_dir)
    record = get_run(run_id, path)
    if record is None:
        raise ValueError("历史记录不存在")
    if not local_mode and record.get("owner_id") != owner_id:
        raise PermissionError("历史记录不存在")
    if record.get("source") != "web":
        raise RuntimeError("仅支持恢复 Web 任务")
    if record.get("run_state") != "closed":
        raise RuntimeError("仅关闭任务可恢复")

    run_config = record.get("run_config")
    if not isinstance(run_config, dict):
        run_config = {}
    previous_state = str(run_config.get("closed_from_state") or "").strip()
    if previous_state not in {"done", "error", "cancelled"}:
        error = str(record.get("error") or "")
        if error == "cancelled":
            previous_state = "cancelled"
        elif error:
            previous_state = "error"
        else:
            previous_state = "done"

    updated = update_run_state(run_id, path, run_state=previous_state)
    if updated is None:
        raise ValueError("历史记录不存在")
    return updated


def mark_unrecoverable_history_item(
    *,
    base_dir: Path,
    run_id: str,
    local_mode: bool,
    owner_id: str,
) -> dict[str, Any]:
    path = user_history_path() if local_mode else service_history_path(base_dir)
    record = get_run(run_id, path)
    if record is None:
        raise ValueError("历史记录不存在")
    if not local_mode and record.get("owner_id") != owner_id:
        raise PermissionError("历史记录不存在")
    if record.get("source") != "web":
        raise RuntimeError("仅支持标记 Web 任务")
    if record.get("run_state") != "running":
        raise RuntimeError("仅运行中任务可标记为不可恢复")
    now = now_iso()
    updated = update_run_state(
        run_id,
        path,
        run_state="cancelled",
        error=UNRECOVERABLE_SESSION_ERROR,
        finished_at=now,
        updated_at=now,
    )
    if updated is None:
        raise ValueError("历史记录不存在")
    return updated


def require_rerunnable_history_item(
    *,
    base_dir: Path,
    run_id: str,
    local_mode: bool,
    owner_id: str,
) -> dict[str, Any]:
    record = get_history_item(
        base_dir=base_dir,
        run_id=run_id,
        local_mode=local_mode,
        owner_id=owner_id,
    )
    if record is None:
        raise ValueError("历史记录不存在")
    state = str(record.get("run_state") or "")
    if state == "closed":
        raise RuntimeError("关闭任务不能重跑")
    if state == "running":
        raise RuntimeError("运行中任务不能重跑")
    if state not in {"done", "error", "cancelled"}:
        raise RuntimeError("当前任务状态不能重跑")
    if record.get("source") != "web":
        raise RuntimeError("仅支持重跑 Web 任务")
    input_path = Path(str(record.get("input_path") or ""))
    if not input_path.exists():
        raise FileNotFoundError("原始输入文件不存在，无法重跑")
    return record
