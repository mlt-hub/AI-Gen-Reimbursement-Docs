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
from web_app.dependencies import get_auth_user, is_local_mode, require_auth, require_local
from web_app.services.config_service import (
    config_dir,
    local_task_input_snapshot_enabled,
    max_concurrent_tasks,
    mode_requires_ai,
    read_config,
    read_config_from_dir,
    remote_session_retention_seconds,
    resolve_task_start_config,
)
from web_app.services import pipeline_runtime
from web_app.services.fpa_project_profile_service import (
    load_project_profile_decisions,
    merge_decision_payloads,
    persist_project_profile_decisions,
    serialize_decisions,
)
from web_app.services.run_history_service import (
    cancel_web_run,
    close_history_item,
    fail_web_run,
    finish_web_run,
    list_tasks,
    mark_web_run_started,
    mark_unrecoverable_history_item,
    require_rerunnable_history_item,
    restore_closed_history_item,
    start_web_run,
)
from web_app.services.session_access import require_session_access
from web_app.services.task_assets_service import (
    cleanup_expired_task_assets,
    snapshot_custom_templates,
    snapshot_input_file,
)
from web_app.services.session_manager import SessionManager
from web_app.services.task_runner import (
    cleanup_expired_sessions,
    execute_in_session,
    start_background_task,
)
from web_app.services.task_queue import QueuedTask, TaskQueue
from web_app.services.template_service import (
    build_templates_dict,
    save_custom_templates,
    save_custom_templates_into,
)
from web_app.services.upload_security import UploadSecurityError, validate_upload_file


def _session_run_state(state) -> Literal["queued", "running", "done", "error", "cancelled"]:
    if state.queue_position is not None and state.task_created_at is None and state.task_done_at is None:
        return "queued"
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
        "queue_position": state.queue_position,
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
    "multi_ui": "多界面口径",
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

RUN_CONFIG_KEYS = (
    "model",
    "base_url",
    "max_tokens",
    "project_name",
    "fpa_profile",
    "fpa_strategy",
    "fpa_rule_set",
    "fpa_core_rules",
    "fpa_system_prompt",
    "fpa_user_prompt",
    "fpa_base_profile",
    "fpa_confirmation_mode",
)


