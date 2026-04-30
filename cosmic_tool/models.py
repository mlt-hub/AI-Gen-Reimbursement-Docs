"""Data models for COSMIC function point decomposition."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionModule:
    """A functional module extracted from requirements document."""
    name: str
    level: int  # 1, 2, or 3 (章节层级)
    description: str = ""
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)


@dataclass
class DataMovement:
    """A single data movement in a COSMIC functional process."""
    order: int
    sub_process: str
    move_type: str  # E, X, R, W
    data_group: str
    data_attrs: str  # comma-separated


@dataclass
class CosmicItem:
    """A complete COSMIC function point item (one functional process)."""
    project: str
    module_l1: str
    module_l2: str
    module_l3: str
    user: str       # "发起者：xxx|接收者：xxx"
    trigger: str    # "用户触发" or "定时触发"
    process: str    # 功能过程名称
    movements: list[DataMovement] = field(default_factory=list)

    def total_cfp(self) -> int:
        """Calculate total CFP (each data movement = 1 for '新增')."""
        return len(self.movements)

    def to_rows(self) -> list[dict]:
        """Convert to flat row dicts for Excel output."""
        rows = []
        for i, m in enumerate(self.movements):
            rows.append({
                "project": self.project,
                "module_l1": self.module_l1,
                "module_l2": self.module_l2,
                "module_l3": self.module_l3,
                "user": self.user if i == 0 else "",
                "trigger": self.trigger if i == 0 else "",
                "process": self.process if i == 0 else "",
                "sub_process": m.sub_process,
                "move_type": m.move_type,
                "data_group": m.data_group,
                "data_attrs": m.data_attrs,
                "reuse": "新增",
                "cfp": "1",
            })
        return rows
