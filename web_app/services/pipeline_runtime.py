import json
import logging
import queue
import threading
from datetime import datetime

from ai_gen_reimbursement_docs.exceptions import CancelledError
from ai_gen_reimbursement_docs.runtime_context import session_var, web_mode_var
from web_app.services.session_manager import SessionManager


def emit_session_event(session_manager: SessionManager, data: dict) -> None:
    """向当前 session 的 SSE 队列发送结构化事件。data 必须含 'type' 字段。"""
    sid = session_var.get()
    if not sid:
        return
    session_manager.record_pipeline_event(sid, data)
    q = session_manager.get_queue(sid)
    if q:
        q.put(json.dumps(data, ensure_ascii=False))


def wait_for_fpa_input(session_manager: SessionManager, default_fpa: float) -> float:
    """在 pipeline 线程中调用，通过 SSE 通知前端弹输入框，等待用户确认送审工作量。"""
    sid = session_var.get()
    if not sid:
        return default_fpa

    event = threading.Event()
    session_manager.set_input_waiter(sid, event)

    emit_session_event(session_manager, {
        "type": "prompt",
        "field": "fpa_reduced",
        "default": default_fpa,
        "msg": f"请输入送审工作量（直接确认则使用默认值：{default_fpa}）",
    })

    event.wait(timeout=1800)
    result = session_manager.pop_input_result(sid)
    if session_manager.is_cancelled(sid):
        raise CancelledError("任务已被用户停止")
    return float(result.get("fpa_reduced", default_fpa))


def wait_for_fpa_confirmation(
    session_manager: SessionManager,
    payload: dict,
) -> dict:
    """在 FPA 批量生成中暂停，等待前端提交计量口径确认结果。"""
    sid = session_var.get()
    if not sid:
        return {}

    event = threading.Event()
    session_manager.set_input_waiter(sid, event)

    emit_session_event(session_manager, {
        "type": "input_required",
        "step": "fpa",
        "message": "等待确认 FPA 计量口径",
        "payload": payload,
    })
    emit_session_event(session_manager, {
        "type": "fpa_confirmation_required",
        **payload,
    })

    event.wait(timeout=1800)
    result = session_manager.pop_input_result(sid)
    if session_manager.is_cancelled(sid):
        raise CancelledError("任务已被用户停止")
    if str(result.get("kind") or "") != "fpa_confirmation":
        return {}
    decisions = result.get("confirmed_decisions")
    return decisions if isinstance(decisions, dict) else {}


def wait_for_list_input(
    session_manager: SessionManager,
    default_cfp: float,
    default_fpa: float,
) -> tuple[float, float]:
    """在 pipeline 线程中调用（gen-list），等待用户确认送审工作量和送审功能点。"""
    sid = session_var.get()
    if not sid:
        return default_cfp, default_fpa

    event = threading.Event()
    session_manager.set_input_waiter(sid, event)

    emit_session_event(session_manager, {
        "type": "prompt_list",
        "cfp_default": default_cfp,
        "fpa_default": default_fpa,
    })

    event.wait(timeout=1800)
    result = session_manager.pop_input_result(sid)
    if session_manager.is_cancelled(sid):
        raise CancelledError("任务已被用户停止")
    cfp_total = float(result.get("cfp_total", default_cfp))
    fpa_reduced = float(result.get("fpa_reduced", default_fpa))
    return cfp_total, fpa_reduced


def is_web_mode() -> bool:
    """判断当前线程是否在 Web UI pipeline 中运行。"""
    return bool(web_mode_var.get())


def check_cancelled(session_manager: SessionManager):
    """检查当前 session 是否已被取消，若是则抛出 CancelledError。"""
    sid = session_var.get()
    if sid and session_manager.is_cancelled(sid):
        raise CancelledError("任务已被用户停止")


class SessionHandler(logging.Handler):
    """将日志路由到对应 session 的队列，实现多会话日志隔离。"""

    def __init__(self, session_manager: SessionManager):
        super().__init__()
        self.session_manager = session_manager

    def emit(self, record):
        sid = session_var.get()
        q = self.session_manager.get_queue(sid) if sid else None
        if q is not None:
            msg = json.dumps(
                {
                    "type": "log",
                    "level": record.levelname,
                    "msg": self.format(record),
                    "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                },
                ensure_ascii=False,
            )
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass
