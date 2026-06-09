import os
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ai_gen_reimbursement_docs.cosmic_confirmation import (
    apply_cosmic_confirmation_export_policy,
)
from ai_gen_reimbursement_docs.cosmic_models import CosmicItem, DataMovement
from ai_gen_reimbursement_docs.cosmic_validator import (
    CosmicIssue,
    CosmicValidationReport,
    CosmicValidationResult,
)
from ai_gen_reimbursement_docs.cosmic_writer import write_cosmic_xlsx
from ai_gen_reimbursement_docs.excel_source import write_cfp_sum
from ai_gen_reimbursement_docs.gen_cosmic import _calculate_cfp_total_for_written_excel
from ai_gen_reimbursement_docs.pipeline import (
    _read_cfp_formula_from_meta_md,
    _resolve_templates,
)
from web_app.dependencies import require_auth, require_local
from web_app.services.artifact_service import find_log_dir
from web_app.services.run_history_service import append_done_file_to_history
from web_app.services.session_access import require_session_access
from web_app.services.session_manager import SessionManager


def _strip_suffix(name: str, suffix: str) -> str:
    return name[:-len(suffix)] if name.endswith(suffix) else name


def _section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end():]
    next_heading = re.search(r"^## .*$", rest, re.MULTILINE)
    return rest[:next_heading.start()].strip() if next_heading else rest.strip()


def _title_module(text: str) -> str:
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    for prefix in ("# FPA 预览调试:", "# FPA 预览响应:"):
        if first_line.startswith(prefix):
            return first_line[len(prefix):].strip()
    return ""


