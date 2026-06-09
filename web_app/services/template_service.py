import glob
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_gen_reimbursement_docs.spec_template_importer import (
    SpecTemplateImportResult,
    import_spec_word_template,
)


async def save_custom_templates_into(
    target_dir: Path,
    fpa_template: Any | None,
    cosmic_template: Any | None,
    list_template: Any | None,
    spec_template: Any | None,
):
    """将自定义模板保存到指定目录。"""
    for tpl_file, tpl_name in [
        (fpa_template, "FPA工作量评估-输出模板.xlsx"),
        (cosmic_template, "项目功能点拆分表-输出模板.xlsx"),
        (list_template, "项目需求清单-输出模板.xlsx"),
        (spec_template, "项目需求说明书-输出模板.docx"),
    ]:
        if tpl_file is not None and tpl_file.filename:
            tpl_content = await tpl_file.read()
            (target_dir / tpl_name).write_bytes(tpl_content)


async def save_custom_templates(
    parent_dir: Path,
    fpa_template: Any | None,
    cosmic_template: Any | None,
    list_template: Any | None,
    spec_template: Any | None,
) -> str:
    """将自定义模板保存到临时目录，返回目录路径。"""
    custom_t_dir = parent_dir / "custom_templates"
    custom_t_dir.mkdir(parents=True, exist_ok=True)
    await save_custom_templates_into(
        custom_t_dir, fpa_template, cosmic_template, list_template, spec_template
    )
    return str(custom_t_dir)


def build_templates_dict(custom_t_dir: str) -> dict[str, str]:
    """构建 templates dict：自定义模板优先。"""
    templates: dict[str, str] = {}
    for key, glob_pat in [
        ("fpa", "FPA*评估*模板*.xlsx"),
        ("cosmic", "*功能点拆分表*模板*.xlsx"),
        ("list", "*需求清单*模板*.xlsx"),
        ("spec", "*需求说明书*模板*.docx"),
    ]:
        matches = glob.glob(os.path.join(custom_t_dir, glob_pat))
        if matches:
            templates[key] = matches[0]
    return templates


async def import_spec_template_upload(
    *,
    upload_file: Any,
    target_root: Path,
) -> SpecTemplateImportResult:
    """导入客户 Word 文档，生成需求说明书输出模板草稿。"""
    filename = str(getattr(upload_file, "filename", "") or "")
    if not filename.lower().endswith(".docx"):
        raise ValueError("仅支持上传 .docx 文件")

    import_id = uuid4().hex[:12]
    import_dir = target_root / "imported_templates" / "spec" / import_id
    import_dir.mkdir(parents=True, exist_ok=True)
    source_path = import_dir / "source.docx"
    source_path.write_bytes(await upload_file.read())

    return import_spec_word_template(
        source_path,
        import_dir,
        template_id=f"imported_spec_{import_id}",
    )
