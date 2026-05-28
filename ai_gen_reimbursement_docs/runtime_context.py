from __future__ import annotations

from contextvars import ContextVar

from ai_gen_reimbursement_docs.pipeline_callbacks import PipelineCallbacks


session_var: ContextVar[str | None] = ContextVar("session_id", default=None)
web_mode_var: ContextVar[str] = ContextVar("web_mode", default="")
callbacks_var: ContextVar[PipelineCallbacks | None] = ContextVar(
    "pipeline_callbacks",
    default=None,
)


def current_callbacks() -> PipelineCallbacks:
    return callbacks_var.get() or PipelineCallbacks()