def create_router(
    *,
    session_manager: SessionManager,
    mode_info: dict[str, dict[str, str]],
    mode_map: dict[str, str],
    base_dir: Path,
) -> APIRouter:
    router = APIRouter()

    def _start_queued_background_task(sm, sid, target, *, on_done=None):
        try:
            return start_background_task(sm, sid, target, on_done=on_done)
        except TypeError:
            task = start_background_task(sm, sid, target)
            if on_done:
                on_done()
            return task

    task_queue = TaskQueue(
        session_manager=session_manager,
        max_concurrent_tasks=max_concurrent_tasks,
        start_fn=_start_queued_background_task,
    )

    def _explicit_task_config(**values: str) -> dict[str, str]:
        return {key: value for key, value in values.items() if str(value or "").strip()}

    def _resolve_task_config_snapshot(
        *,
        explicit: dict[str, str],
        local_mode: bool,
        user: str = "",
        mode: str,
        require_api_key: bool = False,
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
        snapshot = _finalize_fpa_task_config(snapshot)
        if (
            (require_api_key or not local_mode)
            and mode_requires_ai(mode, snapshot.get("fpa_strategy", ""))
            and not snapshot.get("api_key")
        ):
            raise HTTPException(
                400,
                "未配置可用 API Key。请配置个人 API Key，或联系管理员开启共享系统 API Key。",
            )
        return snapshot

    def _cleanup_task_assets() -> None:
        cleanup_expired_task_assets(base_dir=base_dir)

    def _snapshot_history_input(
        *,
        session_id: str,
        source: Path,
        mode: str,
        owner_id: str = "",
        source_run_id: str = "",
    ) -> Path:
        return snapshot_input_file(
            base_dir=base_dir,
            session_id=session_id,
            source=source,
            mode=mode,
            owner_id=owner_id,
            source_run_id=source_run_id,
        )

    def _snapshot_history_templates(
        *,
        session_id: str,
        source_dir: str,
        mode: str,
        owner_id: str = "",
        source_run_id: str = "",
    ) -> str:
        return snapshot_custom_templates(
            base_dir=base_dir,
            session_id=session_id,
            source_dir=source_dir,
            mode=mode,
            owner_id=owner_id,
            source_run_id=source_run_id,
        )

    def _finalize_fpa_task_config(snapshot: dict) -> dict:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_profile_entry
        from ai_gen_reimbursement_docs.fpa_profiles import resolve_fpa_execution_config

        profile_name = str(snapshot.get("fpa_profile") or "").strip()
        if not profile_name:
            return snapshot
        if profile_name == "custom_profile":
            execution = resolve_fpa_execution_config(
                profile_name,
                str(snapshot.get("fpa_strategy") or ""),
                str(snapshot.get("fpa_rule_set") or ""),
                core_rules=str(snapshot.get("fpa_core_rules") or ""),
                system_prompt=str(snapshot.get("fpa_system_prompt") or ""),
                user_prompt=str(snapshot.get("fpa_user_prompt") or ""),
                base_profile=str(snapshot.get("fpa_base_profile") or ""),
            )
        else:
            execution = resolve_fpa_execution_config(profile_name)
            entry = load_fpa_profile_entry(execution.profile.name)
            snapshot["fpa_core_rules"] = str(entry.get("core_rules") or "")
            snapshot["fpa_system_prompt"] = str(entry.get("system_prompt") or "")
            snapshot["fpa_user_prompt"] = str(entry.get("user_prompt") or "")
            snapshot["fpa_confirmation_mode"] = "auto"
        snapshot["fpa_strategy"] = execution.strategy
        snapshot["fpa_rule_set"] = execution.rule_set
        snapshot["fpa_core_rules"] = execution.core_rules
        snapshot["fpa_system_prompt"] = execution.system_prompt
        snapshot["fpa_user_prompt"] = execution.user_prompt
        snapshot["fpa_base_profile"] = execution.base_profile
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

    def _profile_config_root(*, local_mode: bool, user: str = "") -> Path:
        return config_dir() if local_mode else user_config_dir(user)

    def _load_profile_decision_payload(config_root: Path) -> dict[str, dict[str, str]]:
        return serialize_decisions(load_project_profile_decisions(config_root))

    def _run_config_snapshot(
        *,
        task_config: dict,
        clean: bool,
        custom_t_dir: str,
    ) -> dict:
        templates = build_templates_dict(custom_t_dir) if custom_t_dir else {}
        return {
            **{key: str(task_config.get(key) or "") for key in RUN_CONFIG_KEYS},
            "clean": clean,
            "custom_templates_dir": custom_t_dir,
            "custom_templates": {
                key: Path(path).name
                for key, path in templates.items()
            },
        }

    def _rerun_explicit_config(record: dict) -> dict[str, str]:
        run_config = record.get("run_config")
        if not isinstance(run_config, dict):
            return {}
        return {
            key: str(run_config.get(key) or "")
            for key in RUN_CONFIG_KEYS
            if str(run_config.get(key) or "").strip()
        }

    def _rerun_clean(record: dict) -> bool:
        run_config = record.get("run_config")
        return bool(isinstance(run_config, dict) and run_config.get("clean"))

    def _resolve_rerun_custom_templates(record: dict) -> str:
        run_config = record.get("run_config")
        if not isinstance(run_config, dict):
            return ""
        custom_templates = run_config.get("custom_templates")
        if not isinstance(custom_templates, dict) or not custom_templates:
            return ""
        custom_t_dir = Path(str(run_config.get("custom_templates_dir") or ""))
        if not custom_t_dir.exists():
            raise HTTPException(400, "原任务自定义模板目录不存在，无法重跑")
        missing = [
            name for name in custom_templates.values()
            if not (custom_t_dir / str(name)).exists()
        ]
        if missing:
            raise HTTPException(400, "原任务自定义模板不存在，无法重跑")
        return str(custom_t_dir)

    def _persist_and_merge_profile_decisions(
        *,
        config_root: Path,
        confirmed_decisions: object | None,
    ) -> dict[str, dict[str, str]]:
        saved = persist_project_profile_decisions(
            config_root=config_root,
            confirmed_decisions=confirmed_decisions,
        )
        merged = merge_decision_payloads(saved, confirmed_decisions or {})
        return serialize_decisions(merged)

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
        thinking_dir = log_dir / "ai_thinking"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)
        thinking_dir.mkdir(parents=True, exist_ok=True)

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
            "## Parsed Rows",
            json.dumps(debug.get("parsed_rows") or [], ensure_ascii=False, indent=2),
            "",
            "## Quality Review",
            json.dumps(debug.get("quality_review") or {}, ensure_ascii=False, indent=2),
        ]).strip() + "\n"
        thinking_text = "\n".join([
            f"# FPA 预览 Thinking: {module_label}",
            "",
            str(debug.get("thinking") or ""),
        ]).strip() + "\n"

        (prompts_dir / f"{base_name}_prompt.md").write_text(prompt_text, encoding="utf-8")
        (responses_dir / f"{base_name}_response.md").write_text(response_text, encoding="utf-8")
        (thinking_dir / f"{base_name}_thinking.md").write_text(thinking_text, encoding="utf-8")
        records_dir = log_dir / "debug_records"
        records_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "id": base_name,
            "source": "fpa_preview",
            "module": module_label,
            "model": str(debug.get("model") or ""),
            "reason": str(debug.get("reason") or ""),
            "ai_called": bool(debug.get("ai_called")),
            "prompt_file": f"{base_name}_prompt.md",
            "response_file": f"{base_name}_response.md",
            "thinking_file": f"{base_name}_thinking.md",
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

    def _request_scope(request: Request, user: str) -> tuple[bool, str]:
        local = is_local_mode(request)
        return local, "" if local else (user or get_auth_user(request) or "")

    def _safe_output_segment(value: str) -> str:
        import re

        cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value or "").strip(" ._")
        return cleaned or "task"

    def _project_or_input_name(*, task_config: dict, input_path: Path) -> str:
        project_name = str(task_config.get("project_name") or "").strip()
        if project_name:
            return project_name
        return input_path.stem or "task"

    def _local_session_output_dir(
        *,
        output_root: Path,
        task_config: dict,
        input_path: Path,
        session_id: str,
    ) -> Path:
        segment = _safe_output_segment(
            _project_or_input_name(task_config=task_config, input_path=input_path)
        )
        target = output_root / f"{segment}_{session_id}"
        if target.exists():
            raise HTTPException(400, f"目标输出目录已存在: {target}")
        target.mkdir(parents=True)
        return target

    def _queue_task(
        *,
        session_id: str,
        mode: Literal["local", "remote"],
        owner: str,
        target,
    ) -> dict:
        result = task_queue.submit(
            QueuedTask(
                session_id=session_id,
                mode=mode,
                owner=owner,
                target=target,
                on_started=lambda: mark_web_run_started(
                    base_dir=base_dir,
                    session_id=session_id,
                    mode=mode,
                ),
                on_cancelled=lambda message: cancel_web_run(
                    base_dir=base_dir,
                    session_id=session_id,
                    mode=mode,
                    error=message,
                ),
                on_failed_to_start=lambda message: fail_web_run(
                    base_dir=base_dir,
                    session_id=session_id,
                    mode=mode,
                    error=message,
                ),
            )
        )
        return {
            "session_id": session_id,
            "run_state": result["run_state"],
            "queue_position": result["queue_position"],
        }

    def _start_rerun(record: dict, *, local_mode: bool, user: str) -> dict:
        _cleanup_task_assets()
        mode = str(record.get("mode") or "")
        task_mode = str(record.get("task_mode") or "")
        if task_mode not in mode_info:
            raise HTTPException(400, f"未知模式: {task_mode}")
        if mode not in {"local", "remote"}:
            raise HTTPException(400, f"未知任务模式: {mode}")

        input_path = Path(str(record.get("input_path") or ""))
        if not input_path.exists():
            raise HTTPException(400, "原始输入文件不存在，无法重跑")

        session_id = uuid.uuid4().hex[:8]
        task_config = _resolve_task_config_snapshot(
            explicit=_rerun_explicit_config(record),
            local_mode=local_mode,
            user=user,
            mode=task_mode,
            require_api_key=True,
        )
        custom_templates_dir = _resolve_rerun_custom_templates(record)
        clean = _rerun_clean(record)

        if mode == "local":
            previous_output_dir = Path(str(record.get("output_dir") or ""))
            output_root = previous_output_dir.parent if previous_output_dir else input_path.parent
            output_root.mkdir(parents=True, exist_ok=True)
            output_dir = _local_session_output_dir(
                output_root=output_root,
                task_config=task_config,
                input_path=input_path,
                session_id=session_id,
            )
            profile_root = _profile_config_root(local_mode=True)
            profile_decisions = _load_profile_decision_payload(profile_root)
            session_manager.create(
                session_id,
                mode="local",
                output_dir=output_dir,
                config_root=profile_root,
            )
            history_input = input_path
            if local_task_input_snapshot_enabled():
                history_input = _snapshot_history_input(
                    session_id=session_id,
                    source=input_path,
                    mode="local",
                    source_run_id=str(record.get("run_id") or ""),
                )
            history_custom_templates_dir = _snapshot_history_templates(
                session_id=session_id,
                source_dir=custom_templates_dir,
                mode="local",
                source_run_id=str(record.get("run_id") or ""),
            )
            start_web_run(
                base_dir=base_dir,
                session_id=session_id,
                mode="local",
                task_mode=task_mode,
                input_path=str(history_input),
                output_dir=str(output_dir),
                run_config=_run_config_snapshot(
                    task_config=task_config,
                    clean=clean,
                    custom_t_dir=history_custom_templates_dir,
                ),
                run_state="queued",
            )

            def run_local_rerun():
                pipeline_runtime.web_mode_var.set("local")

                def _finish(sid: str, files: list[dict], error: str | None) -> None:
                    finish_web_run(
                        base_dir=base_dir,
                        session_id=sid,
                        mode="local",
                        task_mode=task_mode,
                        input_path=str(history_input),
                        output_dir=str(output_dir),
                        done_files=files,
                        error=error or "",
                    )

                execute_in_session(
                    session_manager,
                    session_id,
                    str(input_path),
                    str(output_dir),
                    custom_templates_dir,
                    task_config["api_key"],
                    task_config["model"],
                    task_config["base_url"],
                    task_config["project_name"],
                    task_config["max_tokens"],
                    task_config["fpa_profile"],
                    task_config["fpa_strategy"],
                    task_config["fpa_rule_set"],
                    task_config["fpa_confirmation_mode"],
                    task_config["fpa_core_rules"],
                    task_config["fpa_system_prompt"],
                    task_config["fpa_user_prompt"],
                    task_config["fpa_base_profile"],
                    profile_decisions,
                    clean,
                    task_mode,
                    mode_info=mode_info,
                    mode_map=mode_map,
                    on_finish=_finish,
                )

            queued = _queue_task(
                session_id=session_id,
                mode="local",
                owner="",
                target=run_local_rerun,
            )
            return {**queued, "mode": "local", "output_dir": str(output_dir)}

        work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        custom_t_dir = work_dir / "custom_templates"
        for directory in [input_dir, output_dir, custom_t_dir]:
            directory.mkdir(parents=True)
        if custom_templates_dir:
            for source in Path(custom_templates_dir).iterdir():
                if source.is_file():
                    shutil.copy2(source, custom_t_dir / source.name)
        rerun_input = input_dir / input_path.name
        shutil.copy2(input_path, rerun_input)
        history_input = _snapshot_history_input(
            session_id=session_id,
            source=rerun_input,
            mode="remote",
            owner_id=user,
            source_run_id=str(record.get("run_id") or ""),
        )
        history_custom_templates_dir = _snapshot_history_templates(
            session_id=session_id,
            source_dir=str(custom_t_dir),
            mode="remote",
            owner_id=user,
            source_run_id=str(record.get("run_id") or ""),
        )
        profile_root = _profile_config_root(local_mode=False, user=user)
        profile_decisions = _load_profile_decision_payload(profile_root)
        session_manager.create(
            session_id,
            mode="remote",
            owner=user,
            work_dir=work_dir,
            config_root=profile_root,
        )
        start_web_run(
            base_dir=base_dir,
            session_id=session_id,
            mode="remote",
            task_mode=task_mode,
            input_path=str(history_input),
            owner_id=user,
            owner_label=user,
            run_config=_run_config_snapshot(
                task_config=task_config,
                clean=clean,
                custom_t_dir=history_custom_templates_dir,
            ),
            run_state="queued",
        )

        def run_remote_rerun():
            pipeline_runtime.web_mode_var.set("remote")

            def _pack_zip(output_dir_path: str, sid: str, result: object) -> None:
                zip_path = work_dir / f"交付物_{sid}.zip"
                shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir_path))
                session_manager.set_zip(sid, zip_path)

            def _finish(sid: str, files: list[dict], error: str | None) -> None:
                state = session_manager.get(sid)
                zip_path = state.zip_path if state else None
                finish_web_run(
                    base_dir=base_dir,
                    session_id=sid,
                    mode="remote",
                    task_mode=task_mode,
                    input_path=str(history_input),
                    owner_id=user,
                    owner_label=user,
                    zip_path=str(zip_path) if zip_path else "",
                    done_files=files,
                    error=error or "",
                )

            execute_in_session(
                session_manager,
                session_id,
                str(rerun_input),
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
                task_config["fpa_core_rules"],
                task_config["fpa_system_prompt"],
                task_config["fpa_user_prompt"],
                task_config["fpa_base_profile"],
                profile_decisions,
                clean,
                task_mode,
                mode_info=mode_info,
                mode_map=mode_map,
                on_success=_pack_zip,
                on_finish=_finish,
            )

        queued = _queue_task(
            session_id=session_id,
            mode="remote",
            owner=user,
            target=run_remote_rerun,
        )
        return {**queued, "mode": "remote", "has_download": True}

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
            core_rules = cfg.get("core_rules", {})
            system_prompt_sets = cfg.get("system_prompt_sets", {})
            user_prompt_sets = cfg.get("user_prompt_sets", {})
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
                    "core_rules": str(entry.get("core_rules") or ""),
                    "system_prompt": str(entry.get("system_prompt") or ""),
                    "user_prompt": str(entry.get("user_prompt") or ""),
                    "confirmation_mode": "auto",
                    "editable": False,
                })
            first_profile = profile_options[0] if profile_options else {}
            profile_options.append({
                "name": "custom_profile",
                "label": "自定义 FPA 方案",
                "kind": str(first_profile.get("kind") or ""),
                "strategy": str(first_profile.get("strategy") or ""),
                "rule_set": str(first_profile.get("rule_set") or ""),
                "core_rules": str(first_profile.get("core_rules") or ""),
                "system_prompt": str(first_profile.get("system_prompt") or ""),
                "user_prompt": str(first_profile.get("user_prompt") or ""),
                "confirmation_mode": "auto",
                "editable": True,
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
                "core_rules": [
                    {"name": str(name), "label": str(name)}
                    for name in (core_rules if isinstance(core_rules, dict) else {})
                ],
                "system_prompt_sets": [
                    {"name": str(name), "label": str(name)}
                    for name in (system_prompt_sets if isinstance(system_prompt_sets, dict) else {})
                ],
                "user_prompt_sets": [
                    {"name": str(name), "label": str(name)}
                    for name in (user_prompt_sets if isinstance(user_prompt_sets, dict) else {})
                ],
            }
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/api/tasks")
    async def api_tasks(
        request: Request,
        user: str = Depends(require_auth),
        mode: str = "all",
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ):
        local, owner_id = _request_scope(request, user)
        result = list_tasks(
            base_dir=base_dir,
            local_mode=local,
            owner_id=owner_id,
            mode=mode,
            state=state,
            limit=limit,
            offset=offset,
        )
        for item in result["items"]:
            session_id = str(item.get("session_id") or item.get("run_id") or "")
            item["session_available"] = bool(
                item.get("run_state") in {"queued", "running"}
                and session_manager.can_access(
                    session_id,
                    owner_id,
                    local_mode=local,
                )
            )
            if item.get("run_state") == "queued":
                item["queue_position"] = task_queue.visible_position(
                    session_id,
                    local_mode=local,
                    owner=owner_id,
                )
        return result

    @router.post("/api/tasks/{run_id}/close")
    async def api_close_task(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local, owner_id = _request_scope(request, user)
        try:
            item = close_history_item(
                base_dir=base_dir,
                run_id=run_id,
                local_mode=local,
                owner_id=owner_id,
            )
        except PermissionError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "item": item}

    @router.post("/api/tasks/{run_id}/restore")
    async def api_restore_task(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local, owner_id = _request_scope(request, user)
        try:
            item = restore_closed_history_item(
                base_dir=base_dir,
                run_id=run_id,
                local_mode=local,
                owner_id=owner_id,
            )
        except PermissionError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "item": item}

    @router.post("/api/tasks/{run_id}/rerun")
    async def api_rerun_task(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local, owner_id = _request_scope(request, user)
        try:
            record = require_rerunnable_history_item(
                base_dir=base_dir,
                run_id=run_id,
                local_mode=local,
                owner_id=owner_id,
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _start_rerun(record, local_mode=local, user=owner_id)

    @router.post("/api/tasks/{run_id}/mark-unrecoverable")
    async def api_mark_unrecoverable_task(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local, owner_id = _request_scope(request, user)
        if session_manager.can_access(run_id, owner_id, local_mode=local):
            raise HTTPException(400, "任务仍可继续执行，不能标记为不可恢复")
        try:
            item = mark_unrecoverable_history_item(
                base_dir=base_dir,
                run_id=run_id,
                local_mode=local,
                owner_id=owner_id,
            )
        except PermissionError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "item": item}

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
        payload = _session_status_payload(session_id, state)
        if payload.get("run_state") == "queued":
            local, owner_id = _request_scope(request, user)
            payload["queue_position"] = task_queue.visible_position(
                session_id,
                local_mode=local,
                owner=owner_id,
            )
        return payload

    @router.get("/api/sessions/{session_id}/logs")
    async def get_session_logs(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回当前进程内保留的 session 事件日志快照。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        if state is None:
            raise HTTPException(404, "未知会话")
        return {
            "session_id": session_id,
            "entries": session_manager.get_log_entries(session_id),
        }

    @router.post("/api/cancel/{session_id}")
    async def cancel_session(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """停止指定 session 的执行。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        if state is not None and _session_run_state(state) == "queued":
            task_queue.cancel(session_id)
            return {
                "ok": True,
                "run_state": "cancelled",
            }
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
        state = session_manager.get(session_id)
        if (
            state is not None
            and str(data.get("kind") or "") == "fpa_confirmation"
            and isinstance(data.get("confirmed_decisions"), dict)
        ):
            config_root = state.config_root or _profile_config_root(
                local_mode=state.mode == "local",
                user=state.owner or user,
            )
            data = dict(data)
            data["confirmed_decisions"] = _persist_and_merge_profile_decisions(
                config_root=config_root,
                confirmed_decisions=data.get("confirmed_decisions"),
            )
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
        state = session_manager.get(session)
        if state is not None and _session_run_state(state) == "queued":
            async def queued_generate():
                data = {
                    "type": "log",
                    "level": "INFO",
                    "msg": "任务正在排队，请在详情页等待启动",
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                queued_generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        subscription = session_manager.subscribe_log_stream(session)
        if subscription is None:
            raise HTTPException(404, "未知会话")
        stream_id, q = subscription

        async def generate():
            try:
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
            finally:
                session_manager.remove_log_stream(session, stream_id)

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
        fpa_core_rules: str = Form(""),
        fpa_system_prompt: str = Form(""),
        fpa_user_prompt: str = Form(""),
        fpa_base_profile: str = Form(""),
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
        _cleanup_task_assets()

        from_dir = ""
        if Path(xlsx_path).is_dir():
            from_dir = xlsx_path
        xlsx = _resolve_local_xlsx_input(xlsx_path)

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
                fpa_core_rules=fpa_core_rules,
                fpa_system_prompt=fpa_system_prompt,
                fpa_user_prompt=fpa_user_prompt,
                fpa_base_profile=fpa_base_profile,
                fpa_confirmation_mode=fpa_confirmation_mode,
            ),
            local_mode=True,
            mode=mode,
        )

        session_id = uuid.uuid4().hex[:8]
        output_root = Path(output_dir) if output_dir else (Path(from_dir) if from_dir else xlsx.parent)
        output_root.mkdir(parents=True, exist_ok=True)
        out = _local_session_output_dir(
            output_root=output_root,
            task_config=task_config,
            input_path=xlsx,
            session_id=session_id,
        )

        custom_t_dir_path = out / "custom_templates"
        try:
            custom_t_dir = await save_custom_templates(
                out, fpa_template, cosmic_template, list_template, spec_template
            )
        except UploadSecurityError as exc:
            shutil.rmtree(custom_t_dir_path, ignore_errors=True)
            raise HTTPException(400, str(exc)) from exc

        profile_root = _profile_config_root(local_mode=True)
        profile_decisions = _load_profile_decision_payload(profile_root)
        history_input = xlsx
        if local_task_input_snapshot_enabled():
            history_input = _snapshot_history_input(
                session_id=session_id,
                source=xlsx,
                mode="local",
            )
        history_custom_templates_dir = _snapshot_history_templates(
            session_id=session_id,
            source_dir=custom_t_dir,
            mode="local",
        )
        session_manager.create(
            session_id,
            mode="local",
            output_dir=out,
            config_root=profile_root,
        )
        start_web_run(
            base_dir=base_dir,
            session_id=session_id,
            mode="local",
            task_mode=mode,
            input_path=str(history_input),
            output_dir=str(out),
            run_config=_run_config_snapshot(
                task_config=task_config,
                clean=bool(clean),
                custom_t_dir=history_custom_templates_dir,
            ),
            run_state="queued",
        )

        def run():
            pipeline_runtime.web_mode_var.set("local")

            def _finish(sid: str, files: list[dict], error: str | None) -> None:
                finish_web_run(
                    base_dir=base_dir,
                    session_id=sid,
                    mode="local",
                    task_mode=mode,
                    input_path=str(history_input),
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
                task_config["fpa_core_rules"],
                task_config["fpa_system_prompt"],
                task_config["fpa_user_prompt"],
                task_config["fpa_base_profile"],
                profile_decisions,
                bool(clean),
                mode,
                mode_info=mode_info,
                mode_map=mode_map,
                on_finish=_finish,
            )

        queued = _queue_task(
            session_id=session_id,
            mode="local",
            owner="",
            target=run,
        )
        return {**queued, "output_dir": str(out)}

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
        fpa_core_rules: str = Form(""),
        fpa_system_prompt: str = Form(""),
        fpa_user_prompt: str = Form(""),
        fpa_base_profile: str = Form(""),
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
        _cleanup_task_assets()
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
                fpa_core_rules=fpa_core_rules,
                fpa_system_prompt=fpa_system_prompt,
                fpa_user_prompt=fpa_user_prompt,
                fpa_base_profile=fpa_base_profile,
                fpa_confirmation_mode=fpa_confirmation_mode,
            ),
            local_mode=False,
            user=user,
            mode=mode,
        )
        try:
            validated_input = await validate_upload_file(file, purpose="input_xlsx")
        except UploadSecurityError as exc:
            raise HTTPException(400, str(exc)) from exc

        session_id = uuid.uuid4().hex[:8]
        work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        custom_t_dir = work_dir / "custom_templates"
        for d in [input_dir, output_dir, custom_t_dir]:
            d.mkdir(parents=True)

        safe_name = validated_input.safe_filename
        file_path = input_dir / safe_name
        file_path.write_bytes(validated_input.content)

        try:
            await save_custom_templates_into(
                custom_t_dir, fpa_template, cosmic_template, list_template, spec_template
            )
        except UploadSecurityError as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise HTTPException(400, str(exc)) from exc
        history_input = _snapshot_history_input(
            session_id=session_id,
            source=file_path,
            mode="remote",
            owner_id=user,
        )
        history_custom_templates_dir = _snapshot_history_templates(
            session_id=session_id,
            source_dir=str(custom_t_dir),
            mode="remote",
            owner_id=user,
        )

        profile_root = _profile_config_root(local_mode=False, user=user)
        profile_decisions = _load_profile_decision_payload(profile_root)
        session_manager.create(
            session_id,
            mode="remote",
            owner=user,
            work_dir=work_dir,
            config_root=profile_root,
        )
        start_web_run(
            base_dir=base_dir,
            session_id=session_id,
            mode="remote",
            task_mode=mode,
            input_path=str(history_input),
            owner_id=user,
            owner_label=user,
            run_config=_run_config_snapshot(
                task_config=task_config,
                clean=bool(clean),
                custom_t_dir=history_custom_templates_dir,
            ),
            run_state="queued",
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
                    input_path=str(history_input),
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
                task_config["fpa_core_rules"],
                task_config["fpa_system_prompt"],
                task_config["fpa_user_prompt"],
                task_config["fpa_base_profile"],
                profile_decisions,
                bool(clean),
                mode,
                mode_info=mode_info,
                mode_map=mode_map,
                on_success=_pack_zip,
                on_finish=_finish,
            )

        queued = _queue_task(
            session_id=session_id,
            mode="remote",
            owner=user,
            target=run,
        )
        return {**queued, "has_download": True}

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
        fpa_core_rules: str = Form(""),
        fpa_system_prompt: str = Form(""),
        fpa_user_prompt: str = Form(""),
        fpa_base_profile: str = Form(""),
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
                validated_input = await validate_upload_file(file, purpose="input_xlsx")
                safe_name = validated_input.safe_filename
                file_path = input_dir / safe_name
                file_path.write_bytes(validated_input.content)
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
                    fpa_core_rules=fpa_core_rules,
                    fpa_system_prompt=fpa_system_prompt,
                    fpa_user_prompt=fpa_user_prompt,
                    fpa_base_profile=fpa_base_profile,
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
            profile_root = _profile_config_root(local_mode=local_preview, user=user)
            confirmed_decisions_payload = _persist_and_merge_profile_decisions(
                config_root=profile_root,
                confirmed_decisions=confirmed_decisions_payload,
            )
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
                core_rules=task_config["fpa_core_rules"],
                system_prompt=task_config["fpa_system_prompt"],
                user_prompt=task_config["fpa_user_prompt"],
                base_profile=task_config["fpa_base_profile"],
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
                validated_input = await validate_upload_file(file, purpose="input_xlsx")
                safe_name = validated_input.safe_filename
                file_path = input_dir / safe_name
                file_path.write_bytes(validated_input.content)
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
