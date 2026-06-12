from pathlib import Path

from web_app.services.session_manager import SessionManager
from web_app.services.task_queue import QueuedTask, TaskQueue


def _task(session_id: str, *, started: list[str], cancelled: list[str], failed: list[str]) -> QueuedTask:
    return QueuedTask(
        session_id=session_id,
        mode="local",
        owner="",
        target=lambda: None,
        on_started=lambda: started.append(session_id),
        on_cancelled=lambda message: cancelled.append(f"{session_id}:{message}"),
        on_failed_to_start=lambda message: failed.append(f"{session_id}:{message}"),
    )


def test_queue_starts_next_task_when_running_task_finishes():
    manager = SessionManager()
    manager.create("s1", mode="local", output_dir=Path("out1"))
    manager.create("s2", mode="local", output_dir=Path("out2"))
    callbacks = []
    started: list[str] = []
    cancelled: list[str] = []
    failed: list[str] = []

    def fake_start(session_manager, session_id, target, *, on_done=None):
        session_manager.mark_task_started(session_id)
        callbacks.append(on_done)
        return None

    queue = TaskQueue(
        session_manager=manager,
        max_concurrent_tasks=lambda: 1,
        start_fn=fake_start,
    )

    first = queue.submit(_task("s1", started=started, cancelled=cancelled, failed=failed))
    second = queue.submit(_task("s2", started=started, cancelled=cancelled, failed=failed))

    assert first == {"run_state": "running", "queue_position": None}
    assert second == {"run_state": "queued", "queue_position": 1}
    assert started == ["s1"]
    assert manager.run_state("s2") == "queued"

    manager.mark_task_finished("s1")
    callbacks[0]()

    assert started == ["s1", "s2"]
    assert manager.run_state("s2") == "running"
    assert manager.get("s2").queue_position is None


def test_queue_cancel_removes_queued_task_without_starting_it():
    manager = SessionManager()
    manager.create("s1", mode="local", output_dir=Path("out1"))
    manager.create("s2", mode="local", output_dir=Path("out2"))
    started: list[str] = []
    cancelled: list[str] = []
    failed: list[str] = []

    def fake_start(session_manager, session_id, target, *, on_done=None):
        session_manager.mark_task_started(session_id)
        return None

    queue = TaskQueue(
        session_manager=manager,
        max_concurrent_tasks=lambda: 1,
        start_fn=fake_start,
    )
    queue.submit(_task("s1", started=started, cancelled=cancelled, failed=failed))
    queue.submit(_task("s2", started=started, cancelled=cancelled, failed=failed))

    assert queue.cancel("s2") is True

    assert started == ["s1"]
    assert cancelled == ["s2:cancelled"]
    assert manager.run_state("s2") == "cancelled"
