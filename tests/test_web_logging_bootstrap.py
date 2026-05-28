import logging
from pathlib import Path

from web_app.services import pipeline_runtime
from web_app.services.logging_bootstrap import _read_project_version, setup_web_logging
from web_app.services.session_manager import SessionManager


def test_setup_web_logging_returns_session_handler(tmp_path):
    logger = logging.getLogger("ai_gen_reimbursement_docs")
    before = list(logger.handlers)
    handler = setup_web_logging(session_manager=SessionManager(), base_dir=tmp_path)

    try:
        assert isinstance(handler, pipeline_runtime.SessionHandler)
        assert handler in logger.handlers
    finally:
        for item in list(logger.handlers):
            if item not in before:
                logger.removeHandler(item)


def test_read_project_version_falls_back_for_missing_file(tmp_path):
    assert _read_project_version(tmp_path) == "unknown"


def test_read_project_version_reads_pyproject(tmp_path):
    pyproject = Path(tmp_path) / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    assert _read_project_version(tmp_path) == "1.2.3"
