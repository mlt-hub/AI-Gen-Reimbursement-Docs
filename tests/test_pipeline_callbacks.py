import pytest
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from ai_gen_reimbursement_docs import pipeline
from ai_gen_reimbursement_docs.cli.logging import render_pipeline_event
from ai_gen_reimbursement_docs.exceptions import CancelledError
from ai_gen_reimbursement_docs.llm_client import call_llm
from ai_gen_reimbursement_docs.pipeline_callbacks import PipelineCallbacks
from ai_gen_reimbursement_docs.runtime_context import callbacks_var, current_callbacks
from ai_gen_reimbursement_docs.template_manifest import TemplateValidationResult


def _append_toc_field(doc: Document) -> None:
    toc = parse_xml(
        f"""
        <w:p {nsdecls('w')}>
          <w:r><w:fldChar w:fldCharType="begin"/></w:r>
          <w:r><w:instrText>TOC \\o "1-3" \\h \\z \\u</w:instrText></w:r>
          <w:r><w:fldChar w:fldCharType="separate"/></w:r>
          <w:r><w:t>目录</w:t></w:r>
          <w:r><w:fldChar w:fldCharType="end"/></w:r>
        </w:p>
        """
    )
    body = doc._element.body
    body.insert(len(body) - 1, toc)


def test_pipeline_callbacks_default_cli_behavior():
    callbacks = PipelineCallbacks()

    assert callbacks.is_web_mode() is False
    assert callbacks.check_cancelled() is None
    assert callbacks.emit_event({"type": "step"}) is None
    assert callbacks.wait_for_fpa_input(1.5) == 1.5
    assert callbacks.wait_for_list_input(2.0, 3.0) == (2.0, 3.0)


def test_current_callbacks_uses_context_and_resets():
    callbacks = PipelineCallbacks(is_web_mode=lambda: True)
    token = callbacks_var.set(callbacks)
    try:
        assert current_callbacks() is callbacks
    finally:
        callbacks_var.reset(token)

    assert current_callbacks().is_web_mode() is False


def test_pipeline_step_uses_callbacks_event():
    events = []
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        emit_event=events.append,
    )
    token = callbacks_var.set(callbacks)
    try:
        pipeline._step("fpa")
    finally:
        callbacks_var.reset(token)

    assert events == [
        {"type": "step_started", "step": "fpa"},
        {"type": "step", "key": "fpa"},
    ]


def test_pipeline_activity_uses_shared_event_model():
    events = []
    callbacks = PipelineCallbacks(emit_event=events.append)
    token = callbacks_var.set(callbacks)
    try:
        pipeline._activity("spec", "正在写入需求说明书 Word 模板")
    finally:
        callbacks_var.reset(token)

    assert events == [{
        "type": "activity",
        "step": "spec",
        "message": "正在写入需求说明书 Word 模板",
    }]


def test_pipeline_artifact_can_include_metadata():
    events = []
    callbacks = PipelineCallbacks(emit_event=events.append)
    token = callbacks_var.set(callbacks)
    try:
        pipeline._artifact(
            "spec",
            "需求说明书.docx",
            "项目需求说明书",
            metadata={"toc_status": "manual_required", "toc_note": "需要手动更新目录"},
        )
    finally:
        callbacks_var.reset(token)

    assert events == [{
        "type": "artifact",
        "step": "spec",
        "message": "已生成项目需求说明书",
        "payload": {
            "label": "项目需求说明书",
            "name": "需求说明书.docx",
            "path": "需求说明书.docx",
            "is_temp": False,
            "toc_status": "manual_required",
            "toc_note": "需要手动更新目录",
        },
    }]


def test_spec_toc_status_reports_manual_required_and_updated(tmp_path):
    docx_path = tmp_path / "spec.docx"
    doc = Document()
    _append_toc_field(doc)
    doc.save(docx_path)

    manual = pipeline._build_spec_toc_status(
        str(docx_path),
        auto_update_enabled=False,
        toc_updated=False,
        reminder_applied=True,
    )
    updated = pipeline._build_spec_toc_status(
        str(docx_path),
        auto_update_enabled=True,
        toc_updated=True,
        reminder_applied=False,
    )

    assert manual["status"] == "manual_required"
    assert manual["note"] == "需要手动更新目录"
    assert manual["present"] is True
    assert manual["reminder_applied"] is True
    assert updated["status"] == "updated"
    assert updated["note"] == "目录已更新"
    assert updated["updated"] is True


