from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict


PipelineEventType = Literal[
    "step_started",
    "activity",
    "artifact",
    "input_required",
    "step_done",
    "step_failed",
    "step_cancelled",
]
PipelineStep = Literal["basedata", "fpa", "spec", "cosmic", "list"]


class PipelineEvent(TypedDict, total=False):
    type: PipelineEventType
    step: PipelineStep
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PipelineCallbacks:
    is_web_mode: Callable[[], bool] = lambda: False
    check_cancelled: Callable[[], None] = lambda: None
    emit_event: Callable[[dict[str, Any]], None] = lambda data: None
    wait_for_fpa_input: Callable[[float], float] = lambda default: default
    wait_for_list_input: Callable[[float, float], tuple[float, float]] = (
        lambda cfp, fpa: (cfp, fpa)
    )
