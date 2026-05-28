from pathlib import Path

from ai_gen_reimbursement_docs import pipeline


def test_read_fpa_sum_reads_value(tmp_path):
    path = tmp_path / "fpa_sum.md"
    path.write_text("FPA工作量（人/天）: 12.5\n", encoding="utf-8")

    assert pipeline._read_fpa_sum(str(path)) == 12.5


def test_read_fpa_sum_returns_zero_when_missing(tmp_path):
    assert pipeline._read_fpa_sum(str(tmp_path / "missing.md")) == 0.0


def test_save_and_read_fpa_reduced_md(tmp_path):
    saved = pipeline._save_fpa_reduced_md(str(tmp_path), 8.75)

    assert Path(saved).exists()
    assert pipeline._read_fpa_reduced_md(str(tmp_path)) == 8.75


def test_read_cfp_formula_from_meta_md(tmp_path):
    meta = tmp_path / "meta.md"
    meta.write_text(
        "\n".join([
            "# 元数据",
            "## 6、项目功能点拆分表-元数据录入",
            "| 字段 | 值 |",
            "| CFP计算公式 | ILF + EIF |",
            "## 下一段",
        ]),
        encoding="utf-8",
    )

    assert pipeline._read_cfp_formula_from_meta_md(str(meta)) == "ILF + EIF"


def test_read_cfp_formula_returns_empty_when_missing(tmp_path):
    meta = tmp_path / "meta.md"
    meta.write_text("## 其他段落\n| 字段 | 值 |\n", encoding="utf-8")

    assert pipeline._read_cfp_formula_from_meta_md(str(meta)) == ""


def test_resolve_output_filename_uses_metadata_filename(tmp_path):
    meta = tmp_path / "meta.md"
    meta.write_text(
        "\n".join([
            "## 4、FPA工作量评估-元数据录入",
            "| 字段 | 值 |",
            "| 文件名 | 自定义FPA.xlsx |",
        ]),
        encoding="utf-8",
    )

    result = pipeline._resolve_output_filename(
        str(meta),
        "4、FPA工作量评估-元数据录入",
        str(tmp_path / "default.xlsx"),
        str(tmp_path / "out"),
    )

    assert result == str(tmp_path / "out" / "自定义FPA.xlsx")


def test_resolve_output_filename_replaces_placeholders(tmp_path):
    meta = tmp_path / "meta.md"
    meta.write_text(
        "\n".join([
            "| 工单编号 | GD-001 |",
            "| 工单标题 | 示例项目 |",
            "## 4、FPA工作量评估-元数据录入",
            "| 字段 | 值 |",
            "| 文件名 | ${工单编号}-${工单标题}-FPA.xlsx |",
        ]),
        encoding="utf-8",
    )

    result = pipeline._resolve_output_filename(
        str(meta),
        "4、FPA工作量评估-元数据录入",
        str(tmp_path / "default.xlsx"),
        str(tmp_path / "out"),
    )

    assert result == str(tmp_path / "out" / "GD-001-示例项目-FPA.xlsx")


def test_resolve_output_filename_falls_back_when_section_missing(tmp_path):
    meta = tmp_path / "meta.md"
    default = tmp_path / "default.xlsx"
    meta.write_text("## 其他段落\n", encoding="utf-8")

    assert pipeline._resolve_output_filename(
        str(meta),
        "4、FPA工作量评估-元数据录入",
        str(default),
        str(tmp_path / "out"),
    ) == str(default)
