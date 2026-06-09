from pathlib import Path

import openpyxl

from ai_gen_reimbursement_docs.gen_fpa import _read_fpa_judgement_rules_from_template


def test_fpa_judgement_rules_reading_uses_manifest_sheet_column_and_range(tmp_path: Path):
    template = tmp_path / "custom-fpa.xlsx"
    manifest = tmp_path / "custom-fpa.manifest.yaml"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "FPA结果"
    appendix = wb.create_sheet("客户FPA附录")
    appendix["D3"] = "忽略的说明"
    appendix["D4"] = "规则一：识别内部逻辑文件。"
    appendix["D5"] = "规则二：识别外部接口文件。"
    appendix["D6"] = "超出范围的规则"
    wb.save(template)
    wb.close()

    manifest.write_text(
        """
template_id: custom_fpa_v1
kind: fpa
version: 1
sheets:
  judgement_rules:
    name: 客户FPA附录
    data_start_row: 4
    data_end_row: 5
    rule_column: D
""".lstrip(),
        encoding="utf-8",
    )

    assert _read_fpa_judgement_rules_from_template(str(template)) == [
        "规则一：识别内部逻辑文件。",
        "规则二：识别外部接口文件。",
    ]