def test_cli_renders_template_preflight_details(capsys):
    render_pipeline_event({
        "type": "activity",
        "step": "basedata",
        "message": "输出模板预检通过",
        "payload": {
            "summary_type": "template_preflight",
            "templates": [{
                "kind": "spec",
                "template_id": "spec_default_v1",
                "source": "manifest",
                "manifest_path": "spec.manifest.yaml",
                "capabilities": {
                    "anchor_mode": "split",
                    "module_table": {
                        "column_count": 4,
                        "supports_sample_table": True,
                    },
                },
                "warnings": [],
            }],
        },
    })

    output = capsys.readouterr().out
    assert "输出模板预检通过" in output
    assert "spec: manifest" in output
    assert "Word=拆分锚点" in output
    assert "模块表列数=4" in output
    assert "支持样例表" in output


def test_pipeline_template_preflight_event_includes_capabilities(monkeypatch, tmp_path):
    input_file = tmp_path / "input.xlsx"
    input_file.write_bytes(b"xlsx")
    events = []

    monkeypatch.setattr(
        pipeline,
        "_resolve_templates",
        lambda *_args, **_kwargs: {"spec": "spec.docx"},
    )
    monkeypatch.setattr(
        pipeline,
        "validate_output_templates",
        lambda *_args, **_kwargs: [
            TemplateValidationResult(
                kind="spec",
                template_path="spec.docx",
                manifest_path="spec.manifest.yaml",
                template_id="spec_default_v1",
                source="manifest",
                capabilities={"anchor_mode": "split"},
            )
        ],
    )

    def stop_after_preflight(*_args, **_kwargs):
        raise RuntimeError("stop")

    monkeypatch.setattr(pipeline, "_ensure_basedata_impl", stop_after_preflight)

    with pytest.raises(RuntimeError, match="stop"):
        pipeline.run_pipeline(
            mode="gen-spec",
            file_path=str(input_file),
            output_dir=str(tmp_path / "out"),
            callbacks=PipelineCallbacks(emit_event=events.append),
        )

    preflight = next(event for event in events if event.get("message") == "输出模板预检通过")
    assert preflight["step"] == "spec"
    assert preflight["payload"]["summary_type"] == "template_preflight"
    assert preflight["payload"]["templates"][0]["capabilities"]["anchor_mode"] == "split"


def test_pipeline_emits_step_failed_for_stage_error(monkeypatch, tmp_path):
    input_file = tmp_path / "input.xlsx"
    input_file.write_bytes(b"xlsx")
    events = []

    def fail_basedata(*args, **kwargs):
        pipeline._step("basedata", "读取功能清单并生成基础数据")
        raise RuntimeError("bad input")

    monkeypatch.setattr(pipeline, "_ensure_basedata_impl", fail_basedata)

    with pytest.raises(RuntimeError, match="bad input"):
        pipeline.run_pipeline(
            mode="gen-basedata",
            file_path=str(input_file),
            output_dir=str(tmp_path / "out"),
            callbacks=PipelineCallbacks(emit_event=events.append),
        )

    assert events[-1] == {
        "type": "step_failed",
        "step": "basedata",
        "message": "bad input",
    }


def test_pipeline_check_cancelled_uses_callbacks():
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        check_cancelled=lambda: (_ for _ in ()).throw(CancelledError("stop")),
    )
    token = callbacks_var.set(callbacks)
    try:
        with pytest.raises(CancelledError, match="stop"):
            pipeline._check_cancelled()
    finally:
        callbacks_var.reset(token)


def test_llm_client_checks_cancelled_before_api_call(monkeypatch):
    called = {"created": False}

    class _Messages:
        def create(self, **kwargs):
            called["created"] = True
            return object()

    class _Anthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    monkeypatch.setattr("anthropic.Anthropic", _Anthropic)
    callbacks = PipelineCallbacks(
        is_web_mode=lambda: True,
        check_cancelled=lambda: (_ for _ in ()).throw(CancelledError("stop")),
    )
    token = callbacks_var.set(callbacks)
    try:
        with pytest.raises(CancelledError, match="stop"):
            call_llm("hello", api_key="key", save_logs=False)
    finally:
        callbacks_var.reset(token)

    assert called["created"] is False
