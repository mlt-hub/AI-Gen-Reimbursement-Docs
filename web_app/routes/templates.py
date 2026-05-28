from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


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
