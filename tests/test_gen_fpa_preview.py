from pathlib import Path
import shutil

import pytest

from ai_gen_reimbursement_docs.gen_fpa import preview_fpa_module, preview_fpa_modules


FIXTURES = Path(__file__).parent / "fixtures"


def test_preview_fpa_module_by_index_uses_fallback(test_excel, tmp_path):
    result = preview_fpa_module(
        file_path=test_excel,
        module_index=1,
        api_key="",
        work_dir=str(tmp_path),
    )

    assert result["module"]["index"] == 1
    assert result["rows"]
    assert result["used_ai"] is False
    assert result["profile"] == "custom_rules"
    assert result["profile_version"] == "1"
    assert result["strategy"] == "rules_first"
    assert result["rule_set"] == "custom_rules_default"
    assert result["rule_set_version"] == "1"
    assert result["audit"]["profile"] == "custom_rules"
    assert result["audit"]["rule_set_version"] == "1"
    assert result["audit"]["coverage"]["process_total"] == result["module"]["process_count"]
    assert result["audit"]["coverage"]["covered_count"] > 0
    assert "fallback" in result["audit"]["generation_counts"]
    assert all(row["generation"] == "fallback" for row in result["rows"])
    assert not list(tmp_path.glob("**/FPA工作量评估.xlsx"))


def test_preview_fpa_modules_returns_selectable_l3_modules(test_excel, tmp_path):
    result = preview_fpa_modules(
        file_path=test_excel,
        work_dir=str(tmp_path),
    )

    modules = result["modules"]
    assert modules
    assert modules[0]["index"] == 1
    assert modules[0]["l3"]
    assert modules[0]["process_count"] > 0
    assert modules[0]["label"].startswith("1. ")
    assert result["warnings"] == []
    assert not list(tmp_path.glob("**/FPA工作量评估.xlsx"))


def test_preview_fpa_module_uses_memory_parse_by_default(test_excel, monkeypatch):
    def fail_generate_md_files(*args, **kwargs):
        raise AssertionError("default preview should not write intermediate MD files")

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.excel_source.generate_md_files",
        fail_generate_md_files,
    )

    result = preview_fpa_module(
        file_path=test_excel,
        module_index=1,
    )

    assert result["rows"]
    assert result["preview_md_dir"] == ""
    assert result["preview_cache_used"] is False


def test_preview_fpa_modules_uses_memory_parse_by_default(test_excel, monkeypatch):
    def fail_generate_md_files(*args, **kwargs):
        raise AssertionError("default module preview list should not write intermediate MD files")

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.excel_source.generate_md_files",
        fail_generate_md_files,
    )

    result = preview_fpa_modules(file_path=test_excel)

    assert result["modules"]
    assert result["preview_md_dir"] == ""
    assert result["preview_cache_used"] is False


def test_preview_fpa_module_can_use_cached_preview_md(test_excel, tmp_path, monkeypatch):
    first = preview_fpa_module(
        file_path=test_excel,
        module_index=1,
        work_dir=str(tmp_path),
    )
    assert first["preview_cache_used"] is False

    def fail_generate_md_files(*args, **kwargs):
        raise AssertionError("generate_md_files should not be called when preview cache is ready")

    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.excel_source.generate_md_files",
        fail_generate_md_files,
    )

    second = preview_fpa_module(
        file_path=test_excel,
        module_index=1,
        work_dir=str(tmp_path),
        use_preview_cache=True,
    )

    assert second["preview_cache_used"] is True
    assert second["preview_md_dir"] == str(tmp_path / "fpa-preview-md")
    assert second["rows"]


def test_preview_fpa_module_keep_preview_files_without_work_dir(test_excel, tmp_path):
    excel_copy = tmp_path / "input.xlsx"
    shutil.copy2(test_excel, excel_copy)

    result = preview_fpa_module(
        file_path=str(excel_copy),
        module_index=1,
        keep_preview_files=True,
    )

    md_dir = tmp_path / ".fpa-preview" / "fpa-preview-md"
    assert result["preview_cache_used"] is False
    assert result["preview_md_dir"] == str(md_dir)
    assert (md_dir / "0.1.gen-basedata-功能清单-模块树.md").exists()
    assert (md_dir / "0.2.gen-basedata-录入文档元数据-模板.md").exists()
    assert result["rows"]


def test_preview_fpa_module_missing_name_raises(test_excel, tmp_path):
    with pytest.raises(ValueError, match="未找到三级模块"):
        preview_fpa_module(
            file_path=test_excel,
            module_name="不存在的三级模块",
            work_dir=str(tmp_path),
        )


def test_preview_fpa_module_rejects_unknown_profile(test_excel, tmp_path):
    with pytest.raises(ValueError, match="未知 FPA profile"):
        preview_fpa_module(
            file_path=test_excel,
            module_index=1,
            profile_name="unknown_profile",
            work_dir=str(tmp_path),
        )


def test_preview_fpa_module_strict_requires_api_key(test_excel, tmp_path):
    with pytest.raises(ValueError, match="需要 API Key"):
        preview_fpa_module(
            file_path=test_excel,
            module_index=1,
            profile_name="strict_fpa",
            work_dir=str(tmp_path),
        )
