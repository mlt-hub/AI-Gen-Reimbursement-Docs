import logging

from ai_gen_reimbursement_docs.cli.logging import ReleaseFileHandler, render_pipeline_event


def test_release_file_handler_disables_itself_after_write_failure(monkeypatch, tmp_path):
    handler = ReleaseFileHandler(str(tmp_path / "blocked.log"))
    handler.setFormatter(logging.Formatter("%(message)s"))

    def fail_open(*args, **kwargs):
        raise PermissionError("blocked")

    monkeypatch.setattr("builtins.open", fail_open)

    record = logging.makeLogRecord({"msg": "hello", "levelno": logging.INFO, "levelname": "INFO"})
    handler.emit(record)
    handler.emit(record)

    assert handler._write_failed is True


def test_render_pipeline_event_prints_activity(capsys):
    render_pipeline_event({
        "type": "activity",
        "step": "spec",
        "message": "正在写入需求说明书 Word 模板",
    })

    assert "正在写入需求说明书 Word 模板" in capsys.readouterr().out
