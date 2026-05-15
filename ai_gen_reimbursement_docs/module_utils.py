"""模块工具 —— FunctionModule 重导出 + 模块查找。"""
from typing import Optional

from ai_gen_reimbursement_docs.models import FunctionModule


def get_module_by_name(modules: list[FunctionModule], name: str) -> Optional[FunctionModule]:
    """在扁平列表中按名称查找模块。"""
    for m in modules:
        if m.name == name:
            return m
    return None
