"""pytest 全局 fixture —— 测试数据路径、Mock 工具。"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from ai_gen_reimbursement_docs.excel_source import parse_module_tree_md

FIXTURES = Path(__file__).parent / "fixtures"
EXCEL_PATH = str(FIXTURES / "功能清单-录入模板.xlsx")


@pytest.fixture(scope="session")
def test_excel():
    """返回最小化测试用 Excel 路径。"""
    if not os.path.exists(EXCEL_PATH):
        pytest.skip(f"测试 Excel 不存在: {EXCEL_PATH}")
    return EXCEL_PATH


@pytest.fixture
def output_dir(tmp_path):
    """临时输出目录，测试后自动清理。"""
    d = tmp_path / "output"
    d.mkdir()
    return str(d)


@pytest.fixture
def mock_ai():
    """Mock 所有 AI 调用，避免实际 API 调用。

    注意：这些函数在 pipeline 中通过 lazy import 使用，
    需要 patch 它们的定义模块而非 pipeline。
    """
    with patch("ai_gen_reimbursement_docs.gen_fpa.ai_fill_fpa_md") as m1, \
         patch("ai_gen_reimbursement_docs.gen_spec.ai_fill_spec_md") as m2, \
         patch("ai_gen_reimbursement_docs.excel_source.ai_fill_meta_md",
               return_value="/fake/meta.md") as m3, \
         patch("ai_gen_reimbursement_docs.excel_source._call_llm_once",
               return_value="AI填充内容") as m4, \
         patch("ai_gen_reimbursement_docs.cosmic_ai.generate_cosmic_items",
               return_value=[]) as m5:
        yield {"fpa": m1, "spec": m2, "meta": m3, "llm": m4, "cosmic": m5}
