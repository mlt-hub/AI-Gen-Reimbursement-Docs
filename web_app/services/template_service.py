import glob
import os
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from docx import Document

from ai_gen_reimbursement_docs.spec_template_importer import (
    SpecTemplateImportResult,
    import_spec_word_template,
)
from ai_gen_reimbursement_docs.template_manifest import load_template_manifest, validate_output_template


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


def imported_spec_templates_root(target_root: Path) -> Path:
    return target_root / "imported_templates" / "spec"


def list_imported_spec_templates(target_root: Path) -> list[dict[str, Any]]:
    """列出已导入的需求说明书 Word 模板草稿。"""
    root = imported_spec_templates_root(target_root)
    if not root.exists():
        return []

    items: list[dict[str, Any]] = []
    for item_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
        template_path = item_dir / "项目需求说明书-输出模板.docx"
        manifest_path = item_dir / "项目需求说明书-输出模板.manifest.yaml"
        if not template_path.exists() or not manifest_path.exists():
            continue

        validation = validate_output_template("spec", str(template_path))
        stat = template_path.stat()
        items.append({
            "id": item_dir.name,
            "template_path": str(template_path),
            "manifest_path": str(manifest_path),
            "template_filename": template_path.name,
            "manifest_filename": manifest_path.name,
            "created_at": stat.st_mtime,
            "size_bytes": stat.st_size,
            "ok": validation.ok,
            "warnings": [issue.message for issue in validation.warnings],
            "errors": [issue.message for issue in validation.errors],
            "capabilities": validation.capabilities,
            "out_templates_patch": {
                "spec_out_template": str(template_path),
            },
        })
    return items


def resolve_imported_spec_template_file(target_root: Path, import_id: str, filename: str) -> Path:
    """Resolve an imported spec template file while preventing path traversal."""
    if filename not in {"项目需求说明书-输出模板.docx", "项目需求说明书-输出模板.manifest.yaml"}:
        raise FileNotFoundError(filename)
    root = imported_spec_templates_root(target_root).resolve()
    path = (root / import_id / filename).resolve()
    if path.parent.parent != root:
        raise FileNotFoundError(filename)
    if not path.exists():
        raise FileNotFoundError(filename)
    return path


def delete_imported_spec_template(target_root: Path, import_id: str) -> bool:
    root = imported_spec_templates_root(target_root).resolve()
    path = (root / import_id).resolve()
    if path.parent != root or not path.exists() or not path.is_dir():
        return False
    shutil.rmtree(path)
    return True


def build_imported_spec_template_preview(target_root: Path, import_id: str) -> dict[str, Any]:
    """Build a lightweight structure preview for an imported Word template draft."""
    template_path = resolve_imported_spec_template_file(
        target_root,
        import_id,
        "项目需求说明书-输出模板.docx",
    )
    manifest, manifest_path, manifest_source = load_template_manifest("spec", str(template_path))
    validation = validate_output_template("spec", str(template_path))
    doc = Document(str(template_path))

    scopes = _collect_word_preview_scopes(doc)
    placeholders = _collect_word_placeholder_occurrences(scopes)
    anchors = _collect_word_anchor_occurrences(scopes, manifest)
    section_candidates = [
        item
        for item in _collect_section_candidates(scopes)
        if item["scope"] == "body"
    ]

    return {
        "id": import_id,
        "template_path": str(template_path),
        "manifest_path": manifest_path,
        "manifest_source": manifest_source,
        "template_id": validation.template_id,
        "ok": validation.ok,
        "errors": [issue.message for issue in validation.errors],
        "warnings": [issue.message for issue in validation.warnings],
        "capabilities": validation.capabilities,
        "summary": {
            "body_paragraph_count": len(doc.paragraphs),
            "body_table_count": len(doc.tables),
            "section_count": len(doc.sections),
            "placeholder_count": len(placeholders),
            "anchor_count": len(anchors),
            "section_candidate_count": len(section_candidates),
        },
        "placeholders": placeholders,
        "anchors": anchors,
        "section_candidates": section_candidates[:20],
        "scopes": scopes,
    }


