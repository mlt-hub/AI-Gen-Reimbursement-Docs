from pathlib import Path
from unittest.mock import patch

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


def test_resolve_templates_prefers_profile_over_out_templates(tmp_path):
    profile_fpa = tmp_path / "profile-fpa.xlsx"
    legacy_fpa = tmp_path / "legacy-fpa.xlsx"
    profile_fpa.write_text("", encoding="utf-8")
    legacy_fpa.write_text("", encoding="utf-8")
    (tmp_path / "system_config.yaml").write_text(
        "\n".join([
            "active_output_template_profile: delivery_a",
            "output_template_profiles:",
            "  delivery_a:",
            "    templates:",
            f"      fpa_out_template: {profile_fpa.as_posix()}",
            "out_templates:",
            f"  fpa_out_template: {legacy_fpa.as_posix()}",
        ]),
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        templates = pipeline._resolve_templates("input.xlsx", None)

    assert Path(templates["fpa"]).resolve() == profile_fpa.resolve()


def test_resolve_templates_cli_overrides_profile(tmp_path):
    cli_fpa = tmp_path / "cli-fpa.xlsx"
    profile_fpa = tmp_path / "profile-fpa.xlsx"
    cli_fpa.write_text("", encoding="utf-8")
    profile_fpa.write_text("", encoding="utf-8")
    (tmp_path / "system_config.yaml").write_text(
        "\n".join([
            "active_output_template_profile: delivery_a",
            "output_template_profiles:",
            "  delivery_a:",
            "    templates:",
            f"      fpa: {profile_fpa.as_posix()}",
        ]),
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        templates = pipeline._resolve_templates("input.xlsx", {"fpa": str(cli_fpa)})

    assert Path(templates["fpa"]).resolve() == cli_fpa.resolve()


def test_resolve_templates_uses_template_pack_profile(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    pack_fpa = pack / "FPA.xlsx"
    pack_fpa.write_text("", encoding="utf-8")
    (pack / "manifest.yaml").write_text(
        "templates:\n  fpa: FPA.xlsx\n",
        encoding="utf-8",
    )
    (tmp_path / "system_config.yaml").write_text(
        "\n".join([
            "active_output_template_profile: packed",
            "output_template_profiles:",
            "  packed:",
            f"    template_pack: {pack.as_posix()}",
        ]),
        encoding="utf-8",
    )

    with patch("ai_gen_reimbursement_docs.config_utils.config_dir", return_value=tmp_path):
        templates = pipeline._resolve_templates("input.xlsx", None)

    assert Path(templates["fpa"]).resolve() == pack_fpa.resolve()
