"""pytest 全局 fixture —— 测试数据路径、Mock 工具。"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
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
def default_fpa_config(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "default-config"
    cfg_dir.mkdir()
    config_dir = Path(__file__).parent.parent / "config"
    shutil.copy2(config_dir / "fpa_config.yaml.example", cfg_dir / "fpa_config.yaml")
    shutil.copy2(config_dir / "fpa_judgement_rules.yaml.example", cfg_dir / "fpa_judgement_rules.yaml")
    monkeypatch.setattr("ai_gen_reimbursement_docs.config_utils.config_dir", lambda: cfg_dir)
    return cfg_dir


@pytest.fixture(autouse=True)
def _default_fpa_config(default_fpa_config):
    yield


@pytest.fixture
def output_dir(tmp_path):
    """临时交付物输出目录，测试后自动清理。"""
    d = tmp_path / "output"
    d.mkdir()
    return str(d)


@pytest.fixture
def mock_ai():
    """Mock 所有 AI 调用，避免实际 API 调用。

    注意：这些函数在 pipeline 中通过 lazy import 使用，
    需要 patch 它们的定义模块而非 pipeline。
    """
    def _copy_fpa_template(tree_md, meta_md, output_md, **kwargs):
        import shutil
        src = output_md.replace("1.3.gen-fpa-AI填充-FPA.md", "1.1.gen-fpa-FPA-模板.md")
        if os.path.exists(src):
            shutil.copy2(src, output_md)
        return output_md

    def _copy_spec_template(template_md, output_md, *args, **kwargs):
        import shutil
        shutil.copy2(template_md, output_md)
        return output_md

    def _cosmic_items(*args, **kwargs):
        return [
            CosmicItem(
                project=kwargs.get("project_name", "测试项目"),
                module_l1="系统管理",
                module_l2="用户管理",
                module_l3="用户注册",
                user="发起者：用户注册|接收者：系统管理",
                trigger="用户触发",
                process="注册用户",
                movements=[
                    DataMovement(1, "接收注册请求", "E", "用户注册请求", "姓名,手机号"),
                    DataMovement(2, "返回注册结果", "X", "用户注册结果", "结果状态,用户编号"),
                ],
            )
        ]

    with patch("ai_gen_reimbursement_docs.pipeline.plan_fpa_md_from_tree",
               side_effect=_copy_fpa_template) as m1b, \
         patch("ai_gen_reimbursement_docs.pipeline.ai_fill_spec_md",
               side_effect=_copy_spec_template) as m2, \
         patch("ai_gen_reimbursement_docs.excel_source.ai_fill_meta_md",
               return_value="/fake/meta.md") as m3, \
         patch("ai_gen_reimbursement_docs.excel_source._call_llm_once",
               return_value="AI填充内容") as m4, \
         patch("ai_gen_reimbursement_docs.cosmic_ai.generate_cosmic_items",
               side_effect=_cosmic_items) as m5:
        yield {"fpa_plan": m1b, "spec": m2, "meta": m3, "llm": m4, "cosmic": m5}
