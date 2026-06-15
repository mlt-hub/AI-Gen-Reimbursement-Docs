from io import BytesIO
import zipfile

import pytest

from web_app.services.upload_security import (
    INPUT_XLSX_MAX_SIZE_BYTES,
    UploadSecurityError,
    validate_upload_bytes,
)


def _zip_bytes(entries: dict[str, bytes | str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _valid_xlsx_bytes() -> bytes:
    return _zip_bytes({
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": "<workbook/>",
    })


def _valid_docx_bytes() -> bytes:
    return _zip_bytes({
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": "<document/>",
    })


def test_validate_upload_accepts_xlsx_and_sanitizes_filename():
    result = validate_upload_bytes(
        _valid_xlsx_bytes(),
        filename="../功能清单.xlsx",
        purpose="input_xlsx",
    )

    assert result.safe_filename == "功能清单.xlsx"
    assert result.extension == ".xlsx"


def test_validate_upload_accepts_docx():
    result = validate_upload_bytes(
        _valid_docx_bytes(),
        filename="客户需求.docx",
        purpose="spec_docx",
    )

    assert result.safe_filename == "客户需求.docx"
    assert result.extension == ".docx"


def test_validate_upload_rejects_xlsm_even_when_content_is_zip():
    with pytest.raises(UploadSecurityError, match=r"\.xlsm"):
        validate_upload_bytes(
            _valid_xlsx_bytes(),
            filename="宏模板.xlsm",
            purpose="input_xlsx",
        )


def test_validate_upload_rejects_disguised_xlsx():
    with pytest.raises(UploadSecurityError, match="Office 文档"):
        validate_upload_bytes(
            b"not a zip",
            filename="伪装.xlsx",
            purpose="input_xlsx",
        )


def test_validate_upload_rejects_empty_file():
    with pytest.raises(UploadSecurityError, match="文件为空"):
        validate_upload_bytes(
            b"",
            filename="空.xlsx",
            purpose="input_xlsx",
        )


def test_validate_upload_rejects_oversized_file_before_parsing_zip():
    content = b"x" * (INPUT_XLSX_MAX_SIZE_BYTES + 1)

    with pytest.raises(UploadSecurityError, match="文件过大"):
        validate_upload_bytes(
            content,
            filename="超大.xlsx",
            purpose="input_xlsx",
        )


def test_validate_upload_rejects_zip_path_traversal():
    content = _zip_bytes({
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": "<workbook/>",
        "../evil.xml": "oops",
    })

    with pytest.raises(UploadSecurityError, match="ZIP 结构异常"):
        validate_upload_bytes(
            content,
            filename="功能清单.xlsx",
            purpose="input_xlsx",
        )


def test_validate_upload_rejects_missing_required_office_entry():
    content = _zip_bytes({"[Content_Types].xml": "<Types/>"})

    with pytest.raises(UploadSecurityError, match="Office 文档"):
        validate_upload_bytes(
            content,
            filename="功能清单.xlsx",
            purpose="input_xlsx",
        )


def test_output_template_security_rejects_macro_template():
    with pytest.raises(UploadSecurityError, match=r"\.xlsm"):
        validate_upload_bytes(
            _valid_xlsx_bytes(),
            filename="FPA工作量评估-输出模板.xlsm",
            purpose="output_template_xlsx",
        )