def _safe_json(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _read_text(path: Path | None) -> str:
    if path and path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _cosmic_confirmation_path(session_manager: SessionManager, session_id: str) -> Path:
    state = session_manager.get(session_id)
    root = state.work_dir if state else None
    if root is None:
        raise HTTPException(404, "未知会话")
    root.mkdir(parents=True, exist_ok=True)
    return root / "cosmic-confirmation.json"


def _session_output_dir(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None
    if state.output_dir is not None:
        return state.output_dir
    if state.work_dir is not None:
        return state.work_dir / "output"
    return None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _cosmic_draft_json_path(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None

    output_dir = _session_output_dir(session_manager, session_id)
    roots = [
        root
        for root in (state.output_dir, output_dir)
        if root is not None and root.exists()
    ]
    standard_name = "3.3.gen-cosmic-AI填充-COSMIC.json"
    cosmic_step = state.progress_steps.get("cosmic", {})
    for artifact in cosmic_step.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        label = str(artifact.get("label") or "")
        name = str(artifact.get("name") or "")
        if label != "COSMIC JSON 草稿" and name != standard_name:
            continue
        candidate = Path(str(artifact.get("path") or ""))
        if candidate.name != standard_name or not candidate.exists() or not candidate.is_file():
            continue
        if any(_is_under(candidate, root) for root in roots):
            return candidate

    if output_dir is None or not output_dir.exists():
        return None
    matches = sorted(path for path in output_dir.rglob(standard_name) if path.is_file())
    return matches[0] if matches else None


def _cosmic_template_path(session_manager: SessionManager, session_id: str) -> Path | None:
    state = session_manager.get(session_id)
    if state is None:
        return None
    custom_roots = [
        root / "custom_templates"
        for root in (state.output_dir, state.work_dir)
        if root is not None
    ]
    for root in custom_roots:
        candidate = root / "项目功能点拆分表-输出模板.xlsx"
        if candidate.exists() and candidate.is_file():
            return candidate
    default = _resolve_templates("", None).get("cosmic", "")
    return Path(default) if default and Path(default).exists() else None


def _cosmic_md_dir_from_draft(path: Path) -> Path:
    return path.parent


def _cosmic_doc_dir_from_draft(path: Path) -> Path:
    return _cosmic_md_dir_from_draft(path).parent / "cosmic文档"


def _cosmic_meta_md_path(md_dir: Path) -> Path:
    filled = md_dir / "0.4.gen-basedata-AI填充-录入文档元数据.md"
    if filled.exists():
        return filled
    return md_dir / "0.2.gen-basedata-录入文档元数据-模板.md"


def _issue_from_dict(data: dict) -> CosmicIssue:
    return CosmicIssue(
        severity=str(data.get("severity") or "info"),
        code=str(data.get("code") or ""),
        message=str(data.get("message") or ""),
        field=str(data.get("field") or ""),
        module_path=str(data.get("module_path") or ""),
        process=str(data.get("process") or ""),
        movement_order=data.get("movement_order") if isinstance(data.get("movement_order"), int) else None,
        scope=str(data.get("scope") or "item"),
        details=data.get("details") if isinstance(data.get("details"), dict) else {},
    )


def _cosmic_report_from_payload(payload: dict) -> CosmicValidationReport:
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(400, "COSMIC JSON 缺少 items")

    review_items = payload.get("review_items")
    if not isinstance(review_items, list):
        review_items = []
    issues_by_item: dict[int, list[CosmicIssue]] = {}
    global_issues: list[CosmicIssue] = []
    for raw_issue in review_items:
        if not isinstance(raw_issue, dict):
            continue
        issue = _issue_from_dict(raw_issue)
        item_index = raw_issue.get("item_index")
        if isinstance(item_index, int):
            issues_by_item.setdefault(item_index, []).append(issue)
        else:
            global_issues.append(issue)

    results: list[CosmicValidationResult] = []
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            continue
        movements = [
            DataMovement(
                order=int(raw_movement.get("order") or movement_index + 1),
                sub_process=str(raw_movement.get("sub_process") or ""),
                move_type=str(raw_movement.get("move_type") or ""),
                data_group=str(raw_movement.get("data_group") or ""),
                data_attrs=str(raw_movement.get("data_attrs") or ""),
                reuse=str(raw_movement.get("reuse") or "新增"),
            )
            for movement_index, raw_movement in enumerate(raw_item.get("movements") or [])
            if isinstance(raw_movement, dict)
        ]
        item = CosmicItem(
            project=str(raw_item.get("project") or payload.get("project") or ""),
            module_l1=str(raw_item.get("module_l1") or ""),
            module_l2=str(raw_item.get("module_l2") or ""),
            module_l3=str(raw_item.get("module_l3") or ""),
            user=str(raw_item.get("user") or ""),
            trigger=str(raw_item.get("trigger") or ""),
            process=str(raw_item.get("process") or ""),
            movements=movements,
        )
        results.append(CosmicValidationResult(
            item=item,
            status=str(raw_item.get("status") or "passed"),
            issues=issues_by_item.get(index, []),
            basis=raw_item.get("basis") if isinstance(raw_item.get("basis"), dict) else {},
        ))

    return CosmicValidationReport(
        project=str(payload.get("project") or ""),
        status=str(payload.get("status") or ""),
        results=results,
        summary=payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
        issue_codes=payload.get("issue_codes") if isinstance(payload.get("issue_codes"), dict) else {},
        cfp_basis=payload.get("cfp_basis") if isinstance(payload.get("cfp_basis"), dict) else {},
        issues=global_issues,
    )


def _record_function_points(record: dict) -> list[str]:
    values: list[str] = []
    for key in ("final_rows", "parsed_rows"):
        rows = record.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("function_point") or "").strip()
            if name and name not in values:
                values.append(name)
    return values


def _build_structured_fpa_debug_records(log_dir: Path) -> list[dict]:
    prompts_dir = log_dir / "ai_prompts"
    responses_dir = log_dir / "ai_responses"
    records_dir = log_dir / "debug_records"
    records: list[dict] = []
    seen_ids: set[str] = set()

    if records_dir.is_dir():
        for path in sorted(records_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or path.stem)
            prompt_file = str(record.get("prompt_file") or f"{record_id}_prompt.txt")
            response_file = str(record.get("response_file") or f"{record_id}_response.txt")
            prompt_content = _read_text(prompts_dir / prompt_file)
            response_content = _read_text(responses_dir / response_file)
            item = {
                "id": record_id,
                "source": str(record.get("source") or "fpa_preview"),
                "module": str(record.get("module") or _title_module(prompt_content) or _title_module(response_content)),
                "model": str(record.get("model") or ""),
                "reason": str(record.get("reason") or ""),
                "ai_called": bool(record.get("ai_called")),
                "prompt_file": prompt_file,
                "response_file": response_file,
                "prompt": prompt_content,
                "response": response_content,
                "parsed_rows": record.get("parsed_rows") if isinstance(record.get("parsed_rows"), list) else [],
                "final_rows": record.get("final_rows") if isinstance(record.get("final_rows"), list) else [],
                "quality_review": record.get("quality_review") if isinstance(record.get("quality_review"), dict) else {},
                "error": str(record.get("error") or ""),
            }
            item["function_points"] = _record_function_points(item)
            records.append(item)
            seen_ids.add(record_id)

    if prompts_dir.is_dir():
        for prompt_path in sorted(prompts_dir.glob("*_prompt.txt")):
            record_id = _strip_suffix(prompt_path.name, "_prompt.txt")
            if record_id in seen_ids:
                continue
            response_path = responses_dir / f"{record_id}_response.txt"
            prompt_content = _read_text(prompt_path)
            response_content = _read_text(response_path)
            item = {
                "id": record_id,
                "source": "fpa_preview" if record_id.startswith("fpa_preview_") else "ai_log",
                "module": _title_module(prompt_content) or _title_module(response_content),
                "model": "",
                "reason": "",
                "ai_called": bool(response_content),
                "prompt_file": prompt_path.name,
                "response_file": response_path.name if response_path.exists() else "",
                "prompt": prompt_content,
                "response": response_content,
                "parsed_rows": _safe_json(_section(response_content, "Parsed Rows"), []),
                "final_rows": [],
                "quality_review": _safe_json(_section(response_content, "Quality Review"), {}),
                "error": "",
            }
            item["function_points"] = _record_function_points(item)
            records.append(item)

    return records


def create_router(session_manager: SessionManager, *, base_dir: Path | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/download/{session_id}")
    async def download(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """远程服务模式：下载交付物 ZIP。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        zip_path = state.zip_path if state else None
        if zip_path is None:
            if state is not None:
                raise HTTPException(409, "任务仍在运行，交付物尚未生成")
            raise HTTPException(404, "交付物不存在或会话已过期")
        if not zip_path.exists():
            raise HTTPException(404, "交付物文件已被清理")

        return FileResponse(
            zip_path,
            filename=f"交付物_{datetime.now():%Y%m%d_%H%M%S}.zip",
            media_type="application/zip",
        )

    @router.get("/api/open-folder")
    async def open_folder(session: str, _local: None = Depends(require_local)):
        """本机模式：在资源管理器中打开交付物目录。"""
        state = session_manager.get(session)
        out_dir = state.output_dir if state else None
        if out_dir is None:
            raise HTTPException(404, "未知会话")
        if not out_dir.exists():
            raise HTTPException(404, "交付物目录不存在")
        os.startfile(str(out_dir))
        return {"ok": True}

    @router.get("/api/ai-log/{session_id}")
    async def get_ai_log(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回 AI 对话日志内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        combined = log_dir / "ai_对话日志.md"
        if not combined.exists():
            raise HTTPException(404, "AI 对话日志尚未生成")

        content = combined.read_text(encoding="utf-8")
        return {"content": content, "filename": combined.name}

    @router.get("/api/ai-interactions/{session_id}")
    async def list_ai_interactions(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """列出 AI prompts 和 responses 文件清单及内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        prompts_dir = log_dir / "ai_prompts"
        responses_dir = log_dir / "ai_responses"

        files: list[dict] = []

        if prompts_dir.is_dir():
            for fname in sorted(os.listdir(prompts_dir)):
                if fname.endswith(".txt"):
                    path = prompts_dir / fname
                    files.append({
                        "name": fname,
                        "type": "prompt",
                        "content": path.read_text(encoding="utf-8"),
                    })

        if responses_dir.is_dir():
            for fname in sorted(os.listdir(responses_dir)):
                if fname.endswith(".txt"):
                    path = responses_dir / fname
                    files.append({
                        "name": fname,
                        "type": "response",
                        "content": path.read_text(encoding="utf-8"),
                    })

        return {"interactions": files, "count": len(files)}

    @router.get("/api/sessions/{session_id}/fpa/debug-records")
    async def list_fpa_debug_records(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回结构化 FPA AI 调试记录。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")
        records = _build_structured_fpa_debug_records(log_dir)
        return {
            "session_id": session_id,
            "records": records,
            "count": len(records),
            "filters": {
                "models": sorted({record["model"] for record in records if record.get("model")}),
                "modules": sorted({record["module"] for record in records if record.get("module")}),
                "function_points": sorted({
                    name
                    for record in records
                    for name in record.get("function_points", [])
                    if name
                }),
            },
        }

    @router.get("/api/sessions/{session_id}/cosmic/confirmation")
    async def get_cosmic_confirmation(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """读取 COSMIC 预览人工确认 JSON。"""
        require_session_access(session_manager, session_id, request, user)
        path = _cosmic_confirmation_path(session_manager, session_id)
        if not path.exists():
            raise HTTPException(404, "COSMIC 确认 JSON 尚未保存")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC 确认 JSON 损坏") from exc
        payload = apply_cosmic_confirmation_export_policy(payload)
        return {
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.get("/api/sessions/{session_id}/cosmic/draft")
    async def get_cosmic_draft(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """读取生成任务产出的 COSMIC JSON 草稿。"""
        require_session_access(session_manager, session_id, request, user)
        path = _cosmic_draft_json_path(session_manager, session_id)
        if path is None:
            raise HTTPException(404, "COSMIC JSON 草稿尚未生成")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC JSON 草稿损坏") from exc
        return {
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.put("/api/sessions/{session_id}/cosmic/confirmation")
    async def save_cosmic_confirmation(
        session_id: str,
        payload: dict,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """保存 COSMIC 预览人工确认 JSON。"""
        require_session_access(session_manager, session_id, request, user)
        if not isinstance(payload, dict):
            raise HTTPException(400, "COSMIC 确认 JSON 必须是对象")
        payload = apply_cosmic_confirmation_export_policy(payload)
        path = _cosmic_confirmation_path(session_manager, session_id)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "session_id": session_id,
            "filename": path.name,
            "payload": payload,
        }

    @router.post("/api/sessions/{session_id}/cosmic/export-confirmed")
    async def export_confirmed_cosmic_excel(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """按已确认 COSMIC JSON 再导出 Excel，不覆盖原生成产物。"""
        require_session_access(session_manager, session_id, request, user)
        draft_path = _cosmic_draft_json_path(session_manager, session_id)
        if draft_path is None:
            raise HTTPException(404, "COSMIC JSON 草稿尚未生成")

        confirmation_path = _cosmic_confirmation_path(session_manager, session_id)
        source_path = confirmation_path if confirmation_path.exists() else draft_path
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(500, "COSMIC 确认 JSON 损坏") from exc
        payload = apply_cosmic_confirmation_export_policy(payload)
        formal_policy = payload.get("export_policy", {}).get("formal_excel", {})
        formal_status = str(formal_policy.get("status") or "")
        if formal_status not in {"allowed", "allowed_after_confirmation"}:
            raise HTTPException(409, str(formal_policy.get("reason") or "COSMIC 确认状态不允许导出正式 Excel"))

        template_path = _cosmic_template_path(session_manager, session_id)
        if template_path is None:
            raise HTTPException(404, "未找到 COSMIC Excel 输出模板")
        report = _cosmic_report_from_payload(payload)
        md_dir = _cosmic_md_dir_from_draft(draft_path)
        doc_dir = _cosmic_doc_dir_from_draft(draft_path)
        doc_dir.mkdir(parents=True, exist_ok=True)
        output_path = doc_dir / "项目功能点拆分表-确认后.xlsx"
        cfp_formula = _read_cfp_formula_from_meta_md(str(_cosmic_meta_md_path(md_dir)))
        saved_path = Path(write_cosmic_xlsx(
            str(template_path),
            str(output_path),
            report,
            cfp_formula=cfp_formula,
        ))
        cfp_total = _calculate_cfp_total_for_written_excel([result.item for result in report.results])
        write_cfp_sum(str(md_dir), cfp_total)
        cfp_summary_path = md_dir / "3.5.gen-cosmic-CFP-总和.md"
        file_info = {
            "label": "项目功能点拆分表（确认后）",
            "path": str(saved_path),
            "size_kb": round(saved_path.stat().st_size / 1024),
            "is_temp": "_TEMP" in saved_path.name,
        }
        cfp_file_info = {
            "label": "COSMIC CFP 总和（确认后）",
            "path": str(cfp_summary_path),
            "size_kb": round(cfp_summary_path.stat().st_size / 1024),
            "is_temp": False,
        }
        state = session_manager.get(session_id)
        if state is not None:
            done_files = list(state.done_files)
            for item in (file_info, cfp_file_info):
                if not any(existing.get("path") == item["path"] for existing in done_files):
                    done_files.append(item)
            session_manager.set_done_files(session_id, done_files)
        if state is not None and state.mode == "remote" and state.zip_path is not None:
            output_dir = _session_output_dir(session_manager, session_id)
            if output_dir is not None and output_dir.exists():
                shutil.make_archive(str(state.zip_path.with_suffix("")), "zip", str(output_dir))
        if state is not None and base_dir is not None:
            for item in (file_info, cfp_file_info):
                append_done_file_to_history(
                    base_dir=base_dir,
                    session_id=session_id,
                    mode=state.mode,
                    done_file=item,
                    zip_path=str(state.zip_path) if state.zip_path else "",
                )
        return {
            "ok": True,
            "session_id": session_id,
            "filename": saved_path.name,
            "path": str(saved_path),
            "file": file_info,
            "files": [file_info, cfp_file_info],
            "cfp_total": cfp_total,
            "cfp_summary_file": cfp_file_info,
            "export_policy": payload.get("export_policy", {}),
        }

    return router
