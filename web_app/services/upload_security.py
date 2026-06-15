"""Shared security checks for uploaded Office documents."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import zipfile
from typing import Any


MB = 1024 * 1024

INPUT_XLSX_MAX_SIZE_BYTES = 30 * MB
TEMPLATE_MAX_SIZE_BYTES = 50 * MB
MAX_ZIP_ENTRIES = 5000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * MB


@dataclass(frozen=True)
class UploadPurposeRule:
    allowed_extensions: frozenset[str]
    max_size_bytes: int
    required_entries: frozenset[str]


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    safe_filename: str
    content: bytes
    extension: str
    size_bytes: int
    purpose: str


class UploadSecurityError(ValueError):
    """Raised when an uploaded file fails the security boundary."""


PURPOSE_RULES: dict[str, UploadPurposeRule] = {
    "input_xlsx": UploadPurposeRule(
        frozenset({".xlsx"}),
        INPUT_XLSX_MAX_SIZE_BYTES,
        frozenset({"[Content_Types].xml", "xl/workbook.xml"}),
    ),
    "output_template_xlsx": UploadPurposeRule(
        frozenset({".xlsx"}),
        TEMPLATE_MAX_SIZE_BYTES,
        frozenset({"[Content_Types].xml", "xl/workbook.xml"}),
    ),
    "output_template_docx": UploadPurposeRule(
        frozenset({".docx"}),
        TEMPLATE_MAX_SIZE_BYTES,
        frozenset({"[Content_Types].xml", "word/document.xml"}),
    ),
    "spec_docx": UploadPurposeRule(
        frozenset({".docx"}),
        TEMPLATE_MAX_SIZE_BYTES,
        frozenset({"[Content_Types].xml", "word/document.xml"}),
    ),
}


async def validate_upload_file(
    upload_file: Any,
    *,
    purpose: str,
    max_size_bytes: int | None = None,
) -> ValidatedUpload:
    """Read and validate an uploaded Office Open XML file."""
    filename = str(getattr(upload_file, "filename", "") or "")
    content = await upload_file.read()
    return validate_upload_bytes(
        content,
        filename=filename,
        purpose=purpose,
        max_size_bytes=max_size_bytes,
    )


def validate_upload_bytes(
    content: bytes,
    *,
    filename: str,
    purpose: str,
    max_size_bytes: int | None = None,
) -> ValidatedUpload:
    rule = PURPOSE_RULES.get(purpose)
    if rule is None:
        raise UploadSecurityError(f"未知上传用途: {purpose}")

    original_filename = str(filename or "")
    safe_filename = Path(original_filename).name
    if not safe_filename:
        raise UploadSecurityError("未选择文件")

    ext = Path(safe_filename).suffix.lower()
    if ext == ".xlsm":
        raise UploadSecurityError("不支持上传 .xlsm 文件")
    if ext not in rule.allowed_extensions:
        raise UploadSecurityError(_extension_error(rule.allowed_extensions))

    size_limit = max_size_bytes or rule.max_size_bytes
    if not content:
        raise UploadSecurityError("文件为空")
    if len(content) > size_limit:
        raise UploadSecurityError(f"文件过大，超过 {_format_mb(size_limit)} 限制")

    _validate_ooxml_package(content, required_entries=rule.required_entries)
    return ValidatedUpload(
        original_filename=original_filename,
        safe_filename=safe_filename,
        content=content,
        extension=ext,
        size_bytes=len(content),
        purpose=purpose,
    )


def _extension_error(allowed_extensions: frozenset[str]) -> str:
    allowed = sorted(allowed_extensions)
    if len(allowed) == 1:
        return f"仅支持上传 {allowed[0]} 文件"
    return "仅支持上传 " + "、".join(allowed) + " 文件"


def _format_mb(size_bytes: int) -> str:
    if size_bytes % MB == 0:
        return f"{size_bytes // MB}MB"
    return f"{size_bytes / MB:.1f}MB"


def _validate_ooxml_package(content: bytes, *, required_entries: frozenset[str]) -> None:
    if not content.startswith(b"PK"):
        raise UploadSecurityError("文件不是有效的 Office 文档")

    buffer = BytesIO(content)
    if not zipfile.is_zipfile(buffer):
        raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")

    buffer.seek(0)
    try:
        with zipfile.ZipFile(buffer) as archive:
            entries = archive.infolist()
            if not entries:
                raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")
            if len(entries) > MAX_ZIP_ENTRIES:
                raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")

            normalized_names: set[str] = set()
            total_uncompressed = 0
            for entry in entries:
                name = _normalize_zip_name(entry.filename)
                _validate_zip_entry_name(name)
                normalized_names.add(name)
                total_uncompressed += int(entry.file_size)
                if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")

            missing = required_entries - normalized_names
            if missing:
                raise UploadSecurityError("文件不是有效的 Office 文档")
    except UploadSecurityError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise UploadSecurityError("ZIP 结构异常，疑似伪装文件") from exc


def _normalize_zip_name(name: str) -> str:
    return str(name or "").replace("\\", "/")


def _validate_zip_entry_name(name: str) -> None:
    if not name:
        raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")
    if name.startswith("/") or name.startswith("\\"):
        raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")
    if re.match(r"^[A-Za-z]:($|/|\\)", name):
        raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")

    parts = name.split("/")
    if any(part in ("", "..") for part in parts):
        if name.endswith("/") and parts[-1] == "":
            parts = parts[:-1]
        if any(part in ("", "..") for part in parts):
            raise UploadSecurityError("ZIP 结构异常，疑似伪装文件")
