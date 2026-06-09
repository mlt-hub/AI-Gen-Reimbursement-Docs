from pathlib import Path

import pytest
from docx import Document

TestClient = pytest.importorskip("fastapi.testclient").TestClient
FastAPI = pytest.importorskip("fastapi").FastAPI

from web_app.routes import templates as template_routes


def _client(monkeypatch, tmp_path, *, local_mode=True):
    app = FastAPI()
    app.include_router(template_routes.router)
    app.dependency_overrides[template_routes.require_auth] = lambda: ""
    monkeypatch.setattr(template_routes, "is_local_mode", lambda request: local_mode)
    monkeypatch.setattr(template_routes, "config_dir", lambda: tmp_path)
    return TestClient(app)


def _write_docx(path: Path) -> None:
    doc = Document()
    doc.add_paragraph("项目名称：客户报账系统")
    doc.add_paragraph("文档标题：客户需求说明书")
    doc.add_paragraph("功能需求")
    doc.save(path)


def test_import_spec_template_route_creates_template_draft(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    source = tmp_path / "customer.docx"
    _write_docx(source)

    with source.open("rb") as f:
        resp = client.post(
            "/api/templates/spec/import",
            files={"file": ("customer.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert Path(data["template_path"]).exists()
    assert Path(data["manifest_path"]).exists()
    assert data["template_filename"] == "项目需求说明书-输出模板.docx"
    assert data["manifest_filename"] == "项目需求说明书-输出模板.manifest.yaml"
    assert data["out_templates_patch"] == {"spec_out_template": data["template_path"]}
    assert {item["key"] for item in data["detected_placeholders"]} >= {
        "project_name",
        "document_title",
    }
    assert [item["key"] for item in data["inserted_anchors"]] == ["module_table", "module_details"]


def test_import_spec_template_route_rejects_non_docx(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    resp = client.post(
        "/api/templates/spec/import",
        files={"file": ("bad.txt", b"text", "text/plain")},
    )

    assert resp.status_code == 400
    assert ".docx" in resp.json()["detail"]


def test_import_spec_template_route_rejects_remote_mode(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, local_mode=False)

    resp = client.post(
        "/api/templates/spec/import",
        files={"file": ("customer.docx", b"docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 403
    assert "本机管理员" in resp.json()["detail"]
