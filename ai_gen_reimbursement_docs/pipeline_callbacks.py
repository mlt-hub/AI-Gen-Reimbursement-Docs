from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PipelineCallbacks:
    is_web_mode: Callable[[], bool] = lambda: False
    check_cancelled: Callable[[], None] = lambda: None
    emit_event: Callable[[dict[str, Any]], None] = lambda data: None
    wait_for_fpa_input: Callable[[float], float] = lambda default: default
    wait_for_list_input: Callable[[float, float], tuple[float, float]] = (
        lambda cfp, fpa: (cfp, fpa)
    )
