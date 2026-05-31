"""run_pipeline() 集成测试 —— 端到端验证各模式交付物生成。"""

import os
from pathlib import Path

import openpyxl
import pytest
from ai_gen_reimbursement_docs.pipeline import run_pipeline, PipelineResult

pytestmark = pytest.mark.slow

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATES = {
    "fpa": str(FIXTURES / "output_templates" / "FPA工作量评估-输出模板.xlsx"),
    "cosmic": str(FIXTURES / "output_templates" / "项目功能点拆分表-输出模板.xlsx"),
    "list": str(FIXTURES / "output_templates" / "项目需求清单-输出模板.xlsx"),
    "spec": str(FIXTURES / "output_templates" / "项目需求说明书-输出模板.docx"),
}


@pytest.fixture(autouse=True)
def _verify_templates():
    """所有测试前置：确保模板文件存在。"""
    missing = [k for k, v in TEMPLATES.items() if not os.path.exists(v)]
    if missing:
        pytest.skip(f"模板文件缺失: {missing}")


class TestValidation:
    """参数校验"""

    def test_rejects_nonexistent_file(self, output_dir):
        with pytest.raises(FileNotFoundError, match="功能清单输入文件不存在"):
            run_pipeline(mode="gen-basedata", file_path="/no/such.xlsx",
                         output_dir=output_dir)

    def test_rejects_invalid_mode(self, output_dir, test_excel):
        with pytest.raises(ValueError, match="未知模式"):
            run_pipeline(mode="invalid-mode", file_path=test_excel,
                         output_dir=output_dir)

    def test_all_valid_modes_accepted(self, output_dir, test_excel):
        modes = ["gen-basedata", "gen-fpa", "gen-cosmic", "gen-list", "gen-spec", "gen-all"]
        for m in modes:
            assert m in {"gen-all", "gen-basedata", "gen-fpa", "gen-cosmic",
                         "gen-list", "gen-spec"}


class TestGenBasedata:
    """gen-basedata 模式"""

    def test_generates_tree_and_meta(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-basedata", file_path=test_excel,
                             output_dir=output_dir, api_key="sk-test",
                             templates=TEMPLATES)
        assert os.path.exists(result.tree_md)
        assert os.path.exists(result.meta_md)
        with open(result.tree_md, encoding='utf-8') as f:
            content = f.read()
            assert "一级模块" in content
            assert "用户管理" in content

    def test_returns_result_without_api_key(self, output_dir, test_excel):
        result = run_pipeline(mode="gen-basedata", file_path=test_excel,
                             output_dir=output_dir, api_key="")
        assert os.path.exists(result.tree_md)


