from __future__ import annotations

import json
import queue
import threading
from uuid import uuid4
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal


def _now_utc() -> datetime:
    return datetime.now(UTC)


def queue_msg(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False)


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
    queue_position: int | None = None
    done_files: list[dict[str, Any]] = field(default_factory=list)
    progress_steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    log_entries: list[dict[str, Any]] = field(default_factory=list)
    log_streams: dict[str, queue.Queue] = field(default_factory=dict)


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

    def subscribe_log_stream(
        self,
        session_id: str,
        *,
        queue_size: int = 2000,
    ) -> tuple[str, queue.Queue] | None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return None
            stream_id = uuid4().hex
            q: queue.Queue = queue.Queue(maxsize=queue_size)
            legacy_queue = state.queue
            if legacy_queue is not None:
                while True:
                    try:
                        q.put_nowait(legacy_queue.get_nowait())
                    except queue.Empty:
                        break
                    except queue.Full:
                        break
            state.log_streams[stream_id] = q
            state.updated_at = _now_utc()
            return stream_id, q

    def remove_log_stream(self, session_id: str, stream_id: str) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.log_streams.pop(stream_id, None)
            state.updated_at = _now_utc()

    def publish_log_event(self, session_id: str, event: dict[str, Any]) -> None:
        msg = queue_msg(event)
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            streams = list(state.log_streams.values())
        for stream_queue in streams:
            try:
                stream_queue.put_nowait(msg)
            except queue.Full:
                pass

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
                state.queue_position = None
                state.updated_at = now

    def mark_task_queued(self, session_id: str, queue_position: int) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                now = _now_utc()
                state.task_created_at = None
                state.task_done_at = None
                state.last_error = None
                state.queue_position = queue_position
                state.updated_at = now

    def set_queue_position(self, session_id: str, queue_position: int | None) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.queue_position = queue_position
                state.updated_at = _now_utc()

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
                state.queue_position = None
                state.updated_at = now

    def run_state(self, session_id: str) -> str | None:
        state = self.get(session_id)
        if state is None:
            return None
        if state.queue_position is not None and state.task_created_at is None and state.task_done_at is None:
            return "queued"
        if state.last_error == "cancelled":
            return "cancelled"
        if state.last_error:
            return "error"
        if state.task_done_at is not None:
            return "done"
        if state.task_created_at is not None:
            return "running"
        return "queued"

    def running_count(self) -> int:
        with self._lock:
            return sum(
                1
                for state in self._sessions.values()
                if state.task_created_at is not None
                and state.task_done_at is None
                and not state.last_error
            )

    def set_done_files(self, session_id: str, files: list[dict[str, Any]]) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.done_files = files
                state.updated_at = _now_utc()

    def record_pipeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        self.record_log_event(session_id, event)
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
                "activity_payloads": [],
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
                payload = dict(event.get("payload") or {})
                if payload and payload not in progress["activity_payloads"]:
                    progress["activity_payloads"].append(payload)
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

    def record_log_event(self, session_id: str, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        if event_type not in {
            "log",
            "done",
            "error",
            "cancelled",
            "prompt",
            "prompt_list",
            "fpa_confirmation_required",
            "step_started",
            "activity",
            "artifact",
            "input_required",
            "step_done",
            "step_failed",
            "step_cancelled",
        }:
            return
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.log_entries.append(dict(event))
            if len(state.log_entries) > 2000:
                state.log_entries = state.log_entries[-2000:]
            state.updated_at = _now_utc()

    def get_log_entries(self, session_id: str) -> list[dict[str, Any]]:
        state = self.get(session_id)
        if state is None:
            return []
        return [dict(entry) for entry in state.log_entries]

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
