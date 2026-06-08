from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RUN_HISTORY_FILENAME = "run_history.sqlite3"
_init_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def user_history_path() -> Path:
    return Path.home() / ".ai-gen-reimbursement-docs" / "history" / RUN_HISTORY_FILENAME


def service_history_path(base_dir: Path) -> Path:
    return base_dir / "products" / RUN_HISTORY_FILENAME


def connect(history_path: Path) -> sqlite3.Connection:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(history_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(history_path: Path) -> None:
    with _init_lock:
        with connect(history_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version INTEGER PRIMARY KEY,
                  applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_history (
                  run_id TEXT PRIMARY KEY,
                  schema_version INTEGER NOT NULL DEFAULT 1,
                  source TEXT NOT NULL,
                  session_id TEXT NOT NULL DEFAULT '',
                  mode TEXT NOT NULL,
                  owner_id TEXT NOT NULL DEFAULT '',
                  owner_label TEXT NOT NULL DEFAULT '',
                  task_mode TEXT NOT NULL DEFAULT '',
                  run_state TEXT NOT NULL,
                  input_name TEXT NOT NULL DEFAULT '',
                  input_path TEXT NOT NULL DEFAULT '',
                  output_dir TEXT NOT NULL DEFAULT '',
                  artifact_kind TEXT NOT NULL,
                  zip_path TEXT NOT NULL DEFAULT '',
                  download_expires_at TEXT NOT NULL DEFAULT '',
                  done_files_json TEXT NOT NULL DEFAULT '[]',
                  run_config_json TEXT NOT NULL DEFAULT '{}',
                  error TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL,
                  started_at TEXT NOT NULL DEFAULT '',
                  finished_at TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_run_history_created
                ON run_history(created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_run_history_owner_created
                ON run_history(owner_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_run_history_source_mode_state
                ON run_history(source, mode, run_state, created_at DESC);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, now_iso()),
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(run_history)").fetchall()
            }
            if "run_config_json" not in columns:
                conn.execute(
                    "ALTER TABLE run_history "
                    "ADD COLUMN run_config_json TEXT NOT NULL DEFAULT '{}'"
                )


def sanitize_done_files(done_files: list[dict[str, Any]], *, remote: bool) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in done_files:
        raw_path = str(item.get("path") or item.get("relative_path") or item.get("name") or "")
        path = Path(raw_path)
        name = str(item.get("name") or item.get("label") or path.name or raw_path)
        entry: dict[str, Any] = {
            "name": name,
            "label": str(item.get("label") or name),
            "is_temp": bool(item.get("is_temp", False)),
        }
        if "size" in item:
            entry["size"] = item["size"]
        if "size_kb" in item:
            entry["size_kb"] = item["size_kb"]
        if remote:
            entry["relative_path"] = path.name or name
        else:
            entry["path"] = raw_path
        sanitized.append(entry)
    return sanitized


def _record_for_db(record: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    created_at = str(record.get("created_at") or now)
    updated_at = str(record.get("updated_at") or now)
    done_files = record.get("done_files", [])
    if not isinstance(done_files, list):
        done_files = []
    remote = record.get("mode") == "remote"
    done_files = sanitize_done_files(done_files, remote=remote)
    values = {
        "run_id": str(record["run_id"]),
        "schema_version": int(record.get("schema_version") or SCHEMA_VERSION),
        "source": str(record.get("source") or "web"),
        "session_id": str(record.get("session_id") or ""),
        "mode": str(record.get("mode") or "local"),
        "owner_id": str(record.get("owner_id") or ""),
        "owner_label": str(record.get("owner_label") or ""),
        "task_mode": str(record.get("task_mode") or ""),
        "run_state": str(record.get("run_state") or "running"),
        "input_name": str(record.get("input_name") or ""),
        "input_path": str(record.get("input_path") or ""),
        "output_dir": str(record.get("output_dir") or ""),
        "artifact_kind": str(record.get("artifact_kind") or "local_dir"),
        "zip_path": str(record.get("zip_path") or ""),
        "download_expires_at": str(record.get("download_expires_at") or ""),
        "done_files_json": json.dumps(done_files, ensure_ascii=False),
        "error": str(record.get("error") or ""),
        "created_at": created_at,
        "started_at": str(record.get("started_at") or ""),
        "finished_at": str(record.get("finished_at") or ""),
        "updated_at": updated_at,
    }
    if "run_config" in record:
        run_config = record.get("run_config")
        if not isinstance(run_config, dict):
            run_config = {}
        run_config = dict(run_config)
        run_config.pop("api_key", None)
        values["run_config_json"] = json.dumps(run_config, ensure_ascii=False)
    return values


def upsert_run(record: dict[str, Any], history_path: Path) -> None:
    init_db(history_path)
    values = _record_for_db(record)
    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    assignments = ", ".join(
        f"{column}=excluded.{column}"
        for column in columns
        if column != "run_id"
    )
    sql = (
        f"INSERT INTO run_history ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(run_id) DO UPDATE SET {assignments}"
    )
    with connect(history_path) as conn:
        conn.execute(sql, tuple(values[column] for column in columns))


def get_run(run_id: str, history_path: Path) -> dict[str, Any] | None:
    init_db(history_path)
    with connect(history_path) as conn:
        row = conn.execute(
            "SELECT * FROM run_history WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return _row_to_record(row) if row else None


def list_runs(
    history_path: Path,
    *,
    filters: dict[str, str] | None = None,
    exclude_states: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    init_db(history_path)
    filters = filters or {}
    where: list[str] = []
    params: list[Any] = []
    for key in ("source", "mode", "run_state", "owner_id"):
        value = filters.get(key)
        if value and value != "all":
            where.append(f"{key} = ?")
            params.append(value)
    if exclude_states:
        placeholders = ", ".join("?" for _ in exclude_states)
        where.append(f"run_state NOT IN ({placeholders})")
        params.extend(exclude_states)
    sql = "SELECT * FROM run_history"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(limit, 200)), max(0, offset)])
    with connect(history_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_row_to_record(row) for row in rows]


def update_run_state(
    run_id: str,
    history_path: Path,
    *,
    run_state: str,
    error: str | None = None,
    finished_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any] | None:
    init_db(history_path)
    updated_at = updated_at or now_iso()
    assignments = ["run_state = ?", "updated_at = ?"]
    params: list[Any] = [run_state, updated_at]
    if error is not None:
        assignments.append("error = ?")
        params.append(error)
    if finished_at is not None:
        assignments.append("finished_at = ?")
        params.append(finished_at)
    params.append(run_id)
    with connect(history_path) as conn:
        cursor = conn.execute(
            f"UPDATE run_history SET {', '.join(assignments)} WHERE run_id = ?",
            tuple(params),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM run_history WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return _row_to_record(row) if row else None


def update_run_config(
    run_id: str,
    history_path: Path,
    *,
    run_config: dict[str, Any],
    updated_at: str | None = None,
) -> dict[str, Any] | None:
    init_db(history_path)
    updated_at = updated_at or now_iso()
    sanitized = dict(run_config) if isinstance(run_config, dict) else {}
    sanitized.pop("api_key", None)
    with connect(history_path) as conn:
        cursor = conn.execute(
            """
            UPDATE run_history
            SET run_config_json = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (json.dumps(sanitized, ensure_ascii=False), updated_at, run_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM run_history WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return _row_to_record(row) if row else None


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    try:
        record["done_files"] = json.loads(record.pop("done_files_json") or "[]")
    except json.JSONDecodeError:
        record["done_files"] = []
    try:
        run_config = json.loads(record.pop("run_config_json", "{}") or "{}")
    except json.JSONDecodeError:
        run_config = {}
    record["run_config"] = run_config if isinstance(run_config, dict) else {}
    return compute_artifact_status(record)


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def compute_artifact_status(record: dict[str, Any]) -> dict[str, Any]:
    artifact_kind = record.get("artifact_kind")
    output_dir = Path(str(record.get("output_dir") or ""))
    zip_path = Path(str(record.get("zip_path") or ""))
    expires_at = _parse_iso(str(record.get("download_expires_at") or ""))
    now = datetime.now(UTC)

    record["open_folder_available"] = bool(
        artifact_kind == "local_dir"
        and record.get("mode") == "local"
        and str(record.get("output_dir") or "")
        and output_dir.exists()
    )
    record["download_available"] = bool(
        artifact_kind == "remote_zip"
        and str(record.get("zip_path") or "")
        and zip_path.exists()
        and (expires_at is None or expires_at > now)
    )
    return record
