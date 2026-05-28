import pytest

from ai_gen_reimbursement_docs import pipeline
from ai_gen_reimbursement_docs.exceptions import CancelledError
from ai_gen_reimbursement_docs.llm_client import call_llm
from ai_gen_reimbursement_docs.pipeline_callbacks import PipelineCallbacks
from ai_gen_reimbursement_docs.runtime_context import callbacks_var, current_callbacks


def test_pipeline_callbacks_default_cli_behavior():
    callbacks = PipelineCallbacks()

    assert callbacks.is_web_mode() is False
    assert callbacks.check_cancelled() is None
    assert callbacks.emit_event({"type": "step"}) is None
    assert callbacks.wait_for_fpa_input(1.5) == 1.5
    assert callbacks.wait_for_list_input(2.0, 3.0) == (2.0, 3.0)


def test_current_callbacks_uses_context_and_resets():
    callbacks = PipelineCallbacks(is_web_mode=lambda: True)
    token = callbacks_var.set(callbacks)
    try:
        assert current_callbacks() is callbacks
    finally:
        callbacks_var.reset(token)

    assert current_callbacks().is_web_mode() is False


def test_pipeline_step_uses_callbacks_event():
    events = []
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        emit_event=events.append,
    )
    token = callbacks_var.set(callbacks)
    try:
        pipeline._step("fpa")
    finally:
        callbacks_var.reset(token)

    assert events == [{"type": "step", "key": "fpa"}]


def test_pipeline_check_cancelled_uses_callbacks():
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        check_cancelled=lambda: (_ for _ in ()).throw(CancelledError("stop")),
    )
    token = callbacks_var.set(callbacks)
    try:
        with pytest.raises(CancelledError, match="stop"):
            pipeline._check_cancelled()
    finally:
        callbacks_var.reset(token)


def test_llm_client_checks_cancelled_before_api_call(monkeypatch):
    called = {"created": False}

    class _Messages:
        def create(self, **kwargs):
            called["created"] = True
            return object()

    class _Anthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    monkeypatch.setattr("anthropic.Anthropic", _Anthropic)
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        check_cancelled=lambda: (_ for _ in ()).throw(CancelledError("stop")),
    )
    token = callbacks_var.set(callbacks)
    try:
        with pytest.raises(CancelledError, match="stop"):
            call_llm("hello", api_key="key", save_logs=False)
    finally:
        callbacks_var.reset(token)

    assert called["created"] is False
