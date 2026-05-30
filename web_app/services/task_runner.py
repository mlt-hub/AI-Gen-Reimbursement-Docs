import asyncio
import logging
import os
import shutil
from collections.abc import Callable

from ai_gen_reimbursement_docs.exceptions import CancelledError
from ai_gen_reimbursement_docs.pipeline_callbacks import PipelineCallbacks
from ai_gen_reimbursement_docs.runtime_context import callbacks_var
from web_app.services import pipeline_runtime
from web_app.services.session_manager import SessionManager
from web_app.services.template_service import build_templates_dict


def cleanup_expired_sessions(
    session_manager: SessionManager,
    max_age_seconds: int = 24 * 3600,
) -> int:
    """清理过期 session 及其远程临时目录。"""
    logger = logging.getLogger("ai_gen_reimbursement_docs")
    work_dirs = session_manager.cleanup_expired(max_age_seconds)
    for work_dir in work_dirs:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info("已清理过期远程 session 目录: %s", work_dir)
    if work_dirs:
        logger.info("过期 session 清理完成: %s 个", len(work_dirs))
    return len(work_dirs)


def start_background_task(
    session_manager: SessionManager,
    session_id: str,
    target: Callable[[], None],
) -> asyncio.Task:
    """启动后台任务并记录其生命周期。"""
    logger = logging.getLogger("ai_gen_reimbursement_docs")
    session_manager.mark_task_started(session_id)
    task = asyncio.create_task(asyncio.to_thread(target))

    def _record_done(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.info("后台任务已取消: session=%s", session_id)
            session_manager.mark_task_finished(session_id, last_error="cancelled")
        except Exception as exc:
            logger.exception("后台任务异常: session=%s", session_id)
            session_manager.mark_task_finished(session_id, last_error=str(exc))
            pipeline_runtime.emit_session_event(
                session_manager,
                {"type": "error", "msg": f"后台任务异常: {exc}"},
            )
        else:
            state = session_manager.get(session_id)
            if state is None or state.task_done_at is None:
                session_manager.mark_task_finished(session_id)

    task.add_done_callback(_record_done)
    return task


def build_file_summary(result) -> list[dict]:
    """从 PipelineResult 构建文件摘要。标注 _TEMP 文件。"""
    files = []
    labels = [
        ("FPA 工作量评估", getattr(result, "fpa_xlsx", "")),
        ("项目功能点拆分表", getattr(result, "cosmic_xlsx", "")),
        ("项目需求清单", getattr(result, "require_xlsx", "")),
        ("项目需求说明书", getattr(result, "spec_docx", "")),
    ]
    for label, path in labels:
        if path and os.path.exists(path):
            size = os.path.getsize(path)
            is_temp = "_TEMP" in os.path.basename(path)
            files.append({
                "label": label,
                "path": path,
                "size_kb": round(size / 1024),
                "is_temp": is_temp,
            })
    return files


def build_web_callbacks(session_manager: SessionManager) -> PipelineCallbacks:
    return PipelineCallbacks(
        is_web_mode=pipeline_runtime.is_web_mode,
        check_cancelled=lambda: pipeline_runtime.check_cancelled(session_manager),
        emit_event=lambda data: pipeline_runtime.emit_session_event(
            session_manager, data
        ),
        wait_for_fpa_input=lambda default: pipeline_runtime.wait_for_fpa_input(
            session_manager, default
        ),
        wait_for_list_input=lambda cfp, fpa: pipeline_runtime.wait_for_list_input(
            session_manager, cfp, fpa
        ),
    )


def execute_mode(
    mode: str,
    file_path: str,
    output_dir: str,
    custom_t_dir: str,
    api_key: str,
    model: str,
    base_url: str,
    project_name: str = "",
    max_tokens: str = "",
    fpa_profile: str = "",
    clean: bool = False,
    *,
    mode_info: dict[str, dict[str, str]],
    mode_map: dict[str, str],
    callbacks: PipelineCallbacks | None = None,
):
    """一站式管道入口，CLI / Web UI 共享。"""
    from ai_gen_reimbursement_docs.pipeline import run_pipeline_simple

    if max_tokens:
        os.environ["AI_REIMBURSEMENT_MAX_TOKENS"] = max_tokens
    if clean and os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            if name not in ("custom_templates",):
                path = os.path.join(output_dir, name)
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)

    logger = logging.getLogger("ai_gen_reimbursement_docs")
    logger.info(f"操作模式: {mode_info.get(mode, {}).get('label', mode)}")

    pipeline_mode = mode_map[mode]
    templates = build_templates_dict(custom_t_dir)

    return run_pipeline_simple(
        mode=pipeline_mode,
        file_path=file_path,
        output_dir=output_dir,
        api_key=api_key,
        model=model,
        base_url=base_url,
        project_name=project_name,
        templates=templates or None,
        fpa_profile=fpa_profile,
        callbacks=callbacks,
    )


def execute_in_session(
    session_manager: SessionManager,
    session_id: str,
    file_path: str,
    output_dir: str,
    custom_t_dir: str,
    api_key: str,
    model: str,
    base_url: str,
    project_name: str,
    max_tokens: str,
    fpa_profile: str,
    clean: bool,
    mode: str,
    *,
    mode_info: dict[str, dict[str, str]],
    mode_map: dict[str, str],
    on_success: Callable[[str, str, object], None] | None = None,
    on_finish: Callable[[str, list[dict], str | None], None] | None = None,
) -> None:
    """在 session 上下文中执行 pipeline，统一处理事件、异常和清理。"""
    session_token = pipeline_runtime.session_var.set(session_id)
    callbacks = build_web_callbacks(session_manager)
    callbacks_token = callbacks_var.set(callbacks)
    result = None
    error_message: str | None = None
    files: list[dict] = []
    try:
        result = execute_mode(
            mode,
            file_path,
            output_dir,
            custom_t_dir,
            api_key,
            model,
            base_url,
            project_name,
            max_tokens=max_tokens,
            fpa_profile=fpa_profile,
            clean=clean,
            mode_info=mode_info,
            mode_map=mode_map,
            callbacks=callbacks,
        )
        if on_success:
            on_success(output_dir, session_id, result)
    except CancelledError as e:
        error_message = "cancelled"
        logging.getLogger("ai_gen_reimbursement_docs").info(f"任务已停止: {e}")
        pipeline_runtime.emit_session_event(session_manager, {"type": "cancelled"})
        session_manager.mark_task_finished(session_id, last_error="cancelled")
    except Exception as e:
        error_message = str(e)
        logging.getLogger("ai_gen_reimbursement_docs").error(f"执行失败: {e}")
        pipeline_runtime.emit_session_event(
            session_manager,
            {"type": "error", "msg": f"执行失败: {e}"},
        )
        session_manager.mark_task_finished(session_id, last_error=error_message)
    finally:
        if error_message is None and not session_manager.is_cancelled(session_id):
            files = build_file_summary(result) if result else []
            session_manager.set_done_files(session_id, files)
            pipeline_runtime.emit_session_event(
                session_manager,
                {
                    "type": "done",
                    "files": files,
                },
            )
            session_manager.mark_task_finished(session_id)
        if on_finish:
            on_finish(session_id, files, error_message)
        session_manager.clear_cancelled(session_id)
        callbacks_var.reset(callbacks_token)
        pipeline_runtime.session_var.reset(session_token)
