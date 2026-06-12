from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_gen_reimbursement_docs.run_history import now_iso
from web_app.services.config_service import task_assets_retention_seconds
from web_app.services.template_service import build_templates_dict


logger = logging.getLogger("ai_gen_reimbursement_docs")
TASK_ASSETS_DIRNAME = "task_assets"
TASK_ASSETS_AUDIT_FILENAME = "task_assets_cleanup.jsonl"
TASK_ASSETS_METADATA_FILENAME = "metadata.json"


def task_assets_root(base_dir: Path) -> Path:
    return base_dir / "products" / TASK_ASSETS_DIRNAME


def task_assets_audit_path(base_dir: Path) -> Path:
    return base_dir / "products" / TASK_ASSETS_AUDIT_FILENAME


def task_assets_retention_label() -> str:
    seconds = task_assets_retention_seconds()
    if seconds <= 0:
        return "不自动清理"
    days = round(seconds / 86400, 2)
    if days == int(days):
        return f"{int(days)} 天"
    return f"{days} 天"


def prepare_task_asset_dir(
    *,
    base_dir: Path,
    session_id: str,
    mode: str,
    owner_id: str = "",
    source_run_id: str = "",
) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
    if not safe_id:
        raise ValueError("session_id 无效")
    path = task_assets_root(base_dir) / safe_id
    path.mkdir(parents=True, exist_ok=True)
    _write_metadata(
        path,
        {
            "session_id": safe_id,
            "source_run_id": source_run_id,
            "mode": mode,
            "owner_id": owner_id,
            "created_at": now_iso(),
            "retention_expires_at": _retention_expires_at(),
        },
    )
    return path


def snapshot_input_file(
    *,
    base_dir: Path,
    session_id: str,
    source: Path,
    mode: str,
    owner_id: str = "",
    source_run_id: str = "",
) -> Path:
    asset_dir = prepare_task_asset_dir(
        base_dir=base_dir,
        session_id=session_id,
        mode=mode,
        owner_id=owner_id,
        source_run_id=source_run_id,
    )
    target_dir = asset_dir / "input"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    _merge_metadata(asset_dir, {"input_path": str(target)})
    return target


def snapshot_custom_templates(
    *,
    base_dir: Path,
    session_id: str,
    source_dir: str,
    mode: str,
    owner_id: str = "",
    source_run_id: str = "",
) -> str:
    if not source_dir:
        return ""
    source = Path(source_dir)
    if not source.exists() or not source.is_dir():
        return ""
    templates = build_templates_dict(str(source))
    if not templates:
        return ""
    asset_dir = prepare_task_asset_dir(
        base_dir=base_dir,
        session_id=session_id,
        mode=mode,
        owner_id=owner_id,
        source_run_id=source_run_id,
    )
    target = asset_dir / "custom_templates"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for key, template_path in templates.items():
        source_file = Path(template_path)
        if source_file.exists() and source_file.is_file():
            target_file = target / source_file.name
            shutil.copy2(source_file, target_file)
            copied[key] = target_file.name
    if not copied:
        return ""
    _merge_metadata(asset_dir, {"custom_templates_dir": str(target), "custom_templates": copied})
    return str(target)


def cleanup_expired_task_assets(*, base_dir: Path) -> int:
    retention_seconds = task_assets_retention_seconds()
    if retention_seconds <= 0:
        return 0
    root = task_assets_root(base_dir)
    if not root.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(seconds=retention_seconds)
    removed = 0
    for item in root.iterdir():
        if not item.is_dir():
            continue
        try:
            created_at = _asset_created_at(item)
            if created_at > cutoff:
                continue
            resolved_root = root.resolve()
            resolved_item = item.resolve()
            if resolved_item.parent != resolved_root:
                continue
            shutil.rmtree(resolved_item)
            removed += 1
            _append_cleanup_audit(
                base_dir,
                {
                    "event": "task_asset_removed",
                    "reason": "retention_expired",
                    "session_id": item.name,
                    "path": str(item),
                    "created_at": created_at.isoformat(),
                    "removed_at": now_iso(),
                    "retention_seconds": retention_seconds,
                },
            )
        except Exception as exc:
            logger.warning("清理重跑资产快照失败 %s: %s", item, exc)
    return removed


def _retention_expires_at() -> str:
    seconds = task_assets_retention_seconds()
    if seconds <= 0:
        return ""
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def _write_metadata(asset_dir: Path, metadata: dict[str, Any]) -> None:
    path = asset_dir / TASK_ASSETS_METADATA_FILENAME
    existing = _read_metadata(asset_dir)
    existing.update({key: value for key, value in metadata.items() if value not in (None, "")})
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_metadata(asset_dir: Path, metadata: dict[str, Any]) -> None:
    _write_metadata(asset_dir, metadata)


def _read_metadata(asset_dir: Path) -> dict[str, Any]:
    path = asset_dir / TASK_ASSETS_METADATA_FILENAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _asset_created_at(asset_dir: Path) -> datetime:
    metadata = _read_metadata(asset_dir)
    raw = str(metadata.get("created_at") or "")
    if raw:
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.fromtimestamp(asset_dir.stat().st_mtime, UTC)


def _append_cleanup_audit(base_dir: Path, record: dict[str, Any]) -> None:
    path = task_assets_audit_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
