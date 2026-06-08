import asyncio
import json
import os
import queue
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from ai_gen_reimbursement_docs.gen_fpa import preview_fpa_module, preview_fpa_modules
from ai_gen_reimbursement_docs.auth import user_config_dir
from web_app.dependencies import require_auth, require_local
from web_app.services.config_service import (
    config_dir,
    mode_requires_ai,
    read_config,
    read_config_from_dir,
    remote_session_retention_seconds,
    resolve_task_start_config,
)
from web_app.services import pipeline_runtime
from web_app.services.run_history_service import finish_web_run, start_web_run
from web_app.services.session_access import require_session_access
from web_app.services.session_manager import SessionManager
from web_app.services.task_runner import (
    cleanup_expired_sessions,
    execute_in_session,
    start_background_task,
)
from web_app.services.template_service import save_custom_templates, save_custom_templates_into


def _session_run_state(state) -> Literal["running", "done", "error", "cancelled"]:
    if state.last_error == "cancelled":
        return "cancelled"
    if state.last_error:
        return "error"
    if state.task_done_at is not None:
        return "done"
    return "running"


def _session_status_payload(session_id: str, state) -> dict:
    output_dir = state.output_dir if state.mode == "local" else None
    zip_path = state.zip_path
    return {
        "session_id": session_id,
        "mode": state.mode,
        "run_state": _session_run_state(state),
        "output_dir": str(output_dir) if output_dir else "",
        "has_zip": bool(zip_path and zip_path.exists()),
        "done_files": state.done_files,
        "progress_steps": state.progress_steps,
        "last_error": state.last_error,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
        "task_created_at": state.task_created_at.isoformat() if state.task_created_at else None,
        "task_done_at": state.task_done_at.isoformat() if state.task_done_at else None,
    }


FPA_PROFILE_LABELS = {
    "strict_fpa": "严格 FPA 口径",
    "unified_ui": "统一界面口径",
    "multi_uis": "多界面口径",
    "ui_api_mapping": "界面接口映射口径",
}

FPA_STRATEGY_LABELS = {
    "rules_first": "规则优先",
    "ai_first": "AI 优先",
    "rules_only": "仅规则",
    "ai_only": "仅 AI",
}

FPA_CONFIRMATION_MODE_LABELS = {
    "auto": "自动模式",
    "cautious": "审慎模式",
    "strict": "严格确认模式",
}


