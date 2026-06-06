from __future__ import annotations

import json
from types import SimpleNamespace

from ai_gen_reimbursement_docs.cli import main as cli_main


def test_cli_history_records_and_prints_json(monkeypatch, tmp_path, capsys):
    db = tmp_path / "run_history.sqlite3"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    artifact = output_dir / "fpa.xlsx"
    artifact.write_bytes(b"xlsx")
    input_path = tmp_path / "功能清单.xlsx"
    input_path.write_bytes(b"xlsx")

    monkeypatch.setattr(cli_main, "user_history_path", lambda: db)

    result = SimpleNamespace(
        fpa_xlsx=str(artifact),
        cosmic_xlsx="",
        require_xlsx="",
        spec_docx="",
    )
    cli_main._record_cli_history(
        run_id="cli1",
        task_mode="gen-fpa",
        run_state="done",
        input_path=str(input_path),
        output_dir=str(output_dir),
        done_files=cli_main._done_files_from_result(result),
    )

    cli_main._print_history(limit=5, as_json=True)

    data = json.loads(capsys.readouterr().out)
    assert data[0]["run_id"] == "cli1"
    assert data[0]["source"] == "cli"
    assert data[0]["mode"] == "local"
    assert data[0]["artifact_kind"] == "local_dir"
    assert data[0]["open_folder_available"] is True
    assert data[0]["done_files"][0]["name"] == "fpa.xlsx"


def test_cli_history_plain_output_marks_missing_directory(monkeypatch, tmp_path, capsys):
    db = tmp_path / "run_history.sqlite3"
    missing_output = tmp_path / "missing"

    monkeypatch.setattr(cli_main, "user_history_path", lambda: db)

    cli_main._record_cli_history(
        run_id="cli2",
        task_mode="gen-all",
        run_state="error",
        input_path=str(tmp_path / "input.xlsx"),
        output_dir=str(missing_output),
        error="failed",
    )

    cli_main._print_history(limit=5, as_json=False)

    output = capsys.readouterr().out
    assert "cli2" in output
    assert "目录不存在" in output


def test_cli_parser_accepts_fpa_stability_report_args():
    parser = cli_main._build_parser()

    args = parser.parse_args([
        "--fpa-stability-report",
        "trace-a.json",
        "trace-b.json",
        "--fpa-stability-output",
        "report.md",
    ])

    assert args.fpa_stability_report == ["trace-a.json", "trace-b.json"]
    assert args.fpa_stability_output == "report.md"


def test_cli_parser_accepts_fpa_stability_sampling_args():
    parser = cli_main._build_parser()

    args = parser.parse_args([
        "--fpa-stability-sample-fixtures",
        "case-a.json",
        "case-b.json",
        "--fpa-stability-sample-suite",
        "standard",
        "--fpa-stability-sample-profiles",
        "strict_fpa,unified_ui",
        "--fpa-stability-sample-strategies",
        "rules_only,rules_first",
        "--fpa-stability-sample-rule-sets",
        "strict_fpa_rs",
        "--output-dir",
        "samples",
        "--fpa-stability-max-retryable-issues",
        "0",
        "--fpa-stability-max-retries",
        "0",
    ])

    assert args.fpa_stability_sample_fixtures == ["case-a.json", "case-b.json"]
    assert args.fpa_stability_sample_suite == "standard"
    assert args.fpa_stability_sample_profiles == "strict_fpa,unified_ui"
    assert args.fpa_stability_sample_strategies == "rules_only,rules_first"
    assert args.fpa_stability_sample_rule_sets == "strict_fpa_rs"
    assert args.output_dir == "samples"
    assert args.fpa_stability_max_retryable_issues == 0
    assert args.fpa_stability_max_retries == 0


def test_cli_parser_accepts_fpa_stability_sampling_preset():
    parser = cli_main._build_parser()

    args = parser.parse_args([
        "--fpa-stability-sample-preset",
        "strict-real-model",
        "--output-dir",
        "samples",
    ])

    assert args.fpa_stability_sample_preset == "strict-real-model"
    assert args.fpa_stability_sample_profiles == ""
    assert args.fpa_stability_sample_strategies == ""
    assert args.output_dir == "samples"
