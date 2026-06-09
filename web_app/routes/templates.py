from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from web_app.dependencies import config_dir, is_local_mode, require_auth
from web_app.services.template_service import import_spec_template_upload


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
IN_TEMPLATE_DIR = BASE_DIR / "data" / "in_templates"
TEMPLATE_DIR = BASE_DIR / "data" / "out_templates"


@router.get("/api/templates/input")
async def download_input_template():
    """下载录入模板（功能清单-录入模板.xlsx）。"""
    path = IN_TEMPLATE_DIR / "功能清单-录入模板.xlsx"
    if not path.exists():
        raise HTTPException(404, "录入模板不存在")
    return FileResponse(
        path,
        filename="功能清单-录入模板.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/api/templates/output")
async def list_output_templates():
    """列出所有可用输出模板。"""
    files = sorted([f.name for f in TEMPLATE_DIR.glob("*.*")])
    return {"templates": files}


@router.get("/api/templates/output/{name}")
async def download_output_template(name: str):
    """下载指定输出模板。"""
    path = (TEMPLATE_DIR / name).resolve()
    if path.parent != TEMPLATE_DIR.resolve():
        raise HTTPException(404, "无效的模板名称")
    if not path.exists():
        raise HTTPException(404, "模板不存在")
    return FileResponse(path, filename=name)


@router.post("/api/templates/spec/import")
async def import_spec_template(
    request: Request,
    file: UploadFile = File(...),
    _user: str = Depends(require_auth),
):
    """上传客户 Word 文档，生成 gen-spec 输出模板草稿和 manifest。"""
    if not is_local_mode(request):
        raise HTTPException(403, "Word 模板导入只能由本机管理员执行")

    try:
        result = await import_spec_template_upload(
            upload_file=file,
            target_root=config_dir(),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Word 模板导入失败: {exc}") from exc

    return {
        "template_path": str(result.template_path),
        "manifest_path": str(result.manifest_path),
        "template_filename": result.template_path.name,
        "manifest_filename": result.manifest_path.name,
        "detected_placeholders": [
            {
                "key": item.key,
                "label": item.label,
                "token": item.token,
                "scope": item.scope,
            }
            for item in result.detected_placeholders
        ],
        "inserted_anchors": [
            {
                "key": item.key,
                "token": item.token,
                "location": item.location,
            }
            for item in result.inserted_anchors
        ],
        "pending_confirmations": result.pending_confirmations,
        "warnings": result.warnings,
        "out_templates_patch": {
            "spec_out_template": str(result.template_path),
        },
    }
