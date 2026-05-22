"""启动时检查 GitHub Releases 是否有新版本。"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger('ai_gen_reimbursement_docs.version_check')

RELEASE_API_URL = "https://api.github.com/repos/mlt-hub/ai-gen-reimbursement-docs-release/releases/latest"
CHECK_INTERVAL_DAYS = 1


def _cache_file() -> Path:
    return Path.home() / ".ai-gen-reimbursement-docs" / ".last_version_check"


def _should_check() -> bool:
    """距上次检查超过 CHECK_INTERVAL_DAYS 天才检查。"""
    cf = _cache_file()
    if not cf.exists():
        return True
    try:
        last = datetime.fromisoformat(cf.read_text(encoding="utf-8").strip())
        return datetime.now() - last > timedelta(days=CHECK_INTERVAL_DAYS)
    except Exception:
        return True


def _mark_checked() -> None:
    cf = _cache_file()
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(datetime.now().isoformat(), encoding="utf-8")


def _parse_version(tag: str) -> tuple[int, ...]:
    """从 'v5.0.2' 解析为 (5, 0, 2)。"""
    tag = tag.lstrip("vV")
    try:
        return tuple(int(x) for x in tag.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def check_version(current_version: str) -> None:
    """非阻塞检查新版本，有新版时打印提示。"""
    if not _should_check():
        logger.debug("距上次版本检查不足 %d 天，跳过", CHECK_INTERVAL_DAYS)
        return

    _mark_checked()

    try:
        req = Request(RELEASE_API_URL, headers={"User-Agent": "ard-version-check", "Accept": "application/vnd.github+json"})
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        latest_tag = data.get("tag_name", "")
    except (URLError, OSError, json.JSONDecodeError) as e:
        logger.debug("版本检查失败: %s", e)
        return
    except Exception as e:
        logger.debug("版本检查异常: %s", e, exc_info=True)
        return

    if not latest_tag:
        return

    current = _parse_version(current_version)
    latest = _parse_version(latest_tag)

    if latest > current:
        print(f"\n  新版本可用: {latest_tag}（当前 {current_version}）")
        print(f"  下载地址: https://github.com/mlt-hub/ai-gen-reimbursement-docs-release/releases/latest\n")
