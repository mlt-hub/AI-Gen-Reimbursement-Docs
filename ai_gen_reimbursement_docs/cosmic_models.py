"""COSMIC 功能点度量数据模型。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataMovement:
    """COSMIC 功能过程中的单次数据移动。"""
    order: int
    sub_process: str
    move_type: str  # E, X, R, W
    data_group: str
    data_attrs: str
    reuse: str = "新增"
    move_type_flagged: bool = False
    cfp_override: float | None = None
    cfp_basis: dict[str, Any] = field(default_factory=dict)


@dataclass
class CosmicItem:
    """一个完整的 COSMIC 功能过程条目。"""
    project: str
    module_l1: str
    module_l2: str
    module_l3: str
    user: str       # "发起者：xxx|接收者：xxx"
    trigger: str    # "用户触发" or "定时触发"
    process: str    # 功能过程名称
    movements: list[DataMovement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def total_cfp(self) -> float:
        """计算总 CFP（新增=1，复用=1/3）。"""
        total = 0.0
        for m in self.movements:
            if m.reuse == "复用":
                total += 1.0 / 3.0
            else:
                total += 1.0
        return total

    def to_rows(self) -> list[dict]:
        """转为 Excel 写入用的扁平行 dict 列表。"""
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
                "cfp_override": None,
                "cfp_basis": {},
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
                "cfp_override": m.cfp_override,
                "cfp_basis": m.cfp_basis,
                "warnings": self.warnings if i == 0 else [],
                "move_type_flagged": m.move_type_flagged,
            })
        return rows
