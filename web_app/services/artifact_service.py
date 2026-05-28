import asyncio
import shutil
from pathlib import Path

from web_app.services.session_manager import SessionManager


def find_log_dir(session_manager: SessionManager, session_id: str) -> Path | None:
    """根据 session 找到日志目录。"""
    state = session_manager.get(session_id)
    out_dir = state.output_dir if state else None
    if out_dir is None and state and state.work_dir:
        out_dir = state.work_dir / "output"
    if out_dir is None or not out_dir.exists():
        return None

    for log_dir in out_dir.rglob("日志"):
        if log_dir.is_dir():
            return log_dir
    return None


async def cleanup_after_download(session_manager: SessionManager, session_id: str):
    """下载完成后延迟 5 分钟清理，避免干扰。"""
    await asyncio.sleep(300)
    work_dir = session_manager.cleanup_download(session_id)
    if work_dir and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
