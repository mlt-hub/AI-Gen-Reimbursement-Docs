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
    reuse: str = "新增"  # 新增/复用/利旧
    move_type_flagged: bool = False  # True if move_type was fuzzy-matched


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
    warnings: list[str] = field(default_factory=list)

    def total_cfp(self) -> int:
        """Calculate total CFP (each data movement = 1 for '新增')."""
        return len(self.movements)

    def to_rows(self) -> list[dict]:
        """Convert to flat row dicts for Excel output。无 movements 时至少生成一行，显示 L1/L2/L3/功能过程。"""
        if not self.movements:
            return [{
                "project": self.project,
                "module_l1": self.module_l1,
                "module_l2": self.module_l2,
                "module_l3": self.module_l3,
                "user": self.user.replace("|", "\n") if self.user else "",
                "trigger": self.trigger,
                "process": self.process,
                "sub_process": "",
                "move_type": "",
                "data_group": "",
                "data_attrs": "",
                "reuse": "",
                "cfp": "",
                "warnings": self.warnings,
                "move_type_flagged": False,
            }]
        rows = []
        for i, m in enumerate(self.movements):
            rows.append({
                "project": self.project,
                "module_l1": self.module_l1,
                "module_l2": self.module_l2,
                "module_l3": self.module_l3,
                "user": self.user.replace("|", "\n"),
                "trigger": self.trigger,
                "process": self.process,
                "sub_process": m.sub_process,
                "move_type": m.move_type,
                "data_group": m.data_group,
                "data_attrs": m.data_attrs,
                "reuse": m.reuse,
                "cfp": "",
                "warnings": self.warnings if i == 0 else [],
                "move_type_flagged": m.move_type_flagged,
            })
        return rows