def create_router(
    *,
    session_manager: SessionManager,
    mode_info: dict[str, dict[str, str]],
    mode_map: dict[str, str],
    base_dir: Path,
) -> APIRouter:
    router = APIRouter()

    def _explicit_task_config(**values: str) -> dict[str, str]:
        return {key: value for key, value in values.items() if str(value or "").strip()}

    def _resolve_task_config_snapshot(
        *,
        explicit: dict[str, str],
        local_mode: bool,
        user: str = "",
        mode: str,
    ) -> dict:
        global_root = config_dir()
        user_root = user_config_dir(user) if user and not local_mode else None
        user_config = read_config_from_dir(user_root) if user_root is not None else None
        snapshot = resolve_task_start_config(
            explicit=explicit,
            global_config=read_config(),
            user_config=user_config,
            local_mode=local_mode,
            global_config_root=global_root,
            user_config_root=user_root,
        )
        if (
            not local_mode
            and mode_requires_ai(mode, snapshot.get("fpa_strategy", ""))
            and not snapshot.get("api_key")
        ):
            raise HTTPException(
                400,
                "未配置可用 API Key。请配置个人 API Key，或联系管理员开启共享系统 API Key。",
            )
        return snapshot

    def _resolve_local_xlsx_input(xlsx_path: str) -> Path:
        xlsx_input = Path(xlsx_path)
        if not xlsx_input.exists():
            raise HTTPException(400, f"路径不存在: {xlsx_path}")
        if not xlsx_input.is_dir():
            return xlsx_input

        import glob
        from ai_gen_reimbursement_docs.excel_source import is_valid_input_xlsx

        xlsx_files = [
            f for f in glob.glob(os.path.join(str(xlsx_input), "*.xlsx"))
            if is_valid_input_xlsx(f)
        ]
        if not xlsx_files:
            raise HTTPException(400, f"目录中未找到符合规范的功能清单 .xlsx: {xlsx_path}")
        preferred = [
            f for f in xlsx_files
            if os.path.basename(f) in ("功能清单-录入模板.xlsx", "功能清单.xlsx")
        ]
        return Path(preferred[0] if preferred else xlsx_files[0])

    def _session_log_dir(session_id: str) -> Path | None:
        state = session_manager.get(session_id)
        if state is None:
            return None
        if state.output_dir is not None:
            out_dir = state.output_dir
        elif state.work_dir is not None:
            out_dir = state.work_dir / "output"
        else:
            return None
        log_dir = out_dir / "日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def _append_fpa_preview_debug_to_session(
        *,
        session_id: str,
        result: dict,
        request: Request,
        user: str,
    ) -> None:
        require_session_access(session_manager, session_id, request, user)
        debug = result.get("debug") if isinstance(result, dict) else None
        if not isinstance(debug, dict):
            return
        log_dir = _session_log_dir(session_id)
        if log_dir is None:
            return

        module = result.get("module") if isinstance(result.get("module"), dict) else {}
        module_label = str(module.get("l3") or module.get("index") or "module")
        safe_module = "".join(ch if ch.isalnum() else "_" for ch in module_label).strip("_") or "module"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_name = f"fpa_preview_{stamp}_{safe_module}"
        prompts_dir = log_dir / "ai_prompts"
        responses_dir = log_dir / "ai_responses"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)

        prompt_text = "\n".join([
            f"# FPA 预览调试: {module_label}",
            "",
            "## System Prompt",
            str(debug.get("system_prompt") or ""),
            "",
            "## User Prompt",
            str(debug.get("user_prompt") or ""),
            "",
            "## AI Prompts",
            str(debug.get("ai_prompt") or ""),
        ]).strip() + "\n"
        response_text = "\n".join([
            f"# FPA 预览响应: {module_label}",
            "",
            "## Raw Response",
            str(debug.get("raw_response") or ""),
            "",
            "## Thinking",
            str(debug.get("thinking") or ""),
            "",
            "## Parsed Rows",
            json.dumps(debug.get("parsed_rows") or [], ensure_ascii=False, indent=2),
            "",
            "## Quality Review",
            json.dumps(debug.get("quality_review") or {}, ensure_ascii=False, indent=2),
        ]).strip() + "\n"

        (prompts_dir / f"{base_name}_prompt.txt").write_text(prompt_text, encoding="utf-8")
        (responses_dir / f"{base_name}_response.txt").write_text(response_text, encoding="utf-8")
        records_dir = log_dir / "debug_records"
        records_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "id": base_name,
            "source": "fpa_preview",
            "module": module_label,
            "model": str(debug.get("model") or ""),
            "reason": str(debug.get("reason") or ""),
            "ai_called": bool(debug.get("ai_called")),
            "prompt_file": f"{base_name}_prompt.txt",
            "response_file": f"{base_name}_response.txt",
            "parsed_rows": debug.get("parsed_rows") or [],
            "final_rows": debug.get("final_rows") or [],
            "quality_review": debug.get("quality_review") or {},
            "error": str(debug.get("error") or ""),
        }
        (records_dir / f"{base_name}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        combined = log_dir / "ai_对话日志.md"
        with combined.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n# FPA 预览调试 - {module_label} - {stamp}\n\n")
            handle.write("## Prompt\n\n")
            handle.write(prompt_text)
            handle.write("\n## Response\n\n")
            handle.write(response_text)

    @router.get("/api/fpa/options")
    async def api_fpa_options(user: str = Depends(require_auth)):
        """Return user-safe FPA option metadata for Web selectors."""
        from ai_gen_reimbursement_docs.config_utils import (
            VALID_FPA_PROFILE_KINDS,
            VALID_FPA_STRATEGIES,
            load_fpa_config,
        )
        from ai_gen_reimbursement_docs.fpa_confirmation import VALID_FPA_CONFIRMATION_MODES

        try:
            cfg = load_fpa_config()
            profiles = cfg.get("profiles", {})
            rule_sets = cfg.get("rule_sets", {})
            if not isinstance(profiles, dict) or not isinstance(rule_sets, dict):
                raise ValueError("FPA 配置结构无效")

            profile_options = []
            for name, entry in profiles.items():
                if not isinstance(entry, dict):
                    continue
                profile_name = str(name)
                profile_options.append({
                    "name": profile_name,
                    "label": FPA_PROFILE_LABELS.get(profile_name, profile_name),
                    "kind": str(entry.get("kind") or ""),
                    "strategy": str(entry.get("strategy") or ""),
                    "rule_set": str(entry.get("rule_set") or ""),
                })

            rule_set_options = []
            for name, entry in rule_sets.items():
                entry_map = entry if isinstance(entry, dict) else {}
                rule_set_name = str(name)
                rule_set_options.append({
                    "name": rule_set_name,
                    "label": rule_set_name,
                    "extends": str(entry_map.get("extends") or ""),
                })

            strategy_names = [
                name for name in FPA_STRATEGY_LABELS
                if name in VALID_FPA_STRATEGIES
            ]
            strategy_options = [
                {"name": name, "label": FPA_STRATEGY_LABELS.get(name, name)}
                for name in strategy_names
            ]

            return {
                "default_profile": str(cfg.get("default-profile") or ""),
                "profiles": profile_options,
                "strategies": strategy_options,
                "confirmation_modes": [
                    {"name": name, "label": FPA_CONFIRMATION_MODE_LABELS.get(name, name)}
                    for name in FPA_CONFIRMATION_MODE_LABELS
                    if name in VALID_FPA_CONFIRMATION_MODES
                ],
                "kinds": [{"name": name, "label": name} for name in sorted(VALID_FPA_PROFILE_KINDS)],
                "rule_sets": rule_set_options,
            }
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/api/sessions/{session_id}")
    async def get_session_status(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """查询 session 状态，用于页面刷新或离开后恢复任务。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        if state is None:
            raise HTTPException(404, "未知会话")
        return _session_status_payload(session_id, state)

    @router.post("/api/cancel/{session_id}")
    async def cancel_session(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """停止指定 session 的执行。"""
        require_session_access(session_manager, session_id, request, user)
        session_manager.cancel(session_id)
        return {"ok": True}

    @router.post("/api/continue/{session_id}")
    async def api_continue(
        session_id: str,
        data: dict,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """接收前端交互输入（送审工作量），唤醒等待中的 pipeline。"""
        require_session_access(session_manager, session_id, request, user)
        if not session_manager.submit_input(session_id, data):
            raise HTTPException(404, "会话不存在或无需输入")
        return {"ok": True}

    @router.get("/api/log-stream")
    async def log_stream(
        session: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        require_session_access(session_manager, session, request, user)
        q = session_manager.get_queue(session)
        if q is None:
            raise HTTPException(404, "未知会话")

        async def generate():
            while True:
                try:
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=0.1)
                    )
                    data = json.loads(msg)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    if data.get("type") in ("done", "cancelled", "error"):
                        break
                except queue.Empty:
                    yield ": heartbeat\n\n"

            session_manager.remove_queue(session)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/api/run-local")
    async def api_run_local(
        request: Request,
        xlsx_path: str = Form(...),
        output_dir: str = Form(""),
        mode: str = Form(...),
        api_key: str = Form(""),
        model: str = Form(""),
        base_url: str = Form(""),
        max_tokens: str = Form(""),
        project_name: str = Form(""),
        fpa_profile: str = Form(""),
        fpa_strategy: str = Form(""),
        fpa_rule_set: str = Form(""),
        fpa_confirmation_mode: str = Form(""),
        clean: str = Form(""),
        fpa_template: UploadFile | None = File(None),
        cosmic_template: UploadFile | None = File(None),
        list_template: UploadFile | None = File(None),
        spec_template: UploadFile | None = File(None),
        _local: None = Depends(require_local),
    ):
        """本机模式：接受文件路径或目录路径，目录则自动搜索功能清单 xlsx。"""
        if mode not in mode_info:
            raise HTTPException(400, f"未知模式: {mode}")

        from_dir = ""
        if Path(xlsx_path).is_dir():
            from_dir = xlsx_path
        xlsx = _resolve_local_xlsx_input(xlsx_path)

        import re
        from ai_gen_reimbursement_docs.pipeline import _try_read_project_name

        task_config = _resolve_task_config_snapshot(
            explicit=_explicit_task_config(
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_tokens=max_tokens,
                project_name=project_name,
                fpa_profile=fpa_profile,
                fpa_strategy=fpa_strategy,
                fpa_rule_set=fpa_rule_set,
                fpa_confirmation_mode=fpa_confirmation_mode,
            ),
            local_mode=True,
            mode=mode,
        )
        project_name = task_config["project_name"]

        if output_dir:
            out = Path(output_dir)
        elif project_name:
            root = Path(from_dir) if from_dir else xlsx.parent
            safe = re.sub(r'[\/:*?"<>|]', "_", project_name)
            out = root / safe
        else:
            root = Path(from_dir) if from_dir else xlsx.parent
            auto_name = _try_read_project_name(str(xlsx))
            if auto_name:
                safe = re.sub(r'[\/:*?"<>|]', "_", auto_name)
                out = root / safe
            else:
                out = root
        out.mkdir(parents=True, exist_ok=True)

        custom_t_dir = await save_custom_templates(
            out, fpa_template, cosmic_template, list_template, spec_template
        )

        session_id = uuid.uuid4().hex[:8]
        session_manager.create(session_id, mode="local", output_dir=out)
        start_web_run(
            base_dir=base_dir,
            session_id=session_id,
            mode="local",
            task_mode=mode,
            input_path=str(xlsx),
            output_dir=str(out),
        )

        def run():
            pipeline_runtime.web_mode_var.set("local")

            def _finish(sid: str, files: list[dict], error: str | None) -> None:
                finish_web_run(
                    base_dir=base_dir,
                    session_id=sid,
                    mode="local",
                    task_mode=mode,
                    input_path=str(xlsx),
                    output_dir=str(out),
                    done_files=files,
                    error=error or "",
                )

            execute_in_session(
                session_manager,
                session_id,
                str(xlsx),
                str(out),
                custom_t_dir,
                task_config["api_key"],
                task_config["model"],
                task_config["base_url"],
                task_config["project_name"],
                task_config["max_tokens"],
                task_config["fpa_profile"],
                task_config["fpa_strategy"],
                task_config["fpa_rule_set"],
                task_config["fpa_confirmation_mode"],
                bool(clean),
                mode,
                mode_info=mode_info,
                mode_map=mode_map,
                on_finish=_finish,
            )

        start_background_task(session_manager, session_id, run)
        return {"session_id": session_id, "output_dir": str(out)}

    @router.post("/api/run-upload")
    async def api_run_upload(
        file: UploadFile = File(...),
        mode: str = Form(...),
        api_key: str = Form(""),
        model: str = Form(""),
        base_url: str = Form(""),
        max_tokens: str = Form(""),
        project_name: str = Form(""),
        fpa_profile: str = Form(""),
        fpa_strategy: str = Form(""),
        fpa_rule_set: str = Form(""),
        fpa_confirmation_mode: str = Form(""),
        clean: str = Form(""),
        fpa_template: UploadFile | None = File(None),
        cosmic_template: UploadFile | None = File(None),
        list_template: UploadFile | None = File(None),
        spec_template: UploadFile | None = File(None),
        user: str = Depends(require_auth),
    ):
        """远程服务模式：上传文件，交付物打包 ZIP 下载。"""
        if mode not in mode_info:
            raise HTTPException(400, f"未知模式: {mode}")

        if not file.filename:
            raise HTTPException(400, "未选择文件")

        cleanup_expired_sessions(
            session_manager,
            max_age_seconds=remote_session_retention_seconds(),
        )
        task_config = _resolve_task_config_snapshot(
            explicit=_explicit_task_config(
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_tokens=max_tokens,
                project_name=project_name,
                fpa_profile=fpa_profile,
                fpa_strategy=fpa_strategy,
                fpa_rule_set=fpa_rule_set,
                fpa_confirmation_mode=fpa_confirmation_mode,
            ),
            local_mode=False,
            user=user,
            mode=mode,
        )

        session_id = uuid.uuid4().hex[:8]
        work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        custom_t_dir = work_dir / "custom_templates"
        for d in [input_dir, output_dir, custom_t_dir]:
            d.mkdir(parents=True)

        safe_name = Path(file.filename).name
        file_path = input_dir / safe_name
        content = await file.read()
        file_path.write_bytes(content)

        await save_custom_templates_into(
            custom_t_dir, fpa_template, cosmic_template, list_template, spec_template
        )

        session_manager.create(session_id, mode="remote", owner=user, work_dir=work_dir)
        start_web_run(
            base_dir=base_dir,
            session_id=session_id,
            mode="remote",
            task_mode=mode,
            input_path=str(file_path),
            owner_id=user,
            owner_label=user,
        )

        def run():
            pipeline_runtime.web_mode_var.set("remote")

            def _pack_zip(output_dir_path: str, sid: str, result: object) -> None:
                zip_path = work_dir / f"交付物_{sid}.zip"
                shutil.make_archive(
                    str(zip_path.with_suffix("")), "zip", str(output_dir_path)
                )
                session_manager.set_zip(sid, zip_path)

            def _finish(sid: str, files: list[dict], error: str | None) -> None:
                state = session_manager.get(sid)
                zip_path = state.zip_path if state else None
                finish_web_run(
                    base_dir=base_dir,
                    session_id=sid,
                    mode="remote",
                    task_mode=mode,
                    input_path=str(file_path),
                    owner_id=user,
                    owner_label=user,
                    zip_path=str(zip_path) if zip_path else "",
                    done_files=files,
                    error=error or "",
                )

            execute_in_session(
                session_manager,
                session_id,
                str(file_path),
                str(output_dir),
                str(custom_t_dir),
                task_config["api_key"],
                task_config["model"],
                task_config["base_url"],
                task_config["project_name"],
                task_config["max_tokens"],
                task_config["fpa_profile"],
                task_config["fpa_strategy"],
                task_config["fpa_rule_set"],
                task_config["fpa_confirmation_mode"],
                bool(clean),
                mode,
                mode_info=mode_info,
                mode_map=mode_map,
                on_success=_pack_zip,
                on_finish=_finish,
            )

        start_background_task(session_manager, session_id, run)
        return {"session_id": session_id, "has_download": True}

    @router.post("/api/fpa/preview-module")
    async def api_preview_fpa_module(
        request: Request,
        xlsx_path: str = Form(""),
        module_name: str = Form(""),
        module_index: int | None = Form(None),
        api_key: str = Form(""),
        model: str = Form(""),
        base_url: str = Form(""),
        fpa_profile: str = Form(""),
        fpa_strategy: str = Form(""),
        fpa_rule_set: str = Form(""),
        fpa_confirmation_mode: str = Form(""),
        confirmed_decisions: str = Form(""),
        session_id: str = Form(""),
        file: UploadFile | None = File(None),
        user: str = Depends(require_auth),
    ):
        """预览单个三级模块的 FPA 规划结果，不创建任务和交付物。"""
        from ai_gen_reimbursement_docs.pipeline import _resolve_templates

        if module_index is None and not module_name.strip():
            raise HTTPException(400, "请填写三级模块名称或序号")

        temp_ctx: tempfile.TemporaryDirectory | None = None
        try:
            if file is not None and file.filename:
                temp_ctx = tempfile.TemporaryDirectory(prefix="ard_web_fpa_preview_")
                input_dir = Path(temp_ctx.name) / "input"
                input_dir.mkdir(parents=True, exist_ok=True)
                safe_name = Path(file.filename).name
                file_path = input_dir / safe_name
                file_path.write_bytes(await file.read())
                work_dir = str(Path(temp_ctx.name) / "work")
                Path(work_dir).mkdir(parents=True, exist_ok=True)
            else:
                require_local(request)
                if not xlsx_path.strip():
                    raise HTTPException(400, "请提供功能清单 .xlsx 路径")
                file_path = _resolve_local_xlsx_input(xlsx_path)
                temp_ctx = tempfile.TemporaryDirectory(prefix="ard_web_fpa_preview_")
                work_dir = str(Path(temp_ctx.name) / "work")
                Path(work_dir).mkdir(parents=True, exist_ok=True)

            local_preview = file is None or not file.filename
            task_config = _resolve_task_config_snapshot(
                explicit=_explicit_task_config(
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    fpa_profile=fpa_profile,
                    fpa_strategy=fpa_strategy,
                    fpa_rule_set=fpa_rule_set,
                    fpa_confirmation_mode=fpa_confirmation_mode,
                ),
                local_mode=local_preview,
                user=user,
                mode="from-excel-gen-fpa",
            )
            templates = _resolve_templates(str(file_path), None)
            confirmed_decisions_payload = {}
            if confirmed_decisions.strip():
                try:
                    parsed_decisions = json.loads(confirmed_decisions)
                except json.JSONDecodeError as exc:
                    raise HTTPException(400, "confirmed_decisions 必须是 JSON 对象") from exc
                if not isinstance(parsed_decisions, dict):
                    raise HTTPException(400, "confirmed_decisions 必须是 JSON 对象")
                confirmed_decisions_payload = parsed_decisions
            result = preview_fpa_module(
                file_path=str(file_path),
                module_name=module_name.strip(),
                module_index=module_index,
                api_key=task_config["api_key"],
                model=task_config["model"],
                base_url=task_config["base_url"],
                template_path=templates.get("fpa", ""),
                work_dir=work_dir,
                profile_name=task_config["fpa_profile"],
                strategy=task_config["fpa_strategy"],
                rule_set=task_config["fpa_rule_set"],
                fpa_confirmation_mode=task_config["fpa_confirmation_mode"] or "auto",
                confirmed_decisions=confirmed_decisions_payload,
            )
            if session_id.strip():
                _append_fpa_preview_debug_to_session(
                    session_id=session_id.strip(),
                    result=result,
                    request=request,
                    user=user,
                )
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            if temp_ctx is not None:
                temp_ctx.cleanup()

    @router.post("/api/fpa/preview-modules")
    async def api_preview_fpa_modules(
        request: Request,
        xlsx_path: str = Form(""),
        file: UploadFile | None = File(None),
        user: str = Depends(require_auth),
    ):
        """生成 FPA 预览用基础数据，返回可选择的三级模块列表。"""
        temp_ctx: tempfile.TemporaryDirectory | None = None
        try:
            if file is not None and file.filename:
                temp_ctx = tempfile.TemporaryDirectory(prefix="ard_web_fpa_preview_modules_")
                input_dir = Path(temp_ctx.name) / "input"
                input_dir.mkdir(parents=True, exist_ok=True)
                safe_name = Path(file.filename).name
                file_path = input_dir / safe_name
                file_path.write_bytes(await file.read())
                work_dir = str(Path(temp_ctx.name) / "work")
                Path(work_dir).mkdir(parents=True, exist_ok=True)
            else:
                require_local(request)
                if not xlsx_path.strip():
                    raise HTTPException(400, "请提供功能清单 .xlsx 路径")
                file_path = _resolve_local_xlsx_input(xlsx_path)
                temp_ctx = tempfile.TemporaryDirectory(prefix="ard_web_fpa_preview_modules_")
                work_dir = str(Path(temp_ctx.name) / "work")
                Path(work_dir).mkdir(parents=True, exist_ok=True)

            return preview_fpa_modules(
                file_path=str(file_path),
                work_dir=work_dir,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            if temp_ctx is not None:
                temp_ctx.cleanup()

    return router
