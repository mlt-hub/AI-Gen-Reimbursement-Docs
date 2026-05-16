"""通用数据模型 —— 文档模块树节点。"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionModule:
    """从需求文档中提取的功能模块节点。"""
    name: str
    level: int  # 1, 2, or 3（章节层级）
    description: str = ""
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)
