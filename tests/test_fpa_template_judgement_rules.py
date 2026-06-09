from pathlib import Path

from openpyxl import Workbook

from ai_gen_reimbursement_docs.gen_fpa import _read_fpa_judgement_rules_from_template


def _save_workbook(path: Path, sheet_name: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    wb.save(path)
    wb.close()


def test_read_fpa_judgement_rules_from_template_uses_default_appendix_layout(tmp_path):
    template = tmp_path / "fpa.xlsx"
    _save_workbook(template, "附录1-FPA评估方法说明")

    wb = Workbook()
    ws = wb.active
    ws.title = "附录1-FPA评估方法说明"
    ws["C1"] = "判定原则"
    ws["C2"] = "规则一"
    ws["C3"] = "规则二"
    wb.save(template)
    wb.close()

    assert _read_fpa_judgement_rules_from_template(str(template)) == ["规则一", "规则二"]


def test_read_fpa_judgement_rules_from_template_uses_manifest_anchor_and_column(tmp_path):
    template = tmp_path / "client-fpa.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "客户附录"
    ws["B4"] = "计算依据归类判定原则"
    ws["E5"] = "客户规则一"
    ws["E6"] = "客户规则二"
    wb.save(template)
    wb.close()
    template.with_suffix(".manifest.yaml").write_text(
        """
template_id: client_fpa_v1
kind: fpa
version: 1
sheets:
  judgement_rules:
    name: 客户附录
    anchor:
      contains: 判定原则
      offset_rows: 1
      column: E
""",
        encoding="utf-8",
    )

    assert _read_fpa_judgement_rules_from_template(str(template)) == ["客户规则一", "客户规则二"]
