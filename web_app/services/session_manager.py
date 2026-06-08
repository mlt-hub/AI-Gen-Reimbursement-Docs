from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class SessionState:
    session_id: str
    mode: Literal["local", "remote"]
    queue: queue.Queue | None
    owner: str | None = None
    output_dir: Path | None = None
    config_root: Path | None = None
    zip_path: Path | None = None
    work_dir: Path | None = None
    cancelled: bool = False
    input_event: threading.Event | None = None
    input_result: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    task_created_at: datetime | None = None
    task_done_at: datetime | None = None
    last_error: str | None = None
    done_files: list[dict[str, Any]] = field(default_factory=list)
    progress_steps: dict[str, dict[str, Any]] = field(default_factory=dict)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def create(
        self,
        session_id: str,
        *,
        mode: Literal["local", "remote"],
        owner: str | None = None,
        output_dir: Path | None = None,
        config_root: Path | None = None,
        work_dir: Path | None = None,
        queue_size: int = 2000,
    ) -> SessionState:
        state = SessionState(
            session_id=session_id,
            mode=mode,
            owner=owner,
            output_dir=output_dir,
            config_root=config_root,
            work_dir=work_dir,
            queue=queue.Queue(maxsize=queue_size),
        )
        with self._lock:
            self._sessions[session_id] = state
        return state

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_queue(self, session_id: str) -> queue.Queue | None:
        state = self.get(session_id)
        return state.queue if state else None

    def can_access(
        self,
        session_id: str,
        user: str | None,
        *,
        local_mode: bool = False,
    ) -> bool:
        state = self.get(session_id)
        if state is None:
            return False
        if local_mode or state.mode == "local":
            return True
        return bool(user and state.owner == user)

    def cancel(self, session_id: str) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.cancelled = True
            state.updated_at = _now_utc()
            if state.input_event:
                state.input_event.set()

    def is_cancelled(self, session_id: str) -> bool:
        state = self.get(session_id)
        return bool(state and state.cancelled)

    def clear_cancelled(self, session_id: str) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.cancelled = False
                state.updated_at = _now_utc()

    def set_input_waiter(self, session_id: str, event: threading.Event) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.input_event = event
                state.input_result = {}
                state.updated_at = _now_utc()

    def pop_input_result(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return {}
            result = state.input_result
            state.input_result = {}
            state.input_event = None
            state.updated_at = _now_utc()
            return result

    def submit_input(self, session_id: str, data: dict[str, Any]) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or state.input_event is None:
                return False
            state.input_result = data
            state.input_event.set()
            state.updated_at = _now_utc()
            return True

    def set_zip(self, session_id: str, zip_path: Path) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.zip_path = zip_path
                state.updated_at = _now_utc()

    def mark_task_started(self, session_id: str) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                now = _now_utc()
                state.task_created_at = now
                state.task_done_at = None
                state.last_error = None
                state.updated_at = now

    def mark_task_finished(
        self,
        session_id: str,
        *,
        last_error: str | None = None,
    ) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                now = _now_utc()
                state.task_done_at = now
                state.last_error = last_error
                state.updated_at = now

    def set_done_files(self, session_id: str, files: list[dict[str, Any]]) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.done_files = files
                state.updated_at = _now_utc()

    def record_pipeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        step = str(event.get("step") or "")
        event_type = str(event.get("type") or "")
        if not step or event_type not in {
            "step_started", "activity", "artifact", "input_required",
            "step_done", "step_failed", "step_cancelled",
        }:
            return
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            now = _now_utc()
            progress = state.progress_steps.setdefault(step, {
                "key": step,
                "status": "pending",
                "current_action": "",
                "artifacts": [],
                "started_at": None,
                "finished_at": None,
                "error": "",
            })
            message = str(event.get("message") or "")
            if event_type == "step_started":
                progress["status"] = "running"
                progress["started_at"] = now.isoformat()
                progress["finished_at"] = None
                progress["error"] = ""
            elif event_type == "activity":
                progress["current_action"] = message
            elif event_type == "artifact":
                artifact = dict(event.get("payload") or {})
                if artifact and artifact not in progress["artifacts"]:
                    progress["artifacts"].append(artifact)
            elif event_type == "input_required":
                progress["status"] = "waiting_input"
                progress["current_action"] = message
            elif event_type == "step_done":
                progress["status"] = "done"
                progress["current_action"] = message
                progress["finished_at"] = now.isoformat()
            elif event_type == "step_failed":
                progress["status"] = "failed"
                progress["error"] = message
                progress["finished_at"] = now.isoformat()
            elif event_type == "step_cancelled":
                progress["status"] = "cancelled"
                progress["current_action"] = message
                progress["finished_at"] = now.isoformat()
            state.updated_at = now

    def cancel_active_progress(self, session_id: str, message: str = "任务已被用户停止") -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            active = None
            for step in state.progress_steps.values():
                if step.get("status") in {"running", "waiting_input"}:
                    active = step
            if active is None:
                return
            now = _now_utc()
            active["status"] = "cancelled"
            active["current_action"] = message
            active["finished_at"] = now.isoformat()
            state.updated_at = now

    def get_progress_steps(self, session_id: str) -> list[dict[str, Any]]:
        state = self.get(session_id)
        if state is None:
            return []
        order = ["basedata", "fpa", "spec", "cosmic", "list"]
        return [
            dict(state.progress_steps[key])
            for key in order
            if key in state.progress_steps
        ]

    def remove_queue(self, session_id: str) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.queue = None
                state.updated_at = _now_utc()

    def cleanup_download(self, session_id: str) -> Path | None:
        with self._lock:
            state = self._sessions.pop(session_id, None)
        return state.work_dir if state else None

    def cleanup_expired(self, max_age_seconds: int) -> list[Path]:
        threshold = _now_utc() - timedelta(seconds=max_age_seconds)
        with self._lock:
            expired = [
                (sid, state) for sid, state in self._sessions.items()
                if state.updated_at < threshold
            ]
            work_dirs = [
                state.work_dir for _, state in expired
                if state.mode == "remote" and state.work_dir is not None
            ]
            for sid, _ in expired:
                self._sessions.pop(sid, None)
        return work_dirs
