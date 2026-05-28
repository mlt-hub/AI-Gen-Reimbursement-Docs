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


def test_can_access_allows_local_mode_and_local_sessions():
    manager = SessionManager()
    manager.create("local-session", mode="local")
    manager.create("remote-session", mode="remote", owner="alice")

    assert manager.can_access("local-session", None) is True
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