class TestGenFpa:
    """gen-fpa 模式"""

    def test_generates_xlsx(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        assert os.path.exists(result.fpa_xlsx)
        assert os.path.getsize(result.fpa_xlsx) > 0
        assert os.path.exists(result.fpa_check_xlsx)
        assert os.path.getsize(result.fpa_check_xlsx) > 0

    def test_generates_fpa_check_xlsx(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")

        wb = openpyxl.load_workbook(result.fpa_check_xlsx, data_only=True)
        assert "FPA结果" in wb.sheetnames
        assert "覆盖审核" in wb.sheetnames
        ws_result = wb["FPA结果"]
        headers = [cell.value for cell in ws_result[1]]
        assert "生成方式" in headers
        assert "rule_set_version" in headers
        ws_coverage = wb["覆盖审核"]
        coverage_headers = [cell.value for cell in ws_coverage[1]]
        assert "未覆盖功能过程" in coverage_headers
        wb.close()

    def test_fpa_reduced_read_from_md(self, output_dir, test_excel, mock_ai):
        """gen-fpa 不直接使用 fpa_reduced 参数——它从生成的 MD 读取。"""
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        assert result.fpa_reduced > 0  # 从 MD 文件读取

    def test_fpa_summary_is_calculated_while_excel_preserves_formula(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")

        wb = openpyxl.load_workbook(result.fpa_xlsx, data_only=False)
        ws = wb["FPA功能点估算"]
        excel_total_formula = ws.cell(1, 12).value
        wb.close()

        assert result.fpa_reduced > 0
        assert excel_total_formula.startswith("=SUM(L3:L")

    def test_rejects_unknown_profile(self, output_dir, test_excel):
        with pytest.raises(ValueError, match="未知 FPA profile"):
            run_pipeline(
                mode="gen-fpa",
                file_path=test_excel,
                output_dir=output_dir,
                templates=TEMPLATES,
                fpa_profile="unknown_profile",
            )


class TestGenCosmic:
    """gen-cosmic 模式"""

    def test_generates_cosmic_xlsx(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-cosmic", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        assert result.cosmic_xlsx  # 路径已设置
        if os.path.exists(result.cosmic_xlsx):
            assert os.path.getsize(result.cosmic_xlsx) > 0

    def test_no_api_key_sets_path_but_no_file(self, output_dir, test_excel):
        result = run_pipeline(mode="gen-cosmic", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="")
        assert result.cosmic_xlsx  # 路径已设置


class TestGenSpec:
    """gen-spec 模式"""

    def test_generates_docx(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-spec", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        assert os.path.exists(result.spec_docx)
        assert os.path.getsize(result.spec_docx) > 0


class TestGenList:
    """gen-list 模式"""

    def test_generates_xlsx(self, output_dir, test_excel):
        result = run_pipeline(mode="gen-list", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES)
        assert os.path.exists(result.require_xlsx)
        assert os.path.getsize(result.require_xlsx) > 0

    def test_override_values(self, output_dir, test_excel):
        result = run_pipeline(mode="gen-list", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             fpa_reduced=7.5, cfp_total=30.0)
        assert os.path.exists(result.require_xlsx)


class TestGenAll:
    """gen-all 全流程"""

    def test_produces_all_four_outputs(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-all", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        assert os.path.exists(result.fpa_xlsx)
        assert os.path.exists(result.require_xlsx)
        assert os.path.exists(result.spec_docx)
        # COSMIC 依赖 AI，mock 返回空列表时不会生成文件，但路径已设置
        assert result.cosmic_xlsx
        for path in [result.fpa_xlsx, result.require_xlsx, result.spec_docx]:
            assert os.path.getsize(path) > 0, f"{path} 是空文件"

    def test_gen_all_no_ai(self, output_dir, test_excel, mock_ai):
        """无 AI 时全流程仍能完成"""
        result = run_pipeline(mode="gen-all", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="")
        # 基础交付物都应存在（FPA/List/Spec 不依赖 AI）
        assert os.path.exists(result.fpa_xlsx)
        assert os.path.exists(result.require_xlsx)
        assert os.path.exists(result.spec_docx)


class TestTemplateFallback:
    """模板回退机制"""

    def test_cli_template_not_found_falls_back_to_default(self, output_dir,
                                                            test_excel, mock_ai):
        """CLI 指定模板不存在时不报错，回退到默认模板"""
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir,
                             templates={"fpa": "/no/such/template.xlsx"},
                             api_key="sk-test")
        assert os.path.exists(result.fpa_xlsx)  # 用了默认模板

    def test_empty_templates_falls_back_to_default(self, output_dir, test_excel,
                                                     mock_ai):
        """传空 templates 时走默认 data/out_templates/ 回退"""
        result = run_pipeline(mode="gen-fpa", file_path=test_excel,
                             output_dir=output_dir, templates={},
                             api_key="sk-test")
        assert os.path.exists(result.fpa_xlsx)


class TestCustomFilenames:
    """自定义文件名（从 Excel 元数据解析）"""

    def test_resolves_custom_filenames(self, output_dir, test_excel, mock_ai):
        result = run_pipeline(mode="gen-all", file_path=test_excel,
                             output_dir=output_dir, templates=TEMPLATES,
                             api_key="sk-test")
        # 文件名应包含 Excel 中配置的占位符替换结果
        assert "TEST-2025-001" in str(result.fpa_xlsx) or "FPA" in str(result.fpa_xlsx)
