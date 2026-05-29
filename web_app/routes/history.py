import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from web_app.dependencies import get_auth_user, is_local_mode, require_auth, require_local
from web_app.services.run_history_service import get_history_item, list_history


def create_router(*, base_dir: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/api/history")
    async def api_history(
        request: Request,
        user: str = Depends(require_auth),
        source: str = Query("all"),
        mode: str = Query("all"),
        state: str = Query("all"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        local = is_local_mode(request)
        owner_id = "" if local else (user or get_auth_user(request) or "")
        return list_history(
            base_dir=base_dir,
            local_mode=local,
            owner_id=owner_id,
            source=source,
            mode=mode,
            state=state,
            limit=limit,
            offset=offset,
        )

    @router.get("/api/history/{run_id}")
    async def api_history_item(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local = is_local_mode(request)
        owner_id = "" if local else (user or get_auth_user(request) or "")
        item = get_history_item(
            base_dir=base_dir,
            run_id=run_id,
            local_mode=local,
            owner_id=owner_id,
        )
        if item is None:
            raise HTTPException(404, "历史记录不存在")
        return item

    @router.post("/api/history/{run_id}/open-folder")
    async def api_history_open_folder(run_id: str, _local: None = Depends(require_local)):
        item = get_history_item(
            base_dir=base_dir,
            run_id=run_id,
            local_mode=True,
            owner_id="",
        )
        if item is None:
            raise HTTPException(404, "历史记录不存在")
        if item.get("mode") != "local" or item.get("artifact_kind") != "local_dir":
            raise HTTPException(400, "远程历史不支持打开服务端目录")
        output_dir = item.get("output_dir") or ""
        if not output_dir:
            raise HTTPException(404, "历史记录没有输出目录")
        path = Path(output_dir)
        if not path.exists():
            raise HTTPException(404, "交付物目录不存在")
        os.startfile(str(path))
        return {"ok": True}

    @router.get("/api/history/{run_id}/download")
    async def api_history_download(
        run_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        local = is_local_mode(request)
        owner_id = "" if local else (user or get_auth_user(request) or "")
        item = get_history_item(
            base_dir=base_dir,
            run_id=run_id,
            local_mode=local,
            owner_id=owner_id,
        )
        if item is None:
            raise HTTPException(404, "历史记录不存在")
        if item.get("artifact_kind") != "remote_zip":
            raise HTTPException(400, "本机历史不提供 zip 下载")
        if not item.get("download_available"):
            raise HTTPException(410, "交付物下载已过期")
        zip_path = Path(item.get("zip_path") or "")
        if not zip_path.exists():
            raise HTTPException(410, "交付物下载已过期")
        return FileResponse(
            zip_path,
            filename=f"交付物_{datetime.now():%Y%m%d_%H%M%S}.zip",
            media_type="application/zip",
        )

    return router
