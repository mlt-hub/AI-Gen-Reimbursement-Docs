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
