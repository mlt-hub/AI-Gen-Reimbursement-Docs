import json
from pathlib import Path

import pytest

from ai_gen_reimbursement_docs.fpa_profiles import get_fpa_profile
from ai_gen_reimbursement_docs.gen_fpa import _build_fpa_rule_rows


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fpa_golden_cases"


def _summarize(rows):
    return [
        {
            "name": str(row.get("新增/修改功能点", "")),
            "type": str(row.get("类型", "")),
        }
        for row in rows
    ]


def _format_diff_report(case_id: str, profile: str, expected, actual) -> str:
    lines = [
        "",
        f"FPA Golden Case 差异: {case_id} / {profile}",
        "",
        "Expected:",
        json.dumps(expected, ensure_ascii=False, indent=2),
        "",
        "Actual:",
        json.dumps(actual, ensure_ascii=False, indent=2),
    ]
    return "\n".join(lines)


def _load_cases():
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
@pytest.mark.parametrize("profile_name", ["unified_ui", "strict_fpa"])
def test_fpa_golden_fixture_matches_expected_output(case, profile_name):
    profile = get_fpa_profile(profile_name)
    actual = _summarize(
        _build_fpa_rule_rows(case["rows"], case["meta"], profile=profile)
    )
    expected = case["expected"][profile_name]

    assert actual == expected, _format_diff_report(
        case["case_id"],
        profile_name,
        expected,
        actual,
    )
