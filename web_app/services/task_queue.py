from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from web_app.services.session_manager import SessionManager
from web_app.services.task_runner import start_background_task


TaskMode = Literal["local", "remote"]
TaskStarter = Callable[[SessionManager, str, Callable[[], None]], object]


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class QueuedTask:
    session_id: str
    mode: TaskMode
    owner: str
    target: Callable[[], None]
    on_started: Callable[[], None]
    on_cancelled: Callable[[str], None]
    on_failed_to_start: Callable[[str], None]
    created_at: datetime = field(default_factory=_now_utc)


class TaskQueue:
    def __init__(
        self,
        *,
        session_manager: SessionManager,
        max_concurrent_tasks: Callable[[], int],
        start_fn: Callable[..., object] = start_background_task,
    ) -> None:
        self._session_manager = session_manager
        self._max_concurrent_tasks = max_concurrent_tasks
        self._start_fn = start_fn
        self._queue: list[QueuedTask] = []
        self._lock = threading.RLock()
        self._logger = logging.getLogger("ai_gen_reimbursement_docs")

    def submit(self, task: QueuedTask) -> dict[str, int | str | None]:
        with self._lock:
            if self._can_start_locked() and not self._queue:
                self._start_locked(task)
                return {"run_state": "running", "queue_position": None}
            self._queue.append(task)
            self._refresh_positions_locked()
            return {
                "run_state": "queued",
                "queue_position": self._visible_position_locked(
                    task.session_id,
                    local_mode=task.mode == "local",
                    owner=task.owner,
                ),
            }

    def cancel(self, session_id: str, *, message: str = "cancelled") -> bool:
        with self._lock:
            for index, task in enumerate(self._queue):
                if task.session_id != session_id:
                    continue
                self._queue.pop(index)
                self._session_manager.cancel(session_id)
                self._session_manager.mark_task_finished(session_id, last_error="cancelled")
                task.on_cancelled(message)
                self._refresh_positions_locked()
                return True
        return False

    def visible_position(
        self,
        session_id: str,
        *,
        local_mode: bool,
        owner: str,
    ) -> int | None:
        with self._lock:
            return self._visible_position_locked(
                session_id,
                local_mode=local_mode,
                owner=owner,
            )

    def schedule_next(self) -> None:
        with self._lock:
            while self._queue and self._can_start_locked():
                task = self._queue.pop(0)
                self._refresh_positions_locked()
                self._start_locked(task)

    def _can_start_locked(self) -> bool:
        return self._session_manager.running_count() < self._max_concurrent()

    def _max_concurrent(self) -> int:
        try:
            value = int(self._max_concurrent_tasks())
        except (TypeError, ValueError):
            return 1
        return max(1, value)

    def _start_locked(self, task: QueuedTask) -> None:
        try:
            task.on_started()
            self._start_fn(
                self._session_manager,
                task.session_id,
                task.target,
                on_done=self.schedule_next,
            )
        except Exception as exc:
            message = str(exc)
            self._logger.exception("启动排队任务失败: session=%s", task.session_id)
            self._session_manager.mark_task_finished(task.session_id, last_error=message)
            task.on_failed_to_start(message)
            self.schedule_next()

    def _refresh_positions_locked(self) -> None:
        for index, task in enumerate(self._queue, start=1):
            self._session_manager.mark_task_queued(task.session_id, index)

    def _visible_position_locked(
        self,
        session_id: str,
        *,
        local_mode: bool,
        owner: str,
    ) -> int | None:
        visible_index = 0
        for task in self._queue:
            if local_mode or task.mode == "local" or task.owner == owner:
                visible_index += 1
            if task.session_id == session_id:
                return visible_index
        return None
