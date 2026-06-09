from pathlib import Path

import yaml
from docx import Document

from ai_gen_reimbursement_docs.spec_template_importer import import_spec_word_template
from ai_gen_reimbursement_docs.template_manifest import validate_output_template


def _write_customer_docx(path: Path) -> None:
    doc = Document()
    section = doc.sections[0]
    section.header.paragraphs[0].text = "项目名称：客户报账系统"
    section.footer.paragraphs[0].text = "文档标题：客户需求说明书"
    doc.add_paragraph("工单编号：WO-001")
    doc.add_paragraph("总体描述：用于测试导入")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "调整因子中的子系统名称"
    table.cell(0, 1).text = "预算子系统"
    table.cell(1, 0).text = "需求部门"
    table.cell(1, 1).text = "财务部"
    doc.add_paragraph("4 功能需求")
    doc.add_paragraph("这里是客户原始功能说明")
    doc.save(path)


def test_import_spec_word_template_creates_draft_and_manifest(tmp_path):
    source = tmp_path / "customer.docx"
    output_dir = tmp_path / "custom_templates"
    _write_customer_docx(source)

    result = import_spec_word_template(
        source,
        output_dir,
        template_id="imported_spec_test_v1",
    )

    assert result.template_path == output_dir / "项目需求说明书-输出模板.docx"
    assert result.manifest_path == output_dir / "项目需求说明书-输出模板.manifest.yaml"
    assert {item.key for item in result.detected_placeholders} >= {
        "project_name",
        "document_title",
        "work_order_no",
        "project_summary",
        "subsystem",
        "demand_department",
    }
    assert [item.key for item in result.inserted_anchors] == ["module_table", "module_details"]

    imported_doc = Document(result.template_path)
    body_text = "\n".join(paragraph.text for paragraph in imported_doc.paragraphs)
    assert "{{模块清单表}}" in body_text
    assert "{{功能过程详情}}" in body_text
    assert imported_doc.sections[0].header.paragraphs[0].text == "项目名称：{{项目名称}}"
    assert imported_doc.sections[0].footer.paragraphs[0].text == "文档标题：{{文档标题}}"
    assert imported_doc.tables[0].cell(0, 1).text == "{{调整因子中的子系统名称}}"
    assert imported_doc.tables[0].cell(1, 1).text == "{{需求部门}}"

    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["template_id"] == "imported_spec_test_v1"
    assert manifest["placeholders"]["module_table"]["required"] is True
    assert manifest["replacement_scopes"] == ["body", "tables", "headers", "footers"]

    validation = validate_output_template("spec", str(result.template_path))
    assert validation.ok
    assert validation.capabilities["anchor_mode"] == "split"


def test_import_spec_word_template_appends_anchors_when_section_not_found(tmp_path):
    source = tmp_path / "customer.docx"
    output_dir = tmp_path / "custom_templates"
    doc = Document()
    doc.add_paragraph("项目名称：客户报账系统")
    doc.add_paragraph("其他章节")
    doc.save(source)

    result = import_spec_word_template(source, output_dir)

    imported_doc = Document(result.template_path)
    body_text = "\n".join(paragraph.text for paragraph in imported_doc.paragraphs)
    assert body_text.endswith("{{模块清单表}}\n{{功能过程详情}}")
    assert any("未识别到功能需求章节标题" in item for item in result.pending_confirmations)
    assert validate_output_template("spec", str(result.template_path)).ok
