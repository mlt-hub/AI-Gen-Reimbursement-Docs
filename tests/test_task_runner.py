from types import SimpleNamespace

from web_app.services.task_runner import build_file_summary


def test_build_file_summary_includes_spec_toc_note(tmp_path):
    spec = tmp_path / "spec.docx"
    spec.write_bytes(b"docx")

    result = SimpleNamespace(
        fpa_xlsx="",
        fpa_check_xlsx="",
        cosmic_xlsx="",
        require_xlsx="",
        spec_docx=str(spec),
        spec_toc_status="updated",
        spec_toc_note="目录已更新",
    )

    assert build_file_summary(result) == [{
        "label": "项目需求说明书",
        "path": str(spec),
        "size_kb": 0,
        "is_temp": False,
        "toc_note": "目录已更新",
        "toc_status": "updated",
    }]
