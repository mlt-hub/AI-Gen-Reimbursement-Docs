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


def _short_name(name):
    text = str(name)
    if not text.startswith("【"):
        return text
    parts = text.split("-", 3)
    return parts[3] if len(parts) == 4 else text


def _row_by_name(rows):
    result = {}
    for row in rows:
        name = str(row.get("新增/修改功能点", ""))
        result[name] = row
        result[_short_name(name)] = row
    return result


def _assert_behavior_assertions(case, profile_name, rows):
    assertions = case.get("assertions", {}).get(profile_name, [])
    by_name = _row_by_name(rows)
    short_names = {_short_name(row.get("新增/修改功能点", "")) for row in rows}
    for assertion in assertions:
        kind = assertion["kind"]
        if kind == "contains":
            row = by_name.get(assertion["name"])
            assert row is not None, f"{case['case_id']} 缺少功能点: {assertion['name']}"
            if assertion.get("type"):
                assert row["类型"] == assertion["type"]
        elif kind == "not_contains_short_names":
            unexpected = sorted(set(assertion["names"]) & short_names)
            assert not unexpected, f"{case['case_id']} 不应出现逐流程功能点: {unexpected}"
        elif kind == "source_processes":
            row = by_name.get(assertion["name"])
            assert row is not None, f"{case['case_id']} 缺少功能点: {assertion['name']}"
            assert row.get("源功能过程") == assertion["value"]
        else:
            raise AssertionError(f"未知 golden assertion kind: {kind}")


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
    rows = _build_fpa_rule_rows(case["rows"], case["meta"], profile=profile)
    actual = _summarize(rows)
    expected = case["expected"][profile_name]

    assert actual == expected, _format_diff_report(
        case["case_id"],
        profile_name,
        expected,
        actual,
    )
    _assert_behavior_assertions(case, profile_name, rows)