def _collect_word_preview_scopes(doc: Document) -> list[dict[str, Any]]:
    return [
        {
            "scope": "body",
            "label": "正文",
            "paragraphs": _paragraph_previews(doc.paragraphs),
            "tables": _table_previews(doc.tables),
        },
        {
            "scope": "headers",
            "label": "页眉",
            "paragraphs": _paragraph_previews(
                paragraph for section in doc.sections for paragraph in section.header.paragraphs
            ),
            "tables": _table_previews(
                table for section in doc.sections for table in section.header.tables
            ),
        },
        {
            "scope": "footers",
            "label": "页脚",
            "paragraphs": _paragraph_previews(
                paragraph for section in doc.sections for paragraph in section.footer.paragraphs
            ),
            "tables": _table_previews(
                table for section in doc.sections for table in section.footer.tables
            ),
        },
    ]


def _paragraph_previews(paragraphs) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs):
        text = _compact_text(paragraph.text)
        if not text:
            continue
        previews.append({
            "index": index,
            "text": text,
            "style": str(paragraph.style.name if paragraph.style else ""),
            "placeholders": _find_tokens(text),
        })
    return previews[:120]


def _table_previews(tables) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for index, table in enumerate(tables):
        cell_texts: list[str] = []
        for row in table.rows[:5]:
            row_text = " | ".join(_compact_text(cell.text) for cell in row.cells)
            if row_text.strip():
                cell_texts.append(row_text)
        joined = "\n".join(cell_texts)
        previews.append({
            "index": index,
            "row_count": len(table.rows),
            "column_count": len(table.columns),
            "style": str(table.style.name if table.style else ""),
            "text_preview": joined[:500],
            "placeholders": _find_tokens(joined),
        })
    return previews[:40]


def _collect_word_placeholder_occurrences(scopes: list[dict[str, Any]]) -> list[dict[str, str]]:
    occurrences: list[dict[str, str]] = []
    for scope in scopes:
        scope_name = scope["scope"]
        for paragraph in scope["paragraphs"]:
            for token in paragraph.get("placeholders", []):
                occurrences.append({
                    "token": token,
                    "scope": scope_name,
                    "location": f"paragraph:{paragraph['index']}",
                    "text": paragraph["text"],
                })
        for table in scope["tables"]:
            for token in table.get("placeholders", []):
                occurrences.append({
                    "token": token,
                    "scope": scope_name if scope_name != "body" else "tables",
                    "location": f"table:{table['index']}",
                    "text": table["text_preview"],
                })
    return occurrences


def _collect_word_anchor_occurrences(
    scopes: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    anchors = manifest.get("anchors", {}) or {}
    if not isinstance(anchors, dict):
        anchors = {}
    anchor_tokens = {
        "legacy_functional_requirements": str(anchors.get("legacy_functional_requirements", "{{功能需求详情}}")),
        "functional_requirements": str(anchors.get("functional_requirements", "{{功能需求章节}}")),
        "module_table": str(anchors.get("module_table", "{{模块清单表}}")),
        "module_details": str(anchors.get("module_details", "{{功能过程详情}}")),
    }
    occurrences: list[dict[str, str]] = []
    for placeholder in _collect_word_placeholder_occurrences(scopes):
        for key, token in anchor_tokens.items():
            if placeholder["token"] == token:
                occurrences.append({
                    "key": key,
                    "token": token,
                    "scope": placeholder["scope"],
                    "location": placeholder["location"],
                    "text": placeholder["text"],
                })
    return occurrences


def _collect_section_candidates(scopes: list[dict[str, Any]]) -> list[dict[str, str]]:
    keywords = ("功能需求", "功能说明", "功能模块", "系统功能")
    candidates: list[dict[str, str]] = []
    for scope in scopes:
        for paragraph in scope["paragraphs"]:
            text = paragraph["text"]
            if any(keyword in text for keyword in keywords):
                candidates.append({
                    "scope": scope["scope"],
                    "location": f"paragraph:{paragraph['index']}",
                    "text": text,
                    "style": paragraph.get("style", ""),
                })
    return candidates


def _find_tokens(text: str) -> list[str]:
    return sorted(set(re.findall(r"\{\{[^}]+\}\}", text or "")))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
