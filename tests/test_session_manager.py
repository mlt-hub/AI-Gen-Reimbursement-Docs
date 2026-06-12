import threading
from datetime import timedelta
from pathlib import Path

from web_app.services.session_manager import SessionManager, _now_utc


def test_create_and_cancel_wakes_input_waiter():
    manager = SessionManager()
    manager.create("s1", mode="local", output_dir=Path("out"))
    event = threading.Event()

    manager.set_input_waiter("s1", event)
    manager.cancel("s1")

    assert manager.is_cancelled("s1") is True
    assert event.is_set()


def test_submit_input_stores_result_and_clears_waiter():
    manager = SessionManager()
    manager.create("s1", mode="remote", owner="alice")
    event = threading.Event()

    manager.set_input_waiter("s1", event)
    ok = manager.submit_input("s1", {"value": 42})

    assert ok is True
    assert event.is_set()
    assert manager.pop_input_result("s1") == {"value": 42}
    assert manager.submit_input("s1", {"value": 43}) is False


def test_cleanup_download_removes_session_and_returns_work_dir():
    manager = SessionManager()
    work_dir = Path("work")
    manager.create("s1", mode="remote", work_dir=work_dir)

    assert manager.cleanup_download("s1") == work_dir
    assert manager.get("s1") is None


def test_can_access_remote_session_only_for_owner():
    manager = SessionManager()
    manager.create("s1", mode="remote", owner="alice")

    assert manager.can_access("s1", "alice") is True
    assert manager.can_access("s1", "bob") is False
    assert manager.can_access("s1", None) is False


def test_can_access_allows_only_request_local_mode_for_local_sessions():
    manager = SessionManager()
    manager.create("local-session", mode="local")
    manager.create("remote-session", mode="remote", owner="alice")

    assert manager.can_access("local-session", None) is False
    assert manager.can_access("local-session", None, local_mode=True) is True
    assert manager.can_access("remote-session", None, local_mode=True) is True
    assert manager.can_access("missing", "alice", local_mode=True) is False


def test_cleanup_expired_returns_remote_work_dirs():
    manager = SessionManager()
    old = _now_utc() - timedelta(seconds=3600)
    fresh = _now_utc()
    old_work_dir = Path("old-work")
    fresh_work_dir = Path("fresh-work")

    manager.create("old-remote", mode="remote", work_dir=old_work_dir).updated_at = old
    manager.create("old-local", mode="local", output_dir=Path("local-out")).updated_at = old
    manager.create("fresh-remote", mode="remote", work_dir=fresh_work_dir).updated_at = fresh

    assert manager.cleanup_expired(60) == [old_work_dir]
    assert manager.get("old-remote") is None
    assert manager.get("old-local") is None
    assert manager.get("fresh-remote") is not None


def test_cleanup_expired_does_not_return_local_work_dir():
    manager = SessionManager()
    old = _now_utc() - timedelta(seconds=3600)
    local_work_dir = Path("local-work")

    manager.create("old-local", mode="local", work_dir=local_work_dir).updated_at = old

    assert manager.cleanup_expired(60) == []
    assert manager.get("old-local") is None


def test_task_lifecycle_fields_are_recorded():
    manager = SessionManager()
    manager.create("s1", mode="remote", owner="alice")

    manager.mark_task_started("s1")
    state = manager.get("s1")

    assert state is not None
    assert state.task_created_at is not None
    assert state.task_done_at is None
    assert state.last_error is None

    manager.mark_task_finished("s1", last_error="boom")

    assert state.task_done_at is not None
    assert state.last_error == "boom"


def test_pipeline_events_build_progress_snapshot():
    manager = SessionManager()
    manager.create("s1", mode="local")

    manager.record_pipeline_event("s1", {
        "type": "step_started",
        "step": "fpa",
        "message": "生成 FPA 工作量评估",
    })
    manager.record_pipeline_event("s1", {
        "type": "activity",
        "step": "fpa",
        "message": "正在写入 FPA Excel 模板",
        "payload": {"summary_type": "template_preflight", "templates": [{"kind": "fpa"}]},
    })
    manager.record_pipeline_event("s1", {
        "type": "artifact",
        "step": "fpa",
        "payload": {"label": "FPA 工作量评估", "path": "fpa.xlsx"},
    })
    manager.record_pipeline_event("s1", {
        "type": "step_done",
        "step": "fpa",
        "message": "FPA 工作量评估已生成",
    })

    progress = manager.get_progress_steps("s1")

    assert progress[0]["key"] == "fpa"
    assert progress[0]["status"] == "done"
    assert progress[0]["current_action"] == "FPA 工作量评估已生成"
    assert progress[0]["activity_payloads"] == [
        {"summary_type": "template_preflight", "templates": [{"kind": "fpa"}]}
    ]
    assert progress[0]["artifacts"] == [{"label": "FPA 工作量评估", "path": "fpa.xlsx"}]
    assert progress[0]["started_at"]
    assert progress[0]["finished_at"]


def test_pipeline_events_are_retained_as_log_snapshot():
    manager = SessionManager()
    manager.create("s1", mode="local")

    manager.record_pipeline_event("s1", {
        "type": "step_started",
        "step": "fpa",
        "message": "生成 FPA 工作量评估",
    })
    manager.record_log_event("s1", {
        "type": "log",
        "level": "INFO",
        "msg": "hello",
        "time": "10:00:00",
    })

    logs = manager.get_log_entries("s1")

    assert logs == [
        {
            "type": "step_started",
            "step": "fpa",
            "message": "生成 FPA 工作量评估",
        },
        {
            "type": "log",
            "level": "INFO",
            "msg": "hello",
            "time": "10:00:00",
        },
    ]


def test_log_stream_subscribers_receive_independent_event_copies():
    manager = SessionManager()
    manager.create("s1", mode="local")
    first = manager.subscribe_log_stream("s1")
    second = manager.subscribe_log_stream("s1")

    assert first is not None
    assert second is not None
    first_id, first_queue = first
    second_id, second_queue = second

    manager.publish_log_event("s1", {"type": "log", "level": "INFO", "msg": "hello"})

    assert first_queue.get_nowait() == '{"type": "log", "level": "INFO", "msg": "hello"}'
    assert second_queue.get_nowait() == '{"type": "log", "level": "INFO", "msg": "hello"}'

    manager.remove_log_stream("s1", first_id)
    manager.publish_log_event("s1", {"type": "done", "files": []})

    assert second_queue.get_nowait() == '{"type": "done", "files": []}'
    assert first_queue.empty()
    manager.remove_log_stream("s1", second_id)


def test_cancel_active_progress_marks_running_step_cancelled():
    manager = SessionManager()
    manager.create("s1", mode="local")
    manager.record_pipeline_event("s1", {
        "type": "step_started",
        "step": "spec",
        "message": "生成需求说明书",
    })

    manager.cancel_active_progress("s1")

    progress = manager.get_progress_steps("s1")
    assert progress[0]["status"] == "cancelled"
    assert progress[0]["current_action"] == "任务已被用户停止"
    assert progress[0]["finished_at"]


def test_step_cancelled_event_updates_progress_snapshot():
    manager = SessionManager()
    manager.create("s1", mode="local")

    manager.record_pipeline_event("s1", {
        "type": "step_cancelled",
        "step": "list",
        "message": "任务已被用户停止",
    })

    progress = manager.get_progress_steps("s1")
    assert progress[0]["key"] == "list"
    assert progress[0]["status"] == "cancelled"
