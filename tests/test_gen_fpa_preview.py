from pathlib import Path

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
